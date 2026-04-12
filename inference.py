"""
inference.py — CodeBug baseline inference script.

Strictly follows the Meta PyTorch Hackathon pre-submission checklist:
  - Environment variables: API_BASE_URL, MODEL_NAME, HF_TOKEN
  - Defaults ONLY for API_BASE_URL and MODEL_NAME (not HF_TOKEN)
  - All LLM calls use `from openai import OpenAI` configured via these variables
  - Stdout logs follow the required [START] / [STEP] / [END] format exactly
"""

import os
import json
import sys

from openai import OpenAI
from tasks.easy.grader import grade as grade_task_easy_001
from tasks.medium.grader import grade as grade_task_medium_002
from tasks.hard.grader import grade as grade_task_hard_003
from tasks.extra1.grader import grade as grade_task_extra_004
from tasks.extra2.grader import grade as grade_task_extra_005

# ─────────────────────────────────────────────────────────────
# Environment variables (checklist requirement)
# Defaults ONLY for API_BASE_URL and MODEL_NAME — NOT HF_TOKEN
# ─────────────────────────────────────────────────────────────
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "gpt-4o-mini")
HF_TOKEN     = os.environ.get("HF_TOKEN")     # No default — must be set by user

if not HF_TOKEN:
    print("[ERROR] HF_TOKEN environment variable is required but not set.", flush=True)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# OpenAI client — configured strictly via the env variables
# ─────────────────────────────────────────────────────────────
client = OpenAI(
    api_key=HF_TOKEN,
    base_url=API_BASE_URL,
)

# ─────────────────────────────────────────────────────────────
# Code review tasks (5 tasks)
# ─────────────────────────────────────────────────────────────
TASKS = [
    {
        "id": "task_easy_001",
        "difficulty": "easy",
        "code": (
            "def transfer(from_account, to_account, amount):\n"
            "    if from_account.balance > amount:\n"
            "        from_account.balance -= amount\n"
            "        to_account.balance += amount\n"
            "        return True\n"
            "    return False"
        ),
        "truth": {"category": "logic", "severity": 4, "line_hint": 2},
    },
    {
        "id": "task_medium_002",
        "difficulty": "medium",
        "code": (
            "def find_max(numbers):\n"
            "    if not numbers:\n"
            "        return None\n"
            "    max_val = numbers[0]\n"
            "    for i in range(len(numbers) - 1):\n"
            "        if numbers[i] > max_val:\n"
            "            max_val = numbers[i]\n"
            "    return max_val"
        ),
        "truth": {"category": "logic", "severity": 3, "line_hint": 5},
    },
    {
        "id": "task_hard_003",
        "difficulty": "hard",
        "code": (
            "def login(username, password):\n"
            "    query = f\"SELECT * FROM users WHERE username = '{username}'"
            " AND password = '{password}'\"\n"
            "    user = db.execute(query)\n"
            "    if user:\n"
            "        return True\n"
            "    return False"
        ),
        "truth": {"category": "security", "severity": 5, "line_hint": 2},
    },
    {
        "id": "task_extra_004",
        "difficulty": "hard",
        "code": (
            "API_KEY = \"sk-1234567890abcdef\"\n"
            "def process_data(data):\n"
            "    return data.upper()"
        ),
        "truth": {"category": "security", "severity": 5, "line_hint": 1},
    },
    {
        "id": "task_extra_005",
        "difficulty": "medium",
        "code": (
            "def divide(a, b):\n"
            "    # Potential bug here\n"
            "    return a / b"
        ),
        "truth": {"category": "logic", "severity": 3, "line_hint": 3},
    },
]

SYSTEM_PROMPT = """\
You are a code review agent. Your task is to identify bugs in code snippets.
Return ONLY a valid JSON object with this exact schema (no markdown, no prose):
{
  "category": "logic" | "security" | "style" | "approve",
  "severity": <integer 1-5>,
  "line_hint": <integer line number or null>,
  "comment": "<short description of the bug>"
}
"""


def call_llm(code: str, difficulty: str) -> dict:
    """Call LLM via OpenAI client and parse the structured JSON response."""
    user_prompt = (
        f"Difficulty level: {difficulty}\n\n"
        f"Review the following code and identify any bugs:\n\n{code}"
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    raw = response.choices[0].message.content
    return json.loads(raw)


# Same callables as openenv.yaml `grader:` entries — validators compare [STEP] rewards to these.
_TASK_GRADERS = {
    "task_easy_001": grade_task_easy_001,
    "task_medium_002": grade_task_medium_002,
    "task_hard_003": grade_task_hard_003,
    "task_extra_004": grade_task_extra_004,
    "task_extra_005": grade_task_extra_005,
}


def grade_action_for_task(task_id: str, action: dict) -> float:
    """Delegate to the YAML-configured grader so stdout matches manifest grading exactly."""
    grader = _TASK_GRADERS[task_id]
    return round(float(grader(action)), 6)


def run_inference():
    total_reward = 0.0

    # ── [START] ───────────────────────────────────────────────
    print(f"[START] api_base={API_BASE_URL} model={MODEL_NAME} tasks={len(TASKS)}", flush=True)

    for task in TASKS:
        task_id   = task["id"]
        code      = task["code"]
        difficulty = task["difficulty"]

        # ── [STEP] send action ─────────────────────────────────
        try:
            action = call_llm(code, difficulty)
        except Exception as exc:
            action = {"category": "approve", "severity": 1, "line_hint": None, "comment": str(exc)}

        reward = grade_action_for_task(task_id, action)
        total_reward += reward

        print(
            f"[STEP] task_id={task_id} difficulty={difficulty} "
            f"category={action.get('category')} severity={action.get('severity')} "
            f"reward={reward:.4f}",
            flush=True,
        )

    # ── [END] ─────────────────────────────────────────────────
    avg_reward = total_reward / len(TASKS)
    print(f"[END] total_reward={total_reward:.4f} avg_reward={avg_reward:.4f}", flush=True)


if __name__ == "__main__":
    run_inference()
