import json
import random

# 1. Define 5 clean Python code snippets
SNIPPETS = [
    {
        "id": "login_func",
        "description": "Standard login function with parameterized database query",
        "code": """def login(username, password):
    # Secure parameterized query
    query = "SELECT * FROM users WHERE username = ? AND password = ?"
    user = db.execute(query, (username, password))
    if user:
        return True
    return False"""
    },
    {
        "id": "money_transfer",
        "description": "Transfer money between accounts with balance check",
        "code": """def transfer(from_account, to_account, amount):
    if from_account.balance >= amount:
        from_account.balance -= amount
        to_account.balance += amount
        return True
    return False"""
    },
    {
        "id": "password_saver",
        "description": "Save a password securely after hashing",
        "code": """import hashlib

def save_password(password):
    # Hash password before saving
    hashed = hashlib.sha256(password.encode()).hexdigest()
    db.save_user_password(hashed)"""
    },
    {
        "id": "find_max",
        "description": "Find the maximum value in a list",
        "code": """def find_max(numbers):
    if not numbers:
        return None
    max_val = numbers[0]
    for i in range(len(numbers)):
        if numbers[i] > max_val:
            max_val = numbers[i]
    return max_val"""
    },
    {
        "id": "word_counter",
        "description": "Count occurrences of words in a string",
        "code": """def count_words(text):
    words = text.split()
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return counts"""
    }
]

# 2. Define 4 bug injector functions

def inject_off_by_one(snippet):
    """Changes range(len(x)) to range(len(x) - 1)"""
    if "range(len(" in snippet["code"]:
        # Find the specific range pattern
        import re
        pattern = r"range\(len\((.*?)\)\)"
        if re.search(pattern, snippet["code"]):
            buggy_code = re.sub(pattern, r"range(len(\1) - 1)", snippet["code"])
            return {
                "snippet_id": snippet["id"],
                "buggy_code": buggy_code,
                "bug": {
                    "type": "logic",
                    "severity": 3,
                    "description": "Off-by-one error: the loop range is shortened, so the last element will be skipped.",
                    "line_hint": None # Will calculate in build
                }
            }
    return None

def inject_sql_injection(snippet):
    """Changes parameterized query to f-string interpolation"""
    if snippet["id"] == "login_func" and "SELECT" in snippet["code"]:
        buggy_code = snippet["code"].replace(
            'query = "SELECT * FROM users WHERE username = ? AND password = ?"',
            'query = f"SELECT * FROM users WHERE username = \'{username}\' AND password = \'{password}\'"'
        ).replace(
            'user = db.execute(query, (username, password))',
            'user = db.execute(query)'
        )
        return {
            "snippet_id": snippet["id"],
            "buggy_code": buggy_code,
            "bug": {
                "type": "security",
                "severity": 5,
                "description": "SQL Injection vulnerability: using f-strings for database queries allows attackers to execute arbitrary SQL.",
                "line_hint": None
            }
        }
    return None

def inject_wrong_operator(snippet):
    """Changes >= to > in a balance check"""
    if "balance >= amount" in snippet["code"]:
        buggy_code = snippet["code"].replace("balance >= amount", "balance > amount")
        return {
            "snippet_id": snippet["id"],
            "buggy_code": buggy_code,
            "bug": {
                "type": "logic",
                "severity": 4,
                "description": "Logic error: balance check uses '>' instead of '>=', preventing transfers when balance matches exactly.",
                "line_hint": None
            }
        }
    return None

def inject_plain_password(snippet):
    """Removes hashing so password is stored as plain text"""
    if "hashlib.sha256" in snippet["code"]:
        lines = snippet["code"].splitlines()
        new_lines = []
        for line in lines:
            if "import hashlib" in line:
                continue
            if "hashed =" in line:
                new_lines.append(line.replace("hashlib.sha256(password.encode()).hexdigest()", "password"))
                continue
            if "db.save_user_password(hashed)" in line:
                new_lines.append(line)
                continue
            new_lines.append(line)
        
        buggy_code = "\n".join(new_lines)
        return {
            "snippet_id": snippet["id"],
            "buggy_code": buggy_code,
            "bug": {
                "type": "security",
                "severity": 5,
                "description": "Security flaw: password is stored in plain text without any hashing mechanism.",
                "line_hint": None
            }
        }
    return None

def get_line_hint(original, buggy):
    """Helper to find the first line number that differs"""
    orig_lines = original.splitlines()
    bug_lines = buggy.splitlines()
    for i, (o, b) in enumerate(zip(orig_lines, bug_lines)):
        if o != b:
            return i + 1
    return 1

# 3. Define build_bug_bank()
def build_bug_bank():
    bank = []
    injectors = [
        inject_off_by_one,
        inject_sql_injection,
        inject_wrong_operator,
        inject_plain_password
    ]
    
    episode_counter = 1
    
    for snippet in SNIPPETS:
        for inject in injectors:
            result = inject(snippet)
            if result:
                # Add metadata
                result["episode_id"] = f"ep_{episode_counter:03d}"
                # Calculate line hint if not provided
                if result["bug"]["line_hint"] is None:
                    result["bug"]["line_hint"] = get_line_hint(snippet["code"], result["buggy_code"])
                
                bank.append(result)
                episode_counter += 1
                
    return bank

# 4. Define save_bank()
def save_bank(bank):
    episodes = []
    answers = []
    
    for entry in bank:
        # What the AI sees
        episodes.append({
            "episode_id": entry["episode_id"],
            "snippet_id": entry["snippet_id"],
            "code": entry["buggy_code"]
        })
        
        # The private answer key
        answers.append({
            "episode_id": entry["episode_id"],
            "snippet_id": entry["snippet_id"],
            "bug": entry["bug"]
        })
        
    with open("episodes.json", "w") as f:
        json.dump(episodes, f, indent=4)
        
    with open("answers.json", "w") as f:
        json.dump(answers, f, indent=4)

# 5. Main block
if __name__ == "__main__":
    print("Building Bug Bank...")
    bug_bank = build_bug_bank()
    save_bank(bug_bank)
    print(f"Success! Created {len(bug_bank)} training episodes.")
    print("Files saved: episodes.json, answers.json")
