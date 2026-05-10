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