# docker/api.Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY src/api/requirements.txt .
RUN pip install -r requirements.txt

# Copy proto files and generate them
COPY src/proto /app/src/proto
RUN python -m grpc_tools.protoc -I./src/proto --python_out=./src/proto --grpc_python_out=./src/proto ./src/proto/model_service.proto

# Copy the rest of the application
COPY . .