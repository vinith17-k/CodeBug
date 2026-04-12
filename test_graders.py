import sys

sys.path.insert(0, "C:/Users/vinit/Projects/CodeBug")

from tasks.easy.grader import grade as grade_easy
from tasks.medium.grader import grade as grade_medium
from tasks.hard.grader import grade as grade_hard
from tasks.extra1.grader import grade as grade_extra1
from tasks.extra2.grader import grade as grade_extra2

# Test with correct actions
correct_easy = {"category": "logic", "severity": 4, "line_hint": 2}
correct_medium = {"category": "logic", "severity": 3, "line_hint": 5}
correct_hard = {"category": "security", "severity": 5, "line_hint": 2}
correct_extra1 = {"category": "security", "severity": 5, "line_hint": 1}
correct_extra2 = {"category": "logic", "severity": 3, "line_hint": 2}

# Test with wrong actions
wrong_action = {"category": "approve", "severity": 1, "line_hint": None}

print("Testing graders:")
scores = {
    "easy": grade_easy(correct_easy),
    "medium": grade_medium(correct_medium),
    "hard": grade_hard(correct_hard),
    "extra1": grade_extra1(correct_extra1),
    "extra2": grade_extra2(correct_extra2),
}

for name, score in scores.items():
    print(f"  {name}: {score}")

print("\nWith wrong action:")
wrong_scores = {
    "easy": grade_easy(wrong_action),
    "medium": grade_medium(wrong_action),
    "hard": grade_hard(wrong_action),
    "extra1": grade_extra1(wrong_action),
    "extra2": grade_extra2(wrong_action),
}

for name, score in wrong_scores.items():
    print(f"  {name}: {score}")

# Check for issues
print("\nIssues:")
for name, score in scores.items():
    if score <= 0 or score >= 1:
        print(f"  {name}: OUT OF RANGE ({score})")

for name, score in wrong_scores.items():
    if score <= 0 or score >= 1:
        print(f"  {name}: OUT OF RANGE ({score})")
