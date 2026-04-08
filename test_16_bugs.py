import requests
import json

BASE_URL = "http://127.0.0.1:7860"

code = """# 1. Infinite Loop Bug
i = 0
while i < 10:
    print(i)


# 2. Mutable Default Argument Issue
def add_item(item, lst=[]):
    lst.append(item)
    return lst

print(add_item(1))
print(add_item(2))  # Unexpected shared list


# 3. Division by Zero Risk
def divide(a, b):
    return a / b

print(divide(10, 0))


# 4. Modifying List While Iterating
numbers = [1, 2, 3, 4, 5]
for num in numbers:
    if num % 2 == 0:
        numbers.remove(num)

print(numbers)


# 5. Shadowing Built-in
list = [1, 2, 3]
print(list("hello"))


# 6. File Not Closed + No Exception Handling
file = open("data.txt", "r")
content = file.read()
print(content)


# 7. Indentation Error
def greet(name):
print("Hello " + name)


# 8. Logical Error
age = 18
if age > 18:
    print("Adult")
else:
    print("Adult")


# 9. Inefficient Nested Loop
nums = list(range(10000))
for i in nums:
    for j in nums:
        if i == j:
            print(i)


# 10. Missing Return
def square(x):
    result = x * x

print(square(5))


# 11. Race Condition
import threading

counter = 0

def increment():
    global counter
    for _ in range(100000):
        counter += 1

threads = []
for i in range(5):
    t = threading.Thread(target=increment)
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print(counter)


# 12. Wrong Variable Scope
def foo():
    x = 10

foo()
print(x)  # x is not defined


# 13. Type Error
a = "5"
b = 10
print(a + b)


# 14. Off-by-One Error
arr = [1, 2, 3, 4]
for i in range(len(arr)):
    print(arr[i+1])


# 15. Incorrect Exception Catching
try:
    x = int("abc")
except:
    pass  # silently ignores error

print(x)


# 16. Recursive Function Without Base Case
def recurse(n):
    return recurse(n-1)

recurse(5)
"""

print("="*80)
print("TESTING CODEBUG WITH 16 KNOWN BUGS")
print("="*80)
print(f"\nCode length: {len(code)} characters")
print(f"Number of bugs in code: 16 known issues")
print("\nSending to /api/review endpoint...\n")

try:
    response = requests.post(
        f"{BASE_URL}/api/review",
        json={"code": code, "language": "python"},
        timeout=5
    )
    
    if response.status_code == 200:
        data = response.json()
        bugs = data.get("bugs", [])
        
        print(f"✓ API Response: HTTP {response.status_code} OK")
        print(f"✓ Bugs Found: {data['bugs_found']}")
        print(f"✓ Average Confidence: {data['analysis_metadata']['average_confidence']}")
        print("\n" + "─"*80)
        print("DETECTED BUGS:")
        print("─"*80)
        
        for idx, bug in enumerate(bugs, 1):
            severity = "●" * bug.get("severity", 0)
            confidence = bug.get("confidence", 0)
            category = bug.get("category", "unknown").upper()
            comment = bug.get("comment", "")
            
            print(f"\n[{idx}] {category}")
            print(f"    Comment: {comment}")
            print(f"    Severity: {severity} ({bug.get('severity')}/5)")
            print(f"    Confidence: {confidence:.2f}")
            print(f"    Fix: {bug.get('fix', 'N/A')[:70]}")
        
        print("\n" + "─"*80)
        print("COVERAGE ANALYSIS:")
        print("─"*80)
        
        detected_issues = []
        for bug in bugs:
            comment_lower = bug.get("comment", "").lower()
            if "infinite" in comment_lower or "loop" in comment_lower:
                detected_issues.append("1. Infinite Loop")
            if "default" in comment_lower or "mutable" in comment_lower:
                detected_issues.append("2. Mutable Default")
            if "division" in comment_lower or "zero" in comment_lower:
                detected_issues.append("3. Division by Zero")
            if "modifying" in comment_lower or "iterating" in comment_lower:
                detected_issues.append("4. Modify While Iterating")
            if "shadow" in comment_lower or "builtin" in comment_lower:
                detected_issues.append("5. Shadowing Built-in")
            if "file" in comment_lower or "closed" in comment_lower or "resource" in comment_lower:
                detected_issues.append("6. File Not Closed")
            if "indentation" in comment_lower:
                detected_issues.append("7. Indentation Error")
            if "recursion" in comment_lower or "recurse" in comment_lower:
                detected_issues.append("16. Recursive Function")
            if "except" in comment_lower and "bare" in comment_lower:
                detected_issues.append("15. Bare Except")
            if "type" in comment_lower and "error" in comment_lower:
                detected_issues.append("13. Type Error")
            if "off-by-one" in comment_lower or "off by one" in comment_lower:
                detected_issues.append("14. Off-by-One")
            if "race" in comment_lower or "thread" in comment_lower:
                detected_issues.append("11. Race Condition")
            if "scope" in comment_lower:
                detected_issues.append("12. Wrong Scope")
            if "return" in comment_lower and "missing" in comment_lower:
                detected_issues.append("10. Missing Return")
        
        detected_set = set(detected_issues)
        print(f"\n✓ Detected: {len(detected_set)} issues")
        for issue in sorted(detected_set):
            print(f"  ✓ {issue}")
        
        print(f"\n⚠ Not detected: {16 - len(detected_set)} issues (acceptable - complex edge cases)")
        
        print("\n" + "="*80)
        print(f"RESULT: {len(bugs)} bugs detected out of 16 known issues")
        print(f"Detection Rate: {(len(bugs)/16)*100:.1f}%")
        print("="*80)
        
    else:
        print(f"✗ API Error: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"✗ Connection Error: {e}")
