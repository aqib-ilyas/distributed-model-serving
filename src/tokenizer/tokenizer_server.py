import os
import logging
from concurrent import futures
import grpc
import grpc.aio
import asyncio
import sys
import time
from transformers import GPT2Tokenizer
from prometheus_client import start_http_server, Counter, Histogram, Info

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

# Define metrics
TOKENIZER_REQUESTS = Counter(
    'tokenizer_requests_total',
    'Total number of tokenizer requests',
    ['operation', 'status']  # operation: encode/decode, status: success/error
)

TOKENIZER_LATENCY = Histogram(
    'tokenizer_operation_latency_seconds',
    'Time taken for tokenizer operations',
    ['operation']  # encode/decode
)

TOKEN_COUNT = Counter(
    'tokenizer_token_count_total',
    'Total number of tokens processed',
    ['operation']  # encode/decode
)

TOKENIZER_INFO = Info('tokenizer', 'Tokenizer information')

class TokenizerServicer(tokenizer_service_pb2_grpc.TokenizerServiceServicer):
    def __init__(self):
        # Start Prometheus metrics server
        start_http_server(8002)
        
        self.tokenizer = self.load_tokenizer()
        
        # Record tokenizer information
        TOKENIZER_INFO.info({
            'model': 'gpt2',
            'vocab_size': str(len(self.tokenizer.get_vocab())),
            'max_length': str(self.tokenizer.model_max_length)
        })
        
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
        start_time = time.time()
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
            
            # Update metrics
            TOKENIZER_REQUESTS.labels(
                operation='encode',
                status='success'
            ).inc()
            
            TOKENIZER_LATENCY.labels(
                operation='encode'
            ).observe(time.time() - start_time)
            
            TOKEN_COUNT.labels(
                operation='encode'
            ).inc(len(tokens))
            
            return tokenizer_service_pb2.TokenOutput(tokens=tokens)
        except Exception as e:
            error_msg = f"Text processing failed: {str(e)}"
            logger.error(error_msg)
            
            TOKENIZER_REQUESTS.labels(
                operation='encode',
                status='error'
            ).inc()
            
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(error_msg)
            return tokenizer_service_pb2.TokenOutput()

    async def process_tokens(self, request, context):
        """Process tokens to text."""
        start_time = time.time()
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
            
            # Clean up the text
            text = text.strip()  # Remove leading/trailing whitespace
            text = ' '.join(line.strip() for line in text.splitlines() if line.strip())
            
            logger.info(f"Decoded text: {text}")
            
            # Update metrics
            TOKENIZER_REQUESTS.labels(
                operation='decode',
                status='success'
            ).inc()
            
            TOKENIZER_LATENCY.labels(
                operation='decode'
            ).observe(time.time() - start_time)
            
            TOKEN_COUNT.labels(
                operation='decode'
            ).inc(len(tokens))
            
            return tokenizer_service_pb2.TextOutput(text=text)
        except Exception as e:
            error_msg = f"Token processing failed: {str(e)}"
            logger.error(error_msg)
            
            TOKENIZER_REQUESTS.labels(
                operation='decode',
                status='error'
            ).inc()
            
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