#!/usr/bin/env python3
"""
Pre-commit hook to detect hardcoded secrets and passwords.

Prevents accidental commit of credentials.
"""

import re
import sys


# Patterns that indicate potential hardcoded secrets
SECRET_PATTERNS = [
    (r'password\s*=\s*["\'](?!\$\{)[a-zA-Z0-9]{8,}["\']', "Hardcoded password"),
    (r'api_key\s*=\s*["\'](?!\$\{)[a-zA-Z0-9]{20,}["\']', "Hardcoded API key"),
    (r'secret\s*=\s*["\'](?!\$\{)[a-zA-Z0-9]{16,}["\']', "Hardcoded secret"),
    (r'token\s*=\s*["\'](?!\$\{)[a-zA-Z0-9]{20,}["\']', "Hardcoded token"),
    (r'requirepass\s+(?!\$)[a-zA-Z0-9]{8,}', "Hardcoded Redis password"),
]

# Allowed patterns (environment variable references)
ALLOWED_PATTERNS = [
    r'\$\{.*\}',  # ${VAR}
    r'\$[A-Z_]+',  # $VAR
    r'example',  # Example values
    r'your-.*',  # Placeholder text
]


def is_allowed(value):
    """Check if value is an allowed pattern (env var reference, placeholder)"""
    for pattern in ALLOWED_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            return True
    return False


def scan_file(filepath):
    """Scan file for hardcoded secrets"""
    errors = []

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        for line_num, line in enumerate(content.split('\n'), 1):
            # Skip comments
            if line.strip().startswith('#'):
                continue

            for pattern, description in SECRET_PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    matched_text = match.group(0)

                    # Skip if it's an allowed pattern
                    if is_allowed(matched_text):
                        continue

                    errors.append(
                        f"  Line {line_num}: {description} - {matched_text[:50]}..."
                    )

    except Exception as e:
        return [f"Error reading file: {e}"]

    return errors


def main():
    """Run validation on all provided files"""
    if len(sys.argv) < 2:
        print("Usage: validate_no_secrets.py <file>...")
        sys.exit(1)

    all_errors = []

    for filepath in sys.argv[1:]:
        errors = scan_file(filepath)
        if errors:
            all_errors.append(f"\n❌ {filepath}:")
            all_errors.extend(errors)

    if all_errors:
        print("\n🚨 SECURITY VIOLATION: Potential hardcoded secrets detected!")
        print("\n".join(all_errors))
        print("\n✅ FIX: Use environment variables like ${PASSWORD} instead of hardcoded values")
        sys.exit(1)

    print("✅ No hardcoded secrets detected")
    sys.exit(0)


if __name__ == "__main__":
    main()
