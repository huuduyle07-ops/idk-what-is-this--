import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path to allow importing config.py
root_dir = str(Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from config import GOOGLE_API_KEY, MODELS
import google.genai as genai
from google.genai import types as genai_types
from core.security import is_safe_path

load_dotenv()


def _max_model_fallbacks(default: int) -> int:
    raw = os.environ.get("MAX_MODEL_FALLBACKS")
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def safe_print(text: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    print(text.encode(encoding, errors="replace").decode(encoding))

def run_gemini_request(prompt: str, file_paths: list[str] | None = None) -> str:
    api_key = GOOGLE_API_KEY

    # Fail fast before doing security/upload work.
    if not api_key:
        return "AGENT_ERROR: GOOGLE_API_KEY is missing."

    file_paths = file_paths or []

    # Security check on uploaded paths.
    repo_path = file_paths[0] if len(file_paths) == 1 and os.path.isdir(file_paths[0]) else None
    allowed_roots = [repo_path] if repo_path else []

    safe_file_paths = []
    for p in file_paths:
        if is_safe_path(p, allowed_roots=allowed_roots):
            safe_file_paths.append(p)
        else:
            sys.stderr.write(f"\n🛑 Security Block in Agent: Access to '{p}' restricted.\n")

    file_paths = safe_file_paths

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        return f"AGENT_ERROR: Failed to initialize Gemini client: {e}"

    # 1. Upload all files once
    TEXT_EXTENSIONS = {".py", ".cs", ".rs", ".cpp", ".c", ".h", ".hpp", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".md", ".txt", ".json"}
    
    contents = [prompt]
    try:
        if file_paths:
            for path in file_paths:
                if os.path.isdir(path): continue # Skip folders in upload
                ext = Path(path).suffix.lower()
                mime_type = "text/plain" if ext in TEXT_EXTENSIONS else None
                
                if mime_type:
                    uploaded_file = client.files.upload(file=path, config={"mime_type": mime_type})
                else:
                    uploaded_file = client.files.upload(file=path)
                    
                contents.append(uploaded_file)
    except Exception as e:
        return f"AGENT_ERROR: Gemini Upload Error: {e}"

    # 2. Try the models one by one using the uploaded contents
    last_error = None
    for model_name in MODELS[:_max_model_fallbacks(len(MODELS))]:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=genai_types.GenerateContentConfig(temperature=0.0),
            )

            output = response.text if getattr(response, "text", None) else "Gemini returned no text."
            return output

        except Exception as e:
            last_error = e
            sys.stderr.write(f"\n⚠️ Warning: Model '{model_name}' failed. Error: {e}\n")

    # If all fail
    return f"AGENT_ERROR: Gemini Final Error: All models failed. Last error: {last_error}"

def run_gemini_request_2(
    prompt: str,
    repo_path: str | None = None,
    file_paths: list[str] | None = None,
) -> str:
    api_key = GOOGLE_API_KEY
    if not api_key:
        return "AGENT_ERROR: GOOGLE_API_KEY is missing."

    file_paths = file_paths or []
    allowed_roots = [repo_path] if repo_path else []

    safe_files = []
    for p in file_paths:
        if is_safe_path(p, allowed_roots=allowed_roots):
            safe_files.append(p)
        else:
            sys.stderr.write(f"\n🛑 Security Block in Agent: Access to '{p}' restricted.\n")

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        return f"AGENT_ERROR: Failed to initialize Gemini client: {e}"

    text_extensions = {
        ".py", ".cs", ".rs", ".cpp", ".c", ".h", ".hpp",
        ".ts", ".tsx", ".js", ".jsx", ".html", ".css",
        ".md", ".txt", ".json",
    }

    contents = [prompt]

    try:
        for path in safe_files:
            if os.path.isdir(path):
                continue

            ext = Path(path).suffix.lower()
            mime_type = "text/plain" if ext in text_extensions else None

            if mime_type:
                uploaded = client.files.upload(
                    file=path,
                    config={"mime_type": mime_type},
                )
            else:
                uploaded = client.files.upload(file=path)

            contents.append(uploaded)

    except Exception as e:
        return f"AGENT_ERROR: Gemini Upload Error: {e}"

    last_error = None
    reviewer_models = [
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
    ]

    for model_name in reviewer_models[:_max_model_fallbacks(len(reviewer_models))]:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=genai_types.GenerateContentConfig(temperature=0.0),
            )
            return response.text if getattr(response, "text", None) else "Gemini returned no text."
        except Exception as e:
            last_error = e
            sys.stderr.write(f"\n⚠️ Reviewer model '{model_name}' failed: {e}\n")

    return f"AGENT_ERROR: Gemini reviewer fallback failed. Last error: {last_error}"

def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "No prompt provided"
    file_paths = sys.argv[2:]
    output = run_gemini_request(prompt, file_paths)
    safe_print(output)

if __name__ == "__main__":
    main()