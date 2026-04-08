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
# Code review tasks (3 difficulty levels: easy → medium → hard)
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
        "truth": {"category": "logic", "severity": 4},
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
        "truth": {"category": "logic", "severity": 3},
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
        "truth": {"category": "security", "severity": 5},
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


def score_action(action: dict, truth: dict) -> float:
    """
    Score the agent's action against ground truth.
    Returns a float in [0.0, 1.0].
    """
    reward = 0.0

    # Category match → 0.5
    if action.get("category", "").lower() == truth["category"]:
        reward += 0.5

    # Severity accuracy → up to 0.3
    sev_diff = abs(int(action.get("severity", 0)) - truth["severity"])
    if sev_diff == 0:
        reward += 0.3
    elif sev_diff == 1:
        reward += 0.15

    # Any non-None line hint when a bug exists → 0.2
    if action.get("line_hint") is not None and truth["category"] != "approve":
        reward += 0.2

    return round(min(reward, 1.0), 4)


def run_inference():
    total_reward = 0.0

    # ── [START] ───────────────────────────────────────────────
    print(f"[START] api_base={API_BASE_URL} model={MODEL_NAME} tasks={len(TASKS)}", flush=True)

    for task in TASKS:
        task_id   = task["id"]
        code      = task["code"]
        difficulty = task["difficulty"]
        truth     = task["truth"]

        # ── [STEP] send action ─────────────────────────────────
        try:
            action = call_llm(code, difficulty)
        except Exception as exc:
            action = {"category": "approve", "severity": 1, "line_hint": None, "comment": str(exc)}

        reward = score_action(action, truth)
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
