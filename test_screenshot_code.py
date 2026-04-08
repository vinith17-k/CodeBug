import requests
import json

code = """try:
    x = int("abc")
except:
    pass

print(x)

# 16. Recursive Function Without Base Case
def recurse(n):
    return recurse(n-1)

recurse(5)"""

print("Testing code from screenshot:")
print("─" * 60)
print(code)
print("─" * 60)

response = requests.post(
    "http://127.0.0.1:7860/api/review",
    json={"code": code, "language": "python"},
    timeout=5
)

print(f"\nStatus: {response.status_code}")
print(f"\nResponse:")
data = response.json()
print(json.dumps(data, indent=2))

print("\n" + "─" * 60)
print(f"Bugs found: {data['bugs_found']}")
if data['bugs']:
    print(f"First bug confidence: {data['bugs'][0]['confidence']}")
    print(f"First bug comment: {data['bugs'][0]['comment']}")
