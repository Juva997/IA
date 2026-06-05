FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN apt-get update \
	&& apt-get install -y --no-install-recommends curl \
	&& rm -rf /var/lib/apt/lists/* \
	&& pip install --no-cache-dir -r requirements.txt
COPY mock_ollama.py /app/mock_ollama.py
EXPOSE 11434
CMD ["uvicorn", "mock_ollama:app", "--host", "0.0.0.0", "--port", "11434"]
