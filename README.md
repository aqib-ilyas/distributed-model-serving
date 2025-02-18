# Distributed Model Serving System

A distributed system for serving large language models across multiple nodes. The system implements a pipeline architecture where the model is split across multiple nodes, with text tokenization handled by a dedicated service.

## Architecture

The system consists of several microservices:

-   **Coordinator Service**: Manages the distribution of work across model nodes
-   **Model Nodes**: Each node handles a portion of the model computation
-   **Tokenizer Service**: Handles text tokenization and detokenization
-   **API Service**: Provides a REST API interface for clients
-   **Frontend**: React-based user interface

### Service Communication

```
Frontend <-> API <-> Coordinator <-> Model Nodes
                 <-> Tokenizer
```

All inter-service communication uses gRPC, except for the Frontend-API communication which uses REST.

## Project Structure

```
src/
├── proto/
│   ├── model_service.proto
│   └── tokenizer_service.proto
├── coordinator/
│   ├── __init__.py
│   └── coordinator_server.py
├── node/
│   ├── __init__.py
│   └── node_server.py
├── tokenizer/
│   ├── __init__.py
│   └── tokenizer_server.py
├── api/
│   ├── __init__.py
│   └── api.py
└── frontend/
    └── src/
        ├── components/
        └── App.tsx

docker/
├── coordinator.Dockerfile
├── node.Dockerfile
├── tokenizer.Dockerfile
├── api.Dockerfile
└── frontend.Dockerfile
```

## Prerequisites

-   Docker and Docker Compose
-   Python 3.9+
-   Node.js 16+
-   gRPC tools

## Setup

1. Clone the repository:

    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2. Generate gRPC code:

    ```bash
    python -m grpc_tools.protoc -I./src/proto \
        --python_out=./src/proto \
        --grpc_python_out=./src/proto \
        ./src/proto/*.proto
    ```

3. Install Python dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Install frontend dependencies:
    ```bash
    cd src/frontend
    npm install
    ```

## Configuration

Create a configuration file at `src/config/config.json`:

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

## Running the System

1. Start all services using Docker Compose:

    ```bash
    docker-compose up --build
    ```

2. Access the services:
    - Frontend: http://localhost:5173
    - API: http://localhost:8000
    - Coordinator: localhost:50050
    - Model Nodes: localhost:50051-50053
    - Tokenizer: localhost:50054

## API Endpoints

### REST API

`POST /api/model/process`

```json
{
    "text": "Input text to process",
    "metadata": {
        "timestamp": "2024-02-17T12:00:00Z",
        "type": "text_generation"
    }
}
```

Response:

```json
{
    "text": "Processed text output",
    "processingTime": 123.45,
    "nodeCount": 3
}
```

## Development

### Adding a New Model Node

1. Update `config.json` with the new node configuration
2. Add the node service to `docker-compose.yml`
3. Update the coordinator to handle the new node

### Modifying the Pipeline

The processing pipeline can be modified in `coordinator_server.py`. The current implementation processes data sequentially through all nodes.

## Testing

Run tests using pytest:

```bash
pytest tests/
```

## Monitoring

Each service includes logging and health check endpoints. Monitor service health using:

```bash
docker-compose ps
```

View logs using:

```bash
docker-compose logs [service_name]
```
