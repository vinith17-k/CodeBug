
_SYSTEM_PROMPT = """\
You are an expert security-focused code reviewer.\n\nYour ONLY job is to return a single valid JSON array of bug objects (not markdown, not prose).\n\nJSON array schema (all fields required in each object):\n{\n  "type":      "bug",\n  "category":  "security" | "logic" | "style",\n  "severity":  1-5,\n  "comment":   "<brief description of the issue>",\n  "fix":       "<how to fix it>",\n  "confidence": 0.75-0.99,\n  "line_hint": "<which line has the issue>"\n}\n\nIf the code is clean, return: []\n\n--- FEW-SHOT EXAMPLES ---\n\nExample 1 — SQL injection and hardcoded password:\nCode:\n  def get_user(uid):\n      q = f\"SELECT * FROM users WHERE id={uid}\"\n      cursor.execute(q)\n      password = 'hunter2'\n\nResponse:\n[\n  {\n    "type": "bug",\n    "category": "security",\n    "severity": 5,\n    "comment": "SQL injection: f-string with variable interpolation in SQL query.",\n    "fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (uid,))",\n    "confidence": 0.95,\n    "line_hint": "2"\n  },\n  {\n    "type": "bug",\n    "category": "security",\n    "severity": 5,\n    "comment": "Hardcoded password/credential detected.",\n    "fix": "Use environment variables: os.getenv('DB_PASSWORD')",\n    "confidence": 0.98,\n    "line_hint": "4"\n  }\n]\n\nExample 2 — clean code:\nCode:\n  def add(a: int, b: int) -> int:\n      return a + b\n\nResponse:\n[]\n\nExample 3 — off-by-one and division by zero:\nCode:\n  for i in range(len(items) - 1):\n      process(items[i])\n  x = 1 / 0\n\nResponse:\n[\n  {\n    "type": "bug",\n    "category": "logic",\n    "severity": 3,\n    "comment": "Off-by-one error: range(len(x)-1) skips the last element.",\n    "fix": "Use range(len(arr)) or check bounds: if i+1 < len(arr)",\n    "confidence": 0.85,\n    "line_hint": "1"\n  },\n  {\n    "type": "bug",\n    "category": "logic",\n    "severity": 3,\n    "comment": "Potential division by zero. Check denominator is non-zero.",\n    "fix": "Add check: if denominator != 0: result = numerator / denominator",\n    "confidence": 0.99,\n    "line_hint": "3"\n  }\n]\n\n--- END EXAMPLES ---\n\nALWAYS look for:\nSECURITY (severity 4-5):\n  - SQL built with f-strings / concatenation\n  - Passwords stored/passed without hashing\n  - Hardcoded secrets, API keys, or tokens\nLOGIC (severity 2-4):\n  - range(len(x) - 1) off-by-one\n  - Strict > / < where >= / <= is needed\n  - Division without zero-check\n  - Missing return in all code paths\n\nIMPORTANT: Return ONLY the JSON array, nothing else.\n"""
            "\n"
            "╔══════════════════════════════════════════════════════════╗\n"
            "║  WARNING: No LLM API key found.                          ║\n"
            "║                                                          ║\n"
            "║  Set at least one of:                                    ║\n"
            "║    ANTHROPIC_API_KEY   (preferred — uses Claude Haiku)   ║\n"
            "║    OPENAI_API_KEY      (fallback — uses GPT-4o-mini)     ║\n"
            "║                                                          ║\n"
            "║  The server will start, but ALL reviews will fall back   ║\n"
            "║  to the local mock reviewer.                             ║\n"
            "╚══════════════════════════════════════════════════════════╝\n",
            file=sys.stderr,
        )
        return

    if has_anthropic:
        logger.info("API key found: Anthropic (primary)")
    if has_openai:
        logger.info("API key found: OpenAI (fallback)")


_check_api_keys()

# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert security-focused code reviewer.
Your ONLY job is to return a single valid JSON object — no markdown, no prose.

JSON schema (all fields required):
{
  "type":      "flag" | "approve",
  "category":  "security" | "logic" | "style" | "ok",
  "line_hint": "<brief description of the suspicious line>",
  "comment":   "<clear explanation of the issue, or empty string>",
  "severity":  1-5
}

Rules:
- "type" = "flag"    when a bug or vulnerability is present
- "type" = "approve" when the code is clean  (category = "ok", severity = 0)
- category must match the dominant bug class

--- FEW-SHOT EXAMPLES ---

Example 1 — SQL injection (flag):
Code:
  query = f"SELECT * FROM users WHERE name='{username}'"
  result = db.execute(query)

Response:
{"type":"flag","category":"security","line_hint":"f-string query on line 1","comment":"User input interpolated directly into SQL query — classic SQL injection. Use parameterized queries instead.","severity":5}

Example 2 — clean code (approve):
Code:
  def add(a: int, b: int) -> int:
      return a + b

Response:
{"type":"approve","category":"ok","line_hint":"","comment":"","severity":0}

Example 3 — off-by-one (flag):
Code:
  for i in range(len(items) - 1):
      process(items[i])

Response:
{"type":"flag","category":"logic","line_hint":"range(len(items) - 1) in for loop","comment":"Off-by-one: range(len(x)-1) skips the last element. Use range(len(x)) or enumerate(x) instead.","severity":3}
--- END EXAMPLES ---

ALWAYS look for:
SECURITY (severity 4-5):
  - SQL built with f-strings / concatenation
  - Passwords stored/passed without hashing
  - Hardcoded secrets, API keys, or tokens
LOGIC (severity 2-4):
  - range(len(x) - 1) off-by-one
  - Strict > / < where >= / <= is needed
  - Division without zero-check
  - Missing return in all code paths
"""

_RETRY_SUFFIX = (
    "\n\nYour previous response was not valid JSON. "
    "Return ONLY the JSON object with the exact schema above — "
    "no markdown fences, no extra keys, no prose."
)


def build_user_message(code: str, retry: bool = False) -> str:
    """Return the user-turn content (code only, plus retry note if needed)."""
    msg = f"Review this code:\n\n{code}"
    if retry:
        msg += _RETRY_SUFFIX
    return msg


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def call_llm(prompt: str, *, system: str | None = None) -> str | None:
    """
    Try Anthropic first, then OpenAI.  Returns the raw text response or None.
    Exceptions are always logged — never silently swallowed.
    """
    # --- Anthropic ---
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            kwargs: dict = {
                "model":      ANTHROPIC_MODEL,
                "max_tokens": MAX_TOKENS,
                "messages":   [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system
            message = client.messages.create(**kwargs)
            return message.content[0].text
        except Exception as exc:
            logger.error("Anthropic call failed: %s: %s", type(exc).__name__, exc)

    # --- OpenAI fallback ---
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                max_tokens=MAX_TOKENS,
                messages=messages,
            )
            return response.choices[0].message.content
        except Exception as exc:
            logger.error("OpenAI call failed: %s: %s", type(exc).__name__, exc)

    logger.warning("All LLM providers failed — falling back to mock reviewer.")
    return None


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> dict | None:
    """Try direct parse, then regex-extracted substring."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\})", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# Mock reviewer (last-resort fallback)
# ---------------------------------------------------------------------------


def mock_review(code: str) -> list:
    """
    Rule-based fallback used only when both LLM providers are unavailable.
    Returns a list of bug objects (same schema as LLM output).
    """
    code_lower = code.lower()
    bugs = []

    # SQL injection
    if 'f"select' in code_lower or "f'select" in code_lower:
        bugs.append({
            "type": "bug",
            "category": "security",
            "severity": 5,
            "comment": "SQL injection: f-string with variable interpolation in SQL query.",
            "fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (uid,))",
            "confidence": 0.95,
            "line_hint": "database query line"
        })

    # Hardcoded password
    if "hashed = password" in code_lower or (
        "password" in code_lower and "hash" not in code_lower and "bcrypt" not in code_lower
    ):
        bugs.append({
            "type": "bug",
            "category": "security",
            "severity": 5,
            "comment": "Hardcoded password/credential detected.",
            "fix": "Use environment variables: os.getenv('DB_PASSWORD')",
            "confidence": 0.98,
            "line_hint": "password assignment line"
        })

    # Off-by-one
    if "range(len(" in code_lower and "- 1" in code_lower:
        bugs.append({
            "type": "bug",
            "category": "logic",
            "severity": 3,
            "comment": "Off-by-one error: range(len(x)-1) skips the last element.",
            "fix": "Use range(len(arr)) or check bounds: if i+1 < len(arr)",
            "confidence": 0.85,
            "line_hint": "loop range call"
        })

    # Division by zero
    if "/ 0" in code_lower:
        bugs.append({
            "type": "bug",
            "category": "logic",
            "severity": 3,
            "comment": "Potential division by zero. Check denominator is non-zero.",
            "fix": "Add check: if denominator != 0: result = numerator / denominator",
            "confidence": 0.99,
            "line_hint": "division line"
        })

    # Strict comparison
    if ("> amount" in code_lower or "< amount" in code_lower) and ">=" not in code_lower and "<=" not in code_lower:
        bugs.append({
            "type": "bug",
            "category": "logic",
            "severity": 4,
            "comment": "Strict > / < in balance check; may miss the equality edge case.",
            "fix": "Use >= or <= to include equality edge case.",
            "confidence": 0.8,
            "line_hint": "comparison check"
        })

    return bugs


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

_REQUIRED_KEYS = {"type", "category", "line_hint", "comment", "severity"}
_DEFAULTS = {"type": "approve", "category": "ok", "line_hint": "", "comment": "", "severity": 0}


def review(code: str) -> list:
    """
    Review a code snippet.

    Flow:
      1. Call LLM with system prompt + user message.
      2. If JSON is malformed, retry once with an explicit correction hint.
      3. If both attempts fail, fall back to the rule-based mock reviewer.
      4. Fill any missing keys in each bug with safe defaults.
    Returns a list of bug objects (empty if code is clean).
    """
    user_msg = build_user_message(code)
    raw = call_llm(user_msg, system=_SYSTEM_PROMPT)
    result = _parse_json(raw)

    if result is None or not isinstance(result, list):
        # One retry: tell the model its output was invalid
        logger.warning("LLM returned malformed JSON or not a list — retrying with correction hint.")
        user_msg_retry = build_user_message(code, retry=True)
        raw_retry = call_llm(user_msg_retry, system=_SYSTEM_PROMPT)
        result = _parse_json(raw_retry)

    if result is None or not isinstance(result, list):
        logger.warning("Retry also failed — using mock reviewer.")
        result = mock_review(code)

    # Fill missing keys in each bug with safe defaults
    for bug in result:
        for key, val in _DEFAULTS.items():
            bug.setdefault(key, val)

    return result


# ---------------------------------------------------------------------------
# Test block (run with: python agent.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _TESTS = [
        ("SQL injection", "def login(u, p, db):\n    q = f\"SELECT * FROM users WHERE username='{u}'\"\n    return db.execute(q)"),
        ("Off-by-one",    "def find_max(nums):\n    mx = nums[0]\n    for i in range(len(nums) - 1):\n        if nums[i] > mx: mx = nums[i]\n    return mx"),
        ("Plain password", "def save(u, pw, db):\n    db.insert('users', {'username': u, 'password': pw})"),
        ("Clean code",    "def add(a: int, b: int) -> int:\n    return a + b"),
    ]

    print("=== Agent Tests ===\n")
    for name, code in _TESTS:
        print(f"[{name}]")
        result = review(code)
        print(json.dumps(result, indent=2))
        print()
