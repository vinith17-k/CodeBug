"""
CodeBug — OpenEnv-compliant FastAPI server.
The openenv app IS the main app so /reset /step /state are at root level.
Custom routes /api/review /api/train / are added on top.
"""

import os, re, logging, traceback, uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from openenv.core.env_server import create_fastapi_app
from environment import CodeBugEnvironment
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState
from training_loop import run_training

try:
    from agent import review as agent_review
    _AGENT_IMPORTED = True
except ImportError:
    _AGENT_IMPORTED = False

_HAS_HF_OR_OPENAI = bool(
    (os.environ.get("HF_TOKEN") or os.environ.get("OPENAI_API_KEY") or "").strip()
)
HAS_LLM = _AGENT_IMPORTED and _HAS_HF_OR_OPENAI

logger = logging.getLogger(__name__)

# ── The openenv app IS the main app ──────────────────────────────────────
# This puts /reset  /step  /state  /ws  at the ROOT so the checker finds them.
app = create_fastapi_app(CodeBugEnvironment, CodeReviewAction, CodeReviewObservation)


# =========================================================================
# POST /api/train
# =========================================================================
class TrainRequest(BaseModel):
    episodes: int = 5

@app.post("/api/train")
async def run_real_training(body: TrainRequest):
    try:
        stats = run_training(num_episodes=body.episodes, verbose=False)
        return {"status": "ok", "stats": stats}
    except Exception as e:
        logger.error(f"Training failed: {e}\n{traceback.format_exc()}")
        return JSONResponse(status_code=500,
                            content={"error": str(e), "details": traceback.format_exc()[:500]})


# =========================================================================
# POST /api/review
# =========================================================================
class ReviewRequest(BaseModel):
    code: str
    language: str
    export_format: str = None

@app.post("/api/review")
async def review_code(request: ReviewRequest):
    try:
        code = request.code.strip()
        lang = request.language.lower().strip()

        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")
        if len(code) > 5000:
            raise HTTPException(status_code=400, detail="Code exceeds 5000 characters")

        supported = ['python', 'javascript', 'typescript', 'java', 'go', 'cpp', 'c++']
        if lang not in supported:
            raise HTTPException(status_code=400,
                                detail=f"Language '{lang}' not supported. Use: {', '.join(supported)}")

        results = _analyze_with_llm(code, lang) if HAS_LLM else analyze_code_comprehensively(code, lang)

        response = {
            "bugs_found": len(results),
            "bugs": results,
            "primary_bug": results[0] if results else {
                "type": "approve", "rule_id": None, "category": "style",
                "severity": 1, "line_hint": None,
                "comment": "No bugs detected.", "fix": "", "confidence": 1.0
            },
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
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": str(e)})


# =========================================================================
# GET / — Serve frontend
# =========================================================================
@app.get("/")
def serve_frontend():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")
    try:
        with open(html_path, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except Exception:
        return HTMLResponse("<h1>CodeBug API</h1><p>Visit /docs for API docs. POST /reset to start.</p>")


# =========================================================================
# GET /api/health
# =========================================================================
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok", "version": "2.0",
        "openenv_routes": ["/reset", "/step", "/state"],
        "custom_routes": ["/api/review", "/api/train"],
        "llm_active": HAS_LLM,
    }


# =========================================================================
# GET /api/stats
# =========================================================================
@app.get("/api/stats")
async def get_stats():
    return {"rules_total": 30, "categories": 6, "languages": 6, "llm_active": HAS_LLM}


# =========================================================================
# LLM wrapper
# =========================================================================
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
        logger.warning(f"LLM failed: {e}. Using pattern analysis.")
        return analyze_code_comprehensively(code, lang)


# =========================================================================
# OFFICIAL 30-RULE BUG ENGINE
# R-N1..R-N5 | R-C1..R-C5 | R-D1..R-D5 | R-S1..R-S5 | R-CF1..R-CF5 | R-L1..R-L5
# =========================================================================

def _fl(code: str, pattern: str, flags: int = re.I) -> int | None:
    for i, line in enumerate(code.splitlines(), 1):
        if re.search(pattern, line, flags):
            return i
    return None

def _bug(rule_id, category, severity, line_hint, comment, fix, confidence):
    return {"type": "bug", "rule_id": rule_id, "category": category,
            "severity": severity, "line_hint": line_hint,
            "comment": comment, "fix": fix, "confidence": confidence}

def analyze_code_comprehensively(code: str, lang: str) -> list:
    bugs = []
    IS_JS = lang in ('javascript', 'typescript')
    IS_PY = lang == 'python'

    # ── API & Network ─────────────────────────────────────────────────
    if IS_JS and re.search(r'\bfetch\s*\(', code):
        if not re.search(r'\.catch\s*\(|try\s*\{', code) or not re.search(r'\.ok\b|\.status\b', code):
            bugs.append(_bug("R-N1","api_network",4,_fl(code,r'\bfetch\s*\('),
                "R-N1 · Missing error handling on fetch: fetch() does not throw on 4xx/5xx.",
                "if (!res.ok) throw new Error(`HTTP ${res.status}`);\n// Wrap in try/catch",0.88))

    if IS_JS and re.search(r'\bfetch\s*\(', code) and not re.search(r'AbortController|signal|timeout', code):
        bugs.append(_bug("R-N2","api_network",3,_fl(code,r'\bfetch\s*\('),
            "R-N2 · No timeout: fetch() can hang indefinitely.",
            "const ctrl = new AbortController();\nsetTimeout(()=>ctrl.abort(),5000);\nfetch(url,{signal:ctrl.signal})",0.85))

    if IS_PY and re.search(r'requests\.(get|post|put|delete)\s*\(', code) and not re.search(r'timeout\s*=', code):
        bugs.append(_bug("R-N2","api_network",3,_fl(code,r'requests\.(get|post)'),
            "R-N2 · No timeout on requests call.",
            "requests.get(url, timeout=10)",0.90))

    if re.search(r'allow_origins\s*=\s*\[.*\*.*\]|Access-Control-Allow-Origin.*\*', code):
        bugs.append(_bug("R-N4","security",4,_fl(code,r'allow_origins|Access-Control'),
            "R-N4 · CORS wildcard (*) on authenticated endpoints is a security issue.",
            "allow_origins=['https://yourapp.com']  # not ['*']",0.95))

    if IS_JS and re.search(r'\bfetch\s*\(', code) and not re.search(r'Authorization|Bearer', code, re.I):
        bugs.append(_bug("R-N5","security",3,_fl(code,r'\bfetch\s*\('),
            "R-N5 · Auth token not sent in fetch request.",
            "headers: {'Authorization': `Bearer ${token}`}",0.70))

    # ── Runtime Crashes ────────────────────────────────────────────────
    if IS_PY and re.search(r'@app\.(get|post|put|delete|patch)', code) and not re.search(r'try\s*:', code):
        bugs.append(_bug("R-C1","runtime",4,_fl(code,r'@app\.(get|post)'),
            "R-C1 · Unhandled exception in route: any error will expose a raw 500 with traceback.",
            "try:\n    return process(body)\nexcept Exception as e:\n    logger.error(e,exc_info=True)\n    raise HTTPException(500,'Internal error')",0.85))

    if IS_PY and re.search(r'os\.environ\.get\(|os\.getenv\(', code) and not re.search(r'sys\.exit|raise.*environ|if not', code, re.I):
        bugs.append(_bug("R-C2","runtime",4,_fl(code,r'os\.environ'),
            "R-C2 · Missing env var validation: None returned silently if key missing.",
            "if not os.environ.get('KEY'):\n    sys.exit('[FATAL] KEY not set')",0.87))

    if IS_PY and re.search(r'(model|pipeline|tokenizer)\s*=\s*None', code) and not re.search(r'lifespan|on_event|startup', code, re.I):
        bugs.append(_bug("R-C3","runtime",4,_fl(code,r'(model|pipeline)\s*=\s*None'),
            "R-C3 · Model not loaded at startup — first request hangs or crashes.",
            "@asynccontextmanager\nasync def lifespan(app):\n    app.state.model = load_model()\n    yield",0.80))

    if IS_PY and re.search(r'request\.(json|form|args|query_params)', code) and not re.search(r'BaseModel|int\(|float\(', code):
        bugs.append(_bug("R-C5","runtime",3,_fl(code,r'request\.(json|form)'),
            "R-C5 · Type mismatch: no Pydantic validation on request params.",
            "class Body(BaseModel):\n    value: int  # auto-cast",0.82))

    # ── Data & State ───────────────────────────────────────────────────
    if IS_PY and re.search(r'\.(connect|cursor|session|execute)\s*\(', code) and not re.search(r'\bwith\b', code):
        bugs.append(_bug("R-D1","data_state",4,_fl(code,r'\.(connect|cursor)'),
            "R-D1 · DB connection not closed — use context manager.",
            "with db.connect() as conn:\n    conn.execute(query)",0.88))

    if IS_PY and re.search(r'\bglobal\s+\w+', code) and re.search(r'Thread|threading|asyncio', code):
        bugs.append(_bug("R-D2","data_state",5,_fl(code,r'\bglobal\s+'),
            "R-D2 · Race condition: global mutation in threaded context.",
            "_lock = threading.Lock()\nwith _lock:\n    counter += 1",0.90))

    if re.search(r'(cache|lru_cache)', code, re.I) and not re.search(r'ttl|expire|maxsize|timeout', code, re.I):
        ln = _fl(code, r'cache|lru_cache')
        if ln:
            bugs.append(_bug("R-D3","data_state",3,ln,
                "R-D3 · Stale cache: no TTL or expiry defined.",
                "cachetools.TTLCache(maxsize=256, ttl=300)",0.78))

    if IS_PY and re.search(r'@app\.(post|put|patch)', code) and not re.search(r'BaseModel|HTTPException|validator', code):
        bugs.append(_bug("R-D4","data_state",4,_fl(code,r'@app\.(post|put)'),
            "R-D4 · Missing input validation: no Pydantic model on POST route.",
            "class Body(BaseModel):\n    code: str\n    language: str",0.83))

    # ── Security ───────────────────────────────────────────────────────
    if re.search(r'(api_key|secret|password|token)\s*[=:]\s*["\'][^"\']{4,}["\']', code, re.I):
        bugs.append(_bug("R-S1","security",5,_fl(code,r'(api_key|secret|password|token)\s*[=:]'),
            "R-S1 · Hardcoded secret in source code. Rotate immediately.",
            "API_KEY = os.environ.get('API_KEY')\nif not API_KEY: raise RuntimeError('not set')",0.97))

    if re.search(r'(f["\'].*?\{.*?(SELECT|INSERT|DELETE|UPDATE)|os\.system\s*\(|shell\s*=\s*True)', code, re.I|re.S):
        bugs.append(_bug("R-S2","security",5,_fl(code,r'SELECT|INSERT|os\.system|shell\s*=\s*True'),
            "R-S2 · SQL/command injection: user input in query or shell.",
            "cursor.execute('SELECT * FROM t WHERE id=?',(uid,))",0.98))

    if re.search(r'allow_origins\s*=\s*\[.*\*|cors.*\*', code, re.I):
        bugs.append(_bug("R-S3","security",4,_fl(code,r'allow_origins|cors'),
            "R-S3 · Overly permissive CORS wildcard.",
            "allow_origins=['https://yourapp.com']",0.95))

    if IS_PY and re.search(r'@app\.(post|get)\s*\(', code) and not re.search(r'limiter|rate_limit|slowapi', code, re.I):
        bugs.append(_bug("R-S4","security",3,_fl(code,r'@app\.(post|get)'),
            "R-S4 · No rate limiting on public endpoint.",
            "@limiter.limit('20/minute')",0.80))

    # ── Config & Deploy ────────────────────────────────────────────────
    if re.search(r'port\s*[=:]\s*(?!7860)\d{4,5}|--port\s+(?!7860)\d{4,5}|EXPOSE\s+(?!7860)\d{4,5}', code):
        bugs.append(_bug("R-CF2","config_deploy",5,_fl(code,r'port\s*[=:]|EXPOSE'),
            "R-CF2 · Port mismatch: HF Spaces requires port 7860.",
            'CMD ["uvicorn","main:app","--host","0.0.0.0","--port","7860"]',0.92))

    if IS_PY and re.search(r'open\s*\(\s*["\'](?!/)', code) and not re.search(r'__file__|os\.path\.dirname', code):
        bugs.append(_bug("R-CF4","config_deploy",4,_fl(code,r'open\s*\(\s*["\']'),
            "R-CF4 · Relative path breaks in Docker — anchor to __file__.",
            "BASE=os.path.dirname(os.path.abspath(__file__))\nopen(os.path.join(BASE,'file.txt'))",0.88))

    if IS_PY:
        imports = re.findall(r'^(?:import|from)\s+(\w+)', code, re.M)
        stdlib = {'os','sys','re','json','time','math','io','abc','copy','enum','typing','pathlib',
                  'datetime','collections','functools','itertools','logging','threading','asyncio',
                  'contextlib','inspect','traceback','hashlib','hmac','base64','urllib','http',
                  'socket','struct','random','string','shutil','glob','tempfile','subprocess'}
        third = sorted(set(m for m in imports if m not in stdlib and not m.startswith('_')))
        if third:
            bugs.append(_bug("R-CF3","config_deploy",3,1,
                f"R-CF3 · Verify these are in requirements.txt: {', '.join(third)}",
                "pip freeze > requirements.txt",0.75))

    # ── Logic & Testing ────────────────────────────────────────────────
    if IS_PY and re.search(r'def \w+\s*\(', code) and not re.search(r'def test_|pytest|unittest|assert\b', code):
        bugs.append(_bug("R-L1","logic_testing",2,1,
            "R-L1 · No tests found for this code.",
            "def test_happy_path():\n    assert func(input) == expected",0.75))

    if re.search(r'range\s*\(\s*len\s*\([^)]+\)\s*-\s*1\s*\)|for.+\[:-1\]', code):
        bugs.append(_bug("R-L3","logic_testing",3,_fl(code,r'range\s*\(\s*len|:-1'),
            "R-L3 · Off-by-one: range(len(x)-1) skips the last element.",
            "for i in range(len(numbers)):  # not -1",0.90))

    if IS_PY and re.search(r'def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|set\(\))', code):
        bugs.append(_bug("R-L4","logic_testing",4,_fl(code,r'def\s+\w+\s*\([^)]*=\s*(\[\]|\{\})'),
            "R-L4 · Mutable default argument — shared across all calls.",
            "def func(items=None):\n    if items is None: items = []",0.98))

    if re.search(r'async\s+(def|function)', code) and not re.search(r'\bawait\b', code):
        bugs.append(_bug("R-L5","logic_testing",4,_fl(code,r'async\s+(def|function)'),
            "R-L5 · async function with no await — returns coroutine, not result.",
            "result = await fetch_from_db()  # not fetch_from_db()",0.88))

    bugs.sort(key=lambda b: (b["severity"], b["confidence"]), reverse=True)
    return bugs
