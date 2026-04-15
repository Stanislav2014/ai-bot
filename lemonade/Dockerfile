FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates libgomp1 libcurl4 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir lemonade-sdk==9.1.4

# Pre-create cache dir with correct permissions
RUN mkdir -p /root/.cache/lemonade

EXPOSE 8000

# Use CPU backend (vulkan/rocm require host GPU passthrough)
CMD ["lemonade-server-dev", "serve", "--host", "0.0.0.0", "--port", "8000", "--llamacpp", "cpu"]
