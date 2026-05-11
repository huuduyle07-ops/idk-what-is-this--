import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Tải biến môi trường từ .env
load_dotenv()

# --- DATABASE CONFIGURATION ---
APP_ENV = os.getenv("APP_ENV", "local").lower()

# Master switch for DB persistence. When false, every database.memory function
# returns a safe default immediately — no connection attempt, no 30s timeout.
DB_ENABLED = os.getenv("DB_ENABLED", "true").lower() not in {"0", "false", "no"}

if APP_ENV == "docker":
    DATABASE_URL = os.getenv("DATABASE_URL_DOCKER")
else:
    DATABASE_URL = os.getenv("DATABASE_URL_LOCAL")

DATABASE_URL = DATABASE_URL or os.getenv("DATABASE_URL")
if DB_ENABLED and not DATABASE_URL:
    print("⚠️  WARNING: DATABASE_URL is not set in .env", file=sys.stderr)

# --- API KEYS ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("⚠️  WARNING: GOOGLE_API_KEY is not set in .env", file=sys.stderr)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    print("⚠️  WARNING: DEEPSEEK_API_KEY is not set in .env", file=sys.stderr)

# --- APP SETTINGS ---
# OUTPUT_FILE is set after BASE_DIR is defined below (anchors log to AI_project root).
PATCH_LOOP_MAX = 2

# --- FILE DISCOVERY ---
SUPPORTED_EXTENSIONS = {
    # text / docs
    ".txt", ".md", ".pdf", ".docx", ".json",
    # python
    ".py",
    # rust
    ".rs",
    # c-family
    ".c", ".h", ".cpp", ".cxx", ".cc", ".hpp", ".hxx",
    # csharp
    ".cs",
    # web (JS/TS + React)
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    # markup / styles
    ".html", ".htm", ".css", ".scss", ".sass",
    # go
    ".go",
    # java / kotlin
    ".java", ".kt", ".kts",
}

FOLDER_BLACKLIST = {
    ".git", "node_modules", "venv", "__pycache__", ".vscode",
    "dist", "build", ".gemini", ".idea", ".vs", "env",".claude","storage",".claude"
}

# --- LANGUAGES ---
LANGUAGE_MAP = {
    # python
    ".py": "python",
    # rust
    ".rs": "rust",
    # csharp
    ".cs": "csharp",
    # c-family
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    # web (JS/TS + React)
    ".js": "javascript",
    ".jsx": "javascript",   # React JSX
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",   # React TSX
    # markup / styles
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".sass": "css",
    # go
    ".go": "go",
    # java / kotlin
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    # docs / data
    ".pdf": "document",
    ".docx": "document",
    ".txt": "text",
    ".md": "text",
    ".json": "json",
}

# Mapping for Tree-sitter language names
TREESITTER_LANG_MAP = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "c": "c",
    "cpp": "cpp",
    "csharp": "csharp",
    "rust": "rust",
    "html": "html",
    "css": "css",
    "go": "go",
    "java": "java",
    "kotlin": "kotlin",
}

# --- AI MODELS ---
MODELS = [
    "gemini-3.1-flash-lite-preview", 
    "gemini-3-flash-preview",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
]
# Ollama models tried in order for the "DeepSeek" review role.
# Strategy: cloud-first when subscription/quota is available; local model as
# the always-works fallback when cloud is unavailable, rate-limited, or quota
# is exhausted.
DEEPSEEK_MODELS = ["deepseek-r1:1.5b"]          # fallback: tiny local model, runs offline

# Đảm bảo encoding luôn là utf-8 để tránh lỗi charmap trên Windows
os.environ["PYTHONIOENCODING"] = "utf-8"

# --- CORE DIRECTORY (Dành cho các xử lý file) ---
BASE_DIR = Path(__file__).parent
STORAGE_PATH = BASE_DIR / "storage"
STORAGE_PATH.mkdir(exist_ok=True)

# Centralized .agent dir (project map, Obsidian graph, etc.) lives in AI_project root,
# namespaced per analyzed repo so multiple targets don't overwrite each other.
AGENT_DIR = BASE_DIR / ".agent"
AGENT_DIR.mkdir(exist_ok=True)

# Session log lives inside .agent so it's always at the project root,
# no matter which directory the user launches main.py from.
OUTPUT_FILE = AGENT_DIR / "session_log.txt"


def get_agent_dir(repo_path: str | None = None) -> Path:
    """Return the .agent directory for a given analyzed repo.

    Subfolder name is the canonical project_tag, so DB and disk share the same key:
        AI_project/.agent/<project_tag>/

    Two repos that share a folder name still get distinct subfolders thanks to
    the fingerprint suffix in project_tag.
    """
    if not repo_path:
        return AGENT_DIR
    repo_abs = Path(repo_path).resolve()
    if repo_abs == BASE_DIR.resolve():
        return AGENT_DIR

    # Lazy import to avoid a circular dependency at module load time.
    from core.project_tag import build_project_tag
    tag = build_project_tag(str(repo_abs))

    sub = AGENT_DIR / tag
    sub.mkdir(parents=True, exist_ok=True)
    return sub

# --- TEACHING RULES (Phần "nặng" nhất được tách từ main.py) ---
TEACHING_RULES = """
You are an expert coding mentor for:
- game development (Unity, Bevy, ECS)
- web development (TS, JS, HTML/CSS)
- engine/tooling discussions (C++, Rust, C#)
- agentic workflows

Rules:
1. Teach step by step.
2. Do not give the full solution immediately.
3. Start with one useful hint and ask one guiding question.
4. Explain tradeoffs clearly (performance vs readability).
5. If the student is close, confirm and nudge.
6. If the student is wrong, explain the mistake simply.

Response Style:
- Professional yet encouraging.
- Use code blocks for snippets.
- Keep explanations concise.
"""

# --- ROUTER SETTINGS ---
TASK_TYPES = [
    "code debugging",
    "code explanation",
    "code review",
    "refactoring",
    "algorithm help",
    "game programming architecture",
    "web development guidance",
    "engine/tooling discussion",
    "concept explanation"
]

TASK_LABELS = [
    "bug_fix",
    "code_explanation",
    "code_review",
    "refactor",
    "feature_add",
    "architecture_planning",
    "algorithm_help",
    "testing_validation",
    "debug_error_log",
    "workflow_orchestration",
]

# Standard coding tasks (3-step pipeline)
COMPLEX_TASKS = {
    "code debugging", 
    "code review", 
    "refactoring", 
    "algorithm help"
}

# Very difficult architecture/planning tasks (Multi-round debate loop)
EXTREME_TASKS = {
    "strict code review", 
    "implementation planning",
    "game programming architecture"
}

DEBATE_LOOPS = 2 # Số vòng lặp review/refine cho các task cực khó

WELCOME = """
🤖 AI Coding Mentor is starting...

Interfaces & their modes:
- human  → tutor      : teach the user step by step
         → explainer  : explain code/design in simpler terms
- agent  → reviewer   : review code or design critically
         → planner    : suggest next steps for an agent/workflow

Type 'exit' anytime to quit.
"""

# --- SCRIPT PATHS ---
# Legacy paths removed for Phase 2 direct integration.

# --- DEV TOOL MODE (Reviewer/Explainer strict rules) ---
DEV_TOOL_MODE_BLOCK = """
You are acting as a precise code analysis tool, not a tutor.

Rules:
- Do NOT ask questions.
- Do NOT give hints or guiding questions.
- Do NOT use teaching tone.

You MUST:
1. Explicitly state which file contains the bug.
2. Quote the exact line or snippet causing the issue.
3. Briefly explain why it is wrong (1–2 sentences max).
4. Suggest a direct fix.
5. Estimate your confidence from 0.0 to 1.0.
6. Set needs_escalation=true if you are uncertain, the task is multi-file/architectural, or the fix may be risky.

Return your answer in the following JSON format:

{
  "file": "<filename>",
  "relative_path": "<relative path if known>",
  "target_node_name": "<name of function/class to replace>",
  "target_node_kind": "function | class",
  "target_snippet": "<matching code snippet for fallback>",
  "patched_snippet": "<new code snippet>",
  "issue": "<short explanation>",
  "patch_reasoning": {
    "state_issue": "...",
    "root_cause": "...",
    "why_patch_is_safe": "..."
  },
  "risk": "<low|medium|high>",
  "confidence": 0.0,
  "needs_escalation": false
}

Only output JSON.
"""

AUTO_PATCH_ENABLED = True
ROLLBACK_ON_VALIDATION_FAIL = True
CONTROL_TIME_BUDGET_SEC = 180
MAX_REVIEW_AGENTS = 2

# --- OLLAMA / LOCAL CRITIC ---
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "false").lower() not in {"0", "false", "no"}
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LOCAL_REVIEWER_MODEL = os.getenv("LOCAL_REVIEWER_MODEL", "deepseek-r1:1.5b")
SHOW_LOCAL_THOUGHT = os.getenv("SHOW_LOCAL_THOUGHT", "false").lower() not in {"0", "false", "no"}