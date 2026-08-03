import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from core.source_file_policy import SUPPORTED_EXTENSIONS

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
    # mojo
    ".mojo": "mojo",
    # lua
    ".lua": "lua",
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
    "gemini-3.1-flash-lite", 
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

    Subfolder identity is path-derived and content-independent:
        AI_project/.agent/<repository_storage_key>/

    This helper resolves one path and creates one directory. It never walks the
    analyzed repository. Human project labels do not choose artifact storage.
    """
    if not repo_path:
        return AGENT_DIR
    repo_abs = Path(repo_path).resolve()
    if repo_abs == BASE_DIR.resolve():
        return AGENT_DIR

    # Lazy import keeps configuration loading lightweight.
    from core.repository_identity import build_repository_storage_key
    storage_key = build_repository_storage_key(repo_abs)

    sub = AGENT_DIR / storage_key
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

AUTO_PATCH_ENABLED = os.getenv("AUTO_PATCH_ENABLED", "true").lower() not in {"0", "false", "no"}
ROLLBACK_ON_VALIDATION_FAIL = True

# Phase 6.0: when true, lessons that pass the Context Poisoning Guard
# (promotion == auto_approved) land directly in active/. Default false:
# human must explicitly promote via promote_lesson().
LESSON_AUTO_ACTIVE = os.getenv("LESSON_AUTO_ACTIVE", "false").lower() not in {"0", "false", "no"}

# Phase 6.3: when true, build_control_prompt injects an [ACTIVE LESSONS]
# advisory block from Active_Knowledge lessons (via core.lesson_retrieval).
# Default false: no behavior change until explicitly enabled.
LESSON_RETRIEVAL_ENABLED = os.getenv("LESSON_RETRIEVAL_ENABLED", "false").lower() not in {"0", "false", "no"}
LESSON_RETRIEVAL_LIMIT = int(os.getenv("LESSON_RETRIEVAL_LIMIT", "5"))
LESSON_RETRIEVAL_MAX_CHARS = int(os.getenv("LESSON_RETRIEVAL_MAX_CHARS", "3000"))

# Phase 11.1: reserved placeholder. Anti-lessons are stored as a first-class
# lesson kind but stay INERT — never auto-activated, never merged with normal
# lessons, and never retrieval-eligible. This flag is the (default-off) seam a
# later Phase 11 slice will use to make active anti-lessons retrieval-eligible.
# It is NOT wired into CONTROL prompts, promotion, the UI, or any automation;
# the only thing it gates today is the fail-closed exclusion in
# core.lesson_retrieval.list_active_lessons. Leave it false.
ANTI_LESSONS_ENABLED = os.getenv("ANTI_LESSONS_ENABLED", "false").lower() not in {"0", "false", "no"}

# Phase 11.7c: the FIRST behavior-changing anti-lesson seam. CONTROL anti-lesson
# injection requires a TWO-KEY gate: this server flag must be true AND the
# specific request must explicitly pass anti_lesson_control_requested=True. When
# either key is missing, build_control_prompt output is byte-identical to Phase
# 11.7b. This is a per-run gate only — there is NO global UI toggle and NO saved
# setting. It never promotes/creates anti-lessons and never makes them
# active-retrieval eligible (ANTI_LESSONS_ENABLED above still governs that, and
# stays independent). Default off; benchmark before any default-on consideration.
ANTI_LESSONS_CONTROL_ENABLED = os.getenv("ANTI_LESSONS_CONTROL_ENABLED", "false").lower() not in {"0", "false", "no"}

# Phase 13.11a: wire the Phase 13.9 Memory Temperature tie-breaker into the
# final lesson-candidate ordering boundary (core.lesson_retrieval), behind a
# disabled-by-default flag so live behavior is exactly unchanged. When false
# (default), lesson ordering is an exact pass-through: no tie-break metadata, no
# mutation. When true (controlled local experiments only), near-equal lessons
# may be reordered by thermal band; the original relevance score is preserved,
# cold lessons are never hard-filtered, and frozen/audit-only/blocked lessons are
# never surfaced. The matching harness control stays READ_ONLY_PLANNED — this is
# an env/config reader, not an editable UI toggle.
MEMORY_TEMPERATURE_RETRIEVAL_ENABLED = os.getenv("MEMORY_TEMPERATURE_RETRIEVAL_ENABLED", "false").lower() not in {"0", "false", "no"}
MEMORY_TEMPERATURE_TIEBREAK_ONLY = os.getenv("MEMORY_TEMPERATURE_TIEBREAK_ONLY", "true").lower() not in {"0", "false", "no"}
CONTROL_TIME_BUDGET_SEC = 180
MAX_REVIEW_AGENTS = 2

# --- MUTATION ORACLE (Phase 2 of the ghost+oracle+MCTS stack) ---
# After a patch passes validation, optionally generate small mutants of the
# patched snippet and re-run validation on each. Surviving mutants = the
# validation command is too weak to trust as a green light.
# Off by default: it multiplies validation-command runtime by N+1.
MUTATION_ORACLE_ENABLED = os.getenv("MUTATION_ORACLE_ENABLED", "false").lower() not in {"0", "false", "no"}
MUTATION_ORACLE_MAX_MUTANTS = int(os.getenv("MUTATION_ORACLE_MAX_MUTANTS", "5"))

# --- OLLAMA / LOCAL CRITIC ---
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "false").lower() not in {"0", "false", "no"}
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LOCAL_REVIEWER_MODEL = os.getenv("LOCAL_REVIEWER_MODEL", "deepseek-r1:1.5b")
SHOW_LOCAL_THOUGHT = os.getenv("SHOW_LOCAL_THOUGHT", "false").lower() not in {"0", "false", "no"}
