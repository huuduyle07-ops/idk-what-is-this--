# AI Project Setup Guide

## Python Environment Setup

This project requires **two Python environments** due to tree-sitter compatibility constraints:

### 1. Main Development Environment (Python 3.13+)
Your primary development environment. Install this for general development work.

```bash
python3.13 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Tree-Sitter Environment (Python 3.12.13)
A secondary environment specifically for tree-sitter components. Create this when you need to work with code parsing:

```bash
python3.12 -m venv .venv-py312
source .venv-py312/bin/activate  # On Windows: .venv-py312\Scripts\activate
pip install -r requirements.txt
```

## Switching Between Environments

- **For general development (Python 3.13):**
  ```bash
  source .venv/bin/activate
  ```

- **For tree-sitter work (Python 3.12.13):**
  ```bash
  source .venv-py312/bin/activate
  ```

## Environment Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Update `.env` with your credentials:
   - `GOOGLE_API_KEY`: Get from [Google AI Studio](https://aistudio.google.com/app/apikeys)
   - `DEEPSEEK_API_KEY`: Get from [Deepseek Platform](https://platform.deepseek.com/api_keys)
   - Database credentials (PostgreSQL)

3. Choose deployment environment:
   - `APP_ENV=local` (development on host)
   - `APP_ENV=docker` (running in container)

## Dependencies

See [requirements.txt](requirements.txt) for the complete list of dependencies.

### Optional Dependencies

Install optional dependencies as needed:
```bash
pip install -r requirements_optional.txt
```

- **ollama**: Local LLM runtime (fallback for Deepseek reviews when cloud API is unavailable)

## Running the Application

```bash
# Activate the appropriate environment first
source .venv/bin/activate

# Run the CLI interface
python main.py

# Or run the web interface
python -m web.app
```

## Database Setup

Ensure PostgreSQL is running and the `codex_db` database exists with proper credentials configured in `.env`.

For Docker setup, see [docker-compose.yml](docker-compose.yml):
```bash
docker-compose up -d
```
