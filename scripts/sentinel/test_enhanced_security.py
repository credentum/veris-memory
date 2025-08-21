#!/usr/bin/env python3
"""
Test enhanced SSH security patterns to verify python/perl blocking.
"""

import os
import sys
import tempfile

# Add the sentinel directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from ssh_security_manager import SSHSecurityManager
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

def test_enhanced_code_execution_blocking():
    """Test that all forms of code execution are properly blocked."""
    if not SECURITY_AVAILABLE:
        print("⏭️ SSH Security Manager not available")
        return None
        
    try:
        # Create minimal config
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as audit_file, \
             tempfile.NamedTemporaryFile(mode='w', delete=False) as session_file:
            
            config = {
                'ssh_config': {'host': 'test', 'user': 'test', 'key_path': '/tmp/test'},
                'audit_log_path': audit_file.name,
                'session_log_path': session_file.name
            }
            
            ssh_mgr = SSHSecurityManager(config)
            
            # Test various code execution patterns that should be blocked
            dangerous_code_commands = [
                'python script.py',
                'python3 -c "print(\'test\')"',
                'python /path/to/script.py',
                'perl script.pl',
                'perl -e "print \'test\'"',
                'ruby script.rb',
                'node app.js',
                'java -cp . MyClass',
                'gcc -o output source.c',
                'g++ -o output source.cpp'
            ]
            
            blocked_count = 0
            for cmd in dangerous_code_commands:
                if not ssh_mgr._validate_command(cmd):
                    blocked_count += 1
                    print(f"✅ Blocked: {cmd}")
                else:
                    print(f"❌ ALLOWED: {cmd}")
            
            # Cleanup
            os.unlink(audit_file.name)
            os.unlink(session_file.name)
            
            # All should be blocked
            success = blocked_count == len(dangerous_code_commands)
            print(f"\nBlocked {blocked_count}/{len(dangerous_code_commands)} dangerous code execution commands")
            
            return success
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    """Run enhanced security tests."""
    print("🔒 Enhanced SSH Security Test")
    print("=" * 40)
    
    result = test_enhanced_code_execution_blocking()
    
    if result is True:
        print("\n✅ Enhanced security patterns working correctly!")
        return 0
    elif result is False:
        print("\n❌ Enhanced security patterns failed!")
        return 1
    else:
        print("\n⚠️ Enhanced security tests could not run")
        return 2

if __name__ == '__main__':
    sys.exit(main())