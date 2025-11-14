#!/usr/bin/env python3
"""
Pre-commit hook to validate all Docker ports are bound to localhost (127.0.0.1).

Prevents accidental exposure of services to the internet.
"""

import re
import sys
import yaml


def validate_localhost_bindings(filepath):
    """Check that all ports in docker-compose are bound to 127.0.0.1"""
    errors = []

    with open(filepath) as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return [f"YAML parsing error: {e}"]

    services = config.get("services", {})

    for service_name, service_config in services.items():
        ports = service_config.get("ports", [])

        for port_mapping in ports:
            port_str = str(port_mapping)

            # Skip if it's a comment or already bound to localhost
            if "#" in port_str and "127.0.0.1:" in port_str.split("#")[0]:
                continue

            if not port_str.startswith("127.0.0.1:"):
                errors.append(
                    f"  Service '{service_name}': Port '{port_str}' MUST start with '127.0.0.1:' "
                    f"to prevent internet exposure"
                )

    return errors


def main():
    """Run validation on all provided files"""
    if len(sys.argv) < 2:
        print("Usage: validate_localhost_bindings.py <file>...")
        sys.exit(1)

    all_errors = []

    for filepath in sys.argv[1:]:
        if not filepath.endswith(('.yml', '.yaml')):
            continue

        errors = validate_localhost_bindings(filepath)
        if errors:
            all_errors.append(f"\n❌ {filepath}:")
            all_errors.extend(errors)

    if all_errors:
        print("\n🚨 SECURITY VIOLATION: Ports not bound to localhost!")
        print("\n".join(all_errors))
        print("\n✅ FIX: Change port bindings from '8000:8000' to '127.0.0.1:8000:8000'")
        sys.exit(1)

    print("✅ All ports correctly bound to localhost (127.0.0.1)")
    sys.exit(0)


if __name__ == "__main__":
    main()
