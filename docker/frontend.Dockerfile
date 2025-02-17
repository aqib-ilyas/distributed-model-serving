# docker/frontend.Dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY src/frontend/package*.json ./

# Install dependencies
RUN npm install

# Copy frontend source code
COPY src/frontend/ .

# Start the Vite development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]