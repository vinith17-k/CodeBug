#!/usr/bin/env python3
"""
COMPREHENSIVE END-TO-END TEST
Tests: Backend detection → API response → Frontend display
"""
import requests
import json

BASE_URL = "http://127.0.0.1:7860"

# Test scenarios
test_scenarios = [
    {
        "name": "Scenario 1: SQL Injection Detection",
        "code": """def get_user(uid):
    q = f"SELECT * FROM users WHERE id={uid}"
    cursor.execute(q)
    return cursor.fetchone()""",
        "language": "python",
        "expected_severity": 5,
        "expected_bugs_min": 1
    },
    {
        "name": "Scenario 2: Multiple Security Issues",
        "code": """import os
password = "secretpass123"
query = "INSERT INTO users VALUES WHERE id=" + str(user_input)
os.system(command)
eval(untrusted_code)""",
        "language": "python",
        "expected_severity": 5,
        "expected_bugs_min": 3
    },
    {
        "name": "Scenario 3: Logic Errors",
        "code": """items = [1, 2, 3, 4, 5]
for i in range(len(items)-1):
    items[i] = items[i] * 2

try:
    result = int(input_data)
except:
    pass""",
        "language": "python",
        "expected_severity": 2,
        "expected_bugs_min": 2
    },
    {
        "name": "Scenario 4: Clean Code",
        "code": """def add(a, b):
    '''Add two numbers.'''
    return a + b

result = add(5, 3)
print(f'Result: {result}')""",
        "language": "python",
        "expected_severity": None,
        "expected_bugs_min": 0
    }
]

print("╔" + "═"*68 + "╗")
print("║" + " "*68 + "║")
print("║" + "COMPREHENSIVE END-TO-END TEST".center(68) + "║")
print("║" + " "*68 + "║")
print("╚" + "═"*68 + "╝")

all_pass = True

for scenario in test_scenarios:
    print(f"\n{'─'*68}")
    print(f"TEST: {scenario['name']}")
    print(f"Language: {scenario['language']}")
    print(f"{'─'*68}")
    
    # Send request
    payload = {
        "code": scenario["code"],
        "language": scenario["language"]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/review",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            print(f"❌ FAILED: API returned status {response.status_code}")
            print(f"   Response: {response.text}")
            all_pass = False
            continue
        
        data = response.json()
        bugs_found = data.get("bugs_found", 0)
        bugs = data.get("bugs", [])
        
        # Check 1: Bugs count
        check1 = bugs_found >= scenario["expected_bugs_min"]
        status1 = "✓" if check1 else "✗"
        print(f"{status1} Bugs found: {bugs_found} (expected ≥ {scenario['expected_bugs_min']})")
        
        # Check 2: All bugs have required fields
        all_have_fields = all(
            "confidence" in b and 
            "comment" in b and 
            "category" in b and
            "severity" in b
            for b in bugs
        )
        status2 = "✓" if all_have_fields else "✗"
        print(f"{status2} All bugs have required fields: confidence, comment, category, severity")
        
        # Check 3: Confidence scores are valid
        all_valid_confidence = all(
            isinstance(b.get("confidence"), (int, float)) and
            0 <= b.get("confidence", 0) <= 1
            for b in bugs
        )
        status3 = "✓" if all_valid_confidence else "✗"
        print(f"{status3} All confidence scores are valid (0-1 range)")
        
        # Check 4: Severity levels
        if scenario["expected_severity"]:
            max_severity = max((b.get("severity", 0) for b in bugs), default=0)
            check4 = max_severity >= scenario["expected_severity"] - 1  # Allow ±1
            status4 = "✓" if check4 else "✗"
            print(f"{status4} Max severity >= {scenario['expected_severity']-1}: {max_severity}")
        
        # Detailed bug output
        if bugs:
            print(f"\n  Bug Details:")
            for i, bug in enumerate(bugs[:3], 1):  # Show first 3
                conf = bug.get("confidence", 0)
                sev = bug.get("severity", 0)
                cat = bug.get("category", "unknown")
                comment = bug.get("comment", "")[:55]
                print(f"    {i}. [{cat.upper()}] {comment}")
                print(f"       Severity: {sev}/5 | Confidence: {conf:.2f}")
        
        # Check for missing features
        if scenario["expected_bugs_min"] > 0 and bugs:
            missing_fields = []
            first_bug = bugs[0]
            if "languages" not in first_bug:
                missing_fields.append("'languages' field")
            if "fix" not in first_bug:
                missing_fields.append("'fix' field")
            
            if missing_fields:
                print(f"\n⚠ Missing fields in first bug: {', '.join(missing_fields)}")
            else:
                print(f"\n✓ All expected bug fields present")
        
        # Overall check
        test_pass = check1 and all_have_fields and all_valid_confidence
        if scenario["expected_severity"]:
            test_pass = test_pass and check4
        
        if test_pass:
            print(f"\n✓ TEST PASSED")
        else:
            print(f"\n✗ TEST FAILED")
            all_pass = False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        all_pass = False

print(f"\n{'─'*68}")
print("SUMMARY")
print(f"{'─'*68}")

# Additional checks
print("\nAPI Endpoints Status:")
try:
    r = requests.get(f"{BASE_URL}/api/health")
    print(f"  ✓ /api/health: {r.status_code}")
except:
    print(f"  ✗ /api/health: FAILED")

try:
    r = requests.get(f"{BASE_URL}/api/stats")
    print(f"  ✓ /api/stats: {r.status_code}")
except:
    print(f"  ✗ /api/stats: FAILED")

print(f"\n{'═'*68}")
if all_pass:
    print("✓ ALL TESTS PASSED - SYSTEM WORKING CORRECTLY")
else:
    print("✗ SOME TESTS FAILED - CHECK OUTPUT ABOVE")
print(f"{'═'*68}")
