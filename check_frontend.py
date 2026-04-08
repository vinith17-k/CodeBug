#!/usr/bin/env python3
"""Test frontend HTML rendering and features"""
import os

html_file = "c:\\Users\\vinit\\Projects\\CodeBug\\templates\\index.html"

print("=" * 70)
print("FRONTEND FEATURE CHECK")
print("=" * 70)

with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read().lower()

# Check for key features
features = {
    "Confidence Meter Display": "confidence-meter",
    "Confidence Bar CSS": "confidence-bar",
    "Export Button": "export-btn",
    "Export Function": "exportbugreport()",
    "Language Selector": "language-select",
    "Bug Navigation (Prev)": "prevbug()",
    "Bug Navigation (Next)": "nextbug()",
    "Tab Display": "displaybug(",
    "Multi-language Dropdown": "typescript",
    "Go Language Support": '"go"',
    "Stats Display": "total-checked",
}

print("\nFeature Checklist:")
for feature, search_str in features.items():
    found = search_str in content
    status = "✓" if found else "✗"
    print(f"  {status} {feature}")

# Check file size
file_size = os.path.getsize(html_file)
print(f"\nFile Size: {file_size:,} bytes")

# Count specific patterns
bug_patterns = {
    "displayBug function": "function displaybug",
    "Navigate bugs": "function navigate",
    "Export JSON": "function exportbugreport",
    "Display confidence": "displayconfidence",
}

print("\nFunction Presence:")
for pattern_name, pattern in bug_patterns.items():
    count = content.count(pattern)
    status = "✓" if count > 0 else "✗"
    print(f"  {status} {pattern_name}")

print("\n" + "=" * 70)
print("✓ FRONTEND CHECK COMPLETED")
print("=" * 70)
