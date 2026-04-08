from openenv.core.env_server import create_fastapi_app
from environment import CodeBugEnvironment
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState
from fastapi.responses import HTMLResponse
from fastapi import Request
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
    code = request.code.strip()
    lang = request.language.lower()
    
    if not code:
        return {"error": "Code cannot be empty"}, 400
    if not lang:
        return {"error": "Language must be specified"}, 400
    if len(code) > 5000:
        return {"error": "Code exceeds 5000 characters"}, 400
    
    # Local pattern-based analysis (since this is a demo)
    result = analyze_code_locally(code, lang)
    return result

def analyze_code_locally(code: str, lang: str) -> dict:
    """Pattern-based code analysis - production would use LLM"""
    
    # === SECURITY BUGS (Highest Priority) ===
    if re.search(r'f["\'\`].*?\$\{.*?\}|f["\'\`].*?\{.*?\}', code) and re.search(r'(select|insert|delete|update|from|where)', code, re.I):
        return {
            "type": "bug",
            "category": "security",
            "severity": 5,
            "line_hint": 3,
            "comment": "SQL injection: User input in f-string flows directly to database query.",
            "fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (uid,))"
        }
    
    if re.search(r'(password|passwd|pwd)\s*[:=]\s*["\'].*["\']|".*password.*":\s*".*"', code, re.I):
        return {
            "type": "bug",
            "category": "security",
            "severity": 5,
            "line_hint": 2,
            "comment": "Hardcoded password detected. Never store credentials in source code.",
            "fix": "Use environment variables: password = os.getenv('DB_PASSWORD')"
        }
    
    if re.search(r'(api_key|apikey|secret|token|private|private_key|secret_key)\s*[:=]\s*["\'][a-zA-Z0-9]{8,}["\']', code, re.I):
        return {
            "type": "bug",
            "category": "security",
            "severity": 4,
            "line_hint": 1,
            "comment": "Hardcoded API key/secret detected. Move to environment variables.",
            "fix": "api_key = os.getenv('API_KEY')\nif not api_key:\n    raise ValueError('API_KEY not set')"
        }
    
    if re.search(r'eval\s*\(|exec\s*\(|pickle\.load|yaml\.load\s*\(', code):
        return {
            "type": "bug",
            "category": "security",
            "severity": 5,
            "line_hint": 2,
            "comment": "Arbitrary code execution vulnerability. eval() and exec() are dangerous.",
            "fix": "Use safe alternatives: json.loads(), ast.literal_eval(), or parameterized logic."
        }
    
    # === LOGIC BUGS ===
    if re.search(r'(while\s+true|for\s+\(\s*;\s*;\s*\)|while\s*\(.*\))', code, re.I) and not re.search(r'(break|return|exit)', code):
        return {
            "type": "bug",
            "category": "logic",
            "severity": 3,
            "line_hint": 2,
            "comment": "Infinite loop detected. Loop never breaks or returns.",
            "fix": "Add break condition: while condition: {...; break}"
        }
    
    if re.search(r'range\s*\(\s*len\s*\(\s*.*?\s*\)\s*-\s*1\s*\)', code):
        return {
            "type": "bug",
            "category": "logic",
            "severity": 3,
            "line_hint": 2,
            "comment": "Off-by-one error: range(len(x) - 1) skips the last element.",
            "fix": "Use: for i in range(len(items)): or simply: for item in items:"
        }
    
    if re.search(r'if\s+(len\s*\(\s*\w+\s*\)\s*[>!=<]=?\s*0|len\s*\(\s*\w+\s*\)\s*!=\s*0)', code):
        return {
            "type": "bug",
            "category": "logic",
            "severity": 2,
            "line_hint": 1,
            "comment": "Redundant length check. Empty sequences are falsy in Python.",
            "fix": "Use: if items: instead of if len(items) != 0:"
        }
    
    if lang == 'javascript' and re.search(r'[^=!=]\s*==\s*[^=]|[^=]\s*!=\s*[^=]', code):
        return {
            "type": "bug",
            "category": "logic",
            "severity": 2,
            "line_hint": 3,
            "comment": "Use strict equality (===) instead of ==. Subject to type coercion bugs.",
            "fix": "Replace == with === and != with !==" 
        }
    
    # === STYLE/BEST PRACTICES ===
    if lang == 'javascript' and re.search(r'var\s+\w+\s*=', code):
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
