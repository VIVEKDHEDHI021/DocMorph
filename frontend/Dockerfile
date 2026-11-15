# ==============================================================================
# DocMorph Frontend Dockerfile
# Production-ready multi-stage Node build with lightweight Nginx alpine server
# ==============================================================================

FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Nginx Alpine Runtime
FROM nginx:1.27-alpine AS runner

# Remove default configuration and copy custom SPA config
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled SPA dist
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

