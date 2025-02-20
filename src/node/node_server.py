import os
import json
import logging
from concurrent import futures
import torch
from transformers import AutoModelForCausalLM, GPT2Tokenizer
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

class ModelNode(model_service_pb2_grpc.ModelServiceServicer):
    
    def __init__(self, config_path: str, node_id: str):
        self.config = self.load_config(config_path, node_id)
        self.tokenizer = GPT2Tokenizer.from_pretrained('gpt2') 
        self.model = self.load_model()
        self.cache = {}
        logger.info("Node %s initialized successfully", node_id)
    
    def load_config(self, config_path: str, node_id: str) -> dict:
        """Load and validate configuration."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                node_config = next((node for node in config['nodes'] 
                                  if node['id'] == node_id), None)
                if not node_config:
                    raise ValueError(f"Node {node_id} not found in config")
                
                return {
                    'model_name': config['model_name'],
                    'node_config': node_config,
                    'total_nodes': len(config['nodes'])
                }
        except Exception as e:
            logger.error("Failed to load config: %s", str(e))
            raise
    
    def create_device_map(self) -> tuple[dict, bool]:
        """Create device map for this node's portion of the model."""
        try:
            # Always use CPU for this test setup
            use_gpu = False
            target_device = 'cpu'
            logger.info(f"Using CPU for model execution")

            model = AutoModelForCausalLM.from_pretrained(self.config['model_name'])
            total_layers = len(model.transformer.h)
            layers_per_node = total_layers // 3  # Split between 3 nodes
            node_idx = self.config['node_config']['model_part']
            
            start_layer = node_idx * layers_per_node
            end_layer = start_layer + layers_per_node
            
            # Create complete device map
            device_map = {
                'transformer.wte': target_device,
                'transformer.wpe': target_device,
                'transformer.drop': target_device,
                'transformer.ln_f': target_device,
                'lm_head': target_device
            }
            
            # Map transformer layers
            for i in range(total_layers):
                device_map[f'transformer.h.{i}'] = target_device
            
            logger.info(f"Created device map with layers {start_layer} to {end_layer} on {target_device}")
            return device_map, use_gpu
                
        except Exception as e:
            logger.error(f"Failed to create device map: {str(e)}")
            raise

    def load_model(self):
        """Load model with memory optimizations."""
        try:
            device_map, use_gpu = self.create_device_map()
            
            model_args = {
                'device_map': device_map,
                'torch_dtype': torch.float16 if use_gpu else torch.float32,
                'low_cpu_mem_usage': True
            }

            # Load model with optimizations
            model = AutoModelForCausalLM.from_pretrained(
                self.config['model_name'],
                **model_args
            )
            model.eval()
            logger.info(f"Model loaded successfully on {'GPU' if use_gpu else 'CPU'}")
            return model
                
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise

    async def process(self, request, context):
        """Process input through this node's portion of the model."""
        try:
            logger.info(f"Node {self.config['node_config']['id']} received input: {list(request.data)}")
            
            # Convert input to tensor
            input_data = torch.tensor([request.data], dtype=torch.long)
            attention_mask = torch.ones_like(input_data)
            input_length = len(request.data)
            
            with torch.no_grad():
                if torch.cuda.is_available():
                    input_data = input_data.cuda()
                    attention_mask = attention_mask.cuda()
                
                # Adjust generation parameters based on node position
                is_first_node = self.config['node_config']['id'] == 'node1'
                is_last_node = self.config['node_config']['id'] == 'node3'
                
                # Configure generation parameters
                generation_params = {
                    'input_ids': input_data,
                    'attention_mask': attention_mask,
                    'num_beams': 5,
                    'do_sample': True,
                    'top_k': 40,         # Increased from 30
                    'top_p': 0.95,       # Increased from 0.92
                    'temperature': 0.8,   # Slightly reduced
                    'pad_token_id': self.model.config.eos_token_id,
                    'repetition_penalty': 1.3,  # Increased from 1.2
                    'length_penalty': 1.2,      # Increased to favor longer sequences
                    'early_stopping': True,
                }
                
                # Adjust parameters based on node position
                if is_first_node:
                    # First node generates a longer main response
                    generation_params.update({
                        'max_length': input_length + 30,  # Increased from 20 
                        'min_length': input_length + 15,  # Increased from 10
                        'no_repeat_ngram_size': 3,
                    })
                elif is_last_node:
                    # Last node adds a proper conclusion
                    generation_params.update({
                        'max_length': input_length + 10,  # Increased from 5
                        'min_length': input_length + 3,   # Increased from 1
                        'no_repeat_ngram_size': 2,
                    })
                else:
                    # Middle node continues the thought
                    generation_params.update({
                        'max_length': input_length + 15,  # Increased from 8
                        'min_length': input_length + 5,   # Increased from 3
                        'no_repeat_ngram_size': 2,
                    })
                
                # Generate text
                outputs = self.model.generate(**generation_params)
                
                # Get only the new tokens
                output_sequence = outputs[0, input_length:].cpu().tolist()
                
                logger.info(f"Node {self.config['node_config']['id']} generated new tokens: {output_sequence}")
                
                # Return combined sequence
                combined_sequence = list(request.data) + output_sequence
                return model_service_pb2.ModelOutput(data=combined_sequence)
                
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            logger.error(error_msg)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(error_msg)
            return model_service_pb2.ModelOutput()

    async def health_check(self, request, context):
        """Implement health check."""
        try:
            # Verify model is loaded
            if not hasattr(self, 'model'):
                raise Exception("Model not loaded")
            
            # Get device info
            device_info = "GPU" if torch.cuda.is_available() else "CPU"
            memory_info = ""
            
            if torch.cuda.is_available():
                gpu_memory = torch.cuda.get_device_properties(0).total_memory
                memory_info = f", GPU Memory: {gpu_memory / (1024**2):.2f}MB"
            
            status = f"OK (Running on {device_info}{memory_info})"
            return model_service_pb2.HealthCheckResponse(status=status)
                
        except Exception as e:
            error_msg = f"Health check failed: {str(e)}"
            logger.error(error_msg)
            return model_service_pb2.HealthCheckResponse(status=f"ERROR: {str(e)}")

async def serve(config_path: str, node_id: str):
    """Start the node server."""
    try:
        # Get node port from config
        with open(config_path, 'r') as f:
            config = json.load(f)
            node_config = next(node for node in config['nodes'] if node['id'] == node_id)
            port = int(node_config['address'].split(':')[-1])
        
        server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024)
            ]
        )
        node = ModelNode(config_path, node_id)
        model_service_pb2_grpc.add_ModelServiceServicer_to_server(node, server)
        server.add_insecure_port(f'[::]:{port}')
        logger.info(f"Starting node server {node_id} on port {port}")
        await server.start()
        await server.wait_for_termination()
    except Exception as e:
        logger.error("Failed to start server: %s", str(e))
        raise

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, help='Path to configuration file')
    parser.add_argument('--node-id', required=True, help='ID of this node from config')
    args = parser.parse_args()
    
    asyncio.run(serve(args.config, args.node_id))