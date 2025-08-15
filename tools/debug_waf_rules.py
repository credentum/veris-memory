#!/usr/bin/env python3
"""
Debug WAF Rule Loading
Sprint 10 Phase 3 - Debug why OWASP patterns aren't being applied
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "context-store"))

from src.security.waf import WAFFilter

def debug_waf_rules():
    """Debug WAF rule loading and pattern matching"""
    
    waf = WAFFilter()
    
    print("=== WAF Configuration Debug ===")
    print(f"WAF enabled: {waf.config.is_enabled()}")
    print(f"Number of rules in config: {len(waf.config.rules)}")
    
    # List all rule names
    print("\n=== Available Rules ===")
    for rule_name in waf.config.rules.keys():
        print(f"- {rule_name}")
    
    # Test specific OWASP patterns that were failing
    owasp_test_payloads = {
        "A04_insecure_design": {"role": "admin"},  # Should match privilege_escalation
        "A05_security_misconfig": {"debug": "true"},  # Should match debug_mode_exposure
        "A06_vulnerable_components": {"version": "1.0.0"},  # Should match version_disclosure  
        "A10_ssrf": {"url": "http://localhost:6379"},  # Should match ssrf_protection
    }
    
    print("\n=== Testing OWASP Patterns ===")
    for test_name, payload in owasp_test_payloads.items():
        print(f"\nTesting {test_name}: {payload}")
        result = waf.check_request(payload)
        print(f"  Blocked: {result.blocked}")
        if result.blocked:
            print(f"  Rule: {result.rule}")
            print(f"  Severity: {result.severity}")
        else:
            print("  ❌ Not blocked - investigating...")
            
            # Check if patterns exist and match
            combined_text = " ".join(f"{k} {v}" for k, v in payload.items())
            print(f"  Combined text: '{combined_text}'")
            
            # Check each rule manually
            for rule_name, rule in waf.config.rules.items():
                if rule.enabled and rule.compiled_pattern:
                    if rule.compiled_pattern.search(combined_text):
                        print(f"  🔍 Pattern match found in rule '{rule_name}': {rule.pattern}")
                        print(f"     Action: {rule.action}")
                        if rule.action == "block":
                            print(f"     ⚠️  Should have been blocked but wasn't!")

if __name__ == "__main__":
    debug_waf_rules()