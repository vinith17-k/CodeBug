"""
grader.py — Reward function for the CodeBug RL loop.

Key improvements over v1:
  - Clean-code correctly approved → small positive reward (+5)   ← NEW
  - Right decision but wrong category → partial credit (+5)      ← NEW
  - All reward values imported from config.py
  - Type annotations on public functions
"""

from __future__ import annotations

from config import (
    PENALTY_MISS_CRITICAL,
    PENALTY_MISS_HIGH,
    PENALTY_MISS_LOW,
    PENALTY_MISS_MEDIUM,
    PENALTY_UNKNOWN_ACTION,
    PENALTY_WRONG_CATEGORY,
    REWARD_CLEAN_APPROVE,
    REWARD_COMMENT_LONG,
    REWARD_COMMENT_SHORT,
    REWARD_LINE_HINT,
    REWARD_LOGIC_CATCH,
    REWARD_OTHER_CATCH,
    REWARD_PARTIAL_CREDIT,
    REWARD_SECURITY_CATCH,
    REWARD_SEVERITY_CLOSE,
    REWARD_SEVERITY_EXACT,
)


# ---------------------------------------------------------------------------
# GradeResult
# ---------------------------------------------------------------------------


class GradeResult:
    def __init__(
        self,
        reward: int,
        breakdown: list[str],
        correct: bool,
        bug_type: str = "unknown",
        bug_severity: int = 0,
    ) -> None:
        self.reward = reward
        self.breakdown = breakdown
        self.correct = correct
        self.bug_type = bug_type
        self.bug_severity = bug_severity

    def summary(self) -> str:
        lines = [
            "GRADE SUMMARY",
            "-" * 25,
            f"Reward:    {self.reward:+d}",
            f"Correct:   {'Yes' if self.correct else 'No'}",
            f"Bug was:   {self.bug_type} (severity {self.bug_severity})",
            "",
            "Breakdown:",
        ]
        for entry in self.breakdown:
            lines.append(f"  {entry}")
        lines.append("-" * 25)
        lines.append(f"Total: {self.reward:+d}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "reward": self.reward,
            "correct": self.correct,
            "bug_type": self.bug_type,
            "bug_severity": self.bug_severity,
            "breakdown": self.breakdown,
        }


# ---------------------------------------------------------------------------
# grade()
# ---------------------------------------------------------------------------


def grade(ai_action: dict, ground_truth: dict | None) -> GradeResult:
    """
    Grade a single AI review against the ground truth.

    ai_action keys  : type, category, line_hint, comment, severity
    ground_truth keys: bug → {type, severity, description, line_hint}
    """
    if ground_truth is None or "bug" not in ground_truth:
        return GradeResult(reward=0, breakdown=["No ground truth available"], correct=False)

    bug = ground_truth["bug"]
    bug_type     = bug.get("type", "none")
    bug_severity = bug.get("severity", 0)
    is_clean     = bug_type in ("none", "ok") or bug_severity == 0

    reward    = 0
    breakdown: list[str] = []
    correct   = False

    ai_type      = ai_action.get("type",      "approve")
    ai_category  = ai_action.get("category",  "ok")
    ai_comment   = ai_action.get("comment",   "")
    ai_severity  = ai_action.get("severity",  3)
    ai_line_hint = ai_action.get("line_hint", "")

    # ------------------------------------------------------------------
    # CASE 1: AI flagged something
    # ------------------------------------------------------------------
    if ai_type == "flag":

        if ai_category == bug_type:
            # ✅ Perfect category match
            correct = True

            if bug_type == "security":
                reward += REWARD_SECURITY_CATCH
                breakdown.append(f"+{REWARD_SECURITY_CATCH}: caught a security vulnerability")
            elif bug_type == "logic":
                reward += REWARD_LOGIC_CATCH
                breakdown.append(f"+{REWARD_LOGIC_CATCH}: caught a logic bug")
            else:
                reward += REWARD_OTHER_CATCH
                breakdown.append(f"+{REWARD_OTHER_CATCH}: caught a style/other issue")

            # Severity accuracy
            sev_diff = abs(ai_severity - bug_severity)
            if sev_diff == 0:
                reward += REWARD_SEVERITY_EXACT
                breakdown.append(f"+{REWARD_SEVERITY_EXACT}: severity rating exact")
            elif sev_diff == 1:
                reward += REWARD_SEVERITY_CLOSE
                breakdown.append(f"+{REWARD_SEVERITY_CLOSE}: severity rating close")
            else:
                breakdown.append("+0: severity rating off")

            # Comment quality
            if len(ai_comment) > 40:
                reward += REWARD_COMMENT_LONG
                breakdown.append(f"+{REWARD_COMMENT_LONG}: detailed comment")
            elif len(ai_comment) > 15:
                reward += REWARD_COMMENT_SHORT
                breakdown.append(f"+{REWARD_COMMENT_SHORT}: brief comment")
            else:
                breakdown.append("+0: comment too short or missing")

            # Line hint
            if len(ai_line_hint) > 5:
                reward += REWARD_LINE_HINT
                breakdown.append(f"+{REWARD_LINE_HINT}: line location specified")
            else:
                breakdown.append("+0: no line location given")

        elif not is_clean:
            # ⚠️  Right decision (it IS a bug), wrong category → partial credit
            reward += REWARD_PARTIAL_CREDIT
            breakdown.append(
                f"+{REWARD_PARTIAL_CREDIT}: partial credit — flagged correctly but "
                f"wrong category ('{ai_category}' vs '{bug_type}')"
            )

        else:
            # ❌ False positive — code was clean
            reward += PENALTY_WRONG_CATEGORY
            breakdown.append(
                f"{PENALTY_WRONG_CATEGORY}: false positive — code was clean, "
                f"flagged as '{ai_category}'"
            )

    # ------------------------------------------------------------------
    # CASE 2: AI approved
    # ------------------------------------------------------------------
    elif ai_type == "approve":

        if is_clean:
            # ✅ Correctly approved clean code — small positive reward
            correct = True
            reward += REWARD_CLEAN_APPROVE
            breakdown.append(f"+{REWARD_CLEAN_APPROVE}: correctly approved clean code")

        else:
            # ❌ Missed a real bug
            if bug_severity >= 5:
                reward += PENALTY_MISS_CRITICAL
                breakdown.append(f"{PENALTY_MISS_CRITICAL}: missed critical severity-5 bug ({bug_type})")
            elif bug_severity >= 4:
                reward += PENALTY_MISS_HIGH
                breakdown.append(f"{PENALTY_MISS_HIGH}: missed high severity-4 bug ({bug_type})")
            elif bug_severity >= 3:
                reward += PENALTY_MISS_MEDIUM
                breakdown.append(f"{PENALTY_MISS_MEDIUM}: missed medium severity-3 bug ({bug_type})")
            else:
                reward += PENALTY_MISS_LOW
                breakdown.append(f"{PENALTY_MISS_LOW}: missed low severity bug ({bug_type})")

    # ------------------------------------------------------------------
    # CASE 3: Unknown action
    # ------------------------------------------------------------------
    else:
        reward += PENALTY_UNKNOWN_ACTION
        breakdown.append(f"{PENALTY_UNKNOWN_ACTION}: unknown action type '{ai_type}'")

    return GradeResult(
        reward=reward,
        breakdown=breakdown,
        correct=correct,
        bug_type=bug_type,
        bug_severity=bug_severity,
    )


# ---------------------------------------------------------------------------
# batch_grade()
# ---------------------------------------------------------------------------


def batch_grade(episodes: list[dict]) -> dict:
    """Summarise grading across multiple episodes."""
    results_list: list[dict] = []
    total_reward    = 0
    correct_count   = 0
    best_score      = -float("inf")
    worst_score     = float("inf")
    caught_security = 0
    caught_logic    = 0
    false_positives = 0
    missed_bugs     = 0
    clean_approved  = 0

    for ep in episodes:
        res = grade(ep["ai_action"], ep["ground_truth"])
        d   = res.to_dict()
        results_list.append(d)

        total_reward += d["reward"]
        if d["correct"]:
            correct_count += 1
            if d["bug_type"] == "security":
                caught_security += 1
            elif d["bug_type"] == "logic":
                caught_logic += 1
            elif d["bug_type"] in ("none", "ok"):
                clean_approved += 1
        else:
            ai_type = ep["ai_action"].get("type")
            if ai_type == "flag":
                false_positives += 1
            elif ai_type == "approve":
                missed_bugs += 1

        if d["reward"] > best_score:
            best_score = d["reward"]
        if d["reward"] < worst_score:
            worst_score = d["reward"]

    count = len(episodes)
    if count == 0:
        return {"error": "no episodes provided"}

    return {
        "results":         results_list,
        "total_reward":    total_reward,
        "average_reward":  total_reward / count,
        "accuracy":        correct_count / count,
        "best_score":      best_score,
        "worst_score":     worst_score,
        "caught_security": caught_security,
        "caught_logic":    caught_logic,
        "clean_approved":  clean_approved,
        "false_positives": false_positives,
        "missed_bugs":     missed_bugs,
    }


# ---------------------------------------------------------------------------
# Test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pprint

    test_cases = [
        # 1. Perfect security catch
        {
            "ai_action":   {"type": "flag", "category": "security",
                            "line_hint": "line 3 query string",
                            "comment": "SQL injection — user input directly in query", "severity": 5},
            "ground_truth": {"bug": {"type": "security", "severity": 5,
                                     "description": "SQL injection", "line_hint": "query line"}},
        },
        # 2. Partial credit (right decision, wrong category)
        {
            "ai_action":   {"type": "flag", "category": "logic",
                            "line_hint": "line 5", "comment": "this looks wrong", "severity": 2},
            "ground_truth": {"bug": {"type": "security", "severity": 5,
                                     "description": "plain text password", "line_hint": "db.insert"}},
        },
        # 3. Missed critical bug
        {
            "ai_action":   {"type": "approve", "category": "ok",
                            "line_hint": "", "comment": "", "severity": 0},
            "ground_truth": {"bug": {"type": "security", "severity": 5,
                                     "description": "SQL injection", "line_hint": "query line"}},
        },
        # 4. Correctly approved clean code  ← NEW
        {
            "ai_action":   {"type": "approve", "category": "ok",
                            "line_hint": "", "comment": "", "severity": 0},
            "ground_truth": {"bug": {"type": "none", "severity": 0,
                                     "description": "clean code", "line_hint": ""}},
        },
    ]

    print("RUNNING GRADER TESTS...\n")
    for i, case in enumerate(test_cases, 1):
        print(f"CASE {i}:")
        result = grade(case["ai_action"], case["ground_truth"])
        print(result.summary())
        print()

    print("BATCH RESULTS:")
    pprint.pprint(batch_grade(test_cases))
