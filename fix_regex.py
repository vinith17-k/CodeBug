#!/usr/bin/env python3
"""Fix bad regex backreferences in main.py"""

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the bad pattern with the fixed one
# OLD: r'def\s+\w+.*:\s*.*return\s+\1\s*\('
# NEW: r'def\s+(\w+).*:\s*.*return\s+\1\s*\('
# The key change: \w+ -> (\w+) to create capturing group 1

bad_pattern = r"r'def\s+\w+.*:\s*.*return\s+\1\s*\('"
good_pattern = r"r'def\s+(\w+).*:\s*.*return\s+\1\s*\('"

# Use simple string replacement
fixed_content = content.replace(bad_pattern, good_pattern)

if fixed_content != content:
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    # Count replacements
    count = content.count(bad_pattern)
    print(f"SUCCESS: Fixed {count} regex backreference(s) in main.py")
else:
    print("No changes needed - pattern not found or already fixed")
