import requests
import json

# Test 1: Simple code with bare except
code1 = """try:
    x = int("abc")
except:
    pass

print(x)"""

print("Test 1: Simple code with bare except")
print("-" * 60)
print(code1)
print("-" * 60)

try:
    response = requests.post(
        "http://127.0.0.1:7860/api/review",
        json={"code": code1, "language": "python"},
        timeout=3,
    )

    data = response.json()
    print(f"Bugs found: {data['bugs_found']}")
    for i, bug in enumerate(data["bugs"], 1):
        print(f"{i}. {bug['comment'][:60]} (confidence: {bug['confidence']})")
except Exception as e:
    print(f"Error: {e}")

print("\n")

# Test 2: Type error
code2 = """a = "5"
b = 10
result = a + b"""

print("Test 2: Type error")
print("-" * 60)
print(code2)
print("-" * 60)

try:
    response = requests.post(
        "http://127.0.0.1:7860/api/review",
        json={"code": code2, "language": "python"},
        timeout=3,
    )

    data = response.json()
    print(f"Bugs found: {data['bugs_found']}")
    for i, bug in enumerate(data["bugs"], 1):
        print(f"{i}. {bug['comment'][:60]} (confidence: {bug['confidence']})")
except Exception as e:
    print(f"Error: {e}")

print("\n")

# Test 3: SQL injection
code3 = """query = f'SELECT * FROM users WHERE id={user_id}'"""

print("Test 3: SQL Injection")
print("-" * 60)
print(code3)
print("-" * 60)

try:
    response = requests.post(
        "http://127.0.0.1:7860/api/review",
        json={"code": code3, "language": "python"},
        timeout=3,
    )

    data = response.json()
    print(f"Bugs found: {data['bugs_found']}")
    for i, bug in enumerate(data["bugs"], 1):
        print(f"{i}. {bug['comment'][:60]} (confidence: {bug['confidence']})")
except Exception as e:
    print(f"Error: {e}")

print("\n✓ All tests completed")
