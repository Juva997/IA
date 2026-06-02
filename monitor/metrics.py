from prometheus_client import Counter, Histogram, Gauge, start_http_server


class Metrics:
    def __init__(self):
        self.requests_total = Counter('assistant_requests_total', 'Total requests', ['endpoint'])
        self.response_time = Histogram('assistant_response_time_seconds', 'Response time', ['endpoint'])
        self.active_goals = Gauge('assistant_active_goals', 'Active goals')
        self.memory_size = Gauge('assistant_memory_size', 'Memory vectors count')
        self.llm_calls = Counter('assistant_llm_calls_total', 'LLM calls', ['model'])

    def start_server(self, port=8001):
        start_http_server(port)
        print(f"📊 Métricas Prometheus em http://localhost:{port}")

    def increment_requests(self, endpoint):
        self.requests_total.labels(endpoint=endpoint).inc()

    def observe_response_time(self, endpoint, duration):
        self.response_time.labels(endpoint=endpoint).observe(duration)

    def set_active_goals(self, count):
        self.active_goals.set(count)

    def set_memory_size(self, size):
        self.memory_size.set(size)

    def increment_llm_calls(self, model):
        self.llm_calls.labels(model=model).inc()
