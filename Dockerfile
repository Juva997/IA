FROM python:3.12-slim

WORKDIR /app

# Instala utilitários necessários para healthchecks e build
COPY requirements.txt /app/requirements.txt
RUN apt-get update \
	&& apt-get install -y --no-install-recommends curl \
	&& rm -rf /var/lib/apt/lists/* \
	&& pip install --upgrade pip setuptools wheel \
	&& pip install --no-cache-dir -r requirements.txt

COPY . /app

CMD ["python", "app.py", "api"]
