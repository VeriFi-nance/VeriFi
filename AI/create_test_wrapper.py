#!/usr/bin/env python3
"""Wrapper to test new_main.py with just first 5 lines"""

import sys
import os

# Read current new_main.py
with open('new_main.py', 'r') as f:
    content = f.read()

# Create test version that processes only first 5 lines
test_content = content.replace(
    'run_verifi_extraction(debug=False)',
    'lines = open("claims.txt").readlines()[:5]\nwith open("test_claims_5.txt", "w") as f:\n    f.writelines(lines)\nrun_verifi_extraction("test_claims_5.txt", "test_output.txt", debug=False)'
)

with open('new_main_test.py', 'w') as f:
    f.write(test_content)

print("Created new_main_test.py - testing with 5 lines only")
print("\nFirst 5 lines from claims.txt:")
with open('claims.txt', 'r') as f:
    for i, line in enumerate(f.readlines()[:5], 1):
        print(f"  {i}: {line.strip()[:60]}...")
