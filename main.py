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
    """Comprehensive pattern-based code analysis"""
    
    code_lower = code.lower()
    code_no_space = code.lower().replace(' ', '')
    lines = code.split('\n')
    
    # ============ CRITICAL SECURITY BUGS (Severity 5) ============
    
    # SQL Injection
    if ('f"' in code or "f'" in code) and any(sql in code_lower for sql in ['select', 'insert', 'delete', 'update', 'from', 'where']) and '{' in code and '}' in code:
        return {
            "type": "bug", "category": "security", "severity": 5, "line_hint": 3,
            "comment": "SQL injection: f-string with variable interpolation in SQL query.",
            "fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (uid,))"
        }
    
    # Command Injection
    if re.search(r'(os\.system|subprocess|popen|shell=true)\s*\(.*f["\']|exec.*os\.getenv', code, re.I):
        return {
            "type": "bug", "category": "security", "severity": 5, "line_hint": 2,
            "comment": "Command injection: User input directly in shell command.",
            "fix": "Use subprocess with args as list: subprocess.run(['ls', filename], shell=False)"
        }
    
    # Hardcoded password/credentials
    if re.search(r'(password|passwd|pwd|secret|credential)\s*[=:]\s*["\'][^"\']{6,}["\']', code, re.I):
        return {
            "type": "bug", "category": "security", "severity": 5, "line_hint": 2,
            "comment": "Hardcoded password/credential detected.",
            "fix": "Use environment variables: os.getenv('DB_PASSWORD')"
        }
    
    # Code execution (eval, exec, pickle)
    if re.search(r'\b(eval|exec|compile)\s*\(', code) or 'pickle.load' in code or 'yaml.load(' in code:
        return {
            "type": "bug", "category": "security", "severity": 5, "line_hint": 2,
            "comment": "Arbitrary code execution: eval/exec/pickle are unsafe with untrusted data.",
            "fix": "Use: json.loads(), ast.literal_eval(), or safe alternatives"
        }
    
    # ============ HIGH SEVERITY SECURITY BUGS (Severity 4) ============
    
    # Hardcoded API keys/tokens
    if re.search(r'(api_key|apikey|secret_key|private_key|token|auth_token|bearer|sk_|pk_)\s*[=:]\s*["\'][a-zA-Z0-9_\-]+["\']', code, re.I):
        return {
            "type": "bug", "category": "security", "severity": 4, "line_hint": 1,
            "comment": "Hardcoded API key/token detected.",
            "fix": "api_key = os.getenv('API_KEY')"
        }
    
    # Missing input validation
    if re.search(r'(user_input|request\.args|request\.form|get\(|input\(\))\s*\[', code) and not re.search(r'(validate|check|strip|sanitize|escape)', code, re.I):
        return {
            "type": "bug", "category": "security", "severity": 4, "line_hint": 2,
            "comment": "Missing input validation: User input used without sanitization.",
            "fix": "Validate and sanitize all user input before using"
        }
    
    # Path traversal vulnerability
    if re.search(r'(open|read|load)\s*\(\s*f?["\'].*\.\.\/', code, re.I) or ('..\\' in code and 'open' in code_lower):
        return {
            "type": "bug", "category": "security", "severity": 4, "line_hint": 2,
            "comment": "Path traversal vulnerability: Relative paths with ../ can access arbitrary files.",
            "fix": "Use absolute paths or validate/normalize paths: os.path.normpath()"
        }
    
    # XSS vulnerability (JavaScript)
    if lang == 'javascript' and re.search(r'\.innerHTML\s*=|\.eval\(|dangerouslySetInnerHTML', code):
        return {
            "type": "bug", "category": "security", "severity": 4, "line_hint": 2,
            "comment": "XSS vulnerability: Setting innerHTML with user data can execute scripts.",
            "fix": "Use .textContent or sanitize HTML: DOMPurify.sanitize()"
        }
    
    # Insecure random (weak randomness)
    if re.search(r'(random\.|Math\.random\(\)|rand\(\))', code) and not re.search(r'(secrets|systemrandom|cryptographically|urandom)', code, re.I):
        return {
            "type": "bug", "category": "security", "severity": 4, "line_hint": 2,
            "comment": "Weak random number generator for security purposes.",
            "fix": "Use: secrets.token_hex() or os.urandom() for cryptographic randomness"
        }
    
    # ============ LOGIC BUGS ============
    
    # Division by zero
    if re.search(r'\/\s*0|divide.*0', code, re.I) or (re.search(r'\/\s*\w+', code) and 'while' not in code_lower):
        if 'while' not in code_lower or '!=' not in code.split('/')[0]:
            return {
                "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
                "comment": "Potential division by zero. Check denominator is non-zero.",
                "fix": "Add check: if denominator != 0: result = numerator / denominator"
            }
    
    # Null/None pointer dereference
    if re.search(r'(?<![=!])\.\w+\s*(?![=])|->|::', code) and not re.search(r'(is not None|!= null|!== undefined|if.*:)', code):
        if re.search(r'\[.*\]\.\w+|\)\.\w+', code):
            return {
                "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
                "comment": "Potential null/None dereference without null check.",
                "fix": "Add null check: if obj is not None: obj.method()"
            }
    
    # Infinite loops
    if ('while true' in code_no_space or 'while(true)' in code_no_space or 'for(;;)' in code_no_space) and 'break' not in code_lower:
        return {
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Infinite loop detected. Loop condition never becomes false.",
            "fix": "Add break condition or change loop condition"
        }
    
    # Off-by-one errors
    if re.search(r'range\s*\(\s*len\s*\([^)]+\)\s*-\s*1\s*\)', code):
        return {
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Off-by-one error: range(len(x) - 1) skips the last element.",
            "fix": "Use: for i in range(len(items)): or: for item in items:"
        }
    
    # Resource leak (unclosed file)
    if re.search(r'open\s*\([^)]+\)\s*(?!with)', code) and '.close()' not in code:
        return {
            "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
            "comment": "Resource leak: File opened without 'with' statement. May not close properly.",
            "fix": "Use: with open(file) as f: ... (automatic close)"
        }
    
    # Missing error handling
    if (re.search(r'(json\.loads|parse|eval|execute|request)\s*\(', code) or lang == 'javascript' and re.search(r'fetch\s*\(|\.then', code)) and not re.search(r'(try|except|catch|error)', code, re.I):
        return {
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
            "comment": "Missing error handling: Code can fail silently.",
            "fix": "Wrap in try/except: try: ... except Exception as e: ..."
        }
    
    # Unreachable code after return
    if re.search(r'return\s*[^;]*\n\s+\w+', code):
        return {
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 3,
            "comment": "Unreachable code: Statements after return will never execute.",
            "fix": "Remove or restructure code after return statement"
        }
    
    # ============ TYPE & COMPARISON BUGS ============
    
    # Loose equality in JavaScript
    if lang == 'javascript' and re.search(r'[^=!<>]\s*==\s*[^=]', code):
        return {
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 3,
            "comment": "Loose equality (==) prone to type coercion bugs. Use ===",
            "fix": "Replace == with === and != with !=="
        }
    
    # Type errors
    if lang == 'javascript' and re.search(r'typeof\s*\w+\s*==', code):
        return {
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
            "comment": "Use === with typeof: typeof always returns string.",
            "fix": "Use: typeof x === 'string'"
        }
    
    # Redundant checks
    if re.search(r'if\s+len\s*\([^)]+\)\s*[!=><]=*\s*0', code):
        return {
            "type": "bug", "category": "logic", "severity": 2, "line_hint": 1,
            "comment": "Redundant length check. Empty sequences are falsy.",
            "fix": "Use: if items: instead of: if len(items) != 0:"
        }
    
    # ============ STYLE & BEST PRACTICES ============
    
    # var in JavaScript
    if lang == 'javascript' and re.search(r'\bvar\s+\w+\s*[=;]', code):
        return {
            "type": "bug", "category": "style", "severity": 2, "line_hint": 1,
            "comment": "Use const/let instead of var. var has function-level scope.",
            "fix": "Replace var with const (or let if reassignment needed)"
        }
    
    # Deprecated functions
    if re.search(r'\b(deprecated|old_function|legacy_method)\s*\(', code, re.I):
        return {
            "type": "bug", "category": "style", "severity": 2, "line_hint": 1,
            "comment": "Deprecated function detected. Use newer alternative.",
            "fix": "Check documentation for recommended replacement"
        }
    
    # Print debugging in production
    if 'print(' in code and lang == 'python' and not re.search(r'(logging|debug)', code):
        if re.search(r'print\s*\(\s*["\'].*["\']', code):
            return {
                "type": "bug", "category": "style", "severity": 1, "line_hint": 2,
                "comment": "Consider using logging instead of print() for production code.",
                "fix": "Use: import logging; logging.info('message')"
            }
    
    # ============ DEFAULT: NO BUGS ============
    
    return {
        "type": "approve",
        "category": "style",
        "severity": 1,
        "line_hint": None,
        "comment": "No obvious bugs detected. Code looks clean.",
        "fix": ""
    }
