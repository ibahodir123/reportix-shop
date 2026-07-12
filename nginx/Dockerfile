FROM node:22-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM caddy:2.10-alpine
COPY nginx/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-builder /app/dist /usr/share/nginx/html
