// AEGIS Go Gateway — High-performance HTTP proxy, rate limiter, WebSocket bridge
// Sits in front of the Node.js API and Python orchestrator.
// Handles: rate limiting, request routing, health aggregation, Redis pub/sub → WS bridge
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/gorilla/mux"
	"github.com/gorilla/websocket"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"golang.org/x/time/rate"
)

// ─── Config ───────────────────────────────────────────────────────────────────
type Config struct {
	Port            string
	APITarget       string
	OrchestratorURL string
	RedisURL        string
	RateLimit       int
	RateBurst       int
}

func loadConfig() Config {
	return Config{
		Port:            getEnv("GATEWAY_PORT", "8080"),
		APITarget:       getEnv("API_URL", "http://localhost:3000"),
		OrchestratorURL: getEnv("ORCHESTRATOR_URL", "http://localhost:8001"),
		RedisURL:        getEnv("REDIS_URL", "redis://localhost:6379"),
		RateLimit:       300,
		RateBurst:       50,
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ─── Metrics ──────────────────────────────────────────────────────────────────
var (
	requestsTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "gateway_requests_total",
		Help: "Total requests through gateway",
	}, []string{"method", "path", "status"})

	requestDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "gateway_request_duration_seconds",
		Help:    "Request duration",
		Buckets: prometheus.DefBuckets,
	}, []string{"path"})

	wsConnections = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "gateway_ws_connections_active",
		Help: "Active WebSocket connections",
	})
)

// ─── Rate Limiter ─────────────────────────────────────────────────────────────
type IPRateLimiter struct {
	mu       sync.RWMutex
	limiters map[string]*rate.Limiter
	r        rate.Limit
	b        int
}

func NewIPRateLimiter(r rate.Limit, b int) *IPRateLimiter {
	return &IPRateLimiter{
		limiters: make(map[string]*rate.Limiter),
		r:        r,
		b:        b,
	}
}

func (i *IPRateLimiter) GetLimiter(ip string) *rate.Limiter {
	i.mu.Lock()
	defer i.mu.Unlock()
	if l, ok := i.limiters[ip]; ok {
		return l
	}
	l := rate.NewLimiter(i.r, i.b)
	i.limiters[ip] = l
	return l
}

// ─── Server ───────────────────────────────────────────────────────────────────
type Server struct {
	cfg         Config
	router      *mux.Router
	apiProxy    *httputil.ReverseProxy
	orchProxy   *httputil.ReverseProxy
	rateLimiter *IPRateLimiter
	redisClient *redis.Client
	upgrader    websocket.Upgrader
	wsClients   map[string]map[*websocket.Conn]bool
	wsMu        sync.RWMutex
}

func NewServer(cfg Config) *Server {
	apiURL, _  := url.Parse(cfg.APITarget)
	orchURL, _ := url.Parse(cfg.OrchestratorURL)
	redisOpts, _ := redis.ParseURL(cfg.RedisURL)

	s := &Server{
		cfg:         cfg,
		router:      mux.NewRouter(),
		apiProxy:    httputil.NewSingleHostReverseProxy(apiURL),
		orchProxy:   httputil.NewSingleHostReverseProxy(orchURL),
		rateLimiter: NewIPRateLimiter(rate.Limit(cfg.RateLimit), cfg.RateBurst),
		redisClient: redis.NewClient(redisOpts),
		upgrader: websocket.Upgrader{
			CheckOrigin:     func(r *http.Request) bool { return true },
			ReadBufferSize:  1024,
			WriteBufferSize: 1024,
		},
		wsClients: make(map[string]map[*websocket.Conn]bool),
	}
	s.setupRoutes()
	return s
}

func (s *Server) setupRoutes() {
	s.router.Use(s.loggingMiddleware)
	s.router.Use(s.rateLimitMiddleware)
	s.router.Use(s.corsMiddleware)

	// Root / Welcome
	s.router.HandleFunc("/", s.handleRoot).Methods("GET")

	// Health
	s.router.HandleFunc("/health", s.handleHealth).Methods("GET")
	s.router.HandleFunc("/health/aggregate", s.handleAggregateHealth).Methods("GET")

	// Metrics
	s.router.Handle("/metrics", promhttp.Handler()).Methods("GET")

	// WebSocket bridge (Redis → WS)
	s.router.HandleFunc("/ws/investigation/{id}", s.handleWebSocket)

	// Proxy: API
	s.router.PathPrefix("/api/").HandlerFunc(s.handleAPIProxy)

	// Proxy: Orchestrator (internal only)
	s.router.PathPrefix("/internal/orchestrator/").HandlerFunc(s.handleOrchestratorProxy)
}

func (s *Server) handleRoot(w http.ResponseWriter, r *http.Request) {
	http.Redirect(w, r, "/health", http.StatusTemporaryRedirect)
}

// ─── Middleware ───────────────────────────────────────────────────────────────
func (s *Server) loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		wrapped := &responseWriter{ResponseWriter: w, statusCode: 200}
		next.ServeHTTP(wrapped, r)

		duration := time.Since(start)
		log.Info().
			Str("method", r.Method).
			Str("path", r.URL.Path).
			Int("status", wrapped.statusCode).
			Dur("duration", duration).
			Str("ip", r.RemoteAddr).
			Msg("request")

		requestsTotal.WithLabelValues(r.Method, r.URL.Path, fmt.Sprintf("%d", wrapped.statusCode)).Inc()
		requestDuration.WithLabelValues(r.URL.Path).Observe(duration.Seconds())
	})
}

func (s *Server) rateLimitMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		limiter := s.rateLimiter.GetLimiter(r.RemoteAddr)
		if !limiter.Allow() {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusTooManyRequests)
			json.NewEncoder(w).Encode(map[string]string{
				"error": "Rate limit exceeded",
			})
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (s *Server) corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type,Authorization,X-User-ID")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// ─── Handlers ─────────────────────────────────────────────────────────────────
func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":    "ok",
		"service":   "go-gateway",
		"timestamp": time.Now().UTC(),
	})
}

func (s *Server) handleAggregateHealth(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancel()

	type serviceHealth struct {
		Name   string `json:"name"`
		Status string `json:"status"`
	}

	var wg sync.WaitGroup
	results := make([]serviceHealth, 0, 3)
	mu := sync.Mutex{}

	checkService := func(name, url string) {
		defer wg.Done()
		status := "ok"
		resp, err := http.Get(url)
		if err != nil || resp.StatusCode >= 500 {
			status = "degraded"
		}
		mu.Lock()
		results = append(results, serviceHealth{Name: name, Status: status})
		mu.Unlock()
	}

	wg.Add(2)
	go checkService("api", s.cfg.APITarget+"/health/live")
	go checkService("orchestrator", s.cfg.OrchestratorURL+"/health")
	wg.Wait()

	// Redis health
	redisStatus := "ok"
	if err := s.redisClient.Ping(ctx).Err(); err != nil {
		redisStatus = "degraded"
	}
	results = append(results, serviceHealth{Name: "redis", Status: redisStatus})

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":   "ok",
		"services": results,
	})
}

func (s *Server) handleAPIProxy(w http.ResponseWriter, r *http.Request) {
	s.apiProxy.ServeHTTP(w, r)
}

func (s *Server) handleOrchestratorProxy(w http.ResponseWriter, r *http.Request) {
	r.URL.Path = r.URL.Path[len("/internal/orchestrator"):]
	s.orchProxy.ServeHTTP(w, r)
}

// ─── WebSocket Bridge (Redis pub/sub → WebSocket) ─────────────────────────────
func (s *Server) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	investigationID := vars["id"]

	conn, err := s.upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Error().Err(err).Msg("ws_upgrade_failed")
		return
	}
	defer conn.Close()

	wsConnections.Inc()
	defer wsConnections.Dec()

	// Register client
	s.wsMu.Lock()
	if s.wsClients[investigationID] == nil {
		s.wsClients[investigationID] = make(map[*websocket.Conn]bool)
	}
	s.wsClients[investigationID][conn] = true
	s.wsMu.Unlock()

	defer func() {
		s.wsMu.Lock()
		delete(s.wsClients[investigationID], conn)
		s.wsMu.Unlock()
	}()

	// Subscribe to Redis channel
	ctx, cancel := context.WithCancel(r.Context())
	defer cancel()

	pubsub := s.redisClient.Subscribe(ctx, fmt.Sprintf("investigation:%s:events", investigationID))
	defer pubsub.Close()

	// Forward messages to WebSocket
	go func() {
		ch := pubsub.Channel()
		for msg := range ch {
			s.wsMu.RLock()
			err := conn.WriteMessage(websocket.TextMessage, []byte(msg.Payload))
			s.wsMu.RUnlock()
			if err != nil {
				cancel()
				return
			}
		}
	}()

	// Keep alive (ping)
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// ─── Response Writer wrapper ──────────────────────────────────────────────────
type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

// ─── Main ─────────────────────────────────────────────────────────────────────
func main() {
	log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr, TimeFormat: time.RFC3339})
	cfg := loadConfig()

	// Start Redis pub/sub listener in background
	srv := NewServer(cfg)

	httpServer := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      srv.router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 60 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// Graceful shutdown
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGTERM, syscall.SIGINT)

	go func() {
		log.Info().Str("port", cfg.Port).Msg("🚀 AEGIS Go Gateway started")
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal().Err(err).Msg("server_failed")
		}
	}()

	<-stop
	log.Info().Msg("Shutting down gateway...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	httpServer.Shutdown(ctx)
}
