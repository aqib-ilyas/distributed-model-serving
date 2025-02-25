# docker/node.Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && pip install prometheus_client psutil \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY src/node/requirements.txt .
RUN pip install -r requirements.txt

# Copy proto files and generate them
COPY src/proto /app/src/proto
RUN python -m grpc_tools.protoc -I./src/proto --python_out=./src/proto --grpc_python_out=./src/proto ./src/proto/model_service.proto

# Copy the rest of the application
COPY . .

# Expose gRPC and metrics ports
EXPOSE 50051 8001