FROM python:3.12-slim

WORKDIR /app

# Atualiza ferramentas de empacotamento e instala dependências
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel \
	&& pip install --no-cache-dir -r requirements.txt

COPY . /app

CMD ["python", "app.py"]
