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

app = FastAPI(title="Model Serving API")

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
        await self.connect()
        try:
            response = await self.stub.process_text(
                tokenizer_service_pb2.TextInput(
                    text=text,
                    metadata=metadata or {}
                )
            )
            return list(response.tokens)
        except Exception as e:
            logger.error(f"Tokenization failed: {str(e)}")
            raise

    async def decode(self, tokens: list[float], metadata: Dict[str, str] = None) -> str:
        await self.connect()
        try:
            response = await self.stub.process_tokens(
                tokenizer_service_pb2.TokenInput(
                    tokens=tokens,
                    metadata=metadata or {}
                )
            )
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
    start_time = time.time()
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
        
        # Create gRPC request
        grpc_request = model_service_pb2.ModelInput(
            data=input_tokens,
            metadata=request.metadata
        )
        
        # Call coordinator service with timeout
        try:
            response = await asyncio.wait_for(
                model_stub.process(grpc_request),
                timeout=30.0
            )
            logger.info(f"Received response from model. Tokens: {list(response.data)}")
        except asyncio.TimeoutError:
            logger.error("Request timed out")
            raise HTTPException(status_code=504, detail="Request timed out")
        
        # Decode output tokens
        output_text = await tokenizer_client.decode(
            list(response.data),
            request.metadata
        )
        logger.info(f"Final decoded output text: {output_text}")
        
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        return ModelResponse(
            text=output_text,
            processingTime=round(processing_time, 2),
            nodeCount=3
        )
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
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