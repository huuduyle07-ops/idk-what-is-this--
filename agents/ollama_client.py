import json
import os
import re
from typing import Optional, Dict, Any

import requests


class OllamaClient:
    """
    Client for local Ollama models.

    Intended role:
    - local critic
    - cheap disagreement detector
    - not the final patch writer
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
    ):
        self.base_url = (base_url or os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        self.model = model or os.getenv("LOCAL_REVIEWER_MODEL") or "deepseek-r1:1.5b"
        self.timeout = timeout

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        url = f"{self.base_url}/api/generate"

        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except Exception as e:
            return f"AGENT_ERROR: Ollama request failed: {e}"

    def generate_with_thought(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, str]:
        raw_response = self.generate(prompt, system_prompt)

        if raw_response.startswith("AGENT_ERROR:"):
            return {
                "thought": "",
                "answer": raw_response,
                "raw": raw_response,
            }

        think_match = re.search(r"<think>(.*?)</think>", raw_response, re.DOTALL | re.IGNORECASE)
        thought = think_match.group(1).strip() if think_match else ""

        answer = re.sub(
            r"<think>.*?</think>",
            "",
            raw_response,
            flags=re.DOTALL | re.IGNORECASE,
        ).strip()

        return {
            "thought": thought,
            "answer": answer,
            "raw": raw_response,
        }


def _extract_json_object(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def run_local_critique(prompt: str, model: str = "deepseek-r1:1.5b") -> dict:
    """
    Run local DeepSeek critique.

    Returns a dict:
      {"critic": {...}, "thought": "..."}   on success
      {"error": "..."}                      on failure

    Important:
    - Do NOT pass raw chain-of-thought to Gemini.
    - Thought is returned separately so callers can choose to show or hide it.
    """
    system_prompt = """
You are a local code critic.
Do not write the final patch.
Return ONLY JSON.

Schema:
{
  "verdict": "accept|revise|reject",
  "critic_summary": "short summary",
  "risk_flags": [],
  "must_fix": [],
  "confidence": 0.0
}
"""

    client = OllamaClient(model=model)
    result = client.generate_with_thought(prompt, system_prompt=system_prompt)

    if result["answer"].startswith("AGENT_ERROR:"):
        return {"error": result["answer"]}

    parsed = _extract_json_object(result["answer"])

    if parsed:
        safe = {
            "verdict": parsed.get("verdict", "revise"),
            "critic_summary": parsed.get("critic_summary", ""),
            "risk_flags": parsed.get("risk_flags", []),
            "must_fix": parsed.get("must_fix", []),
            "confidence": parsed.get("confidence", 0.0),
        }
        return {"critic": safe, "thought": result.get("thought", "")}

    # Fallback if the local model ignores JSON instruction.
    fallback = {
        "verdict": "revise",
        "critic_summary": result["answer"][:1000],
        "risk_flags": ["unstructured_local_critique"],
        "must_fix": [],
        "confidence": 0.4,
    }
    return {"critic": fallback, "thought": result.get("thought", "")}