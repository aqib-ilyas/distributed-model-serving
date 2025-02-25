# Distributed Model Inference System

A scalable, distributed system for serving machine learning models with high availability and monitoring capabilities.

### Components:

1. **Frontend Service**

    - React/Vite application serving the user interface
    - Communicates with API service over HTTP

2. **API Service**

    - FastAPI application that handles client requests
    - Coordinates with Tokenizer for text encoding/decoding
    - Communicates with Coordinator for model inference
    - Exposes metrics for Prometheus

3. **Tokenizer Service**

    - Handles text tokenization and detokenization using GPT2 tokenizer
    - Communicates with API service via gRPC
    - Exposes metrics for Prometheus

4. **Coordinator Service**

    - Orchestrates distributed inference across model nodes
    - Manages request routing and response aggregation
    - Handles node health checking
    - Exposes metrics for Prometheus

5. **Model Nodes (1,2,3)**

    - Each runs a portion of the model
    - Communicates with Coordinator via gRPC
    - Can be scaled with replicas for fault tolerance
    - Expose metrics for Prometheus

6. **Monitoring Stack**
    - Prometheus: Collects metrics from all services
    - Grafana: Visualizes metrics with customizable dashboards

## Getting Started

### Prerequisites

-   Docker and Docker Compose
-   8GB+ RAM for running the full stack
-   Git

### Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/distributed-model-inference.git
cd distributed-model-inference
```

2. Create the Docker network:

```bash
docker network create model-network
```

3. Build and start the services:

```bash
docker-compose up -d
```

4. Start the monitoring stack:

```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

5. Access the interfaces:
    - Frontend: http://localhost:5173
    - API Docs: http://localhost:8000/docs
    - Prometheus: http://localhost:9090
    - Grafana: http://localhost:3000 (default login: admin/admin)

## Usage

### Using the UI

1. Open http://localhost:5173 in your browser
2. Enter your text in the input field
3. Click "Process Input"
4. View the results and processing metrics

### Using the API Directly

```bash
curl -X POST http://localhost:8000/api/model/process \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, how are you?", "metadata": {}}'
```

## Monitoring

The system includes comprehensive monitoring with Prometheus and Grafana.

### Key Metrics:

-   **API Metrics**: Request counts, latencies, token counts
-   **Model Metrics**: Inference times, memory usage
-   **Node Health**: Status of each node
-   **Tokenizer Metrics**: Operation counts and latencies

### Grafana Dashboards:

A default dashboard is provided showing:

-   API request latency
-   Model inference latency by node
-   Tokenizer operations
-   Memory usage
-   Request success/error rates
-   Token counts
-   Node health status

## Configuration

### Model Configuration

The `config.json` file configures the distribution of the model:

```json
{
    "model_name": "gpt2",
    "nodes": [
        {
            "id": "node1",
            "address": "node1:50051",
            "model_part": 0
        },
        {
            "id": "node2",
            "address": "node2:50052",
            "model_part": 1
        },
        {
            "id": "node3",
            "address": "node3:50053",
            "model_part": 2
        }
    ]
}
```

### Prometheus Configuration

`prometheus/prometheus.yml` configures metric collection:

```yaml
global:
    scrape_interval: 15s
    evaluation_interval: 15s

scrape_configs:
    - job_name: "coordinator"
      static_configs:
          - targets: ["coordinator:8000"]
    - job_name: "nodes"
      static_configs:
          - targets: ["node1:8001", "node2:8001", "node3:8001"]
    - job_name: "tokenizer"
      static_configs:
          - targets: ["tokenizer:8002"]
    - job_name: "api"
      static_configs:
          - targets: ["api:8000"]
```

## Deployment Options

### Docker Compose (Local Development)

```bash
# Create Docker network if it doesn't exist
docker network create model-network

# Start services
docker-compose up -d
docker-compose -f docker-compose.monitoring.yml up -d
```

### Kubernetes (Production)

Kubernetes manifests are provided in the `k8s/` directory:

```bash
kubectl create namespace model-inference
kubectl apply -f k8s/config.yaml -n model-inference
kubectl apply -f k8s/ -n model-inference
```

## Scalability and High Availability

The system supports high availability through node replication:

1. **Model Nodes**: Each can be scaled with multiple replicas
2. **Tokenizer**: Can be scaled for higher throughput
3. **API Service**: Can be scaled horizontally behind a load balancer

## Extending the System

### Adding New Model Types

1. Update the tokenizer service to support the new model's tokenization
2. Modify the node service to load the new model
3. Update the configuration to specify the new model and its partitioning

### Custom Metrics

1. Add new metrics to the relevant service in `src/metrics/metrics.py`
2. Restart the service
3. Update or create Grafana dashboards to visualize the new metrics

## Troubleshooting

### Common Issues

1. **Service fails to start**: Check logs with `docker-compose logs <service_name>`
2. **Network connectivity issues**: Verify the `model-network` exists with `docker network ls`
3. **Grafana can't connect to Prometheus**: Verify network connectivity and datasource configuration
4. **Model inference errors**: Check node logs and memory usage

### Checking Logs

```bash
# View logs for a specific service
docker-compose logs api

# Follow logs
docker-compose logs -f coordinator
```

## Acknowledgements

-   The OpenAI GPT-2 model
-   FastAPI for the API framework
-   gRPC for high-performance communication
-   Prometheus and Grafana for monitoring
