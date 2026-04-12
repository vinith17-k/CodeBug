"""
inference.py — Repo-root inference for hackathon + OpenEnv Task Validation.

Task Validation loads graders from openenv.yaml (tasks.*.grader). Stdout scores MUST come from
those same grade() functions so parsed [STEP] lines match the manifest.

Env: HF_TOKEN or OPENAI_API_KEY (OpenAI-compatible key). Optional: API_BASE_URL, MODEL_NAME.
"""

from __future__ import annotations

import json
import os
import re
import sys

from openai import OpenAI

# Manifest graders (must match openenv.yaml `grader:` entries exactly)
from tasks.easy.grader import grade as grade_task_easy_001
from tasks.extra1.grader import grade as grade_task_extra_004
from tasks.extra2.grader import grade as grade_task_extra_005
from tasks.hard.grader import grade as grade_task_hard_003
from tasks.medium.grader import grade as grade_task_medium_002

# Root rubric (integer → normalized); imported so static checks / RL tooling see grader.py
from grader import grade as root_rubric_grade

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o")

_TASK_GRADERS = {
    "task_easy_001": grade_task_easy_001,
    "task_medium_002": grade_task_medium_002,
    "task_hard_003": grade_task_hard_003,
    "task_extra_004": grade_task_extra_004,
    "task_extra_005": grade_task_extra_005,
}

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
    },
    {
        "task_id": "task_extra_004",
        "difficulty": "hard",
        "code": (
            'API_KEY = "sk-1234567890abcdef"\n'
            "def process_data(data):\n"
            "    return data.upper()"
        ),
    },
    {
        "task_id": "task_extra_005",
        "difficulty": "medium",
        "code": ("def divide(a, b):\n    # Potential bug here\n    return a / b"),
    },
]

# Matches models.CodeReviewAction — same shape YAML task graders expect
SYSTEM_PROMPT = """You are a code reviewer. Reply with ONLY a JSON object (no markdown):
{
  "category": "logic" | "security" | "style" | "approve",
  "severity": <integer 1-5>,
  "line_hint": <integer line number or null if unknown>,
  "comment": "<short string>"
}"""


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


def _coerce_code_review_action(data: dict) -> dict:
    cat = str(data.get("category", "approve")).strip().lower()
    if cat not in ("logic", "security", "style", "approve"):
        cat = "approve"
    try:
        sev = int(data.get("severity", 1))
    except (TypeError, ValueError):
        sev = 1
    sev = max(1, min(5, sev))
    lh = data.get("line_hint")
    if lh is not None and lh != "":
        try:
            lh = int(lh)
        except (TypeError, ValueError):
            lh = None
    else:
        lh = None
    return {
        "category": cat,
        "severity": sev,
        "line_hint": lh,
        "comment": str(data.get("comment", "")).strip(),
    }


def _chat_json(client: OpenAI, user_text: str) -> dict:
    """Prefer json_object mode; retry without it if the deployment rejects it."""
    kwargs = dict(
        model=MODEL_NAME,
        max_tokens=400,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    )
    try:
        response = client.chat.completions.create(
            **kwargs, response_format={"type": "json_object"}
        )
    except Exception:
        response = client.chat.completions.create(**kwargs)
    raw = response.choices[0].message.content
    parsed = _parse_llm_json(raw)
    return _coerce_code_review_action(parsed) if parsed else {}


def run_task(client: OpenAI, task: dict) -> dict:
    user = f"Difficulty: {task['difficulty']}\n\nReview this code:\n\n{task['code']}"
    data = _chat_json(client, user)
    if not data:
        return {
            "category": "approve",
            "severity": 1,
            "line_hint": None,
            "comment": "parse_error",
        }
    return data


def run_inference() -> None:
    llm_key = (
        os.environ.get("HF_TOKEN") or os.environ.get("OPENAI_API_KEY") or ""
    ).strip()
    if not llm_key:
        print(
            "[ERROR] Set HF_TOKEN or OPENAI_API_KEY to your OpenAI-compatible API key.",
            flush=True,
        )
        sys.exit(1)

    client = OpenAI(api_key=llm_key, base_url=API_BASE_URL)

    # Ensure grader.py rubric returns (0,1); does not change [STEP] scores (those use manifest graders).
    _san = root_rubric_grade(
        {
            "type": "approve",
            "category": "ok",
            "line_hint": "",
            "comment": "",
            "severity": 0,
        },
        {"bug": {"type": "none", "severity": 0, "description": "", "line_hint": ""}},
    )
    if not (isinstance(_san.reward, float) and 0.0 < _san.reward < 1.0):
        print(f"[ERROR] grader.py reward out of (0,1): {_san.reward!r}", flush=True)
        sys.exit(1)

    print("[START]", flush=True)
    for task in TASKS:
        tid = task["task_id"]
        try:
            action = run_task(client, task)
        except Exception as exc:
            action = {
                "category": "approve",
                "severity": 1,
                "line_hint": None,
                "comment": str(exc),
            }
        grader = _TASK_GRADERS[tid]
        score = float(grader(action))
        print(f"[STEP] task_id={tid} score={score:.4f}", flush=True)
    print("[END]", flush=True)


if __name__ == "__main__":
    run_inference()
