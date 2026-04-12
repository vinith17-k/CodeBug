"""
inference.py — Hackathon baseline inference (repo root).

Requires env: HF_TOKEN (no default). Optional: API_BASE_URL, MODEL_NAME (OpenAI-compatible defaults).
Uses openai.OpenAI only. Emits exact stdout lines for the evaluator: [START], [STEP] … score=…, [END].
"""

from __future__ import annotations

import json
import os
import re
import sys

from openai import OpenAI

from grader import grade

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.environ.get("HF_TOKEN")

if not HF_TOKEN:
    print("[ERROR] HF_TOKEN environment variable is required but not set.", flush=True)
    sys.exit(1)

client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)

TASKS = [
    {
        "task_id": "task_easy_001",
        "difficulty": "easy",
        "code": (
            "def transfer(from_account, to_account, amount):\n"
            "    if from_account.balance > amount:\n"
            "        from_account.balance -= amount\n"
            "        to_account.balance += amount\n"
            "        return True\n"
            "    return False"
        ),
        "ground_truth": {
            "bug": {
                "type": "logic",
                "severity": 4,
                "description": "Strict > should likely be >= for balance transfer edge case",
                "line_hint": "if balance check",
            }
        },
    },
    {
        "task_id": "task_medium_002",
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
        "ground_truth": {
            "bug": {
                "type": "logic",
                "severity": 3,
                "description": "Off-by-one: range(len(numbers)-1) skips last element",
                "line_hint": "for loop range",
            }
        },
    },
    {
        "task_id": "task_hard_003",
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
        "ground_truth": {
            "bug": {
                "type": "security",
                "severity": 5,
                "description": "SQL injection via f-string query",
                "line_hint": "query construction line",
            }
        },
    },
    {
        "task_id": "task_extra_004",
        "difficulty": "hard",
        "code": (
            "API_KEY = \"sk-1234567890abcdef\"\n"
            "def process_data(data):\n"
            "    return data.upper()"
        ),
        "ground_truth": {
            "bug": {
                "type": "security",
                "severity": 5,
                "description": "Hardcoded API key / secret",
                "line_hint": "API_KEY assignment",
            }
        },
    },
    {
        "task_id": "task_extra_005",
        "difficulty": "medium",
        "code": (
            "def divide(a, b):\n"
            "    # Potential bug here\n"
            "    return a / b"
        ),
        "ground_truth": {
            "bug": {
                "type": "logic",
                "severity": 3,
                "description": "Division without zero check",
                "line_hint": "return division",
            }
        },
    },
]

SYSTEM_PROMPT = """You are a code reviewer. Respond with ONLY a JSON object (no markdown) using this schema:
{
  "type": "flag" or "approve",
  "category": "security" or "logic" or "style" or "ok",
  "line_hint": "<string, line or location description>",
  "comment": "<string explanation>",
  "severity": <integer 1-5>
}
Use type \"flag\" if you report a bug, \"approve\" if the snippet is fine."""


def _parse_llm_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def _coerce_action(data: dict) -> dict:
    """Shape model output for grader.grade(ai_action, ground_truth)."""
    typ = str(data.get("type", "approve")).strip().lower()
    if typ not in ("flag", "approve"):
        typ = "approve"
    cat = str(data.get("category", "ok")).strip().lower()
    if cat not in ("security", "logic", "style", "ok"):
        cat = "ok"
    lh = data.get("line_hint", "")
    if lh is None:
        lh = ""
    lh = str(lh).strip()
    comment = str(data.get("comment", "")).strip()
    try:
        sev = int(data.get("severity", 0))
    except (TypeError, ValueError):
        sev = 0
    return {
        "type": typ,
        "category": cat,
        "line_hint": lh,
        "comment": comment,
        "severity": sev,
    }


def run_task(task: dict) -> dict:
    user = (
        f"Difficulty: {task['difficulty']}\n\n"
        f"Review this code:\n\n{task['code']}"
    )
    response = client.chat.completions.create(
        model=MODEL_NAME,
        max_tokens=300,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    parsed = _parse_llm_json(raw)
    if not parsed:
        return {
            "type": "approve",
            "category": "ok",
            "line_hint": "",
            "comment": "parse_error",
            "severity": 0,
        }
    return _coerce_action(parsed)


def run_inference() -> None:
    print("[START]", flush=True)
    for task in TASKS:
        tid = task["task_id"]
        try:
            action = run_task(task)
        except Exception as exc:
            action = {
                "type": "approve",
                "category": "ok",
                "line_hint": "",
                "comment": str(exc),
                "severity": 0,
            }
        result = grade(action, task["ground_truth"])
        score = result.reward
        print(f"[STEP] task_id={tid} score={score}", flush=True)
    print("[END]", flush=True)


if __name__ == "__main__":
    run_inference()
