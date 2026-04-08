#!/usr/bin/env python3
"""Comprehensive bug detection test"""
import sys
sys.path.insert(0, '.')
from main import analyze_code_comprehensively

# Test 1: SQL Injection
sql_injection_code = '''
def get_user(uid):
    q = f"SELECT * FROM users WHERE id={uid}"
    cursor.execute(q)
    return cursor.fetchone()
'''

print("=" * 60)
print("TEST 1: SQL Injection Detection")
print("=" * 60)
bugs = analyze_code_comprehensively(sql_injection_code, 'python')
print(f"Bugs found: {len(bugs)}")
for i, bug in enumerate(bugs, 1):
    print(f"\n  [{i}] {bug['comment']}")
    print(f"      Severity: {bug['severity']}, Confidence: {bug['confidence']}")
    print(f"      Category: {bug['category']}")

# Test 2: Multiple Security Issues
multi_issue_code = '''
import os
password = "admin123"
query = "SELECT * FROM users WHERE pwd=" + user_input
eval(user_code)
os.system(command)
'''

print("\n" + "=" * 60)
print("TEST 2: Multiple Security Issues")
print("=" * 60)
bugs = analyze_code_comprehensively(multi_issue_code, 'python')
print(f"Bugs found: {len(bugs)}")
for i, bug in enumerate(bugs, 1):
    print(f"\n  [{i}] {bug['comment']}")
    print(f"      Severity: {bug['severity']}, Confidence: {bug['confidence']}")
    print(f"      Category: {bug['category']}")

# Test 3: Logic Errors
logic_code = '''
items = [1, 2, 3, 4, 5]
for i in range(len(items)-1):
    items[i] = items[i] * 2

try:
    result = int("not a number")
except:
    pass
'''

print("\n" + "=" * 60)
print("TEST 3: Logic Errors")
print("=" * 60)
bugs = analyze_code_comprehensively(logic_code, 'python')
print(f"Bugs found: {len(bugs)}")
for i, bug in enumerate(bugs, 1):
    print(f"\n  [{i}] {bug['comment']}")
    print(f"      Severity: {bug['severity']}, Confidence: {bug['confidence']}")
    print(f"      Category: {bug['category']}")

# Test 4: Clean Code
clean_code = '''
def add(a, b):
    """Add two numbers."""
    return a + b

result = add(5, 3)
'''

print("\n" + "=" * 60)
print("TEST 4: Clean Code (Should be 0 bugs)")
print("=" * 60)
bugs = analyze_code_comprehensively(clean_code, 'python')
print(f"Bugs found: {len(bugs)}")
if bugs:
    for i, bug in enumerate(bugs, 1):
        print(f"\n  [{i}] {bug['comment']}")

# Test 5: Multi-language Support
test_cases = [
    ('js_code', 'var password = "admin123"; eval(userInput);', 'javascript'),
    ('java_code', 'String query = "SELECT * FROM users WHERE id=" + userId;', 'java'),
    ('go_code', 'cmd := "SELECT * FROM users WHERE id=" + userId', 'go'),
]

print("\n" + "=" * 60)
print("TEST 5: Multi-Language Support")
print("=" * 60)
for name, code, lang in test_cases:
    bugs = analyze_code_comprehensively(code, lang)
    print(f"\n{lang.upper()}: {len(bugs)} bugs")
    for bug in bugs[:2]:  # Show first 2
        print(f"  - {bug['comment'][:60]}... (conf: {bug['confidence']})")

print("\n" + "=" * 60)
print("✓ ALL TESTS COMPLETED")
print("=" * 60)
