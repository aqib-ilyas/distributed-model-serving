# src/metrics/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Info
import time

# API Metrics
request_counter = Counter(
    'model_requests_total',
    'Total number of requests processed',
    ['service', 'status']
)

request_latency = Histogram(
    'request_latency_seconds',
    'Request latency in seconds',
    ['service', 'endpoint']
)

# Model Node Metrics
model_inference_time = Histogram(
    'model_inference_time_seconds',
    'Time taken for model inference',
    ['node_id']
)

model_memory_usage = Gauge(
    'model_memory_usage_bytes',
    'Current memory usage of the model',
    ['node_id']
)

# Tokenizer Metrics
tokenizer_requests = Counter(
    'tokenizer_requests_total',
    'Total number of tokenizer requests',
    ['operation']  # 'encode' or 'decode'
)

tokenizer_latency = Histogram(
    'tokenizer_latency_seconds',
    'Tokenizer operation latency',
    ['operation']
)

# System Info
system_info = Info('model_system', 'Model system information')

class MetricsMiddleware:
    def __init__(self, service_name):
        self.service_name = service_name
    
    async def __call__(self, request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            request_counter.labels(
                service=self.service_name,
                status=response.status_code
            ).inc()
        except Exception as e:
            request_counter.labels(
                service=self.service_name,
                status=500
            ).inc()
            raise e
        finally:
            request_latency.labels(
                service=self.service_name,
                endpoint=request.url.path
            ).observe(time.time() - start_time)
        
        return response