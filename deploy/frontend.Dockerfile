# Frontend image — Vite React app, built to static files and served by nginx.
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Vite only inlines VITE_*-prefixed vars at build time.
ARG NEXT_PUBLIC_API_BASE_URL
ENV VITE_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 3000
RUN sed -i 's/listen\s*80;/listen 3000;/' /etc/nginx/conf.d/default.conf
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000 || exit 1
CMD ["nginx", "-g", "daemon off;"]
