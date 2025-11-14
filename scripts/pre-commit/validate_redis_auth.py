#!/usr/bin/env python3
"""
Pre-commit hook to validate Redis authentication is configured.

Ensures Redis requires password authentication and all services use it.
"""

import sys
import yaml


def validate_redis_auth(filepath):
    """Check that Redis requires password and services use authenticated URLs"""
    errors = []

    with open(filepath) as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return [f"YAML parsing error: {e}"]

    services = config.get("services", {})

    # Check Redis service
    redis_service = services.get("redis")
    if redis_service:
        command = redis_service.get("command", "")
        command_str = " ".join(command) if isinstance(command, list) else str(command)

        if "--requirepass" not in command_str:
            errors.append("  Redis service MUST include '--requirepass ${REDIS_PASSWORD}'")

        if "${REDIS_PASSWORD}" not in command_str and "$REDIS_PASSWORD" not in command_str:
            errors.append("  Redis MUST use REDIS_PASSWORD environment variable")

        # Check healthcheck
        healthcheck = redis_service.get("healthcheck", {})
        test_command = healthcheck.get("test", [])
        test_str = " ".join(test_command) if isinstance(test_command, list) else str(test_command)

        if "-a" not in test_str and "--auth" not in test_str:
            errors.append("  Redis healthcheck MUST use '-a' flag for authentication")

    # Check all services using Redis
    for service_name, service_config in services.items():
        env_vars = service_config.get("environment", [])

        # Convert to dict if list
        if isinstance(env_vars, list):
            env_dict = {}
            for item in env_vars:
                if "=" in str(item):
                    key, value = str(item).split("=", 1)
                    env_dict[key.strip()] = value.strip()
        else:
            env_dict = env_vars

        redis_url = env_dict.get("REDIS_URL", "")

        if redis_url and "redis://" in redis_url:
            # Redis URL must include password
            if ":${REDIS_PASSWORD}@" not in redis_url and "::${REDIS_PASSWORD}@" not in redis_url:
                errors.append(
                    f"  Service '{service_name}' uses Redis WITHOUT password. "
                    f"Must use 'redis://:${{REDIS_PASSWORD}}@redis:6379'"
                )

    return errors


def main():
    """Run validation on all provided files"""
    if len(sys.argv) < 2:
        print("Usage: validate_redis_auth.py <file>...")
        sys.exit(1)

    all_errors = []

    for filepath in sys.argv[1:]:
        if not filepath.endswith(('.yml', '.yaml')):
            continue

        errors = validate_redis_auth(filepath)
        if errors:
            all_errors.append(f"\n❌ {filepath}:")
            all_errors.extend(errors)

    if all_errors:
        print("\n🚨 SECURITY VIOLATION: Redis authentication not configured!")
        print("\n".join(all_errors))
        print("\n✅ FIX: Ensure Redis uses --requirepass and all services use authenticated URLs")
        sys.exit(1)

    print("✅ Redis authentication correctly configured")
    sys.exit(0)


if __name__ == "__main__":
    main()
