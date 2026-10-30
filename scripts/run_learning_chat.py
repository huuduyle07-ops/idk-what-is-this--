"""Start the local learning UI with an explicitly selected chat model."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("ollama", "gemini"), default="ollama")
    parser.add_argument("--model", required=True, help="An already installed/local or available/cloud model")
    parser.add_argument("--port", type=int, default=5055)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    os.environ["LEARNING_CHAT_PROVIDER"] = args.provider
    os.environ["LEARNING_CHAT_MODEL"] = args.model
    # The learning UI needs no PostgreSQL or embedding model at startup.
    for name in ("DB_ENABLED", "INDEX_USE_EMBEDDINGS", "ROUTER_USE_EMBEDDINGS", "RETRIEVER_USE_DB"):
        os.environ.setdefault(name, "false")
    os.environ.setdefault("EMBEDDING_PROVIDER", "off")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from web.app import app
    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
