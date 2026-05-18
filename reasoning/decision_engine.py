from typing import Dict, Any

def decide_patch_action(risk_info: Dict[str, Any], issues: list[str]) -> Dict[str, Any]:
    level = risk_info.get("risk_level", "low")

    decision = {
        "action": "auto_patch",
        "confidence": 0.5,
        "reason": [],
    }

    if level == "high":
        decision["action"] = "require_review"
        decision["confidence"] = 0.3
        decision["reason"].append("High impact function")

    elif level == "medium":
        decision["action"] = "safe_patch_with_check"
        decision["confidence"] = 0.6
        decision["reason"].append("Moderate impact")

    else:
        decision["action"] = "auto_patch"
        decision["confidence"] = 0.8
        decision["reason"].append("Low impact")

    if issues:
        decision["confidence"] += 0.2
        decision["reason"].append(f"{len(issues)} state issues detected")
    
    severity = len(issues)
    if severity >= 2:
        decision["action"] = "require_review"
        decision["confidence"] -= 0.2
    

    return decision