# docker/api.Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY src/api/requirements.txt .
RUN pip install -r requirements.txt \
    && pip install prometheus_client  # Add Prometheus client

# Copy proto files and generate them
COPY src/proto /app/src/proto
RUN python -m grpc_tools.protoc -I./src/proto --python_out=./src/proto --grpc_python_out=./src/proto ./src/proto/model_service.proto

# Copy the rest of the application
COPY . .

# Expose API and metrics ports
EXPOSE 8000 8000

# Command to run the application
CMD ["uvicorn", "src.api.api:app", "--host", "0.0.0.0", "--port", "8000"]