#!/usr/bin/env python
"""Test the new LLM-powered API"""

import requests
import json
import time

BASE_URL = "http://localhost:7860"

# Test code with SQL injection
test_code = '''def get_user(uid):
    q = f"SELECT * FROM users WHERE id={uid}"
    cursor.execute(q)
    return cursor.fetchone()
'''

print("=" * 60)
print("TEST 1: SQL Injection Detection (LLM)")
print("=" * 60)

payload = {
    "code": test_code,
    "language": "python"
}

try:
    response = requests.post(f"{BASE_URL}/api/review", json=payload, timeout=10)
    print(f"Status: {response.status_code}")
    
    data = response.json()
    print(f"\n✓ Bugs found: {data.get('bugs_found', 0)}")
    
    if data.get('bugs'):
        for i, bug in enumerate(data['bugs'], 1):
            print(f"\nBug #{i}:")
            print(f"  Category: {bug.get('category')}")
            print(f"  Severity: {bug.get('severity')}/5")
            print(f"  Confidence: {bug.get('confidence', 0):.2f}")
            print(f"  Comment: {bug.get('comment', 'N/A')}")
    
    print(f"\nAverage Confidence: {data.get('analysis_metadata', {}).get('average_confidence', 'N/A')}")
    
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 60)
print("TEST 2: Clean Code")
print("=" * 60)

clean_code = '''def add(a, b):
    return a + b
'''

payload = {
    "code": clean_code,
    "language": "python"
}

try:
    response = requests.post(f"{BASE_URL}/api/review", json=payload, timeout=10)
    print(f"Status: {response.status_code}")
    
    data = response.json()
    print(f"✓ Bugs found: {data.get('bugs_found', 0)}")
    
    if data.get('primary_bug'):
        bug = data['primary_bug']
        print(f"  Result: {bug.get('comment', 'No issues')}")
        print(f"  Confidence: {bug.get('confidence', 1.0)}")
        
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 60)
print("DONE!")
print("=" * 60)
