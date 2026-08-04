FROM python:3.13-slim
LABEL maintainer="oleggalas8@gmail.com"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Use Daphne ASGI server for WebSocket support
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
