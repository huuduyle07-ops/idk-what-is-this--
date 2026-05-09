import sys
from pathlib import Path
try:
    import ollama
except Exception:
    ollama = None

# Add project root to sys.path to allow importing config.py
root_dir = str(Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from config import DEEPSEEK_MODELS
from agents.gemini_client import run_gemini_request_2


def run_deepseek_review(content: str) -> str:
    """Try DEEPSEEK_MODELS in order, return the first model that responds.

    This mirrors the Gemini client's fallback pattern: if the strongest model is
    unavailable (rate-limited, cloud outage, not pulled), we transparently fall
    back to the next one instead of hard-failing the whole pipeline.
    """
    last_error = None
    messages = [
        {"role": "system", "content": "You are a strict code reviewer."},
        {"role": "user", "content": content},
    ]

    if ollama is not None:
        last_error = None

        for model_name in DEEPSEEK_MODELS:
            try:
                response = ollama.chat(model=model_name, messages=messages)
                return response["message"]["content"]
            except Exception as e:
                last_error = e
                sys.stderr.write(f"\n⚠️ DeepSeek model '{model_name}' failed: {e}\n")
                continue

        sys.stderr.write(
            f"\n⚠️ Ollama review failed; falling back to Google model. Last error: {last_error}\n"
        )
    else:
        sys.stderr.write("\n⚠️ Ollama package not available; using Google model fallback.\n")

    return run_gemini_request_2(
        "You are a strict code reviewer.\n\nReview this content:\n\n" + content,
        repo_path=None,
        file_paths=None,
    )

def main():
    content_to_review = sys.argv[1] if len(sys.argv) > 1 else "No content"
    output = run_deepseek_review(content_to_review)
    print(output)

if __name__ == "__main__":
    main()
