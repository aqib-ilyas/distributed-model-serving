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

# Pre-download models - add this section
RUN python -c "from transformers import GPT2Tokenizer, AutoModelForCausalLM; \
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2'); \
    model = AutoModelForCausalLM.from_pretrained('gpt2')"

# Copy the rest of the application
COPY . .

# Expose gRPC and metrics ports
EXPOSE 50051-50053 8001

# Command to run the application
# Note: For Kubernetes, you'll need to set the NODE_ID and potentially PORT as environment variables
# This example defaults to node1, but should be overridden in k8s deployment
CMD ["python", "/app/src/node/node_server.py", "--config", "/app/src/config/config.json", "--node-id", "${NODE_ID:-node1}"]