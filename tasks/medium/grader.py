"""
Grader for task_medium_002 — find_max off-by-one bug.
"""

TRUTH = {"category": "logic", "severity": 3, "line_hint": 5}

def _clamp(score: float) -> float:
    return max(0.01, min(0.99, score))

def grade(action: any) -> float:
    reward = 0.0
    
    def get_attr(obj, attr, default=None):
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    cat = str(get_attr(action, "category", "")).strip().lower()
    if cat == TRUTH["category"]:
        reward += 0.5

    try:
        sev = int(get_attr(action, "severity", 0))
        sev_diff = abs(sev - TRUTH["severity"])
    except (ValueError, TypeError):
        sev_diff = 99
    
    if sev_diff == 0:
        reward += 0.3
    elif sev_diff == 1:
        reward += 0.15

    lh = get_attr(action, "line_hint")
    if lh is not None:
        try:
            if int(lh) == TRUTH["line_hint"]:
                reward += 0.2
        except (ValueError, TypeError):
            pass

    return _clamp(reward)
