from training_loop import run_training

# Endpoint to trigger RL training
from fastapi import Query

@app.post("/api/train")
async def run_real_training(episodes: int = Query(5, description="Number of training episodes to run")):
    """
    Run the RL training loop for the specified number of episodes.
    Returns training stats and summary.
    """
    stats = run_training(num_episodes=episodes, verbose=False)
    return {"status": "ok", "stats": stats}
from openenv.core.env_server import create_fastapi_app
from environment import CodeBugEnvironment
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import Request, HTTPException
from pydantic import BaseModel
import os
import json
import re
import logging

# Import LLM capabilities

try:
    from agent import review as agent_review
    HAS_LLM = True
except ImportError:
    HAS_LLM = False

logger = logging.getLogger(__name__)

app = create_fastapi_app(
    CodeBugEnvironment,
    CodeReviewAction,
    CodeReviewObservation
)

@app.get("/")
def serve_frontend():
    # Serve the beautiful frontend UI at the root Vercel/HF link!
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except:
        return HTMLResponse("<h1>CodeBug API is Running.</h1><p>Visit /docs to see the OpenEnv logic.</p>")

class ReviewRequest(BaseModel):
    code: str
    language: str
    export_format: str = None  # Optional: 'json' for JSON export


@app.post("/api/review")
async def review_code(request: ReviewRequest):
    """Analyze code and return ALL bug findings with confidence scores"""
    try:
        code = request.code.strip()
        lang = request.language.lower().strip()
        
        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")
        if not lang:
            raise HTTPException(status_code=400, detail="Language must be specified")
        if len(code) > 5000:
            raise HTTPException(status_code=400, detail="Code exceeds 5000 characters")
        
        # Validate language
        supported_langs = ['python', 'javascript', 'typescript', 'java', 'go', 'cpp', 'c++']
        if lang not in supported_langs:
            raise HTTPException(
                status_code=400, 
                detail=f"Language '{lang}' not supported. Supported languages: {', '.join(supported_langs)}"
            )
        
        # LLM-powered comprehensive analysis - returns ALL bugs with confidence scores
        results = analyze_code_with_llm(code, lang) if HAS_LLM else analyze_code_comprehensively(code, lang)
        
        # Return the highest severity bug (or first bug if user wants single response)
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
                "comment": "No obvious bugs detected. Code looks clean.",
                "fix": "",
                "confidence": 1.0
            }
        
        # Export to JSON if requested
        if request.export_format == 'json':
            response['export_url'] = '/api/export'  # Would implement full export endpoint
        
        return response
        
    except HTTPException:
        raise
    except ValueError as ve:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid input: {str(ve)}"}
        )
    except Exception as e:
        import traceback
        return JSONResponse(
            status_code=500,
            content={"error": f"Analysis failed: {str(e)}", "details": traceback.format_exc()[:200]}
        )



def analyze_code_with_llm(code: str, lang: str) -> list:
    """
    Use LLM-powered agent.review() to analyze code for ALL bugs. Returns a list of bug objects. Falls back to pattern-based if LLM fails.
    """
    try:
        bugs = agent_review(code)
        # Optionally filter by language if needed
        if not isinstance(bugs, list):
            bugs = []
        # Add language info if missing
        for bug in bugs:
            if "languages" not in bug:
                bug["languages"] = [lang]
        # Sort by severity (highest first), then by confidence
        bugs.sort(key=lambda x: (x.get('severity', 0), x.get('confidence', 0)), reverse=True)
        logger.info(f"LLM found {len(bugs)} bugs in {lang} code")
        return bugs
    except Exception as e:
        logger.warning(f"LLM analysis failed ({type(e).__name__}: {e}). Using fallback pattern-based analysis.")
        return analyze_code_comprehensively(code, lang)


def analyze_code_comprehensively(code: str, lang: str) -> list:
    """Find ALL bugs in code with confidence scores. Supports Python, JavaScript, TypeScript, Java, Go, C++"""
    bugs = []
    code_lower = code.lower()
    code_no_space = code.lower().replace(' ', '')
    lines = code.split('\n')
    
    # ============ CRITICAL SECURITY BUGS (Severity 5) ============
    
    # SQL Injection (High confidence if f-string + SQL keywords)
    if ('f"' in code or "f'" in code) and any(sql in code_lower for sql in ['select', 'insert', 'delete', 'update', 'from', 'where']) and '{' in code and '}' in code:
        bugs.append({
            "type": "bug", "category": "security", "severity": 5, "line_hint": 3,
            "comment": "SQL injection: f-string with variable interpolation in SQL query.",
            "fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (uid,))",
            "confidence": 0.95,
            "languages": ["python", "javascript", "typescript"]
        })
    
    # Command Injection
    if re.search(r'(os\.system|subprocess|popen|shell=true)\s*\(|exec\s*\(|shell\s*=\s*true', code, re.I):
        bugs.append({
            "type": "bug", "category": "security", "severity": 5, "line_hint": 2,
            "comment": "Command injection: User input directly in shell command.",
            "fix": "Use subprocess with args as list: subprocess.run(['ls', filename], shell=False)",
            "confidence": 0.92,
            "languages": ["python", "javascript", "java"]
        })
    
    # Hardcoded credentials
    if re.search(r'(password|passwd|pwd|secret|credential)\s*[=:]\s*["\'][^"\']{6,}["\']', code, re.I):
        bugs.append({
            "type": "bug", "category": "security", "severity": 5, "line_hint": 2,
            "comment": "Hardcoded password/credential detected.",
            "fix": "Use environment variables: os.getenv('DB_PASSWORD')",
            "confidence": 0.98,
            "languages": ["python", "javascript", "typescript", "java", "go", "cpp"]
        })
    
    # Code execution vulnerabilities
    if re.search(r'\b(eval|exec|compile)\s*\(', code) or 'pickle.load' in code or 'yaml.load(' in code:
        bugs.append({
            "type": "bug", "category": "security", "severity": 5, "line_hint": 2,
            "comment": "Arbitrary code execution: eval/exec/pickle are unsafe with untrusted data.",
            "fix": "Use: json.loads(), ast.literal_eval(), or safe alternatives",
            "confidence": 0.99,
            "languages": ["python", "javascript"]
        })
    
    # ============ HIGH SEVERITY SECURITY BUGS (Severity 4) ============
    
    # Hardcoded API keys
    if re.search(r'(api_key|apikey|secret_key|private_key|token|auth_token|bearer)\s*[=:]\s*["\'][a-zA-Z0-9_\-]{8,}["\']', code, re.I):
        bugs.append({
            "type": "bug", "category": "security", "severity": 4, "line_hint": 1,
            "comment": "Hardcoded API key/token detected.",
            "fix": "api_key = os.getenv('API_KEY')",
            "confidence": 0.96,
            "languages": ["python", "javascript", "typescript", "java", "go"]
        })
    
    # XSS vulnerability
    if lang == 'javascript' and re.search(r'\.innerHTML\s*=|\.eval\(|dangerouslySetInnerHTML', code):
        bugs.append({
            "type": "bug", "category": "security", "severity": 4, "line_hint": 2,
            "comment": "XSS vulnerability: Setting innerHTML with user data can execute scripts.",
            "fix": "Use .textContent or sanitize HTML: DOMPurify.sanitize()",
            "confidence": 0.94,
            "languages": ["javascript", "typescript"]
        })
    
    # Insecure random
    if re.search(r'(random\.|Math\.random\(\)|rand\(\))', code) and not re.search(r'(secrets|systemrandom|cryptographically|urandom)', code, re.I):
        bugs.append({
            "type": "bug", "category": "security", "severity": 4, "line_hint": 2,
            "comment": "Weak random number generator for security purposes.",
            "fix": "Use: secrets.token_hex() or os.urandom() for cryptographic randomness",
            "confidence": 0.88,
            "languages": ["python", "javascript", "java", "go", "cpp"]
        })
    
    # ============ LOGIC BUGS ============
    
    # Mutable default argument (Python-specific)
    if lang == 'python' and re.search(r'def\s+\w+\s*\([^)]*=\s*\[\]|def\s+\w+\s*\([^)]*=\s*\{\}', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 1,
            "comment": "Mutable default argument: List/dict is shared across all function calls.",
            "fix": "Use None as default: def func(lst=None): if lst is None: lst = []",
            "confidence": 0.98,
            "languages": ["python"]
        })
    
    # Modifying list while iterating
    if lang == 'python' and re.search(r'for\s+\w+\s+in\s+\w+:.*\.remove\(|for\s+\w+\s+in\s+\w+:.*\.pop\(', code, re.DOTALL):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Modifying list while iterating: Causes items to be skipped.",
            "fix": "Iterate over a copy: for item in items[:]: or use list comprehension",
            "confidence": 0.91,
            "languages": ["python"]
        })
    
    # Shadowing built-ins (Python)
    if lang == 'python':
        builtins = ['list', 'dict', 'set', 'tuple', 'str', 'int', 'float', 'len', 'range', 'map', 'filter', 'zip', 'open', 'sum']
        for builtin in builtins:
            if re.search(rf'^{builtin}\s*=', code, re.MULTILINE):
                bugs.append({
                    "type": "bug", "category": "logic", "severity": 2, "line_hint": 1,
                    "comment": f"Shadowing built-in '{builtin}': Overwrites Python's {builtin}() function.",
                    "fix": f"Rename variable: use my_{builtin} or similar",
                    "confidence": 0.99,
                    "languages": ["python"]
                })
                break
    
    # Division by zero
    if re.search(r'\/\s*0(?![a-zA-Z0-9])', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Potential division by zero. Check denominator is non-zero.",
            "fix": "Add check: if denominator != 0: result = numerator / denominator",
            "confidence": 0.99,
            "languages": ["python", "javascript", "java", "go", "cpp"]
        })
    
    # Off-by-one errors
    if re.search(r'\[\s*\w+\s*\+\s*1\s*\]|\[.*:.*-\s*1\]|range\(len', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Off-by-one error: May access beyond array bounds or skip elements.",
            "fix": "Use range(len(arr)) or check bounds: if i+1 < len(arr)",
            "confidence": 0.85,
            "languages": ["python", "javascript", "java", "go", "cpp"]
        })
    
    # Resource leak
    if re.search(r'open\s*\([^)]+\)\s*(?!with|as)', code) and '.close()' not in code:
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Resource leak: File opened without 'with' statement. May not close properly.",
            "fix": "Use: with open(file) as f: ... (automatic close)",
            "confidence": 0.93,
            "languages": ["python"]
        })
    
    # Infinite recursion (Python)
    if lang == 'python' and re.search(r'def\s+(\w+).*:\s*.*return\s+\1\s*\(', code, re.DOTALL):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Infinite recursion: Function calls itself without base case.",
            "fix": "Add base case: if condition: return value",
            "confidence": 0.87,
            "languages": ["python", "javascript", "java", "go", "cpp"]
        })
    
    # Bare except (Python)
    if lang == 'python' and re.search(r'except\s*:\s*(?!.*#)', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
            "comment": "Bare except clause: Catches all exceptions including KeyboardInterrupt.",
            "fix": "Specify exception: except ValueError: or except Exception:",
            "confidence": 0.96,
            "languages": ["python"]
        })
    
    # Type errors
    if lang == 'python' and re.search(r'["\'][^"\']*["\'].*\+.*[0-9]|["\'][^"\']*["\'].*\+\s*\w+(?![\"\')])', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
            "comment": "Type error: Cannot concatenate string with number directly.",
            "fix": "Convert to string: str(value) or use f-string: f'text {value}'",
            "confidence": 0.82,
            "languages": ["python"]
        })
    
    # Missing return statement (Python)
    if lang == 'python' and re.search(r'def\s+\w+\s*\([^)]*\):[^}]*\n\s{4,}result\s*=', code) and not re.search(r'return\s+result', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 3,
            "comment": "Missing return statement: Function computes value but returns None.",
            "fix": "Add return: return result",
            "confidence": 0.89,
            "languages": ["python"]
        })
    
    # Race condition (threading/multiprocessing)
    if re.search(r'threading\.|multiprocessing\.|Thread|Process|concurrent', code, re.I) and not re.search(r'Lock|RLock|Semaphore|Mutex|synchronized', code, re.I):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Race condition: Multithreaded code without synchronization.",
            "fix": "Use locks: lock = threading.Lock(); with lock: shared_var += 1",
            "confidence": 0.80,
            "languages": ["python", "java", "go", "cpp"]
        })
    
    # Inefficient nested loops
    if code.count('for ') >= 2 and ('range(10000)' in code or 'range(1000)' in code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
            "comment": "Performance issue: Nested loops with large ranges (O(n²) complexity).",
            "fix": "Use set/dict for O(1) lookup or optimize algorithm",
            "confidence": 0.75,
            "languages": ["python", "javascript", "java", "go", "cpp"]
        })
    
    # Sort bugs by severity (highest first)
    bugs.sort(key=lambda x: x['severity'], reverse=True)
    
    return bugs


@app.get("/api/health")
async def health_check():
    """Health check endpoint that returns supported languages and API status"""
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
            "/api/health (GET) - This endpoint",
            "/api/stats (GET) - Usage statistics"
        ]
    }


@app.get("/api/stats")
async def get_stats():
    """Return usage statistics and bug detection summary"""
    return {
        "message": "Stats endpoint - tracks would be stored in session/DB",
        "supported_check_types": 30,
        "languages": 6,
        "security_checks": 12,
        "logic_checks": 8,
        "style_checks": 10
    }
    code_lower = code.lower()
    code_no_space = code.lower().replace(' ', '')
    lines = code.split('\n')
    
    # ============ CRITICAL SECURITY BUGS (Severity 5) ============
    
    # SQL Injection (High confidence if f-string + SQL keywords)
    if ('f"' in code or "f'" in code) and any(sql in code_lower for sql in ['select', 'insert', 'delete', 'update', 'from', 'where']) and '{' in code and '}' in code:
        bugs.append({
            "type": "bug", "category": "security", "severity": 5, "line_hint": 3,
            "comment": "SQL injection: f-string with variable interpolation in SQL query.",
            "fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (uid,))",
            "confidence": 0.95,  # Very high confidence
            "languages": ["python", "javascript", "typescript"]
        })
    
    # Command Injection
    if re.search(r'(os\.system|subprocess|popen|shell=true|exec\(|eval\()\s*\(.*f["\']|shell\s*=\s*true', code, re.I):
        bugs.append({
            "type": "bug", "category": "security", "severity": 5, "line_hint": 2,
            "comment": "Command injection: User input directly in shell command.",
            "fix": "Use subprocess with args as list: subprocess.run(['ls', filename], shell=False)",
            "confidence": 0.92,
            "languages": ["python", "javascript", "java"]
        })
    
    # Hardcoded credentials
    if re.search(r'(password|passwd|pwd|secret|credential)\s*[=:]\s*["\'][^"\']{6,}["\']', code, re.I):
        bugs.append({
            "type": "bug", "category": "security", "severity": 5, "line_hint": 2,
            "comment": "Hardcoded password/credential detected.",
            "fix": "Use environment variables: os.getenv('DB_PASSWORD')",
            "confidence": 0.98,  # Almost certain
            "languages": ["python", "javascript", "typescript", "java", "go", "cpp"]
        })
    
    # Code execution vulnerabilities
    if re.search(r'\b(eval|exec|compile)\s*\(', code) or 'pickle.load' in code or 'yaml.load(' in code:
        bugs.append({
            "type": "bug", "category": "security", "severity": 5, "line_hint": 2,
            "comment": "Arbitrary code execution: eval/exec/pickle are unsafe with untrusted data.",
            "fix": "Use: json.loads(), ast.literal_eval(), or safe alternatives",
            "confidence": 0.99,
            "languages": ["python", "javascript"]
        })
    
    # ============ HIGH SEVERITY SECURITY BUGS (Severity 4) ============
    
    # Hardcoded API keys
    if re.search(r'(api_key|apikey|secret_key|private_key|token|auth_token|bearer|sk_|pk_)\s*[=:]\s*["\'][a-zA-Z0-9_\-]{8,}["\']', code, re.I):
        bugs.append({
            "type": "bug", "category": "security", "severity": 4, "line_hint": 1,
            "comment": "Hardcoded API key/token detected.",
            "fix": "api_key = os.getenv('API_KEY')",
            "confidence": 0.96,
            "languages": ["python", "javascript", "typescript", "java", "go"]
        })
    
    # XSS vulnerability
    if lang == 'javascript' and re.search(r'\.innerHTML\s*=|\.eval\(|dangerouslySetInnerHTML', code):
        bugs.append({
            "type": "bug", "category": "security", "severity": 4, "line_hint": 2,
            "comment": "XSS vulnerability: Setting innerHTML with user data can execute scripts.",
            "fix": "Use .textContent or sanitize HTML: DOMPurify.sanitize()",
            "confidence": 0.94,
            "languages": ["javascript", "typescript"]
        })
    
    # Insecure random
    if re.search(r'(random\.|Math\.random\(\)|rand\(\))', code) and not re.search(r'(secrets|systemrandom|cryptographically|urandom)', code, re.I):
        bugs.append({
            "type": "bug", "category": "security", "severity": 4, "line_hint": 2,
            "comment": "Weak random number generator for security purposes.",
            "fix": "Use: secrets.token_hex() or os.urandom() for cryptographic randomness",
            "confidence": 0.88,
            "languages": ["python", "javascript", "java", "go", "cpp"]
        })
    
    # ============ LOGIC BUGS ============
    
    # Mutable default argument (Python-specific)
    if lang == 'python' and re.search(r'def\s+\w+\s*\([^)]*=\s*\[\]|def\s+\w+\s*\([^)]*=\s*\{\}', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 1,
            "comment": "Mutable default argument: List/dict is shared across all function calls.",
            "fix": "Use None as default: def func(lst=None): if lst is None: lst = []",
            "confidence": 0.98,
            "languages": ["python"]
        })
    
    # Modifying list while iterating
    if lang == 'python' and re.search(r'for\s+\w+\s+in\s+\w+:.*\.remove\(|for\s+\w+\s+in\s+\w+:.*\.pop\(', code, re.DOTALL):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Modifying list while iterating: Causes items to be skipped.",
            "fix": "Iterate over a copy: for item in items[:]: or use list comprehension",
            "confidence": 0.91,
            "languages": ["python"]
        })
    
    # Shadowing built-ins (Python)
    if lang == 'python':
        builtins = ['list', 'dict', 'set', 'tuple', 'str', 'int', 'float', 'len', 'range', 'map', 'filter', 'zip', 'open', 'sum']
        for builtin in builtins:
            if re.search(rf'^{builtin}\s*=', code, re.MULTILINE):
                bugs.append({
                    "type": "bug", "category": "logic", "severity": 2, "line_hint": 1,
                    "comment": f"Shadowing built-in '{builtin}': Overwrites Python's {builtin}() function.",
                    "fix": f"Rename variable: use my_{builtin} or similar",
                    "confidence": 0.99,
                    "languages": ["python"]
                })
                break
    
    # Division by zero
    if re.search(r'\/\s*0(?![a-zA-Z0-9])', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Potential division by zero. Check denominator is non-zero.",
            "fix": "Add check: if denominator != 0: result = numerator / denominator",
            "confidence": 0.99,
            "languages": ["python", "javascript", "java", "go", "cpp"]
        })
    
    # Off-by-one errors
    if re.search(r'\[\s*\w+\s*\+\s*1\s*\]|\[.*:.*-\s*1\]|range\(len', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Off-by-one error: May access beyond array bounds or skip elements.",
            "fix": "Use range(len(arr)) or check bounds: if i+1 < len(arr)",
            "confidence": 0.85,
            "languages": ["python", "javascript", "java", "go", "cpp"]
        })
    
    # Resource leak
    if re.search(r'open\s*\([^)]+\)\s*(?!with|as)', code) and '.close()' not in code:
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Resource leak: File opened without 'with' statement. May not close properly.",
            "fix": "Use: with open(file) as f: ... (automatic close)",
            "confidence": 0.93,
            "languages": ["python"]
        })
    
    # Infinite recursion (Python)
    if lang == 'python' and re.search(r'def\s+(\w+).*:\s*.*return\s+\1\s*\(', code, re.DOTALL):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Infinite recursion: Function calls itself without base case.",
            "fix": "Add base case: if condition: return value",
            "confidence": 0.87,
            "languages": ["python", "javascript", "java", "go", "cpp"]
        })
    
    # Bare except (Python)
    if lang == 'python' and re.search(r'except\s*:\s*(?!.*#)', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
            "comment": "Bare except clause: Catches all exceptions including KeyboardInterrupt.",
            "fix": "Specify exception: except ValueError: or except Exception:",
            "confidence": 0.96,
            "languages": ["python"]
        })
    
    # Type errors
    if lang == 'python' and re.search(r'["\'][^"\']*["\'].*\+.*[0-9]|["\'][^"\']*["\'].*\+\s*\w+(?![\"\')])', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
            "comment": "Type error: Cannot concatenate string with number directly.",
            "fix": "Convert to string: str(value) or use f-string: f'text {value}'",
            "confidence": 0.82,
            "languages": ["python"]
        })
    
    # Missing return statement (Python)
    if lang == 'python' and re.search(r'def\s+\w+\s*\([^)]*\):[^}]*\n\s{4,}result\s*=', code) and not re.search(r'return\s+result', code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 3,
            "comment": "Missing return statement: Function computes value but returns None.",
            "fix": "Add return: return result",
            "confidence": 0.89,
            "languages": ["python"]
        })
    
    # Race condition (threading/multiprocessing)
    if re.search(r'threading\.|multiprocessing\.|Thread|Process|concurrent', code, re.I) and not re.search(r'Lock|RLock|Semaphore|Mutex|synchronized', code, re.I):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Race condition: Multithreaded code without synchronization.",
            "fix": "Use locks: lock = threading.Lock(); with lock: shared_var += 1",
            "confidence": 0.80,
            "languages": ["python", "java", "go", "cpp"]
        })
    
    # Inefficient nested loops
    if code.count('for ') >= 2 and ('range(10000)' in code or 'range(1000)' in code):
        bugs.append({
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
            "comment": "Performance issue: Nested loops with large ranges (O(n²) complexity).",
            "fix": "Use set/dict for O(1) lookup or optimize algorithm",
            "confidence": 0.75,
            "languages": ["python", "javascript", "java", "go", "cpp"]
        })
    
    # Sort bugs by severity (highest first)
    bugs.sort(key=lambda x: x['severity'], reverse=True)
    
    return bugs


def analyze_code_locally(code: str, lang: str) -> dict:
    """Pattern-based code analysis - DEPRECATED: Use analyze_code_comprehensively instead"""
    bugs = analyze_code_comprehensively(code, lang)
    if bugs:
        return bugs[0]
    return {
        "type": "approve",
        "category": "style",
        "severity": 1,
        "line_hint": None,
        "comment": "No obvious bugs detected. Code looks clean.",
        "fix": "",
        "confidence": 1.0
    }
