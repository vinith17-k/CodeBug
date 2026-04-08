#!/usr/bin/env python3
"""Test CodeBug API functionality comprehensively"""

import requests
import json
import sys

BASE_URL = 'http://127.0.0.1:8000/api/review'

def test_case(name, code, language='python'):
    """Run a test case and print results"""
    print(f"\n{'='*70}")
    print(f"TEST: {name}")
    print(f"{'='*70}")
    
    try:
        response = requests.post(
            BASE_URL,
            json={'code': code, 'language': language},
            timeout=5
        )
        
        if response.status_code != 200:
            print(f"ERROR: Status {response.status_code}")
            print(response.text)
            return
        
        data = response.json()
        bugs_found = data.get('bugs_found', 0)
        
        print(f"✓ Bugs found: {bugs_found}")
        print(f"✓ Average confidence: {data['analysis_metadata'].get('average_confidence', 'N/A')}")
        
        bugs = data.get('bugs', [])
        if bugs:
            print(f"\nAll {len(bugs)} bugs:")
            for i, bug in enumerate(bugs[:15], 1):
                severity_map = {5: 'CRITICAL', 4: 'HIGH', 3: 'MEDIUM', 2: 'LOW', 1: 'INFO'}
                sev = severity_map.get(bug.get('severity', 0), '?')
                confidence = bug.get('confidence', 0)
                category = bug.get('category', '?')
                comment = bug.get('comment', '')[:55]
                has_languages = 'languages' in bug
                has_confidence = 'confidence' in bug
                print(f"  [{i:2}] {sev:8} | {category:8} | Conf:{confidence:5.2f} | {comment}")
                if not has_confidence:
                    print(f"        ⚠ MISSING 'confidence' field!")
                if not has_languages:
                    print(f"        ⚠ MISSING 'languages' field!")
        else:
            print(f"✓ No bugs found (clean code)")
            if data.get('primary_bug'):
                pb = data['primary_bug']
                print(f"  Primary: {pb.get('comment', '')}")
    
    except Exception as e:
        print(f"✗ ERROR: {str(e)}")

# Test 1: Clean code
test_case("CLEAN CODE", 'x = 1')

# Test 2: Simple hardcoded password
test_case("HARDCODED PASSWORD", 'password = "secret123"')

# Test 3: SQL Injection
test_case("SQL INJECTION", '''def get_user(uid):
    query = f"SELECT * FROM users WHERE id={uid}"
    cursor.execute(query)''')

# Test 4: Multiple bugs
test_case("MULTIPLE BUGS", '''def get_user(uid):
    pwd = "SecurePass123"
    query = f"SELECT * FROM users WHERE id={uid}"
    cursor.execute(query)
    
def proc(items=[]):
    for i in range(len(items)):
        items[i] *= 2
    except:
        pass
    
x = eval(input())''')

# Test 5: Complex with many issues
test_case("COMPLEX CODE", '''import sqlite3
def get_user(uid):
    password = "admin123"
    api_key = "sk_test_12345678"
    query = f"SELECT * FROM users WHERE id={uid}"
    cursor.execute(query)
    os.system(f"echo {uid}")
    return get_user(uid)
    
def process_list(items=[]):
    for i in range(len(items)):
        items[i] = items[i] * 2
    except:
        pass''')

print(f"\n{'='*70}")
print("Testing complete!")
print(f"{'='*70}")
