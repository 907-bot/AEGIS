FROM node:22-alpine AS base
WORKDIR /app
RUN apk add --no-cache dumb-init

# Dependencies
FROM base AS deps
COPY package*.json ./
RUN npm install --omit=dev

# Builder
FROM base AS builder
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Runner
FROM base AS runner
ENV NODE_ENV=production
USER node
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/src/db/schema.sql ./src/db/schema.sql
EXPOSE 3000
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "dist/index.js"]
