FROM mcr.microsoft.com/devcontainers/python:3.12

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    nodejs \
    npm \
    golang-go \
    && rm -rf /var/lib/apt/lists/*

USER vscode

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y

ENV PATH="/home/vscode/.cargo/bin:${PATH}"

WORKDIR /app

COPY --chown=vscode:vscode requirements.txt requirements_optional.txt ./
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
ENV WEB_HOST=0.0.0.0
CMD ["python", "main.py", "--web"]