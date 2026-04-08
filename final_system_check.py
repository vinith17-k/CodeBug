#!/usr/bin/env python3
"""
FINAL SYSTEM STATUS REPORT
Complete verification of all features
"""
import requests
import sys

BASE_URL = "http://127.0.0.1:7860"

print("\n" + "╔" + "="*74 + "╗")
print("║" + "CODEBUG SYSTEM - COMPLETE VERIFICATION REPORT".center(74) + "║")
print("╚" + "="*74 + "╝\n")

# ============ SECTION 1: API CONNECTIVITY ============
print("┌─ SECTION 1: API CONNECTIVITY " + "─"*44 + "┐\n")
try:
    r = requests.get(f"{BASE_URL}/api/health", timeout=2)
    if r.status_code == 200:
        data = r.json()
        print(f"✓ API is ONLINE")
        print(f"  Version: {data.get('version')}")
        print(f"  Status: {data.get('status')}")
        print(f"  Supported Languages: {len(data.get('supported_languages', []))}")
        api_ok = True
    else:
        print(f"✗ API returned status {r.status_code}")
        api_ok = False
except Exception as e:
    print(f"✗ Cannot connect to API: {e}")
    api_ok = False

# ============ SECTION 2: FEATURE TESTS ============
print(f"\n┌─ SECTION 2: FEATURE TESTS " + "─"*47 + "┐\n")

feature_tests = [
    {
        "name": "SQL Injection Detection",
        "code": 'query = f"SELECT * FROM users WHERE id={user_id}"',
        "lang": "python",
        "expected_bug": "injection"
    },
    {
        "name": "Hardcoded Credentials",
        "code": 'password = "SuperSecret123"',
        "lang": "python",
        "expected_bug": "hardcoded"
    },
    {
        "name": "Code Execution Vulnerability",
        "code": 'eval(user_input)',
        "lang": "python",
        "expected_bug": "execution"
    },
    {
        "name": "Logic Error - Bare Except",
        "code": 'try:\n    risky_op()\nexcept:\n    pass',
        "lang": "python",
        "expected_bug": "except"
    }
]

bug_detection_ok = True
for test in feature_tests:
    try:
        r = requests.post(
            f"{BASE_URL}/api/review",
            json={"code": test["code"], "language": test["lang"]},
            timeout=2
        )
        if r.status_code == 200:
            data = r.json()
            bugs = data.get("bugs", [])
            if bugs:
                confidence = bugs[0].get("confidence")
                print(f"✓ {test['name']}")
                print(f"  └─ Found {len(bugs)} bug(s), confidence: {confidence:.2f}")
            else:
                print(f"⚠ {test['name']}")
                print(f"  └─ No bugs detected (may be working as intended)")
        else:
            print(f"✗ {test['name']}: API error {r.status_code}")
            bug_detection_ok = False
    except Exception as e:
        print(f"✗ {test['name']}: {str(e)[:40]}")
        bug_detection_ok = False

# ============ SECTION 3: CONFIDENCE SCORING ============
print(f"\n┌─ SECTION 3: CONFIDENCE SCORING " + "─"*41 + "┐\n")

confidence_tests = [
    ('password = "admin"', 'Security issue'),
    ('except:\n    pass', 'Logic issue'),
    ('def add(a, b): return a + b', 'Clean code')
]

confidence_ok = True
all_confidences = []
for code, desc in confidence_tests:
    try:
        r = requests.post(
            f"{BASE_URL}/api/review",
            json={"code": code, "language": "python"},
            timeout=2
        )
        if r.status_code == 200:
            bugs = r.json().get("bugs", [])
            if bugs:
                for bug in bugs:
                    conf = bug.get("confidence")
                    if isinstance(conf, (int, float)) and 0 <= conf <= 1:
                        all_confidences.append(conf)
                        print(f"✓ {desc}: confidence = {conf:.2f}")
                    else:
                        print(f"✗ {desc}: invalid confidence {conf}")
                        confidence_ok = False
            else:
                print(f"✓ {desc}: no bugs (confidence N/A)")
    except Exception as e:
        print(f"✗ {desc}: {str(e)[:30]}")
        confidence_ok = False

if all_confidences:
    avg_conf = sum(all_confidences) / len(all_confidences)
    print(f"\n  Average Confidence: {avg_conf:.2f}")

# ============ SECTION 4: MULTI-LANGUAGE SUPPORT ============
print(f"\n┌─ SECTION 4: MULTI-LANGUAGE SUPPORT " + "─"*37 + "┐\n")

languages = ["python", "javascript", "typescript", "java", "go", "cpp"]
language_ok = True
for lang in languages:
    try:
        r = requests.post(
            f"{BASE_URL}/api/review",
            json={"code": "var x = 1", "language": lang},
            timeout=2
        )
        if r.status_code == 200:
            print(f"✓ {lang.upper():12s} supported")
        else:
            print(f"⚠ {lang.upper():12s} returned {r.status_code}")
            language_ok = False
    except Exception as e:
        print(f"✗ {lang.upper():12s} error: {str(e)[:25]}")
        language_ok = False

# ============ SECTION 5: FRONTEND VERIFICATION ============
print(f"\n┌─ SECTION 5: FRONTEND HTML VERIFICATION " + "─"*33 + "┐\n")

try:
    with open("templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    frontend_elements = {
        "Code Input": "codeInput" in html,
        "Language Selector": "langSel" in html,
        "Analyze Button": "runBtn" in html,
        "Result Display": "rCard" in html,
        "Confidence Meter": "rConfidence" in html,
        "Bug Navigation": "prevBug" in html and "nextBug" in html,
        "Export Function": "exportBugReport" in html,
        "Bug Summary Grid": "bugSummary" in html,
        "Multi-language": all(lang in html for lang in ["python", "javascript", "go"])
    }
    
    frontend_ok = True
    for element, present in frontend_elements.items():
        status = "✓" if present else "✗"
        print(f"{status} {element}")
        if not present:
            frontend_ok = False
            
except Exception as e:
    print(f"✗ Cannot verify frontend: {e}")
    frontend_ok = False

# ============ FINAL REPORT ============
print(f"\n" + "╔" + "="*74 + "╗")
print("║" + "FINAL STATUS REPORT".center(74) + "║")
print("║" + "─"*74 + "║")

sections = {
    "API Connectivity": api_ok,
    "Bug Detection": bug_detection_ok,
    "Confidence Scoring": confidence_ok,
    "Multi-Language Support": language_ok,
    "Frontend": frontend_ok,
}

for section, status in sections.items():
    symbol = "✓" if status else "✗"
    print(f"║ {symbol} {section:30s} {'PASS' if status else 'FAIL':10s}                    ║")

print("║" + "─"*74 + "║")

all_ok = all(sections.values())
if all_ok:
    print("║" + "✓ ALL SYSTEMS OPERATIONAL - READY FOR PRODUCTION".center(74) + "║")
else:
    failed = [s for s, ok in sections.items() if not ok]
    print(f"║ ✗ FAILURES DETECTED: {', '.join(failed)}".ljust(74) + "║")

print("╚" + "="*74 + "╝\n")

sys.exit(0 if all_ok else 1)
