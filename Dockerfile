FROM python:3.12-slim

WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV WEB_HOST=0.0.0.0
ENV PATH="/home/appuser/.local/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m appuser

COPY requirements.txt requirements.txt
COPY requirements_embeddings.txt requirements_embeddings.txt
COPY requirements_optional.txt requirements_optional.txt

ARG INSTALL_EMBEDDINGS=false
ARG INSTALL_OLLAMA_CLIENT=false

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_EMBEDDINGS" = "true" ]; then pip install --no-cache-dir -r requirements_embeddings.txt; fi \
    && if [ "$INSTALL_OLLAMA_CLIENT" = "true" ]; then pip install --no-cache-dir -r requirements_optional.txt; fi

USER appuser

EXPOSE 5000

CMD ["python", "main.py", "--web"]