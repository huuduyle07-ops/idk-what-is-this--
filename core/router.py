from __future__ import annotations
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any
import re
# Add project root to sys.path to allow importing config.py
root_dir = str(Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config import LANGUAGE_MAP, TASK_LABELS, SUPPORTED_EXTENSIONS
import numpy as np

def detect_repo_language(
    repo_path: str,
    *,
    inventory=None,
) -> str:
    from core.repo_librarian import detect_repo_language as _detect

    return _detect(
        repo_path,
        inventory=inventory,
    )

_model = None
_label_embeddings = None


def get_model():
    global _model
    if _model is None:
        # Lazy import: sentence-transformers (and torch) are heavy to import.
        # Keeping this inside the function makes `import main` fast and avoids
        # startup "hangs" when embeddings aren't needed.
        from sentence_transformers import SentenceTransformer  # type: ignore

        model_name = os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        hf_token = os.getenv("HF_TOKEN") or None

        try:
            _model = SentenceTransformer(model_name, token=hf_token)
        except TypeError:
            # Compatibility fallback for older sentence-transformers versions.
            _model = SentenceTransformer(model_name, use_auth_token=hf_token)

    return _model


def get_label_embeddings():
    global _label_embeddings
    if _label_embeddings is None:
        model = get_model()
        _label_embeddings = model.encode(TASK_LABELS)
    return _label_embeddings


def detect_input_mode(user_input: str) -> str:
    text = user_input.lower().strip()

    patch_signals = [
        '"target_snippet"',
        '"patched_snippet"',
        '"target_node_name"',
        '"target_node_kind"',
        '"file"',
        '"relative_path"',
        '"confidence"',
        '"needs_escalation"',
    ]
    if text.startswith("{") and any(sig in text for sig in patch_signals):
        return "patch_request"

    error_log_signals = [
        "traceback (most recent call last)",
        "syntaxerror",
        "typeerror",
        "nameerror",
        "modulenotfounderror",
        "assertionerror",
        "nullreferenceexception",
        "build failed",
        "compilation failed",
        "error cs",
        "failed",
        "exception:",
    ]
    if any(sig in text for sig in error_log_signals):
        return "error_log"

    architecture_signals = [
        "architecture",
        "codebase",
        "system design",
        "workflow",
        "pipeline",
        "orchestrator",
        "multi-file",
        "project structure",
        "repo structure",
        "how should i structure",
    ]
    if any(sig in text for sig in architecture_signals):
        return "architecture"

    code_signals = [
        "def ", "class ", "import ", "fn ", "let ", "const ", "function ",
        "console.log", "println!", "#include", "public class", "using ",
        "<html", "body {", "interface ", "type ", "=>", "monobehaviour",
        "resmut<", "commands", "return ", "if __name__ ==",
        "func ", "package ", "system.out.println", "public static void main",
        "fun ", "suspend fun", "val ", "var ",
    ]
    if any(sig in text for sig in code_signals):
        return "code"

    return "question"


def detect_language(user_input: str, file_path: str | None = None) -> str:
    if file_path:
        ext = Path(file_path).suffix.lower()
        if ext in LANGUAGE_MAP:
            return LANGUAGE_MAP[ext]

    text = user_input.lower()

    if "monobehaviour" in text or "using unityengine" in text or "[serializefield]" in text or "namespace " in text:
        return "csharp"
    if "fn " in text or "println!" in text or "resmut<" in text or "commands" in text or "impl " in text or "trait " in text:
        return "rust"
    if "func " in text or 'import "fmt"' in text or "package main" in text or "fmt.println" in text:
        return "go"
    if "public static void main" in text or "import java." in text or "system.out.println" in text:
        return "java"
    if "fun " in text or "suspend fun" in text or "val " in text and "var " in text:
        return "kotlin"
    if "#include" in text or "std::" in text or "::" in text:
        return "cpp"
    if "interface " in text or "type " in text or ": string" in text or "tsx" in text:
        return "typescript"
    if "function " in text or "console.log" in text or "=>" in text:
        return "javascript"
    if "<html" in text or "<div" in text or "<body" in text:
        return "html"
    if "body {" in text or ".container {" in text or "@media" in text:
        return "css"
    if "def " in text or "import " in text or "elif " in text or "print(" in text:
        return "python"

    # Fallback: check if the user mentioned a file with a known extension
    
    matches = re.findall(r"\b[\w-]+\.([a-z0-9]+)\b", text)
    for ext in matches:
        ext_with_dot = "." + ext
        if ext_with_dot in LANGUAGE_MAP:
            return LANGUAGE_MAP[ext_with_dot]

    return "unknown"

def should_allow_ai_language_guess(language: str) -> str:
    if language == "unknown":
        return """
        Language is unknown.
        First infer likely language from syntax and filenames.
        Do not propose an auto patch unless exact source_snippet is provided.
        """
    else:
        return ""
    

def _cosine_scores(query_embedding: np.ndarray, label_embeddings: np.ndarray) -> np.ndarray:
    return np.dot(label_embeddings, query_embedding) / (
        np.linalg.norm(label_embeddings, axis=1) * np.linalg.norm(query_embedding)
    )


def classify_task(
    prompt: str,
    mode: str = "tutor",
    language: str = "unknown",
    audience: str = "human",
) -> Dict[str, Any]:
    text = prompt.lower()

    intent_hint = None

    if any(x in text for x in ["traceback", "syntaxerror", "assertionerror", "bug", "fix this", "why is this failing"]):
        intent_hint = "bug_fix"
    elif any(x in text for x in ["explain", "what does this do", "how does this work", "why this code"]):
        intent_hint = "code_explanation"
    elif any(x in text for x in ["review", "criticize", "find issues", "code review"]):
        intent_hint = "code_review"
    elif any(x in text for x in ["refactor", "clean up", "improve structure"]):
        intent_hint = "refactor"
    elif any(x in text for x in ["add feature", "implement", "build", "create system"]):
        intent_hint = "feature_add"
    elif any(x in text for x in ["architecture", "planner", "plan", "workflow", "design"]):
        intent_hint = "architecture_planning"
    elif any(x in text for x in ["test", "pytest", "unit test", "validation"]):
        intent_hint = "testing_validation"

    enriched_prompt = (
        f"Audience: {audience}. Mode: {mode}. "
        f"Language: {language}. Content: {prompt}"
    )

    use_embedding_router = os.getenv(
        "ROUTER_USE_EMBEDDINGS",
        "true",
    ).lower() not in {"0", "false", "no"}

    if intent_hint:
       best_match = intent_hint
    elif not use_embedding_router:
        if mode == "reviewer":
            best_match = "code_review"
        elif mode == "planner":
            best_match = "architecture_planning"
        else:
            best_match = "code_explanation"
    else:
        model = get_model()
        task_embeddings = get_label_embeddings()
        prompt_embedding = model.encode([enriched_prompt])[0]
        scores = _cosine_scores(prompt_embedding, task_embeddings)
        best_match = TASK_LABELS[int(np.argmax(scores))]

    complexity = estimate_complexity(prompt, mode=mode, audience=audience)
    if language == "unknown":
        language = detect_language(prompt)
        
    return {
        "intent": best_match,
        "complexity": complexity,
        "audience": audience,
        "mode": mode,
        "language": language,
    }


def estimate_complexity(prompt: str, mode: str = "tutor", audience: str = "human") -> str:
    text = prompt.lower()

    extreme_signals = [
        "architecture",
        "codebase",
        "system design",
        "multi-file",
        "entire project",
        "workflow",
        "agent",
        "orchestrator",
        "engine",
    ]
    complex_signals = [
        "bug",
        "refactor",
        "optimize",
        "review",
        "implement",
        "test",
        "validation",
        "patch",
        "planner",
    ]

    if any(sig in text for sig in extreme_signals):
        return "extreme"

    if any(sig in text for sig in complex_signals):
        return "complex"

    if audience == "agent" and mode in {"reviewer", "planner"}:
        return "complex"

    return "simple"


def should_use_retriever(
    file_path: str | None,
    task_info: Optional[Dict[str, Any]] = None,
) -> bool:
    if not file_path:
        return False

    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return False

    if not task_info:
        return True

    intent = task_info.get("intent", "")
    input_mode = task_info.get("input_mode", "")

    if input_mode in {"error_log", "architecture", "patch_request"}:
        return True

    if intent in {
        "bug_fix",
        "code_explanation",
        "code_review",
        "refactor",
        "feature_add",
        "architecture_planning",
        "testing_validation",
    }:
        return True

    return False


def should_auto_patch(
    mode: str,
    audience: str,
    confidence: float,
    task_info: Optional[Dict[str, Any]] = None,
) -> bool:
    if audience != "agent":
        return False

    if mode != "reviewer":
        return False

    if confidence < 0.7:
        return False

    if task_info and task_info.get("language") == "unknown":
        return False

    if not task_info:
        return True

    intent = task_info.get("intent", "")
    complexity = task_info.get("complexity", "simple")

    if intent in {"architecture_planning", "workflow_orchestration"}:
        return False

    if complexity == "extreme":
        return False

    return True


def route_request(
    user_input: str,
    mode: str,
    audience: str,
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
    input_mode = detect_input_mode(user_input)
    language = detect_language(user_input, file_path)
    task_info = classify_task(
        prompt=user_input,
        mode=mode,
        language=language,
        audience=audience,
    )
    task_info["input_mode"] = input_mode
    task_info["use_retriever"] = should_use_retriever(
        file_path=file_path,
        task_info=task_info,
    )
    return {
        "input_mode": input_mode,
        "language": language,
        "task_info": task_info,
    }
