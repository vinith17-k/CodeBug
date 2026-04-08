"""
CodeBug FastAPI server — Official 30-rule bug detection engine.
Rules: R-N1..R-N5 | R-C1..R-C5 | R-D1..R-D5 | R-S1..R-S5 | R-CF1..R-CF5 | R-L1..R-L5
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import os, re, logging, traceback
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

# Create the OpenEnv app
openenv_app = create_fastapi_app(CodeBugEnvironment, CodeReviewAction, CodeReviewObservation)

# Main FastAPI app
app = FastAPI(title="CodeBug API", version="2.0")


# ========================================================================
# POST /api/train
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
        logger.error(f"Training failed: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Training failed: {str(e)}", "details": traceback.format_exc()[:500]}
        )


# ========================================================================
# POST /api/review
# ========================================================================
class ReviewRequest(BaseModel):
    code: str
    language: str
    export_format: str = None

@app.post("/api/review")
async def review_code(request: ReviewRequest):
    """Analyze code and return ALL bug findings with rule IDs and confidence scores."""
    try:
        code = request.code.strip()
        lang = request.language.lower().strip()

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

        logger.info(f"Analyzing {lang} code ({len(code)} chars)...")
        if HAS_LLM:
            results = _analyze_with_llm(code, lang)
        else:
            results = analyze_code_comprehensively(code, lang)

        response = {
            "bugs_found": len(results),
            "bugs": results,
            "primary_bug": results[0] if results else None,
            "analysis_metadata": {
                "language": lang,
                "code_length": len(code),
                "lines_of_code": len(code.split('\n')),
                "rules_engine": "30-rule official spec",
                "average_confidence": round(
                    sum(b.get("confidence", 0.5) for b in results) / max(len(results), 1), 2
                ) if results else 1.0
            }
        }

        if not results:
            response["primary_bug"] = {
                "type": "approve",
                "rule_id": None,
                "category": "style",
                "severity": 1,
                "line_hint": None,
                "comment": "No bugs detected by the 30-rule engine.",
                "fix": "",
                "confidence": 1.0
            }

        logger.info(f"Found {len(results)} bugs in {lang} code")
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Review endpoint failed: {e}\n{error_trace}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Analysis failed: {str(e)}", "details": error_trace[:500]}
        )


# ========================================================================
# LLM wrapper
# ========================================================================
def _analyze_with_llm(code: str, lang: str) -> list:
    if not HAS_LLM:
        return analyze_code_comprehensively(code, lang)
    try:
        bugs = agent_review(code)
        if not isinstance(bugs, list):
            bugs = []
        bugs.sort(key=lambda x: (x.get('severity', 0), x.get('confidence', 0)), reverse=True)
        return bugs
    except Exception as e:
        logger.warning(f"LLM failed ({type(e).__name__}: {e}). Using pattern analysis.")
        return analyze_code_comprehensively(code, lang)


# ========================================================================
# OFFICIAL 30-RULE BUG ENGINE
# Spec: R-N1..R-N5 | R-C1..R-C5 | R-D1..R-D5 | R-S1..R-S5 | R-CF1..R-CF5 | R-L1..R-L5
# ========================================================================

def _fl(code: str, pattern: str, flags: int = re.I) -> int | None:
    """Return 1-indexed line number of first regex match, or None."""
    for i, line in enumerate(code.splitlines(), 1):
        if re.search(pattern, line, flags):
            return i
    return None


def _bug(rule_id: str, category: str, severity: int, line_hint, comment: str, fix: str, confidence: float) -> dict:
    return {
        "type": "bug",
        "rule_id": rule_id,
        "category": category,
        "severity": severity,
        "line_hint": line_hint,
        "comment": comment,
        "fix": fix,
        "confidence": confidence,
    }


def analyze_code_comprehensively(code: str, lang: str) -> list:
    """
    Official 30-rule bug detector. Every matching rule fires independently.
    Multiple bugs can be returned for the same code snippet.
    """
    bugs = []
    IS_JS = lang in ('javascript', 'typescript')
    IS_PY = lang == 'python'

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CATEGORY 1 — API & Network
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # R-N1 · Missing error handling on fetch
    if IS_JS and re.search(r'\bfetch\s*\(', code):
        has_catch  = bool(re.search(r'\.catch\s*\(|try\s*\{', code))
        has_status = bool(re.search(r'\.ok\b|\.status\b', code))
        if not has_catch or not has_status:
            ln = _fl(code, r'\bfetch\s*\(')
            bugs.append(_bug(
                "R-N1", "api_network", 4, ln,
                "R-N1 · Missing error handling on fetch: fetch() does NOT throw on 4xx/5xx. "
                "You must check response.ok and wrap in try/catch.",
                "const res = await fetch(url);\n"
                "if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);\n"
                "const data = await res.json();\n"
                "// Always wrap in: try { ... } catch (err) { console.error(err); }",
                0.88
            ))

    # R-N2 · No timeout defined
    if IS_JS and re.search(r'\bfetch\s*\(', code) \
            and not re.search(r'AbortController|signal|timeout', code):
        ln = _fl(code, r'\bfetch\s*\(')
        bugs.append(_bug(
            "R-N2", "api_network", 3, ln,
            "R-N2 · No timeout defined: fetch() has no built-in timeout. "
            "A hanging request blocks indefinitely and causes silent 500s.",
            "const ctrl = new AbortController();\n"
            "const tid  = setTimeout(() => ctrl.abort(), 5000);\n"
            "try {\n"
            "  const res = await fetch(url, { signal: ctrl.signal });\n"
            "} finally { clearTimeout(tid); }",
            0.85
        ))

    if IS_PY and re.search(r'requests\.(get|post|put|delete|patch)\s*\(', code) \
            and not re.search(r'timeout\s*=', code):
        ln = _fl(code, r'requests\.(get|post|put|delete|patch)\s*\(')
        bugs.append(_bug(
            "R-N2", "api_network", 3, ln,
            "R-N2 · No timeout on requests call: without timeout the request can hang indefinitely.",
            "response = requests.get(url, timeout=10)  # always set timeout",
            0.90
        ))

    # R-N3 · Route not registered
    if IS_PY and re.search(r'@app\.(get|post|put|delete|patch)', code):
        if not re.findall(r'@app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', code):
            ln = _fl(code, r'@app\.')
            bugs.append(_bug(
                "R-N3", "api_network", 4, ln,
                "R-N3 · Route not registered: @app decorator found but route paths appear missing or malformed. "
                "Ensure routes are registered on the exact app instance that uvicorn serves.",
                "@app.post('/api/review')   # route must be on the served app object\n"
                "async def review(body: Body): ...\n"
                "# Run: uvicorn main:app   # 'app' must be the same object",
                0.72
            ))

    # R-N4 · CORS misconfiguration
    if re.search(r'allow_origins\s*=\s*\[.*\*.*\]|Access-Control-Allow-Origin.*\*', code):
        ln = _fl(code, r'allow_origins|Access-Control-Allow-Origin')
        bugs.append(_bug(
            "R-N4", "security", 4, ln,
            "R-N4 · Overly permissive CORS: wildcard origin (*) on authenticated endpoints "
            "is both a security issue and breaks browser credential policies.",
            "app.add_middleware(CORSMiddleware,\n"
            "    allow_origins=['https://yourapp.com'],  # explicit, not ['*']\n"
            "    allow_credentials=True,\n"
            "    allow_methods=['GET', 'POST'])",
            0.95
        ))

    # R-N5 · Auth token not sent
    if IS_JS and re.search(r'\bfetch\s*\(', code) \
            and not re.search(r'Authorization|Bearer|headers.*token', code, re.I):
        ln = _fl(code, r'\bfetch\s*\(')
        bugs.append(_bug(
            "R-N5", "security", 3, ln,
            "R-N5 · Auth token not sent: fetch() call appears to be missing an Authorization header.",
            "fetch(url, {\n"
            "  headers: {\n"
            "    'Authorization': `Bearer ${token}`,\n"
            "    'Content-Type': 'application/json'\n"
            "  }\n"
            "});",
            0.70
        ))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CATEGORY 2 — Runtime Crashes
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # R-C1 · Unhandled exception in route handler
    if IS_PY and re.search(r'@app\.(get|post|put|delete|patch)', code) \
            and not re.search(r'try\s*:', code):
        ln = _fl(code, r'@app\.(get|post|put|delete|patch)')
        bugs.append(_bug(
            "R-C1", "runtime", 4, ln,
            "R-C1 · Unhandled exception in route: route handler has no try/except. "
            "Any uncaught exception returns a raw 500 with traceback exposed to clients.",
            "@app.post('/api/review')\n"
            "async def review(body: ReviewRequest):\n"
            "    try:\n"
            "        return process(body)\n"
            "    except Exception as e:\n"
            "        logger.error('Review failed', exc_info=True)\n"
            "        raise HTTPException(status_code=500, detail='Internal error')",
            0.85
        ))

    # R-C2 · Missing environment variable validation
    if IS_PY and re.search(r'os\.environ\.get\(|os\.getenv\(', code) \
            and not re.search(r'if not .*(key|token|secret|api)|sys\.exit|raise.*environ', code, re.I):
        ln = _fl(code, r'os\.environ\.get|os\.getenv')
        bugs.append(_bug(
            "R-C2", "runtime", 4, ln,
            "R-C2 · Missing env var validation: os.environ.get() returns None silently. "
            "Missing required keys will crash mid-request instead of at startup.",
            "REQUIRED = ['API_KEY', 'DB_URL']\n"
            "for key in REQUIRED:\n"
            "    if not os.environ.get(key):\n"
            "        import sys\n"
            "        sys.exit(f'[FATAL] Missing env var: {key}')",
            0.87
        ))

    # R-C3 · Model/resource not loaded at startup
    if IS_PY and re.search(r'(model|pipeline|tokenizer|engine)\s*=\s*None', code) \
            and not re.search(r'lifespan|on_event|startup|__init__', code, re.I):
        ln = _fl(code, r'(model|pipeline|tokenizer|engine)\s*=\s*None')
        bugs.append(_bug(
            "R-C3", "runtime", 4, ln,
            "R-C3 · Model not loaded at startup: resource initialised as None, likely loaded lazily "
            "inside a route — causes the first request to hang or crash.",
            "from contextlib import asynccontextmanager\n"
            "@asynccontextmanager\n"
            "async def lifespan(app):\n"
            "    app.state.model = load_model()  # load once at startup\n"
            "    yield\n"
            "app = FastAPI(lifespan=lifespan)",
            0.80
        ))

    # R-C4 · NoneType access risk
    if re.search(r'\.get\(|request\.|response\.', code) \
            and re.search(r'(\w+)\.\w+|\w+\[', code) \
            and not re.search(r'is not None|!= None|is None|if \w+', code):
        ln = _fl(code, r'\w+\.\w+')
        if ln:
            bugs.append(_bug(
                "R-C4", "runtime", 4, ln,
                "R-C4 · NoneType access risk: chained attribute or index access on a value that "
                "could be None — the #1 cause of 500 errors.",
                "# Guard before access:\n"
                "if value is not None:\n"
                "    result = value.attribute\n"
                "# JS optional chaining:\n"
                "const name = user?.profile?.name ?? 'default';",
                0.75
            ))

    # R-C5 · Type mismatch (no casting)
    if IS_PY and re.search(r'request\.(json|form|args|query_params)', code) \
            and not re.search(r'int\(|float\(|str\(|BaseModel|pydantic', code):
        ln = _fl(code, r'request\.(json|form|args|query_params)')
        bugs.append(_bug(
            "R-C5", "runtime", 3, ln,
            "R-C5 · Type mismatch: request parameters used without type casting or Pydantic validation. "
            "A string where int is expected causes a silent crash.",
            "class Body(BaseModel):\n"
            "    code: str\n"
            "    severity: int  # auto-cast & validated\n"
            "\n"
            "@app.post('/api/review')\n"
            "async def review(body: Body): ...",
            0.82
        ))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CATEGORY 3 — Data & State
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # R-D1 · DB connection not closed
    if IS_PY and re.search(r'\.(connect|cursor|session|execute)\s*\(', code) \
            and not re.search(r'\bwith\b.*(connect|session)|finally\s*:', code):
        ln = _fl(code, r'\.(connect|cursor|session|execute)\s*\(')
        bugs.append(_bug(
            "R-D1", "data_state", 4, ln,
            "R-D1 · DB connection not closed: connection opened without context manager. "
            "Leaked connections exhaust the pool and cause cascade failures.",
            "with db.connect() as conn:\n"
            "    result = conn.execute(query)\n"
            "# SQLAlchemy:\n"
            "with SessionLocal() as session:\n"
            "    session.add(record)\n"
            "    session.commit()",
            0.88
        ))

    # R-D2 · Race condition on shared state
    if IS_PY and re.search(r'\bglobal\s+\w+', code) \
            and re.search(r'Thread|threading|asyncio|concurrent', code):
        ln = _fl(code, r'\bglobal\s+\w+')
        bugs.append(_bug(
            "R-D2", "data_state", 5, ln,
            "R-D2 · Race condition: global variable mutated in threaded/async context without a lock. "
            "Concurrent writes will corrupt state.",
            "import threading\n"
            "_lock = threading.Lock()\n"
            "_counter = 0\n"
            "\n"
            "def increment():\n"
            "    global _counter\n"
            "    with _lock:\n"
            "        _counter += 1",
            0.90
        ))

    # R-D3 · Stale cache (no TTL)
    if re.search(r'(cache|lru_cache|@cache)', code, re.I) \
            and not re.search(r'ttl|expire|maxsize|timeout|invalidate', code, re.I):
        ln = _fl(code, r'cache|lru_cache')
        if ln:
            bugs.append(_bug(
                "R-D3", "data_state", 3, ln,
                "R-D3 · Stale cache: cache with no TTL, expiry, or invalidation strategy. "
                "A never-expiring cache is a latent data-correctness bug.",
                "import cachetools\n"
                "cache = cachetools.TTLCache(maxsize=256, ttl=300)  # expires after 5 min\n"
                "# Or: @lru_cache(maxsize=256) for size-bounded (but no TTL)",
                0.78
            ))

    # R-D4 · Missing input validation
    if IS_PY and re.search(r'@app\.(post|put|patch)', code) \
            and not re.search(r'BaseModel|HTTPException|raise.*400|raise.*422|validator', code):
        ln = _fl(code, r'@app\.(post|put|patch)')
        bugs.append(_bug(
            "R-D4", "data_state", 4, ln,
            "R-D4 · Missing input validation: POST/PUT route has no Pydantic model or explicit validation. "
            "Invalid input causes 500 instead of 422 with field-level errors.",
            "from pydantic import BaseModel, validator\n"
            "\n"
            "class Body(BaseModel):\n"
            "    code: str\n"
            "    language: str\n"
            "\n"
            "    @validator('code')\n"
            "    def not_empty(cls, v):\n"
            "        if not v.strip(): raise ValueError('code is empty')\n"
            "        return v",
            0.83
        ))

    # R-D5 · Silent data truncation
    if IS_PY and re.search(r'(\.save\(|\.add\(|\.insert\(|db\.execute)', code) \
            and not re.search(r'len\s*\(|max_length|maxlength', code):
        ln = _fl(code, r'\.save\(|\.add\(|db\.execute')
        if ln:
            bugs.append(_bug(
                "R-D5", "data_state", 3, ln,
                "R-D5 · Silent data truncation: data written to DB without length validation. "
                "Values exceeding column limits are silently truncated or cause insertion errors.",
                "MAX_LEN = 255\n"
                "if len(value) > MAX_LEN:\n"
                "    raise HTTPException(400, f'Value too long (max {MAX_LEN})')\n"
                "db.save(value)",
                0.72
            ))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CATEGORY 4 — Security
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # R-S1 · Secrets in source code
    if re.search(
        r'(api_key|apikey|secret|password|passwd|token|auth_token|private_key)\s*[=:]\s*["\'][^"\']{4,}["\']',
        code, re.I
    ):
        ln = _fl(code, r'(api_key|apikey|secret|password|token)\s*[=:]')
        bugs.append(_bug(
            "R-S1", "security", 5, ln,
            "R-S1 · Secrets in source code: API key/token/password hardcoded in source. "
            "This secret is now in version control — rotate it immediately.",
            "import os\n"
            "API_KEY = os.environ.get('API_KEY')\n"
            "if not API_KEY:\n"
            "    raise RuntimeError('API_KEY not set')\n"
            "# Scan history: pip install detect-secrets && detect-secrets scan",
            0.97
        ))

    # R-S2 · SQL / command injection
    if re.search(
        r'(f["\'].*?\{.*?(SELECT|INSERT|DELETE|UPDATE|WHERE)|execute\s*\(\s*f["\']|os\.system\s*\(|shell\s*=\s*True)',
        code, re.I | re.S
    ):
        ln = _fl(code, r'SELECT|INSERT|DELETE|os\.system|shell\s*=\s*True')
        bugs.append(_bug(
            "R-S2", "security", 5, ln,
            "R-S2 · SQL/command injection: user input interpolated into SQL or shell command. "
            "Attackers can execute arbitrary queries or OS commands.",
            "# SQL — parameterized queries:\n"
            "cursor.execute('SELECT * FROM t WHERE id = ?', (uid,))\n"
            "\n"
            "# Shell — list args without shell=True:\n"
            "subprocess.run(['ls', path], shell=False, capture_output=True)",
            0.98
        ))

    # R-S3 · Overly permissive CORS
    if re.search(r'allow_origins\s*=\s*\[.*\*.*\]|Access-Control-Allow-Origin.*\*|cors.*origin.*\*', code, re.I):
        ln = _fl(code, r'allow_origins|Access-Control-Allow-Origin')
        bugs.append(_bug(
            "R-S3", "security", 4, ln,
            "R-S3 · Overly permissive CORS: wildcard origin (*) allows any website to call your API. "
            "Never use * on authenticated endpoints.",
            "app.add_middleware(\n"
            "    CORSMiddleware,\n"
            "    allow_origins=['https://yourapp.com'],  # no wildcard\n"
            "    allow_credentials=True,\n"
            ")",
            0.95
        ))

    # R-S4 · No rate limiting
    if IS_PY and re.search(r'@app\.(post|get)\s*\(', code) \
            and not re.search(r'limiter|rate_limit|RateLimiter|slowapi|Throttle', code, re.I):
        ln = _fl(code, r'@app\.(post|get)\s*\(')
        bugs.append(_bug(
            "R-S4", "security", 3, ln,
            "R-S4 · No rate limiting: public endpoints without throttling can be scraped, abused, or DoS'd.",
            "from slowapi import Limiter\n"
            "from slowapi.util import get_remote_address\n"
            "limiter = Limiter(key_func=get_remote_address)\n"
            "\n"
            "@app.post('/api/review')\n"
            "@limiter.limit('20/minute')\n"
            "async def review(request: Request, body: Body): ...",
            0.80
        ))

    # R-S5 · Exposed stack traces
    if re.search(r'traceback\.format_exc\(\)|format_exception', code) \
            and re.search(r'return.*detail|JSONResponse.*trace', code, re.I):
        ln = _fl(code, r'traceback\.format_exc|format_exception')
        bugs.append(_bug(
            "R-S5", "security", 4, ln,
            "R-S5 · Exposed stack traces: raw traceback returned to HTTP client. "
            "This leaks file paths, library versions, and internal logic.",
            "except Exception as e:\n"
            "    logger.error('Request failed', exc_info=True)  # log internally\n"
            "    raise HTTPException(status_code=500, detail='An error occurred')  # generic to client",
            0.92
        ))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CATEGORY 5 — Config & Deploy
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # R-CF1 · Wrong startup command
    if re.search(r'\bCMD\b|\bENTRYPOINT\b', code):
        cmd = re.search(r'CMD\s+\[?"?([^\]"\n]+)', code)
        if cmd and not any(k in cmd.group(1) for k in ('uvicorn', 'gunicorn', 'app', 'python')):
            ln = _fl(code, r'\bCMD\b|\bENTRYPOINT\b')
            bugs.append(_bug(
                "R-CF1", "config_deploy", 5, ln,
                "R-CF1 · Wrong startup command: CMD/ENTRYPOINT doesn't reference uvicorn/gunicorn. "
                "A typo here causes the container to exit immediately with code 1.",
                'CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]\n'
                "# Verify entry module name: main.py -> main:app",
                0.80
            ))

    # R-CF2 · Port mismatch (HF Spaces expects 7860)
    if re.search(r'port\s*[=:]\s*(?!7860)\d{4,5}|--port\s+(?!7860)\d{4,5}|EXPOSE\s+(?!7860)\d{4,5}', code):
        ln = _fl(code, r'port\s*[=:]|--port\s+|EXPOSE\s+')
        bugs.append(_bug(
            "R-CF2", "config_deploy", 5, ln,
            "R-CF2 · Port mismatch: app binds to a port other than 7860. "
            "Hugging Face Spaces requires port 7860 — all other ports are unreachable.",
            "EXPOSE 7860\n"
            'CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]',
            0.92
        ))

    # R-CF3 · Missing dependency in requirements
    if IS_PY:
        imports = re.findall(r'^(?:import|from)\s+(\w+)', code, re.M)
        stdlib = {
            'os', 'sys', 're', 'json', 'time', 'math', 'io', 'abc', 'copy', 'enum',
            'typing', 'pathlib', 'datetime', 'collections', 'functools', 'itertools',
            'logging', 'threading', 'asyncio', 'contextlib', 'inspect', 'traceback',
            'hashlib', 'hmac', 'base64', 'urllib', 'http', 'socket', 'struct',
            'random', 'string', 'shutil', 'glob', 'tempfile', 'subprocess', 'signal',
        }
        third_party = sorted(set(m for m in imports if m not in stdlib and not m.startswith('_')))
        if third_party:
            bugs.append(_bug(
                "R-CF3", "config_deploy", 3, 1,
                f"R-CF3 · Missing dependency check: third-party imports detected "
                f"({', '.join(third_party)}) — verify all are in requirements.txt / Dockerfile.",
                "pip freeze > requirements.txt\n"
                "# In Dockerfile:\n"
                "COPY requirements.txt .\n"
                "RUN pip install --no-cache-dir -r requirements.txt",
                0.75
            ))

    # R-CF4 · Wrong working directory (relative paths without __file__)
    if IS_PY and re.search(r'open\s*\(\s*["\'](?!/)', code) \
            and not re.search(r'__file__|os\.path\.dirname|pathlib\.Path', code):
        ln = _fl(code, r'open\s*\(\s*["\']')
        bugs.append(_bug(
            "R-CF4", "config_deploy", 4, ln,
            "R-CF4 · Wrong working directory: relative file path without __file__ anchor. "
            "Works locally but breaks in Docker containers where CWD differs.",
            "import os\n"
            "BASE = os.path.dirname(os.path.abspath(__file__))\n"
            "path = os.path.join(BASE, 'templates', 'index.html')\n"
            "with open(path) as f: ...",
            0.88
        ))

    # R-CF5 · Build vs runtime confusion (heavy deps at module level)
    if IS_PY and re.search(r'^import (torch|transformers|tensorflow|keras)', code, re.M):
        ln = _fl(code, r'^import (torch|transformers|tensorflow|keras)')
        if ln:
            bugs.append(_bug(
                "R-CF5", "config_deploy", 3, ln,
                "R-CF5 · Build vs runtime confusion: heavy ML library imported at module level. "
                "If the Docker layer is cached without GPU, the import fails at runtime.",
                "def get_model():\n"
                "    import torch  # lazy import — only when needed\n"
                "    return torch.load('model.pt')",
                0.72
            ))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CATEGORY 6 — Logic & Testing
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # R-L1 · No test for the happy path
    if IS_PY and re.search(r'def \w+\s*\(', code) \
            and not re.search(r'def test_|import pytest|import unittest|assert\b', code):
        bugs.append(_bug(
            "R-L1", "logic_testing", 2, 1,
            "R-L1 · No test for the happy path: no pytest/unittest tests found. "
            "Every endpoint and function needs at least one integration test.",
            "from fastapi.testclient import TestClient\n"
            "client = TestClient(app)\n"
            "\n"
            "def test_review_happy_path():\n"
            "    r = client.post('/api/review', json={'code': 'x=1', 'language': 'python'})\n"
            "    assert r.status_code == 200\n"
            "    assert 'bugs' in r.json()",
            0.75
        ))

    # R-L2 · Edge cases not covered
    if IS_PY and re.search(r'def test_', code) \
            and not re.search(r'empty|null|none|zero|boundary|edge|invalid|negative|max|min', code, re.I):
        ln = _fl(code, r'def test_')
        bugs.append(_bug(
            "R-L2", "logic_testing", 2, ln,
            "R-L2 · Edge cases not covered: tests found but none test empty, null, zero, max, or boundary values.",
            "def test_empty_code_returns_400():\n"
            "    r = client.post('/api/review', json={'code': '', 'language': 'python'})\n"
            "    assert r.status_code == 400\n"
            "\n"
            "def test_oversized_code_returns_400():\n"
            "    r = client.post('/api/review', json={'code': 'x' * 6000, 'language': 'python'})\n"
            "    assert r.status_code == 400",
            0.70
        ))

    # R-L3 · Off-by-one errors
    if re.search(r'range\s*\(\s*len\s*\([^)]+\)\s*-\s*1\s*\)|for.+in.+\[\s*:-1\s*\]', code):
        ln = _fl(code, r'range\s*\(\s*len|:\s*-1\s*\]')
        bugs.append(_bug(
            "R-L3", "logic_testing", 3, ln,
            "R-L3 · Off-by-one error: range(len(x)-1) or x[:-1] skips the last element. "
            "Review every loop bound, slice, and pagination offset.",
            "for i in range(len(numbers)):      # not len(numbers)-1\n"
            "for item in numbers:               # preferred\n"
            "for i, item in enumerate(numbers): # with index\n"
            "x[:]  # full slice",
            0.90
        ))

    # R-L4 · Wrong default values (mutable defaults)
    if IS_PY and re.search(r'def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|set\(\)|list\(\)|dict\(\))', code):
        ln = _fl(code, r'def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|set\(\))')
        bugs.append(_bug(
            "R-L4", "logic_testing", 4, ln,
            "R-L4 · Wrong default value: mutable default ([], {}, set()) is shared across ALL calls. "
            "State from one call leaks into the next — a classic Python bug.",
            "def process(items=None, config=None):\n"
            "    if items is None: items = []\n"
            "    if config is None: config = {}\n"
            "    # Each call now gets a fresh object",
            0.98
        ))

    # R-L5 · Async/await misuse
    if re.search(r'async\s+(def|function)', code) \
            and not re.search(r'\bawait\b', code):
        ln = _fl(code, r'async\s+(def|function)')
        bugs.append(_bug(
            "R-L5", "logic_testing", 4, ln,
            "R-L5 · Async/await misuse: async function with no await returns a coroutine object, not the result. "
            "Enable async linting to catch this automatically.",
            "async def get_data():\n"
            "    result = await fetch_from_db()  # not fetch_from_db()\n"
            "    return result\n"
            "\n"
            "# Enable warnings:\n"
            "# python -W error::RuntimeWarning",
            0.88
        ))

    # Sort by severity DESC, then confidence DESC
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
    except Exception:
        return HTMLResponse("<h1>CodeBug API Running.</h1><p>Visit /docs for API documentation.</p>")


# ========================================================================
# GET /api/health
# ========================================================================
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "version": "2.0",
        "rules_engine": "30-rule official spec",
        "rule_categories": [
            "API & Network (R-N1..R-N5)",
            "Runtime Crashes (R-C1..R-C5)",
            "Data & State (R-D1..R-D5)",
            "Security (R-S1..R-S5)",
            "Config & Deploy (R-CF1..R-CF5)",
            "Logic & Testing (R-L1..R-L5)",
        ],
        "supported_languages": ["python", "javascript", "typescript", "java", "go", "cpp"],
        "llm_active": HAS_LLM,
    }


# ========================================================================
# GET /api/stats
# ========================================================================
@app.get("/api/stats")
async def get_stats():
    return {
        "rules_total": 30,
        "categories": 6,
        "rules_per_category": 5,
        "languages_supported": 6,
        "llm_active": HAS_LLM,
    }


# ========================================================================
# Mount OpenEnv app at /openenv
# ========================================================================
app.mount("/openenv", openenv_app)
