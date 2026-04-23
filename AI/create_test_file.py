#!/usr/bin/env python3
"""Test with first 3 lines only."""
import sys
import shutil

# Read first 3 lines
with open('claims.txt', 'r') as f:
    lines = f.readlines()[:3]

# Write to temp test file
with open('test_claims_small.txt', 'w') as f:
    f.writelines(lines)

print("Test file created with 3 lines")
print("Lines:")
for i, line in enumerate(lines, 1):
    print(f"  {i}: {line.strip()}")
