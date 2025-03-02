FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    netcat-traditional \
    && pip install prometheus_client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY src/tokenizer/requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ /app/src/

# Generate gRPC code
RUN python -m grpc_tools.protoc -I./src/proto \
    --python_out=./src/proto \
    --grpc_python_out=./src/proto \
    ./src/proto/*.proto

# Set Python path
ENV PYTHONPATH=/app

# Expose gRPC and metrics ports
EXPOSE 50054 8002

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD nc -z 0.0.0.0 50054 || exit 1

# Run the application - removed the --host argument
CMD ["python", "src/tokenizer/tokenizer_server.py", "--port", "50054"]