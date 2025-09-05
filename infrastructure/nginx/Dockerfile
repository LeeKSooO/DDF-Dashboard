# ===============================================
# Pure Nginx Proxy Microservice Dockerfile
# Next.js SSR과 Backend 서비스를 프록시
# ===============================================

FROM nginx:1.25-alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Remove default nginx configuration
RUN rm /etc/nginx/conf.d/default.conf

# Copy environment-specific nginx configuration  
ARG BUILD_ENV=dev
COPY nginx-${BUILD_ENV}.conf /etc/nginx/nginx.conf

# Create nginx user and set permissions
RUN chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    chmod -R 755 /var/cache/nginx && \
    chmod -R 755 /var/log/nginx

# Create log directory
RUN mkdir -p /var/log/nginx && \
    touch /var/log/nginx/access.log && \
    touch /var/log/nginx/error.log && \
    chown -R nginx:nginx /var/log/nginx

# Switch to nginx user
USER nginx

# Expose Nginx port
EXPOSE 8080

# Health check for Nginx
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8080/nginx-health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]