import requests
import json

BASE_URL = "http://127.0.0.1:7860"

print("=" * 70)
print("LIVE API ENDPOINT TESTS")
print("=" * 70)

# Test health
print("\n[1] /api/health")
try:
    r = requests.get(f"{BASE_URL}/api/health")
    print(f"    Status: {r.status_code}, Version: {r.json().get('version')}")
except Exception as e:
    print(f"    ✗ {e}")

# Test SQL injection code
print("\n[2] /api/review - SQL Injection Code")
code = 'def get_user(uid):\n    q = f"SELECT * FROM users WHERE id={uid}"\n    cursor.execute(q)'
try:
    r = requests.post(f"{BASE_URL}/api/review", json={"code": code, "language": "python"})
    data = r.json()
    print(f"    Status: {r.status_code}")
    print(f"    Bugs Found: {data.get('bugs_found', 'N/A')}")
    bugs = data.get('bugs', [])
    if bugs:
        print(f"    First bug: {bugs[0].get('comment')[:60]}")
        print(f"    Has confidence: {'✓' if 'confidence' in bugs[0] else '✗'}")
        print(f"    Confidence value: {bugs[0].get('confidence', 'N/A')}")
except Exception as e:
    print(f"    ✗ {e}")

# Test multiple issues
print("\n[3] /api/review - Multiple Issues")
code = 'password = "admin123"\nevalllll = exec(user_code)'
try:
    r = requests.post(f"{BASE_URL}/api/review", json={"code": code, "language": "python"})
    data = r.json()
    print(f"    Status: {r.status_code}")
    print(f"    Bugs Found: {data.get('bugs_found', 'N/A')}")
    bugs = data.get('bugs', [])
    print(f"    Number of bugs in response: {len(bugs)}")
    for i, bug in enumerate(bugs[:3], 1):
        print(f"      {i}. {bug.get('comment')[:50]}... (conf: {bug.get('confidence', 'N/A')})")
except Exception as e:
    print(f"    ✗ {e}")

# Test clean code
print("\n[4] /api/review - Clean Code")
code = 'def add(a, b):\n    return a + b'
try:
    r = requests.post(f"{BASE_URL}/api/review", json={"code": code, "language": "python"})
    data = r.json()
    print(f"    Status: {r.status_code}")
    print(f"    Bugs Found: {data.get('bugs_found', 'N/A')}")
except Exception as e:
    print(f"    ✗ {e}")

print("\n" + "=" * 70)
print("✓ TEST COMPLETED")
print("=" * 70)
