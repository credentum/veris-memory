#!/usr/bin/env python3
"""
Pre-commit hook to validate security documentation matches actual configurations.

Ensures docs stay in sync with docker-compose.yml and security scripts.
"""

import sys
import yaml
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.parent
DOCKER_COMPOSE = REPO_ROOT / "docker-compose.yml"
SECURITY_README = REPO_ROOT / "SECURITY_README.md"


def get_configured_ports():
    """Extract all port bindings from docker-compose.yml"""
    with open(DOCKER_COMPOSE) as f:
        config = yaml.safe_load(f)

    ports = []
    services = config.get("services", {})

    for service_name, service_config in services.items():
        service_ports = service_config.get("ports", [])
        for port in service_ports:
            port_str = str(port)
            # Extract port number
            if ":" in port_str:
                port_num = port_str.split(":")[-1].split("/")[0]
                ports.append((service_name, port_num))

    return ports


def validate_ports_documented():
    """Verify all critical ports are documented"""
    errors = []

    if not SECURITY_README.exists():
        return ["SECURITY_README.md not found"]

    with open(SECURITY_README) as f:
        readme_content = f.read()

    configured_ports = get_configured_ports()
    critical_ports = ["6379", "6333", "7474", "7687", "8000", "8001"]

    for port in critical_ports:
        if port not in readme_content:
            # Find which service uses this port
            service = next((svc for svc, p in configured_ports if p == port), "unknown")
            errors.append(
                f"  Port {port} ({service}) is configured but not documented in SECURITY_README.md"
            )

    return errors


def validate_localhost_binding_documented():
    """Verify localhost binding is documented"""
    errors = []

    if not SECURITY_README.exists():
        return []

    with open(SECURITY_README) as f:
        content = f.read()

    required_docs = [
        ("127.0.0.1", "Localhost binding documentation"),
        ("SSH tunnel", "Remote access documentation"),
        ("password", "Authentication documentation"),
    ]

    for keyword, description in required_docs:
        if keyword.lower() not in content.lower():
            errors.append(f"  Missing documentation: {description} ({keyword})")

    return errors


def main():
    """Run documentation validation"""
    all_errors = []

    # Validate ports are documented
    port_errors = validate_ports_documented()
    if port_errors:
        all_errors.append("\n❌ Port Documentation Issues:")
        all_errors.extend(port_errors)

    # Validate localhost binding is documented
    binding_errors = validate_localhost_binding_documented()
    if binding_errors:
        all_errors.append("\n❌ Security Configuration Documentation Issues:")
        all_errors.extend(binding_errors)

    if all_errors:
        print("\n🚨 DOCUMENTATION OUT OF SYNC WITH CONFIGURATION!")
        print("\n".join(all_errors))
        print("\n✅ FIX: Update SECURITY_README.md to match docker-compose.yml")
        sys.exit(1)

    print("✅ Security documentation matches configuration")
    sys.exit(0)


if __name__ == "__main__":
    main()
