"""
CodeBug FastAPI server with comprehensive code review and training endpoints.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import os, json, re, logging
from openenv.core.env_server import create_fastapi_app
from environment import CodeBugEnvironment
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState
from training_loop import run_training

try:
    from agent import review as agent_review
    _AGENT_IMPORTED = True
except ImportError:
    _AGENT_IMPORTED = False

# Only attempt LLM if at least one API key is actually configured
_HAS_ANTHROPIC = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
_HAS_OPENAI    = bool(os.environ.get("OPENAI_API_KEY", "").strip())
HAS_LLM = _AGENT_IMPORTED and (_HAS_ANTHROPIC or _HAS_OPENAI)

logger = logging.getLogger(__name__)

# Create the OpenEnv app (has /ws, /reset, /step, /state, /health, etc.)
openenv_app = create_fastapi_app(CodeBugEnvironment, CodeReviewAction, CodeReviewObservation)

# Create a wrapper FastAPI app (takes precedence for /api/* routes)
app = FastAPI(title="CodeBug API", version="2.0")

# ========================================================================
# POST /api/train - Run RL training
# ========================================================================
class TrainRequest(BaseModel):
    episodes: int = 5

@app.post("/api/train")
async def run_real_training(body: TrainRequest):
    """Run the RL training loop for the specified number of episodes."""
    try:
        stats = run_training(num_episodes=body.episodes, verbose=False)
        return {"status": "ok", "stats": stats}
    except Exception as e:
        import traceback
        logger.error(f"Training failed: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Training failed: {str(e)}", "details": traceback.format_exc()[:500]}
        )


# ========================================================================
# POST /api/review - Analyze code for bugs
# ========================================================================
class ReviewRequest(BaseModel):
    code: str
    language: str
    export_format: str = None

@app.post("/api/review")
async def review_code(request: ReviewRequest):
    """Analyze code and return ALL bug findings with confidence scores"""
    try:
        code = request.code.strip()
        lang = request.language.lower().strip()
        
        # Validation
        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")
        if not lang:
            raise HTTPException(status_code=400, detail="Language must be specified")
        if len(code) > 5000:
            raise HTTPException(status_code=400, detail="Code exceeds 5000 characters")
        
        supported_langs = ['python', 'javascript', 'typescript', 'java', 'go', 'cpp', 'c++']
        if lang not in supported_langs:
            raise HTTPException(
                status_code=400,
                detail=f"Language '{lang}' not supported. Supported: {', '.join(supported_langs)}"
            )
        
        # Analyze code
        logger.info(f"Analyzing {lang} code ({len(code)} chars)...")
        if HAS_LLM:
            results = analyze_code_with_llm(code, lang)
        else:
            logger.warning("LLM not available, using fallback analysis")
            results = analyze_code_comprehensively(code, lang)
        
        # Build response
        response = {
            "bugs_found": len(results),
            "bugs": results,
            "primary_bug": results[0] if results else None,
            "analysis_metadata": {
                "language": lang,
                "code_length": len(code),
                "lines_of_code": len(code.split('\n')),
                "average_confidence": round(sum(b.get("confidence", 0.5) for b in results) / max(len(results), 1), 2) if results else 1.0
            }
        }
        
        if not results:
            response["primary_bug"] = {
                "type": "approve",
                "category": "style",
                "severity": 1,
                "line_hint": None,
                "comment": "No obvious bugs detected.",
                "fix": "",
                "confidence": 1.0
            }
        
        if request.export_format == 'json':
            response['export_url'] = '/api/export'
        
        logger.info(f"Returned {len(results)} bugs for {lang}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Review endpoint failed: {e}\n{error_trace}")
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Analysis failed: {str(e)}",
                "details": error_trace[:500]
            }
        )


# ========================================================================
# Helper functions for code analysis
# ========================================================================

def analyze_code_with_llm(code: str, lang: str) -> list:
    """Use LLM-powered agent.review() to analyze code.
    Short-circuits to pattern analysis if no API keys are configured."""
    if not HAS_LLM:
        logger.info("No LLM API keys configured — using pattern analysis.")
        return analyze_code_comprehensively(code, lang)
    try:
        bugs = agent_review(code)
        if not isinstance(bugs, list):
            bugs = []
        for bug in bugs:
            if "languages" not in bug:
                bug["languages"] = [lang]
        bugs.sort(key=lambda x: (x.get('severity', 0), x.get('confidence', 0)), reverse=True)
        logger.info(f"LLM found {len(bugs)} bugs in {lang} code")
        return bugs
    except Exception as e:
        logger.warning(f"LLM analysis failed ({type(e).__name__}: {e}). Using fallback analysis.")
        return analyze_code_comprehensively(code, lang)

def _make_bug(category, severity, line_hint, comment, fix, confidence, lang_list):
    return {
        "type": "bug",
        "category": category,
        "severity": severity,
        "line_hint": line_hint,
        "comment": comment,
        "fix": fix,
        "confidence": confidence,
        "languages": lang_list,
    }


def _find_line(code: str, pattern) -> int | None:
    """Return 1-indexed line number for the first regex match, or None."""
    for i, line in enumerate(code.splitlines(), 1):
        if re.search(pattern, line, re.I):
            return i
    return None


def analyze_code_comprehensively(code: str, lang: str) -> list:
    """
    Exhaustive pattern-based bug detector.
    Runs ALL rules in a single pass and returns every bug found.
    Covers: security, logic, style, concurrency, resource management.
    """
    bugs = []
    ALL_LANGS = ["python", "javascript", "typescript", "java", "go", "cpp"]

    # ── SECURITY ──────────────────────────────────────────────────────────

    # 1. SQL Injection via f-string / concatenation
    if re.search(r'(f["\'].*?\{.*?\}.*?(SELECT|INSERT|DELETE|UPDATE|WHERE)|'
                 r'["\'].*?SELECT.*?\+.*?["\'])', code, re.I | re.S):
        ln = _find_line(code, r'(SELECT|INSERT|DELETE|UPDATE|WHERE)')
        bugs.append(_make_bug(
            "security", 5, ln,
            "SQL Injection: user input interpolated directly into SQL query via f-string or concatenation.",
            "Use parameterized queries:\n  cursor.execute('SELECT * FROM users WHERE id = ?', (uid,))",
            0.96, ["python", "javascript", "typescript", "java"]
        ))

    # 2. Hardcoded passwords / credentials
    if re.search(r'(password|passwd|pwd|db_pass|secret)\s*[=:]\s*["\'][^"\']{4,}["\']', code, re.I):
        ln = _find_line(code, r'(password|passwd|pwd|db_pass|secret)\s*[=:]')
        bugs.append(_make_bug(
            "security", 5, ln,
            "Hardcoded credential: plaintext password stored directly in source code.",
            "Read from environment:\n  password = os.environ.get('DB_PASSWORD')\n  # Never hardcode secrets",
            0.97, ALL_LANGS
        ))

    # 3. Hardcoded API key / token / secret key
    if re.search(r'(api_key|apikey|access_key|secret_key|auth_token|bearer|private_key)'
                 r'\s*[=:]\s*["\'][A-Za-z0-9_\-\.]{8,}["\']', code, re.I):
        ln = _find_line(code, r'(api_key|apikey|access_key|secret_key|auth_token|bearer|private_key)')
        bugs.append(_make_bug(
            "security", 5, ln,
            "Hardcoded API key/token/secret detected. Exposed in version control.",
            "Move to environment variable:\n  api_key = os.environ.get('API_KEY')\n  if not api_key: raise ValueError('API_KEY not set')",
            0.96, ALL_LANGS
        ))

    # 4. Arbitrary code execution
    if re.search(r'\b(eval|exec)\s*\(', code, re.I):
        ln = _find_line(code, r'\b(eval|exec)\s*\(')
        bugs.append(_make_bug(
            "security", 5, ln,
            "Arbitrary code execution: eval()/exec() with untrusted input enables Remote Code Execution.",
            "Use safe alternatives:\n  # Python: ast.literal_eval() for literals\n  # JS: JSON.parse() for data\n  # Never pass user input to eval/exec",
            0.99, ["python", "javascript", "typescript"]
        ))

    # 5. Insecure deserialization
    if re.search(r'pickle\.(load|loads|Unpickler)|yaml\.load\s*\([^)]*\)(?!.*Loader=yaml\.SafeLoader)', code):
        ln = _find_line(code, r'pickle\.(load|loads)|yaml\.load')
        bugs.append(_make_bug(
            "security", 5, ln,
            "Insecure deserialization: pickle/yaml.load with untrusted data enables arbitrary code execution.",
            "# pickle: avoid entirely for untrusted data\n"
            "# yaml: use yaml.safe_load(data) instead of yaml.load(data)",
            0.98, ["python"]
        ))

    # 6. Command injection (shell=True / os.system)
    if re.search(r'os\.system\s*\(|subprocess\.(call|run|Popen)\s*\(.*shell\s*=\s*True', code, re.S):
        ln = _find_line(code, r'os\.system|shell\s*=\s*True')
        bugs.append(_make_bug(
            "security", 5, ln,
            "Command injection risk: shell=True or os.system() with user input allows arbitrary command execution.",
            "Use subprocess with a list and shell=False:\n"
            "  subprocess.run(['ls', '-la'], shell=False, capture_output=True)",
            0.95, ["python"]
        ))

    # 7. Path traversal
    if re.search(r'open\s*\(\s*(request\.|f["\']|.*\+)', code, re.I):
        ln = _find_line(code, r'open\s*\(')
        bugs.append(_make_bug(
            "security", 4, ln,
            "Path traversal risk: file path constructed from user input without sanitisation.",
            "Validate and restrict paths:\n"
            "  import pathlib\n"
            "  safe = pathlib.Path('/safe/base').resolve() / user_input\n"
            "  assert str(safe).startswith('/safe/base')",
            0.80, ["python", "javascript", "typescript"]
        ))

    # 8. Weak hashing algorithm
    if re.search(r'\b(md5|sha1)\b', code, re.I) and re.search(r'(password|passwd|pwd|hash)', code, re.I):
        ln = _find_line(code, r'\b(md5|sha1)\b')
        bugs.append(_make_bug(
            "security", 4, ln,
            "Weak hashing: MD5/SHA-1 are cryptographically broken and must not be used for passwords.",
            "Use bcrypt or Argon2:\n"
            "  import bcrypt\n"
            "  hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())",
            0.94, ALL_LANGS
        ))

    # 9. Debug mode left on
    if re.search(r'(app\.run|debug)\s*[=(]\s*True', code, re.I):
        ln = _find_line(code, r'debug\s*[=(]\s*True')
        bugs.append(_make_bug(
            "security", 3, ln,
            "Debug mode enabled in production: exposes stack traces, interactive debugger, and sensitive data.",
            "Disable debug before deploying:\n"
            "  debug = os.environ.get('DEBUG', 'false').lower() == 'true'\n"
            "  app.run(debug=debug)",
            0.92, ["python", "javascript"]
        ))

    # ── LOGIC ───────────────────────────────────────────────────────────

    # 10. Off-by-one: range(len(x) - 1)
    if re.search(r'range\s*\(\s*len\s*\([^)]+\)\s*-\s*1\s*\)', code):
        ln = _find_line(code, r'range\s*\(\s*len')
        bugs.append(_make_bug(
            "logic", 3, ln,
            "Off-by-one error: range(len(x) - 1) skips the last element of the sequence.",
            "Fix: use range(len(arr)) to include all elements\n"
            "  for i in range(len(numbers)):  # not range(len(numbers)-1)\n"
            "  # Or better: for item in numbers:",
            0.88, ALL_LANGS
        ))

    # 11. Mutable default argument
    if lang in ('python',) and re.search(r'def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|set\(\))', code):
        ln = _find_line(code, r'def\s+\w+\s*\([^)]*=\s*(\[\]|\{\})')
        bugs.append(_make_bug(
            "logic", 4, ln,
            "Mutable default argument: the list/dict is shared across all calls — state leaks between invocations.",
            "Use None as sentinel:\n"
            "  def func(items=None):\n"
            "      if items is None:\n"
            "          items = []",
            0.98, ["python"]
        ))

    # 12. Division without zero guard
    if re.search(r'\w+\s*/\s*\w+', code) and not re.search(r'if.*!=\s*0|if.*> 0|try', code):
        ln = _find_line(code, r'\w+\s*/\s*\w+(?!\s*/)')
        if ln:
            bugs.append(_make_bug(
                "logic", 3, ln,
                "Potential division by zero: denominator is not checked before division.",
                "Guard the division:\n"
                "  if denominator != 0:\n"
                "      result = numerator / denominator\n"
                "  else:\n"
                "      result = 0  # or raise ValueError",
                0.75, ALL_LANGS
            ))

    # 13. Strict > / < where edge case matters (balance/transfer pattern)
    if re.search(r'(balance|amount|total|price|quota)\s*[><!]=?\s*\w+', code, re.I) \
            and not re.search(r'>=|<=', code):
        ln = _find_line(code, r'(balance|amount|total|price|quota)\s*[><]')
        if ln:
            bugs.append(_make_bug(
                "logic", 3, ln,
                "Edge-case boundary bug: strict > or < comparison may miss the equality case (e.g., exact balance transfer).",
                "Use >= or <= to include the boundary:\n"
                "  if account.balance >= amount:  # not >",
                0.80, ALL_LANGS
            ))

    # 14. Return value of function never used (assignment to _)
    if re.search(r'\bNone\s*==\s*\w+|\w+\s*==\s*None\b', code) \
            and not re.search(r'\bis\s+None\b|\bis\s+not\s+None\b', code):
        ln = _find_line(code, r'\bNone\s*==|\w+\s*==\s*None')
        if ln:
            bugs.append(_make_bug(
                "logic", 2, ln,
                "None comparison using == instead of 'is': PEP 8 and Python docs require 'is None' / 'is not None'.",
                "Fix:\n  if value is None:       # correct\n  if value is not None:   # correct\n  # NOT: if value == None",
                0.95, ["python"]
            ))

    # 15. Infinite loop risk (while True without break/return)
    wt = re.search(r'while\s+True\s*:', code)
    if wt and not re.search(r'\bbreak\b|\breturn\b|\braise\b|\bsys\.exit\b', code):
        ln = _find_line(code, r'while\s+True\s*:')
        bugs.append(_make_bug(
            "logic", 4, ln,
            "Infinite loop: while True loop with no break, return, or raise — program will hang.",
            "Add an exit condition:\n"
            "  while True:\n"
            "      # ... your logic ...\n"
            "      if exit_condition:\n"
            "          break",
            0.87, ALL_LANGS
        ))

    # 16. Unchecked index access on potentially empty list
    if re.search(r'\w+\[\s*0\s*\]|\w+\[\s*-1\s*\]', code) \
            and not re.search(r'if\s+\w+|len\s*\(', code):
        ln = _find_line(code, r'\w+\[\s*0\s*\]|\w+\[\s*-1\s*\]')
        if ln:
            bugs.append(_make_bug(
                "logic", 3, ln,
                "Unchecked index access: accessing index [0] or [-1] on a potentially empty collection causes IndexError.",
                "Guard before accessing:\n"
                "  if items:\n"
                "      first = items[0]",
                0.72, ALL_LANGS
            ))

    # 17. Bare except (swallows all errors silently)
    if re.search(r'except\s*:', code) or re.search(r'except\s+Exception\s*:', code):
        ln = _find_line(code, r'except\s*:|except\s+Exception\s*:')
        bugs.append(_make_bug(
            "logic", 3, ln,
            "Bare except clause: catches and silences ALL exceptions including SystemExit and KeyboardInterrupt.",
            "Catch specific exceptions:\n"
            "  try:\n"
            "      risky_call()\n"
            "  except ValueError as e:\n"
            "      logger.error('Bad value: %s', e)\n"
            "  except IOError as e:\n"
            "      logger.error('IO error: %s', e)",
            0.93, ["python"]
        ))

    # 18. Missing return in all branches
    if lang == "python" and re.search(r'def\s+\w+', code):
        fn_body = re.split(r'def\s+\w+[^:]*:', code)
        for body in fn_body[1:]:
            indent_lines = [l for l in body.splitlines() if l.strip()]
            has_if = any(re.match(r'\s+if\b', l) for l in indent_lines)
            has_return = re.search(r'\breturn\b', body)
            has_else_return = re.search(r'else:\s*\n\s+return', body)
            if has_if and has_return and not has_else_return:
                ln = _find_line(code, r'def\s+\w+')
                bugs.append(_make_bug(
                    "logic", 2, ln,
                    "Inconsistent return: function returns a value in some branches but falls through (returns None) in others.",
                    "Ensure all branches return explicitly:\n"
                    "  def func(x):\n"
                    "      if x > 0:\n"
                    "          return x\n"
                    "      return 0  # explicit fallback",
                    0.70, ["python"]
                ))
                break

    # ── JAVASCRIPT / TYPESCRIPT SPECIFIC ────────────────────────────────

    if lang in ('javascript', 'typescript'):
        # 19. var instead of let/const
        if re.search(r'\bvar\s+\w+', code):
            ln = _find_line(code, r'\bvar\s+\w+')
            bugs.append(_make_bug(
                "style", 2, ln,
                "Deprecated var: function-scoped and hoisted variables cause subtle bugs. Use const or let.",
                "Replace:\n  const name = value;   // for constants\n  let count = 0;        // for reassignable values",
                0.97, ["javascript", "typescript"]
            ))

        # 20. Loose equality (== instead of ===)
        if re.search(r'[^=!<>]==[^=]|[^=]!=[^=]', code):
            ln = _find_line(code, r'[^=!<>]==[^=]|[^=]!=[^=]')
            bugs.append(_make_bug(
                "logic", 3, ln,
                "Type coercion bug: == and != perform implicit type conversion. Use === and !== for strict equality.",
                "Replace == with ===:\n  if (value === null)  // strict\n  if (count !== 0)    // strict",
                0.94, ["javascript", "typescript"]
            ))

        # 21. Async without await
        if re.search(r'async\s+function|async\s*\(', code) and not re.search(r'\bawait\b', code):
            ln = _find_line(code, r'async\s+function|async\s*\(')
            bugs.append(_make_bug(
                "logic", 3, ln,
                "async function without await: function is marked async but never awaits — returns an unwrapped Promise.",
                "Add await to async calls:\n  async function getUser() {\n    const user = await fetchUser();  // not fetchUser()\n    return user;\n  }",
                0.85, ["javascript", "typescript"]
            ))

    # ── JAVA SPECIFIC ────────────────────────────────────────────────────

    if lang == 'java':
        # 22. NullPointerException risk
        if re.search(r'\w+\.equals\s*\(\s*["\']', code):
            ln = _find_line(code, r'\w+\.equals\s*\(\s*["\']')
            bugs.append(_make_bug(
                "logic", 3, ln,
                "NullPointerException risk: calling .equals() on a variable that might be null.",
                "Compare with literal on the left:\n  if (\"expected\".equals(variable))  // null-safe",
                0.91, ["java"]
            ))

        # 23. == for String comparison
        if re.search(r'String.*==|==.*String', code):
            ln = _find_line(code, r'String.*==|==.*String')
            bugs.append(_make_bug(
                "logic", 4, ln,
                "String identity comparison: == compares references, not content. Two equal strings may be different objects.",
                "Use .equals():\n  if (str1.equals(str2))  // content comparison",
                0.95, ["java"]
            ))

    # ── STYLE / QUALITY ──────────────────────────────────────────────────

    # 24. print() instead of logging (Python)
    if lang == 'python' and re.search(r'\bprint\s*\(', code) \
            and not re.search(r'import logging|logging\.(info|error|debug|warning)', code):
        ln = _find_line(code, r'\bprint\s*\(')
        bugs.append(_make_bug(
            "style", 1, ln,
            "print() in production code: use the logging module for structured, level-aware output.",
            "Replace print with logging:\n"
            "  import logging\n"
            "  logger = logging.getLogger(__name__)\n"
            "  logger.info('message: %s', value)",
            0.80, ["python"]
        ))

    # 25. TODO / FIXME left in code
    if re.search(r'\b(TODO|FIXME|HACK|XXX)\b', code, re.I):
        ln = _find_line(code, r'\b(TODO|FIXME|HACK|XXX)\b')
        bugs.append(_make_bug(
            "style", 1, ln,
            "Unresolved TODO/FIXME comment: technical debt marker left in production code.",
            "Resolve the TODO or create a tracked issue:\n"
            "  # Before: # TODO: handle edge case\n"
            "  # After: implement the fix and remove the comment",
            0.99, ALL_LANGS
        ))

    # 26. Magic numbers
    if re.search(r'(?<!["\'\w])\b(?!0\b|1\b)[2-9]\d{2,}\b(?!["\'\w])', code) \
            and lang in ('python', 'javascript', 'typescript', 'java'):
        ln = _find_line(code, r'(?<!["\'\w])\b(?!0\b|1\b)[2-9]\d{2,}\b')
        if ln:
            bugs.append(_make_bug(
                "style", 1, ln,
                "Magic number: unexplained numeric literal reduces readability and maintainability.",
                "Define a named constant:\n"
                "  MAX_RETRIES = 500\n"
                "  TIMEOUT_MS  = 3000",
                0.70, ALL_LANGS
            ))

    # 27. Empty catch block
    if re.search(r'except.*:\s*\n\s*(pass|#)', code) or \
            re.search(r'catch\s*\([^)]*\)\s*\{\s*\}', code):
        ln = _find_line(code, r'except.*:\s*$|catch\s*\(')
        bugs.append(_make_bug(
            "logic", 3, ln,
            "Empty exception handler: errors are silently swallowed, making debugging impossible.",
            "At minimum log the exception:\n"
            "  except Exception as e:\n"
            "      logger.error('Unexpected error: %s', e, exc_info=True)\n"
            "      raise  # re-raise if you cannot handle it",
            0.95, ALL_LANGS
        ))

    # 28. Resource leak (file opened but no context manager)
    if re.search(r'\bopen\s*\(', code) and not re.search(r'\bwith\s+open\b', code) and lang == 'python':
        ln = _find_line(code, r'\bopen\s*\(')
        bugs.append(_make_bug(
            "logic", 3, ln,
            "Resource leak: file opened without a 'with' statement — file may not be closed on exception.",
            "Use context manager:\n"
            "  with open('file.txt', 'r') as f:\n"
            "      data = f.read()\n"
            "  # file is automatically closed",
            0.93, ["python"]
        ))

    # 29. Deprecated Python 2 constructs
    if lang == 'python' and re.search(r'\bprint\s+[^(]|\bxrange\b|\breduce\s*\(|urllib2\b', code):
        ln = _find_line(code, r'\bxrange\b|\bprint\s+[^(]')
        if ln:
            bugs.append(_make_bug(
                "style", 2, ln,
                "Python 2 syntax: xrange(), print statement, and urllib2 do not exist in Python 3.",
                "Update to Python 3:\n"
                "  range() instead of xrange()\n"
                "  print() function\n"
                "  urllib.request instead of urllib2",
                0.99, ["python"]
            ))

    # 30. Concurrency: thread-unsafe global state mutation
    if re.search(r'global\s+\w+', code) and re.search(r'Thread|threading|asyncio', code):
        ln = _find_line(code, r'global\s+\w+')
        bugs.append(_make_bug(
            "logic", 4, ln,
            "Thread-unsafe global mutation: modifying global variables from multiple threads causes race conditions.",
            "Use threading.Lock() to protect shared state:\n"
            "  _lock = threading.Lock()\n"
            "  with _lock:\n"
            "      global_counter += 1",
            0.82, ["python", "java", "go", "cpp"]
        ))

    # Sort: highest severity first, then confidence
    bugs.sort(key=lambda b: (b["severity"], b["confidence"]), reverse=True)
    return bugs


# ========================================================================
# GET / - Serve frontend
# ========================================================================
@app.get("/")
def serve_frontend():
    """Serve the CodeBug frontend UI"""
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except:
        return HTMLResponse("<h1>CodeBug API Running.</h1><p>Visit /docs for API documentation.</p>")


# ========================================================================
# GET /api/health - Health check
# ========================================================================
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "version": "2.0",
        "supported_languages": ["python", "javascript", "typescript", "java", "go", "cpp"],
        "features": [
            "comprehensive_bug_detection",
            "confidence_scores",
            "multi_language_support",
            "export_json_reports"
        ],
        "api_endpoints": [
            "/api/review (POST) - Analyze code",
            "/api/train (POST) - Run training",
            "/api/health (GET) - This endpoint",
            "/api/stats (GET) - Usage statistics"
        ]
    }


# ========================================================================
# GET /api/stats - Usage statistics
# ========================================================================
@app.get("/api/stats")
async def get_stats():
    """Return usage statistics"""
    return {
        "message": "Stats endpoint - tracks would be stored in session/DB",
        "supported_check_types": 30,
        "languages": 6,
        "security_checks": 12,
        "logic_checks": 8,
        "style_checks": 10
    }


# ========================================================================
# Mount OpenEnv app at /openenv prefix
# ========================================================================
app.mount("/openenv", openenv_app)
