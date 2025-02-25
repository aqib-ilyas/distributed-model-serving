import os
import logging
from typing import Dict
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import grpc
import grpc.aio
import time
import asyncio
import sys
from prometheus_client import start_http_server, Counter, Histogram, Gauge, Info, make_asgi_app

# Add relative import path for proto files
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
proto_dir = os.path.join(parent_dir, 'proto')
sys.path.append(proto_dir)

import model_service_pb2
import model_service_pb2_grpc
import tokenizer_service_pb2
import tokenizer_service_pb2_grpc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define Prometheus metrics
REQUEST_COUNT = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'api_request_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint']
)

TOKENIZATION_LATENCY = Histogram(
    'api_tokenization_latency_seconds',
    'Time taken for tokenization operations',
    ['operation']  # 'encode' or 'decode'
)

MODEL_PROCESSING_LATENCY = Histogram(
    'api_model_processing_latency_seconds',
    'Time taken for model processing'
)

TOKEN_COUNT = Gauge(
    'api_token_count',
    'Number of tokens in request/response',
    ['type']  # 'input' or 'output'
)

app = FastAPI(title="Model Serving API")

# Add prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ModelRequest(BaseModel):
    text: str
    metadata: Dict[str, str] = {}

class ModelResponse(BaseModel):
    text: str
    processingTime: float
    nodeCount: int = 3

class TokenizerClient:
    def __init__(self):
        self.channel = None
        self.stub = None

    async def connect(self):
        if not self.channel:
            self.channel = grpc.aio.insecure_channel(
                'tokenizer:50054',
                options=[
                    ('grpc.max_send_message_length', 50 * 1024 * 1024),
                    ('grpc.max_receive_message_length', 50 * 1024 * 1024)
                ]
            )
            self.stub = tokenizer_service_pb2_grpc.TokenizerServiceStub(self.channel)

    async def tokenize(self, text: str, metadata: Dict[str, str] = None) -> list[float]:
        start_time = time.time()
        await self.connect()
        try:
            response = await self.stub.process_text(
                tokenizer_service_pb2.TextInput(
                    text=text,
                    metadata=metadata or {}
                )
            )
            
            # Record metrics
            TOKENIZATION_LATENCY.labels('encode').observe(time.time() - start_time)
            TOKEN_COUNT.labels('input').set(len(response.tokens))
            
            return list(response.tokens)
        except Exception as e:
            logger.error(f"Tokenization failed: {str(e)}")
            raise

    async def decode(self, tokens: list[float], metadata: Dict[str, str] = None) -> str:
        start_time = time.time()
        await self.connect()
        try:
            response = await self.stub.process_tokens(
                tokenizer_service_pb2.TokenInput(
                    tokens=tokens,
                    metadata=metadata or {}
                )
            )
            
            # Record metrics
            TOKENIZATION_LATENCY.labels('decode').observe(time.time() - start_time)
            TOKEN_COUNT.labels('output').set(len(tokens))
            
            return response.text
        except Exception as e:
            logger.error(f"Decoding failed: {str(e)}")
            raise

    async def close(self):
        if self.channel:
            await self.channel.close()

tokenizer_client = TokenizerClient()

@app.on_event("shutdown")
async def shutdown_event():
    await tokenizer_client.close()

@app.post("/api/model/process")
async def process_model(request: ModelRequest):
    """Process text through the distributed model"""
    request_start_time = time.time()
    model_channel = None
    
    try:
        logger.info(f"Received text request: {request.text}")
        
        # Tokenize input text
        input_tokens = await tokenizer_client.tokenize(request.text, request.metadata)
        logger.info(f"Tokenized input tokens: {input_tokens}")
        
        # Connect to coordinator service
        model_channel = grpc.aio.insecure_channel(
            'coordinator:50050',
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024),
                ('grpc.keepalive_time_ms', 30000),
                ('grpc.keepalive_timeout_ms', 10000)
            ]
        )
        model_stub = model_service_pb2_grpc.ModelServiceStub(model_channel)
        
        # Process through model
        model_start_time = time.time()
        try:
            response = await asyncio.wait_for(
                model_stub.process(model_service_pb2.ModelInput(
                    data=input_tokens,
                    metadata=request.metadata
                )),
                timeout=30.0
            )
            # Record model processing time
            MODEL_PROCESSING_LATENCY.observe(time.time() - model_start_time)
            logger.info(f"Received response from model. Tokens: {list(response.data)}")
            
        except asyncio.TimeoutError:
            logger.error("Request timed out")
            REQUEST_COUNT.labels(
                method='POST',
                endpoint='/api/model/process',
                status='timeout'
            ).inc()
            raise HTTPException(status_code=504, detail="Request timed out")
        
        # Decode output tokens
        output_text = await tokenizer_client.decode(
            list(response.data),
            request.metadata
        )
        logger.info(f"Final decoded output text: {output_text}")
        
        # Calculate total processing time
        processing_time = (time.time() - request_start_time) * 1000  # Convert to milliseconds
        
        # Record request metrics
        REQUEST_COUNT.labels(
            method='POST',
            endpoint='/api/model/process',
            status='success'
        ).inc()
        REQUEST_LATENCY.labels(
            method='POST',
            endpoint='/api/model/process'
        ).observe(time.time() - request_start_time)
        
        return ModelResponse(
            text=output_text,
            processingTime=round(processing_time, 2),
            nodeCount=3
        )
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        REQUEST_COUNT.labels(
            method='POST',
            endpoint='/api/model/process',
            status='error'
        ).inc()
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {str(e)}"
        )
        
    finally:
        if model_channel:
            await model_channel.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )