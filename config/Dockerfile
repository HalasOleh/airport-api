FROM python:3.13-slim
LABEL maintainer="oleggalas8@gmail.com"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

# torch comes first, and from the CPU-only index. The default PyPI wheel bundles
# the whole CUDA runtime - roughly 7 GB of libraries this container can never
# use. Installing it up front means sentence-transformers finds the requirement
# already satisfied and does not pull the GPU build.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch

RUN pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into the image so the first request does not wait
# on a download.
ENV EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-small
ENV HF_HOME=/opt/hf-cache
RUN python -c "from sentence_transformers import SentenceTransformer; import os; SentenceTransformer(os.environ['EMBEDDING_MODEL_NAME'])"

# Without this the library still calls huggingface.co on every model load to
# revalidate the cache: dozens of requests, slow startup, and a hard dependency
# on the Hub being reachable in production.
ENV HF_HUB_OFFLINE=1

COPY . .

EXPOSE 8000

# Use Daphne ASGI server for WebSocket support
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
