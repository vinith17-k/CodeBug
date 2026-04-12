import sys

sys.path.insert(0, "C:/Users/vinit/Projects/CodeBug")
import os

print("=== API Configuration ===")
print(f"HF_TOKEN set: {bool(os.environ.get('HF_TOKEN'))}")
print(f"OPENAI_API_KEY set: {bool(os.environ.get('OPENAI_API_KEY'))}")

from main import HAS_LLM, analyze_code_comprehensively

print(f"\nHAS_LLM: {HAS_LLM}")

test_cases = [
    ("python", "query = f'SELECT * FROM users WHERE id={user_id}'"),
    ("python", "import requests\nresponse = requests.get(url)"),
    ("python", "api_key = 'sk-1234567890abcdef'"),
    ("python", "@app.get('/users')\ndef get_users():\n    return []"),
    ("javascript", "fetch(url)"),
]

for lang, code in test_cases:
    result = analyze_code_comprehensively(code, lang)
    print(f"\n=== {lang}: {code[:40]}... ===")
    print(f"Bugs found: {len(result)}")
    for bug in result:
        print(f"  - {bug['category']} ({bug['rule_id']}): {bug['comment'][:50]}")
