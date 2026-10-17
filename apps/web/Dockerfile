FROM node:22-alpine AS base
WORKDIR /app
RUN apk add --no-cache libc6-compat

FROM base AS deps
COPY package*.json ./
RUN npm install --omit=dev

FROM base AS builder
COPY package*.json ./
RUN npm install
COPY . .
ENV NEXT_TELEMETRY_DISABLED 1
ARG NEXT_PUBLIC_API_URL=http://localhost:3000
ARG NEXT_PUBLIC_WS_URL=ws://localhost:3000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL}
RUN npm run build

FROM base AS runner
ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy the Next.js standalone build correctly
# The standalone build creates the structure at /app/.next/standalone/
# We need to copy the entire standalone directory to /app
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./

# Copy the static assets
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Copy node_modules from deps stage
COPY --from=deps --chown=nextjs:nodejs /app/node_modules ./node_modules

USER nextjs
EXPOSE 3001
ENV PORT 3001
ENV HOSTNAME "0.0.0.0"
WORKDIR /app
CMD ["node", "server.js"]
