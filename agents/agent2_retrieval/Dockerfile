FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY agents/agent2_retrieval/requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared code and agent code
COPY shared /workspace/shared
COPY agents/agent2_retrieval /workspace/agents/agent2_retrieval

WORKDIR /workspace/agents/agent2_retrieval
ENV PYTHONPATH=/workspace:/workspace/agents/agent2_retrieval

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
