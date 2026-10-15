# Frontend Dockerfile
FROM nginx:alpine

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy static HTML files
COPY static/ /usr/share/nginx/html/

# Expose port
EXPOSE 80

# Nginx will start automatically
