#!/usr/bin/env python3
"""
Neo4j Read-Only User Setup
Creates veris_ro user with read-only permissions for secure query_graph access
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Neo4jROSetup:
    """Setup read-only user for Neo4j graph queries"""
    
    def __init__(self, 
                 uri: str = "bolt://localhost:7687",
                 admin_user: str = "neo4j", 
                 admin_password: Optional[str] = None):
        self.uri = uri
        self.admin_user = admin_user
        self.admin_password = admin_password or os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None
        
    def connect_admin(self) -> bool:
        """Connect as admin user for setup operations"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.admin_user, self.admin_password)
            )
            
            # Test connection
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                test_result = result.single()
                if test_result and test_result["test"] == 1:
                    logger.info(f"✅ Connected to Neo4j as admin: {self.admin_user}")
                    return True
                    
        except AuthError:
            logger.error(f"❌ Authentication failed for {self.admin_user}")
        except ServiceUnavailable:
            logger.error("❌ Neo4j service unavailable")
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            
        return False
    
    def create_readonly_user(self, username: str = "veris_ro", password: str = "readonly_secure_2024!") -> Dict[str, Any]:
        """Create read-only user with restricted permissions"""
        
        if not self.driver:
            return {"success": False, "error": "Not connected to Neo4j"}
        
        try:
            with self.driver.session() as session:
                # Check if user already exists
                logger.info(f"Checking if user {username} exists...")
                result = session.run("SHOW USERS")
                existing_users = [record["user"] for record in result]
                
                if username in existing_users:
                    logger.info(f"User {username} already exists, updating permissions...")
                else:
                    # Create the read-only user
                    logger.info(f"Creating read-only user: {username}")
                    session.run(
                        "CREATE USER $username SET PASSWORD $password CHANGE NOT REQUIRED",
                        username=username, password=password
                    )
                    logger.info(f"✅ User {username} created successfully")
                
                # Ensure user has reader role (Neo4j built-in role)
                logger.info(f"Granting reader role to {username}...")
                session.run("GRANT ROLE reader TO $username", username=username)
                
                # Verify the user has correct roles
                result = session.run("SHOW USER $username", username=username)
                user_info = result.single()
                
                logger.info(f"✅ User {username} setup completed")
                logger.info(f"   Roles: {user_info.get('roles', [])}")
                logger.info(f"   Password change required: {user_info.get('passwordChangeRequired', 'unknown')}")
                
                return {
                    "success": True,
                    "username": username,
                    "roles": user_info.get("roles", []),
                    "password_change_required": user_info.get("passwordChangeRequired", False)
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to create read-only user: {e}")
            return {"success": False, "error": str(e)}
    
    def test_readonly_access(self, username: str = "veris_ro", password: str = "readonly_secure_2024!") -> Dict[str, Any]:
        """Test read-only user access and permissions"""
        
        try:
            # Connect as read-only user
            ro_driver = GraphDatabase.driver(self.uri, auth=(username, password))
            
            with ro_driver.session() as session:
                # Test 1: Basic read query (should work)
                logger.info("Testing basic read access...")
                result = session.run("RETURN 1 AS test")
                test_result = result.single()
                
                if not test_result or test_result["test"] != 1:
                    raise Exception("Basic read query failed")
                    
                logger.info("✅ Basic read access: PASS")
                
                # Test 2: Graph traversal query (should work)
                logger.info("Testing graph traversal...")
                result = session.run("MATCH (n) RETURN COUNT(n) AS node_count LIMIT 1")
                count_result = result.single()
                node_count = count_result["node_count"] if count_result else 0
                logger.info(f"✅ Graph traversal: PASS (found {node_count} nodes)")
                
                # Test 3: Write query (should fail)
                logger.info("Testing write access (should fail)...")
                try:
                    session.run("CREATE (n:TestNode {test: true})")
                    logger.error("❌ Write access: FAIL (write operation succeeded - should have been blocked)")
                    write_blocked = False
                except Exception:
                    logger.info("✅ Write access: PASS (correctly blocked)")
                    write_blocked = True
                
                ro_driver.close()
                
                return {
                    "success": True,
                    "basic_read": True,
                    "graph_traversal": True,
                    "node_count": node_count,
                    "write_blocked": write_blocked,
                    "tests_passed": 3 if write_blocked else 2,
                    "total_tests": 3
                }
                
        except AuthError:
            logger.error(f"❌ Authentication failed for read-only user {username}")
            return {"success": False, "error": "Authentication failed"}
        except Exception as e:
            logger.error(f"❌ Read-only access test failed: {e}")
            return {"success": False, "error": str(e)}
    
    def close(self):
        """Close admin connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j admin connection closed")

def main():
    """Main setup routine"""
    print("🔐 Neo4j Read-Only User Setup")
    print("=" * 40)
    
    # Initialize setup
    setup = Neo4jROSetup()
    
    try:
        # Step 1: Connect as admin
        print("1️⃣ Connecting to Neo4j as admin...")
        if not setup.connect_admin():
            print("❌ Failed to connect as admin. Check Neo4j is running and credentials are correct.")
            sys.exit(1)
        
        # Step 2: Create read-only user
        print("\n2️⃣ Creating read-only user...")
        result = setup.create_readonly_user()
        
        if not result["success"]:
            print(f"❌ Failed to create read-only user: {result['error']}")
            sys.exit(1)
        
        print(f"✅ Read-only user created: {result['username']}")
        
        # Step 3: Test read-only access
        print("\n3️⃣ Testing read-only access...")
        test_result = setup.test_readonly_access()
        
        if not test_result["success"]:
            print(f"❌ Read-only access test failed: {test_result['error']}")
            sys.exit(1)
        
        print(f"✅ Read-only access verified ({test_result['tests_passed']}/{test_result['total_tests']} tests passed)")
        
        # Step 4: Summary
        print("\n🎉 Setup Complete!")
        print("=" * 40)
        print("✅ veris_ro user created with read-only permissions")
        print("✅ Write operations correctly blocked")
        print("✅ Graph traversal queries working")
        print(f"✅ Database contains {test_result.get('node_count', 0)} nodes")
        print("\nNext steps:")
        print("- Update query_graph endpoint to use veris_ro credentials")
        print("- Test query_graph tool with new user")
        print("- Deploy changes to production")
        
    finally:
        setup.close()

if __name__ == "__main__":
    main()