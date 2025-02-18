import os
import logging
from concurrent import futures
import grpc
import grpc.aio
import asyncio
import sys
from transformers import GPT2Tokenizer

# Add relative import path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
proto_dir = os.path.join(parent_dir, 'proto')
sys.path.append(proto_dir)

import tokenizer_service_pb2
import tokenizer_service_pb2_grpc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TokenizerServicer(tokenizer_service_pb2_grpc.TokenizerServiceServicer):
    def __init__(self):
        self.tokenizer = self.load_tokenizer()
        logger.info("Tokenizer service initialized")

    def load_tokenizer(self):
        """Load the GPT2 tokenizer."""
        try:
            tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
            # Set padding token to ensure consistent handling
            tokenizer.pad_token = tokenizer.eos_token
            logger.info("GPT2 Tokenizer loaded successfully")
            
            # Test tokenization
            test_input = "Hello, how are you?"
            test_tokens = tokenizer.encode(test_input, return_tensors='pt')[0].tolist()
            test_decode = tokenizer.decode(test_tokens)
            logger.info(f"Test tokenization - Input: {test_input}")
            logger.info(f"Test tokenization - Tokens: {test_tokens}")
            logger.info(f"Test tokenization - Decoded: {test_decode}")
            
            return tokenizer
        except Exception as e:
            logger.error(f"Failed to load tokenizer: {str(e)}")
            raise

    async def process_text(self, request, context):
        """Tokenize input text."""
        try:
            # Add EOS token and return as normal Python list
            tokens = self.tokenizer.encode(
                request.text,
                add_special_tokens=True,
                return_tensors='pt'
            )[0].tolist()
            
            logger.info(f"Input text: {request.text}")
            logger.info(f"Encoded tokens: {tokens}")
            
            # Verify decoding
            verify = self.tokenizer.decode(tokens)
            logger.info(f"Verification decode: {verify}")
            
            return tokenizer_service_pb2.TokenOutput(tokens=tokens)
        except Exception as e:
            error_msg = f"Text processing failed: {str(e)}"
            logger.error(error_msg)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(error_msg)
            return tokenizer_service_pb2.TokenOutput()

    async def process_tokens(self, request, context):
        """Process tokens to text."""
        try:
            # Convert float tokens to integers
            tokens = [int(float(t)) for t in request.tokens]
            logger.info(f"Processing tokens: {tokens}")
            
            # Decode tokens
            text = self.tokenizer.decode(
                tokens,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True
            )
            logger.info(f"Decoded text: {text}")
            return tokenizer_service_pb2.TextOutput(text=text)
        except Exception as e:
            error_msg = f"Token processing failed: {str(e)}"
            logger.error(error_msg)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(error_msg)
            return tokenizer_service_pb2.TextOutput()

    async def health_check(self, request, context):
        """Implement health check."""
        try:
            if not hasattr(self, 'tokenizer'):
                raise Exception("Tokenizer not loaded")
            return tokenizer_service_pb2.HealthCheckResponse(status="OK")
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return tokenizer_service_pb2.HealthCheckResponse(status=f"ERROR: {str(e)}")

async def serve(port: int):
    """Start the tokenizer server."""
    try:
        server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024)
            ]
        )
        tokenizer_service_pb2_grpc.add_TokenizerServiceServicer_to_server(
            TokenizerServicer(), server
        )
        server.add_insecure_port(f'[::]:{port}')
        logger.info(f"Starting tokenizer server on port {port}")
        await server.start()
        await server.wait_for_termination()
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=50054, help='Port to run tokenizer on')
    args = parser.parse_args()
    
    asyncio.run(serve(args.port))