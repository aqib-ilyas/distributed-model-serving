# docker/coordinator.Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install netcat for healthcheck and metrics dependencies
RUN apt-get update && apt-get install -y netcat-openbsd \
    && pip install prometheus_client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY src/coordinator/requirements.txt .
RUN pip install -r requirements.txt

# Copy proto files and generate them
COPY src/proto /app/src/proto
RUN python -m grpc_tools.protoc -I./src/proto --python_out=./src/proto --grpc_python_out=./src/proto ./src/proto/model_service.proto

# Copy the rest of the application
COPY . .

# Expose gRPC and metrics ports
EXPOSE 50050 8000