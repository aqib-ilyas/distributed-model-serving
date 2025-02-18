import os
import json
import logging
from concurrent import futures
import grpc
import grpc.aio  # Add explicit import for grpc.aio
import asyncio
import sys

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

class ModelCoordinator(model_service_pb2_grpc.ModelServiceServicer):
    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        self.node_stubs = {}
        self.setup_connections()
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
                channel = grpc.aio.insecure_channel(  # Changed to aio.insecure_channel
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
            except grpc.RpcError as e:
                logger.warning("Node %s is unhealthy: %s", node['id'], str(e))
                unhealthy_nodes.append(node['id'])
        return unhealthy_nodes
    
    async def process(self, request, context):
        """Process request through all nodes in sequence."""
        try:
            # Check node health
            unhealthy_nodes = await self.check_node_health()
            if unhealthy_nodes:
                error_msg = f"Nodes {unhealthy_nodes} are unavailable"
                logger.error(error_msg)
                context.set_code(grpc.StatusCode.UNAVAILABLE)
                context.set_details(error_msg)
                return model_service_pb2.ModelOutput()
            
            # Store the input data
            current_data = list(request.data)
            logger.info(f"Coordinator received input data: {current_data}")
            
            # Keep track of all node outputs
            all_node_outputs = []
            
            # Process through each node in sequence
            for node in self.config['nodes']:
                try:
                    logger.info(f"Sending data to node {node['id']}")
                    
                    # Create node request with current data
                    node_input = model_service_pb2.ModelInput(
                        data=current_data,
                        metadata={'node_id': node['id']}
                    )
                    
                    # Get response from node
                    response = await self.node_stubs[node['id']].process(node_input)
                    node_output = list(response.data)
                    logger.info(f"Response from node {node['id']}: {node_output}")
                    
                    # Add node output to our collection
                    all_node_outputs.append(node_output)
                    
                    # Update current_data for next node in sequence
                    current_data = node_output
                    
                except Exception as e:
                    error_msg = f"Processing failed at node {node['id']}: {str(e)}"
                    logger.error(error_msg)
                    context.set_code(grpc.StatusCode.INTERNAL)
                    context.set_details(error_msg)
                    return model_service_pb2.ModelOutput()
            
            # Combine outputs from all nodes for the final response
            # Taking the last output as it should contain the final processed result
            final_output = all_node_outputs[-1]
            
            logger.info(f"Node outputs collected:")
            for i, output in enumerate(all_node_outputs):
                logger.info(f"Node {self.config['nodes'][i]['id']} output: {output}")
            logger.info(f"Final output: {final_output}")
            
            return model_service_pb2.ModelOutput(data=final_output)
            
        except Exception as e:
            error_msg = f"Request processing failed: {str(e)}"
            logger.error(error_msg)
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