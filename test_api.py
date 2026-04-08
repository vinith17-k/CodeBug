import requests
import json

url = 'http://127.0.0.1:7860/api/review'

# Comprehensive test cases covering 20+ bug types
test_cases = [
    # SECURITY - Severity 5
    ('SQL Injection', 'def get_user(uid):\n    q = f"SELECT * FROM users WHERE id={uid}"\n    cursor.execute(q)', 'python'),
    ('Command Injection', 'import os\nos.system(f"rm {filename}")', 'python'),
    ('Hardcoded Password', 'password = "admin123"\ndb.connect(password)', 'python'),
    ('Code Execution (eval)', 'result = eval(user_input)', 'python'),
    
    # SECURITY - Severity 4
    ('Hardcoded API Key', 'api_key = "sk_live_1234567890abcd"\nheaders = {"key": api_key}', 'python'),
    ('Missing Input Validation', 'filename = request.args["file"]\ndata = open(filename).read()', 'python'),
    ('Path Traversal', 'file_path = f"uploads/{filename}"\nopen(file_path)', 'python'),
    ('XSS Vulnerability', 'document.getElementById("div").innerHTML = userInput;', 'javascript'),
    ('Weak Random', 'import random\ntoken = random.randint(0, 1000000)', 'python'),
    
    # LOGIC BUGS
    ('Division by Zero', 'result = 10 / denominator', 'python'),
    ('Null Dereference', 'obj = get_object()\nobj.method()', 'python'),
    ('Infinite Loop', 'while True:\n    print("loop")', 'python'),
    ('Off-by-One Error', 'for i in range(len(items) - 1):\n    print(items[i])', 'python'),
    ('Resource Leak', 'f = open("file.txt")\ndata = f.read()', 'python'),
    ('Missing Error Handling', 'data = json.loads(user_input)', 'python'),
    ('Unreachable Code', 'def func():\n    return 42\n    print("never runs")', 'python'),
    
    # TYPE & COMPARISON
    ('Loose Equality', 'if (x == 5) { console.log("equal"); }', 'javascript'),
    ('Typeof with ==', 'if (typeof x == "string") { }', 'javascript'),
    ('Redundant Length Check', 'if len(items) != 0:\n    process()', 'python'),
    
    # STYLE
    ('var instead of const', 'var x = 10;\nvar y = 20;', 'javascript'),
    ('Print instead of Logging', 'print("Debug: value is", value)', 'python'),
    
    # CLEAN CODE
    ('Clean Code', 'def greet(name):\n    return f"Hello, {name}!"\nprint(greet("World"))', 'python'),
]

print(f"{'='*70}")
print(f"CodeBug Comprehensive Analysis Test Suite")
print(f"{'='*70}\n")

results = {"security": 0, "logic": 0, "style": 0, "approve": 0}

for idx, (name, code, lang) in enumerate(test_cases, 1):
    try:
        resp = requests.post(
            url,
            json={'code': code, 'language': lang},
            timeout=5
        )
        data = resp.json()
        
        result_type = data['type'].upper()
        category = data.get('category', 'N/A')
        severity = data.get('severity', '0')
        
        if data['type'] == 'approve':
            results["approve"] += 1
            status_icon = "✓"
        else:
            results[category] += 1
            status_icon = "⚠"
        
        print(f"{idx:2}. {status_icon} {name:<30} [{result_type:<7}] Sev: {severity}/5")
        print(f"    {data['comment']}")
        if category != 'style':
            print(f"    Fix: {data.get('fix', 'N/A')[:50]}...")
        print()
        
    except Exception as e:
        print(f"ERROR testing {name}: {str(e)}\n")

print(f"{'='*70}")
print(f"Summary: {results['security']} security, {results['logic']} logic, {results['style']} style, {results['approve']} approved")
print(f"{'='*70}")

