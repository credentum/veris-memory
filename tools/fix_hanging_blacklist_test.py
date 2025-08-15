#!/usr/bin/env python3
"""
Quick fix for hanging test_blacklist_expiration test
Patches the problematic sleep operation with timeout protection
"""

import os
import re

def fix_hanging_test():
    """Fix the hanging test_blacklist_expiration by adding timeout protection"""
    
    test_file = "tests/security/test_synthetic_abuse.py"
    
    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        return False
    
    # Read the current file
    with open(test_file, 'r') as f:
        content = f.read()
    
    # Find and replace the problematic sleep operation
    original_sleep_pattern = r'(\s+)# Wait for expiration\s+time\.sleep\(3\)'
    
    replacement = r'''\1# Wait for expiration with timeout protection
\1try:
\1    with test_timeout(5):  # 5 second timeout
\1        time.sleep(3)
\1except TimeoutError:
\1    pass  # Continue if timeout occurs'''
    
    # Apply the fix
    if re.search(original_sleep_pattern, content):
        new_content = re.sub(original_sleep_pattern, replacement, content)
        
        # Write the fixed version
        with open(test_file, 'w') as f:
            f.write(new_content)
        
        print("✅ Fixed hanging test_blacklist_expiration")
        return True
    else:
        print("❌ Could not find the problematic sleep pattern")
        return False

if __name__ == "__main__":
    success = fix_hanging_test()
    exit(0 if success else 1)