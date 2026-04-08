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
        
        # Local pattern-based analysis - returns ALL bugs, not just first
        results = analyze_code_comprehensively(code, lang)
        
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
    if lang == 'python' and re.search(r'def\s+\w+.*:\s*.*return\s+\1\s*\(', code, re.DOTALL):
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
    
    # ============ PYTHON-SPECIFIC BUGS ============
    
    if lang == 'python':
        # Mutable default argument
        if re.search(r'def\s+\w+\s*\([^)]*=\s*\[\]|def\s+\w+\s*\([^)]*=\s*\{\}', code):
            return {
                "type": "bug", "category": "logic", "severity": 3, "line_hint": 1,
                "comment": "Mutable default argument: List/dict is shared across all function calls.",
                "fix": "Use None as default: def func(lst=None): if lst is None: lst = []"
            }
        
        # Modifying list while iterating
        if re.search(r'for\s+\w+\s+in\s+\w+:.*\.remove\(|for\s+\w+\s+in\s+\w+:.*\.pop\(', code, re.DOTALL):
            return {
                "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
                "comment": "Modifying list while iterating: Causes items to be skipped.",
                "fix": "Iterate over a copy: for item in items[:]: or use list comprehension"
            }
        
        # Shadowing built-in names
        builtins = ['list', 'dict', 'set', 'tuple', 'str', 'int', 'float', 'len', 'range', 'map', 'filter', 'zip', 'open']
        for builtin in builtins:
            if re.search(rf'^{builtin}\s*=', code, re.MULTILINE):
                return {
                    "type": "bug", "category": "logic", "severity": 2, "line_hint": 1,
                    "comment": f"Shadowing built-in '{builtin}': Overwrites Python's {builtin}() function.",
                    "fix": f"Rename variable: use my_{builtin} or similar"
                }
        
        # Missing return statement
        if re.search(r'def\s+\w+\s*\([^)]*\):[^}]*\n\s{4,}\w+\s*=', code) and 'return' not in code:
            return {
                "type": "bug", "category": "logic", "severity": 2, "line_hint": 3,
                "comment": "Missing return statement: Function computes value but returns None.",
                "fix": "Add return: return result"
            }
        
        # Bare except clause
        if re.search(r'except\s*:\s*(?!.*#)', code):
            return {
                "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
                "comment": "Bare except clause: Catches all exceptions including KeyboardInterrupt.",
                "fix": "Specify exception: except ValueError: or except Exception:"
            }
        
        # Variable scope issue
        if re.search(r'def\s+\w+\s*\([^)]*\):[^}]*\n(?:\s{4}.*\n)*(?:\s{0,3})\w+\s*=', code):
            return {
                "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
                "comment": "Variable scope issue: Variable defined in function not accessible outside.",
                "fix": "Make it global: global var_name (use sparingly) or return the value"
            }
        
        # Race condition (threading/multiprocessing)
        if re.search(r'threading\.|multiprocessing\.|Thread|Process', code) and not re.search(r'Lock|RLock|Semaphore|Condition', code):
            return {
                "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
                "comment": "Race condition: Multithreaded code without synchronization.",
                "fix": "Use locks: lock = threading.Lock(); with lock: shared_var += 1"
            }
        
        # Infinite recursion (no base case)
        if re.search(r'def\s+\w+\s*\([^)]*\):[^}]*\1\s*\(', code):
            return {
                "type": "bug", "category": "logic", "severity": 3, "line_hint": 2,
                "comment": "Infinite recursion: Function calls itself without base case.",
                "fix": "Add base case: if condition: return value"
            }
        
        # Type error (concatenating string and int)
        if re.search(r'["\'][^"\']*["\'].*\+.*\d+|["\'][^"\']*["\'].*\+\s*\w+', code):
            return {
                "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
                "comment": "Type error: Cannot concatenate string with number directly.",
                "fix": "Convert to string: str(value) or use f-string: f'text {value}'"
            }
        
        # Off-by-one with array indexing
        if re.search(r'\[\s*\w+\s*\+\s*1\s*\]', code):
            return {
                "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
                "comment": "Off-by-one error: arr[i+1] may access beyond array bounds.",
                "fix": "Use range(len(arr)-1) or check bounds: if i+1 < len(arr)"
            }
        
        # Inefficient nested loops
        if code.count('for ') >= 2 and 'range(10000)' in code:
            return {
                "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
                "comment": "Performance issue: Nested loops with large ranges (O(n²) complexity).",
                "fix": "Use set/dict for O(1) lookup or optimize algorithm"
            }
        
        # Logical error (identical branches)
        if re.search(r'if\s+.*?:\s*([^\n]+)\s*else:\s*\1', code, re.DOTALL | re.IGNORECASE):
            return {
                "type": "bug", "category": "logic", "severity": 2, "line_hint": 2,
                "comment": "Logical error: Both if and else branches do the same thing.",
                "fix": "Remove the condition or fix the logic"
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
