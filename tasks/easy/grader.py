"""
Grader for task_easy_001 — Balance Transfer boundary bug.
"""

TRUTH = {"category": "logic", "severity": 4, "line_hint": 2}

def _clamp(x: float) -> float:
    """Strictly between 0 and 1 exclusive."""
    try:
        val = float(x)
    except (ValueError, TypeError):
        val = 0.5
    return max(0.01, min(0.99, val))

def grade(action: object, **kwargs) -> float:
    reward = 0.0
    
    def get_attr(obj, attr, default=None):
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    # Category match → 0.5
    cat = str(get_attr(action, "category", "")).strip().lower()
    if cat == TRUTH["category"]:
        reward += 0.5

    # Severity accuracy → up to 0.3
    try:
        sev = int(get_attr(action, "severity", 0))
        sev_diff = abs(sev - TRUTH["severity"])
    except (ValueError, TypeError):
        sev_diff = 99
    
    if sev_diff == 0:
        reward += 0.3
    elif sev_diff == 1:
        reward += 0.15

    # Line hint → 0.2
    lh = get_attr(action, "line_hint")
    if lh is not None:
        try:
            if int(lh) == TRUTH["line_hint"]:
                reward += 0.2
        except (ValueError, TypeError):
            pass

    return _clamp(reward)
