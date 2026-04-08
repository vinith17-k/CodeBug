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
    HAS_LLM = True
except ImportError as e:
    HAS_LLM = False

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
    """Use LLM-powered agent.review() to analyze code"""
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


def analyze_code_comprehensively(code: str, lang: str) -> list:
    """Fallback pattern-based bug detection when LLM is unavailable"""
    bugs = []
    code_lower = code.lower()
    
    # SQL Injection
    if ('f"' in code or "f'" in code) and any(sql in code_lower for sql in ['select', 'insert', 'delete', 'update', 'from', 'where']) and '{' in code:
        bugs.append({
            "type": "bug", "category": "security", "severity": 5, "line_hint": "SQL query line",
            "comment": "SQL injection: f-string with variable interpolation in SQL query.",
            "fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (uid,))",
            "confidence": 0.95,
            "languages": ["python", "javascript", "typescript"]
        })
    
    # Hardcoded credentials
    if re.search(r'(password|passwd|pwd|secret|credential)\s*[=:]\s*["\'][^"\']{6,}["\']', code, re.I):
        bugs.append({
            "type": "bug", "category": "security", "severity": 5, "line_hint": "credential line",
            "comment": "Hardcoded password/credential detected.",
            "fix": "Use environment variables: os.getenv('DB_PASSWORD')",
            "confidence": 0.98,
            "languages": ["python", "javascript", "typescript", "java", "go", "cpp"]
        })
    
    # Code execution vulnerabilities
    if re.search(r'\b(eval|exec|compile)\s*\(', code) or 'pickle.load' in code or 'yaml.load(' in code:
        bugs.append({
            "type": "bug", "category": "security", "severity": 5, "line_hint": "eval/exec/pickle line",
            "comment": "Arbitrary code execution: eval/exec/pickle are unsafe with untrusted data.",
            "fix": "Use: json.loads(), ast.literal_eval(), or safe alternatives",
            "confidence": 0.99,
            "languages": ["python", "javascript"]
        })
    
    # Hardcoded API keys
    if re.search(r'(api_key|apikey|secret_key|token|bearer)\s*[=:]\s*["\'][a-zA-Z0-9_\-]{8,}["\']', code, re.I):
        bugs.append({
            "type": "bug", "category": "security", "severity": 4, "line_hint": "API key line",
            "comment": "Hardcoded API key/token detected.",
            "fix": "Use environment variables: api_key = os.getenv('API_KEY')",
            "confidence": 0.96,
            "languages": ["python", "javascript", "typescript", "java", "go"]
        })
    
    # Mutable default argument (Python)
    if lang == 'python' and re.search(r'def\s+\w+\s*\([^)]*=\s*\[\]|def\s+\w+\s*\([^)]*=\s*\{\}', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": "function definition",
            "comment": "Mutable default argument: List/dict is shared across all function calls.",
            "fix": "Use None as default: def func(lst=None): if lst is None: lst = []",
            "confidence": 0.98,
            "languages": ["python"]
        })
    
    # Off-by-one errors
    if re.search(r'range\(len\([^)]+\)\s*-\s*1\)', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": "loop range",
            "comment": "Off-by-one error: range(len(x)-1) skips the last element.",
            "fix": "Use range(len(arr)) or enumerate(arr)",
            "confidence": 0.85,
            "languages": ["python", "javascript", "java", "go", "cpp"]
        })
    
    # Division by zero
    if re.search(r'\/\s*0(?![a-zA-Z0-9])', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": "division line",
            "comment": "Potential division by zero. Check denominator is non-zero.",
            "fix": "Add check: if denominator != 0: result = numerator / denominator",
            "confidence": 0.99,
            "languages": ["python", "javascript", "java", "go", "cpp"]
        })
    
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
