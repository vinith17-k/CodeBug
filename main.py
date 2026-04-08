from openenv.core.env_server import create_fastapi_app
from environment import CodeBugEnvironment
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import Request, HTTPException
from pydantic import BaseModel
import os
import json
import re

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

@app.post("/api/review")
async def review_code(request: ReviewRequest):
    """Analyze code and return bug findings"""
    try:
        code = request.code.strip()
        lang = request.language.lower()
        
        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")
        if not lang:
            raise HTTPException(status_code=400, detail="Language must be specified")
        if len(code) > 5000:
            raise HTTPException(status_code=400, detail="Code exceeds 5000 characters")
        
        # Local pattern-based analysis
        result = analyze_code_locally(code, lang)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

def analyze_code_locally(code: str, lang: str) -> dict:
    """Pattern-based code analysis - production would use LLM"""
    
    code_lower = code.lower()
    code_no_space = code.lower().replace(' ', '')
    
    # === SECURITY BUGS (Highest Priority) ===
    # SQL Injection: f-string + SQL keywords + variable interpolation
    if ('f"' in code or "f'" in code) and any(sql in code_lower for sql in ['select', 'insert', 'delete', 'update', 'from', 'where']) and '{' in code and '}' in code:
        return {
            "type": "bug",
            "category": "security",
            "severity": 5,
            "line_hint": 3,
            "comment": "SQL injection: f-string with variable interpolation in SQL query. User input flows directly to database.",
            "fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (uid,))"
        }
    
    # Hardcoded password
    if re.search(r'(password|passwd|pwd)\s*[=:]\s*["\'][^"\']+["\']', code, re.I):
        return {
            "type": "bug",
            "category": "security",
            "severity": 5,
            "line_hint": 2,
            "comment": "Hardcoded password detected. Never store credentials in source code.",
            "fix": "Use environment variables: password = os.getenv('DB_PASSWORD')"
        }
    
    # Hardcoded API keys / secrets
    if re.search(r'(api_key|apikey|secret_key|private_key|token|access_token)\s*[=:]\s*["\'][a-zA-Z0-9_\-]+["\']', code, re.I):
        return {
            "type": "bug",
            "category": "security",
            "severity": 4,
            "line_hint": 1,
            "comment": "Hardcoded API key or secret detected. Move to environment variables.",
            "fix": "api_key = os.getenv('API_KEY')\nif not api_key:\n    raise ValueError('API_KEY not set')"
        }
    
    # Code execution vulnerabilities
    if re.search(r'\b(eval|exec)\s*\(', code) or 'pickle.load' in code or 'yaml.load' in code:
        return {
            "type": "bug",
            "category": "security",
            "severity": 5,
            "line_hint": 2,
            "comment": "Arbitrary code execution vulnerability. eval() and exec() are dangerous.",
            "fix": "Use safe alternatives: json.loads(), ast.literal_eval(), or parameterized logic."
        }
    
    # === LOGIC BUGS ===
    # Infinite loops
    if ('while true' in code_no_space or 'while(true)' in code_no_space or 'for(;;)' in code_no_space) and 'break' not in code_lower:
        return {
            "type": "bug",
            "category": "logic",
            "severity": 3,
            "line_hint": 2,
            "comment": "Infinite loop detected. Loop condition never becomes false.",
            "fix": "Add a break condition or change the loop condition."
        }
    
    # Off-by-one errors: range(len(x) - 1)
    if re.search(r'range\s*\(\s*len\s*\([^)]+\)\s*-\s*1\s*\)', code):
        return {
            "type": "bug",
            "category": "logic",
            "severity": 3,
            "line_hint": 2,
            "comment": "Off-by-one error: range(len(x) - 1) skips the last element.",
            "fix": "Use range(len(items)) or simply: for item in items:"
        }
    
    # Redundant length checks
    if re.search(r'if\s+len\s*\([^)]+\)\s*[!=><]=*\s*0', code):
        return {
            "type": "bug",
            "category": "logic",
            "severity": 2,
            "line_hint": 1,
            "comment": "Redundant length check. Empty sequences are falsy in Python.",
            "fix": "Use: if items: instead of if len(items) != 0:"
        }
    
    # Type coercion bugs in JavaScript
    if lang == 'javascript':
        # Loose equality (== instead of ===)
        if re.search(r'==\s|==[\'\"]|==\d|\s==', code) and not re.search(r'===', code):
            return {
                "type": "bug",
                "category": "logic",
                "severity": 2,
                "line_hint": 3,
                "comment": "Use strict equality (===) instead of ==. Prone to type coercion bugs.",
                "fix": "Replace == with === and != with !=="
            }
        
        # var instead of const/let
        if re.search(r'\bvar\s+\w+\s*[=;]', code):
            return {
                "type": "bug",
                "category": "style",
                "severity": 2,
                "line_hint": 1,
                "comment": "Use const/let instead of var. var has scope issues.",
                "fix": "Replace var with const (or let if reassignment needed)"
            }
    
    # === DEFAULT: NO BUGS ===
    return {
        "type": "approve",
        "category": "style",
        "severity": 1,
        "line_hint": None,
        "comment": "No obvious bugs detected. Code looks clean.",
        "fix": ""
    }
