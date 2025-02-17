import os
import logging
from typing import List, Dict
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import grpc
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Model Serving API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ModelRequest(BaseModel):
    data: List[float]
    metadata: Dict[str, str] = {}

class ModelResponse(BaseModel):
    data: List[float]
    processingTime: float
    nodeCount: int = 3

# Error handler middleware
@app.middleware("http")
async def error_handler(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/api/model/process")
async def process_model(request: ModelRequest):
    """Process data through the distributed model"""
    start_time = time.time()
    channel = None
    
    try:
        logger.info(f"Received request with data length: {len(request.data)}")
        logger.info(f"Request metadata: {request.metadata}")
        
        # Connect to coordinator service
        channel = grpc.aio.insecure_channel(
            'coordinator:50050',
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024),
                ('grpc.keepalive_time_ms', 30000),
                ('grpc.keepalive_timeout_ms', 10000)
            ]
        )
        stub = model_service_pb2_grpc.ModelServiceStub(channel)
        
        # Add timestamp to metadata if not present
        if 'timestamp' not in request.metadata:
            request.metadata['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Create gRPC request
        grpc_request = model_service_pb2.ModelInput(
            data=request.data,
            metadata=request.metadata
        )
        
        # Call coordinator service with timeout
        try:
            response = await asyncio.wait_for(
                stub.process(grpc_request),
                timeout=30.0  # 30 second timeout
            )
        except asyncio.TimeoutError:
            logger.error("Request timed out")
            raise HTTPException(status_code=504, detail="Request timed out")
        
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        return ModelResponse(
            data=list(response.data),
            processingTime=round(processing_time, 2),
            nodeCount=3
        )
        
    except grpc.RpcError as e:
        logger.error(f"gRPC error: {e.details() if hasattr(e, 'details') else str(e)}")
        status_code = e.code() if hasattr(e, 'code') else grpc.StatusCode.UNKNOWN
        if status_code == grpc.StatusCode.UNAVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable. Nodes are not ready."
            )
        raise HTTPException(
            status_code=500,
            detail=f"Model processing failed: {e.details() if hasattr(e, 'details') else str(e)}"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
        
    finally:
        if channel:
            await channel.close()

@app.get("/api/model/config")
async def get_model_config():
    """Get current model configuration"""
    return {
        "nodeCount": 3,
        "modelName": "gpt2",
        "maxInputSize": 1024,
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Enable auto-reload during development
    )