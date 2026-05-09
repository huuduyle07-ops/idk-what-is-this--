from typing import List, Dict, Any
import re

def update_symbolic(var, value, state):
    if var in state:
        return f"({state[var]}) -> {value}"
    return value

def extract_used_vars(text: str) -> List[str]:
    # Extract potential variables (words starting with letter)
    words = set(re.findall(r"\b[A-Za-z_]\w*\b", text))
    keywords = {"if", "for", "while", "return", "True", "False", "None", "and", "or", "not", "is", "in"}
    return list(words - keywords)

def extract_assignment(text: str):
    # x = a + b
    m = re.match(r"(\w+)\s*=\s*(.+)", text)
    if not m:
        return None, text

    var = m.group(1)
    value = m.group(2)

    return var, value

def extract_condition(text: str):
    # if x > 5:
    text = text.replace("if", "").replace(":", "").strip()
    return text

def dedupe_states(states):
    seen = set()
    result = []

    for s in states:
        key = tuple(sorted(s["vars"].items()))
        if key not in seen:
            seen.add(key)
            result.append(s)

    return result

def infer_branch_states(cond: str, current_state: dict):
    # 매우 단순한 추론- Very simple reasoning
    return {
        "true_branch": f"{cond} is True",
        "false_branch": f"{cond} is False"
    }

def build_symbol_state_map(symbols: list[dict]) -> dict:
    symbol_map = {}

    for symbol in symbols:
        name = symbol.get("name")
        if not name:
            continue

        trace = build_state_trace(symbol, symbol_map)
        symbol_map[name] = trace

    return symbol_map

def build_state_trace(symbol: dict, symbol_map: dict = None) -> dict:
    if symbol_map is None:
        symbol_map = {}

    flow = symbol.get("execution_flow", [])

    states = [
        {"constraints": [], "vars": {}, "history": []}
    ]
    trace = []

    for step in flow:
        step_type = step.get("type")
        text = step.get("text", "")

        if step_type == "assignment":
            var, value = extract_assignment(text)
            new_states = []

            for st in states:
                new_st = {
                    "constraints": list(st["constraints"]),
                    "vars": dict(st["vars"]),
                    "history": list(st.get("history", [])),
                }

                if var:
                    call, args = extract_call(value)
                    if call and call in symbol_map:
                        return_states = symbol_map[call].get("final_states", [])
                        if return_states:
                            inferred = return_states[0]["vars"]
                            value = f"{call}({args}) -> {inferred}"
                            
                    new_st["vars"][var] = update_symbolic(var, value, new_st["vars"])
                    new_st["history"].append({
                        "action": "assign",
                        "var": var,
                        "value": value,
                        "under": list(new_st["constraints"])
                    })
                    
                    used_vars = extract_used_vars(value)
                    if used_vars:
                        new_st["history"].append({
                            "action": "data_flow",
                            "from": used_vars,
                            "to": var
                        })

                new_states.append(new_st)

            states = dedupe_states(new_states)[:6]

            trace.append({
                "type": "assignment",
                "text": text,
                "states": states,
            })

        elif step_type == "branch":
            cond = extract_condition(text)
            new_states = []

            for st in states:
                true_st = {
                    "constraints": st["constraints"] + [cond],
                    "vars": dict(st["vars"]),
                    "history": list(st.get("history", [])),
                }
                true_st["history"].append({
                    "action": "branch",
                    "condition": cond,
                    "path": "true"
                })

                false_st = {
                    "constraints": st["constraints"] + [f"NOT ({cond})"],
                    "vars": dict(st["vars"]),
                    "history": list(st.get("history", [])),
                }
                false_st["history"].append({
                    "action": "branch",
                    "condition": cond,
                    "path": "false"
                })

                new_states.extend([true_st, false_st])

            states = dedupe_states(new_states)[:6]

            trace.append({
                "type": "branch",
                "condition": cond,
                "states": states,
            })

        elif step_type == "return":
            trace.append({
                "type": "return",
                "value": text,
                "states": states,
            })

    return {
        "symbol": symbol.get("name"),
        "state_trace": trace,
        "final_states": states,
    }

def format_state_trace(st):
    lines = []
    for step in st["state_trace"]:
        if step["type"] == "assignment":
            lines.append(f"ASSIGN → {step['text']}")
            lines.append(f"  states: {step['states']}")

        elif step["type"] == "branch":
            lines.append(f"BRANCH → {step['condition']}")
            for s in step["states"]:
                lines.append(f"  - constraints: {s['constraints']} | vars: {s['vars']}")

        elif step["type"] == "return":
            lines.append(f"RETURN → {step['value']}")
            lines.append(f"  states: {step['states']}")
    return "\n".join(lines)

def detect_overwrite(trace):
    issues = []
    last_assign = {}

    for step in trace:
        text = step.get("text", "")
        if step["type"] == "assignment":
            var, value = extract_assignment(text)
            
            if value:
                used = extract_used_vars(value)
                for u in used:
                    if u in last_assign:
                        del last_assign[u]
            
            if var:
                if var in last_assign:
                    issues.append(f"{var} overwritten before being used")
                last_assign[var] = True
        
        elif step["type"] == "branch":
            cond = step.get("condition", "")
            used = extract_used_vars(cond)
            for u in used:
                if u in last_assign:
                    del last_assign[u]
                    
        elif step["type"] == "return":
            val = step.get("value", "")
            used = extract_used_vars(val)
            for u in used:
                if u in last_assign:
                    del last_assign[u]

    return issues

def detect_useless_branch(trace):
    issues = []

    for step in trace:
        if step["type"] == "branch":
            cond = step.get("condition", "").lower()
            if cond in ("true", "false", "1", "0"):
                issues.append(f"Branch condition is trivially {cond}")

    return issues

def extract_call(text):
    m = re.match(r"(\w+)\((.*)\)", text)
    if m:
        name = m.group(1)
        args = m.group(2)
        return name, args
    return None, None

def detect_return_conflict(trace):
    issues = []

    for step in trace:
        if step["type"] == "return":
            states = step["states"]

            if len(states) < 2:
                continue

            values = [tuple(sorted(s["vars"].items())) for s in states]

            if len(set(values)) > 1:
                explanations = []

                for s in states:
                    explanations.append([
                        h for h in s["history"]
                        if h["action"] in ("branch", "assign")
                    ][-4:])

                issues.append({
                    "type": "return_conflict",
                    "reason": "Return value differs across execution paths",
                    "paths": explanations
                })

    return issues

def explain_root_cause(issue):
    if isinstance(issue, dict):
        return f"{issue['reason']} caused by divergent assignments in branches"
    else:
        return str(issue)

def generate_patch_candidate(issue, symbol):
    if "overwritten" in str(issue):
        return {
            "fix_type": "logic",
            "suggestion": "Avoid overwriting variable before usage"
        }

    if isinstance(issue, dict) and issue.get("type") == "return_conflict":
        return {
            "fix_type": "branch",
            "suggestion": "Ensure both branches produce consistent output"
        }

    return None

def trace_code(code: str, language: str) -> Dict[str, Any]:
    """Analyze raw code for state issues without needing a repo context."""
    from core.treesitter_parse import parse_code_with_treesitter
    parsed = parse_code_with_treesitter(code, language)
    symbols = parsed.get("symbols", [])
    
    symbol_map = build_symbol_state_map(symbols)
    
    all_results = []
    for name, st in symbol_map.items():
        issues = []
        issues += detect_overwrite(st["state_trace"])
        issues += detect_useless_branch(st["state_trace"])
        issues += detect_return_conflict(st["state_trace"])
        
        all_results.append({
            "symbol": name,
            "issues": issues,
            "trace": st
        })
        
    return {
        "symbols_analyzed": list(symbol_map.keys()),
        "results": all_results
    }