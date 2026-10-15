# Development image: Vite dev server with hot reload
FROM node:24-alpine

WORKDIR /app

# Install dependencies first to cache this layer
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# --host: listen on 0.0.0.0 so the server is reachable from outside the container
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
