import os
import json
import logging
from concurrent import futures
import grpc
import grpc.aio
import asyncio
import sys
import time
from prometheus_client import start_http_server, Counter, Histogram, Gauge, Info

# Add relative import path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
proto_dir = os.path.join(parent_dir, 'proto')
sys.path.append(proto_dir)

import model_service_pb2
import model_service_pb2_grpc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define metrics
COORDINATOR_REQUESTS = Counter(
    'coordinator_requests_total',
    'Total number of coordinator requests',
    ['status']  # success/error
)

NODE_LATENCY = Histogram(
    'node_processing_latency_seconds',
    'Time taken for processing in each node',
    ['node_id']
)

TOTAL_PROCESSING_TIME = Histogram(
    'total_processing_time_seconds',
    'Total time taken for complete request processing'
)

NODE_HEALTH = Gauge(
    'node_health_status',
    'Health status of each node',
    ['node_id']  # 1 for healthy, 0 for unhealthy
)

COORDINATOR_INFO = Info('coordinator', 'Coordinator information')

class ModelCoordinator(model_service_pb2_grpc.ModelServiceServicer):
    def __init__(self, config_path: str):
        # Start Prometheus metrics server
        start_http_server(8000)
        
        self.config = self.load_config(config_path)
        self.node_stubs = {}
        self.setup_connections()
        
        # Record coordinator information
        COORDINATOR_INFO.info({
            'model_name': self.config['model_name'],
            'node_count': str(len(self.config['nodes'])),
            'config_path': config_path
        })
        
        logger.info("Coordinator initialized with %d nodes", len(self.config['nodes']))
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                assert len(config['nodes']) == 3, "Configuration must contain exactly 3 nodes"
                return config
        except Exception as e:
            logger.error("Failed to load config: %s", str(e))
            raise
    
    def setup_connections(self):
        """Setup gRPC connections to all nodes."""
        for node in self.config['nodes']:
            try:
                channel = grpc.aio.insecure_channel(
                    node['address'],
                    options=[
                        ('grpc.max_send_message_length', 50 * 1024 * 1024),
                        ('grpc.max_receive_message_length', 50 * 1024 * 1024),
                        ('grpc.keepalive_time_ms', 30000),
                        ('grpc.keepalive_timeout_ms', 10000)
                    ]
                )
                self.node_stubs[node['id']] = model_service_pb2_grpc.ModelServiceStub(channel)
                logger.info("Connected to node %s at %s", node['id'], node['address'])
            except Exception as e:
                logger.error("Failed to connect to node %s: %s", node['id'], str(e))
                raise
    
    async def check_node_health(self):
        """Check if all nodes are accessible."""
        unhealthy_nodes = []
        for node in self.config['nodes']:
            try:
                await self.node_stubs[node['id']].health_check(
                    model_service_pb2.HealthCheckRequest(),
                    timeout=5
                )
                NODE_HEALTH.labels(node_id=node['id']).set(1)
            except grpc.RpcError as e:
                logger.warning("Node %s is unhealthy: %s", node['id'], str(e))
                NODE_HEALTH.labels(node_id=node['id']).set(0)
                unhealthy_nodes.append(node['id'])
        return unhealthy_nodes
    
    async def process(self, request, context):
        """Process request through all nodes in sequence."""
        start_time = time.time()
        try:
            # Check node health
            unhealthy_nodes = await self.check_node_health()
            if unhealthy_nodes:
                error_msg = f"Nodes {unhealthy_nodes} are unavailable"
                logger.error(error_msg)
                COORDINATOR_REQUESTS.labels(status='error').inc()
                context.set_code(grpc.StatusCode.UNAVAILABLE)
                context.set_details(error_msg)
                return model_service_pb2.ModelOutput()
            
            # Keep track of the original input length
            input_length = len(request.data)
            current_sequence = list(request.data)
            logger.info(f"Initial input sequence: {current_sequence}")
            
            # Process through nodes in sequence
            for i, node in enumerate(self.config['nodes']):
                try:
                    logger.info(f"Processing through node {node['id']}")
                    node_start_time = time.time()
                    
                    response = await self.node_stubs[node['id']].process(
                        model_service_pb2.ModelInput(
                            data=current_sequence,
                            metadata={
                                'node_id': node['id'],
                                'node_index': str(i),
                                'total_nodes': str(len(self.config['nodes'])),
                                'input_length': str(input_length)
                            }
                        )
                    )
                    
                    # Record node processing time
                    NODE_LATENCY.labels(node_id=node['id']).observe(
                        time.time() - node_start_time
                    )
                    
                    # Get only the new tokens (excluding the input)
                    new_tokens = list(response.data)[len(current_sequence):]
                    logger.info(f"Node {node['id']} added tokens: {new_tokens}")
                    
                    # Update current sequence
                    current_sequence = list(response.data)
                    
                except Exception as e:
                    error_msg = f"Processing failed at node {node['id']}: {str(e)}"
                    logger.error(error_msg)
                    COORDINATOR_REQUESTS.labels(status='error').inc()
                    context.set_code(grpc.StatusCode.INTERNAL)
                    context.set_details(error_msg)
                    return model_service_pb2.ModelOutput()
            
            # Record total processing time and success
            TOTAL_PROCESSING_TIME.observe(time.time() - start_time)
            COORDINATOR_REQUESTS.labels(status='success').inc()
            
            # For the final response, only return the generated tokens (exclude the original input)
            final_response = current_sequence[input_length:]
            logger.info(f"Final generated tokens: {final_response}")
            return model_service_pb2.ModelOutput(data=final_response)
            
        except Exception as e:
            error_msg = f"Request processing failed: {str(e)}"
            logger.error(error_msg)
            COORDINATOR_REQUESTS.labels(status='error').inc()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(error_msg)
            return model_service_pb2.ModelOutput()

async def serve(config_path: str, port: int):
    """Start the coordinator server."""
    try:
        server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024)
            ]
        )
        coordinator = ModelCoordinator(config_path)
        model_service_pb2_grpc.add_ModelServiceServicer_to_server(coordinator, server)
        server.add_insecure_port(f'[::]:{port}')
        logger.info(f"Starting coordinator server on port {port}")
        await server.start()
        await server.wait_for_termination()
    except Exception as e:
        logger.error("Failed to start server: %s", str(e))
        raise

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, help='Path to configuration file')
    parser.add_argument('--port', type=int, default=50050, help='Port to run coordinator on')
    args = parser.parse_args()
    
    asyncio.run(serve(args.config, args.port))