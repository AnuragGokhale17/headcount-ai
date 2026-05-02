# Stage 1: Build
FROM node:20-alpine AS build

WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Copy custom nginx config if needed, otherwise default is fine for simple SPA
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
