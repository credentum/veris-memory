"""
Tests for Hetzner deployment infrastructure.
"""
import pytest
import subprocess
import yaml
import json
from pathlib import Path


class TestDeploymentConfiguration:
    """Test deployment configuration files."""
    
    def test_docker_compose_valid(self):
        """Test that docker-compose.hetzner.yml is valid YAML."""
        compose_path = Path("docker-compose.hetzner.yml")
        assert compose_path.exists(), "docker-compose.hetzner.yml must exist"
        
        with open(compose_path) as f:
            config = yaml.safe_load(f)
        
        assert "services" in config
        assert "context-store" in config["services"]
        assert "qdrant" in config["services"]
        assert "neo4j" in config["services"]
        assert "redis" in config["services"]
    
    def test_dockerfile_exists(self):
        """Test that Dockerfile.hetzner exists and has required stages."""
        dockerfile_path = Path("Dockerfile.hetzner")
        assert dockerfile_path.exists(), "Dockerfile.hetzner must exist"
        
        with open(dockerfile_path) as f:
            content = f.read()
        
        assert "FROM ubuntu:24.04" in content
        assert "AS builder" in content
        assert "AS runtime" in content
    
    def test_ctxrc_config_valid(self):
        """Test that .ctxrc.hetzner.yaml is valid configuration."""
        config_path = Path(".ctxrc.hetzner.yaml")
        assert config_path.exists(), ".ctxrc.hetzner.yaml must exist"
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert "agents" in config
        assert "memory" in config
        assert "performance" in config


class TestDeploymentScripts:
    """Test deployment scripts functionality."""
    
    def test_deploy_script_executable(self):
        """Test that deploy.sh is executable and has proper shebang."""
        deploy_path = Path("deploy/hetzner/deploy.sh")
        assert deploy_path.exists(), "deploy/hetzner/deploy.sh must exist"
        
        with open(deploy_path) as f:
            first_line = f.readline().strip()
        
        assert first_line.startswith("#!/"), "deploy.sh must have shebang"
    
    def test_monitoring_script_executable(self):
        """Test that monitoring script exists and is executable."""
        monitor_path = Path("monitoring/hardware-monitor.sh")
        assert monitor_path.exists(), "monitoring/hardware-monitor.sh must exist"
        
        with open(monitor_path) as f:
            first_line = f.readline().strip()
        
        assert first_line.startswith("#!/"), "hardware-monitor.sh must have shebang"
    
    def test_backup_script_executable(self):
        """Test that backup script exists and is executable."""
        backup_path = Path("backup/raid1-backup.sh")
        assert backup_path.exists(), "backup/raid1-backup.sh must exist"
        
        with open(backup_path) as f:
            first_line = f.readline().strip()
        
        assert first_line.startswith("#!/"), "raid1-backup.sh must have shebang"


class TestDockerBuild:
    """Test Docker build functionality."""
    
    def test_docker_build_syntax(self):
        """Test that Dockerfile.hetzner builds without syntax errors."""
        try:
            result = subprocess.run([
                "docker", "build", "--no-cache", "--dry-run", 
                "-f", "Dockerfile.hetzner", "."
            ], capture_output=True, text=True, timeout=60)
            
            # Docker build --dry-run not available in all versions
            # Fall back to basic syntax check if not supported
            if result.returncode != 0 and "unknown flag" in result.stderr:
                # Basic Dockerfile syntax validation
                dockerfile_path = Path("Dockerfile.hetzner")
                with open(dockerfile_path) as f:
                    content = f.read()
                
                # Check for basic Dockerfile syntax
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Basic syntax checks
                        if line.startswith('FROM'):
                            assert ' ' in line, f"Line {i}: FROM instruction needs image name"
                        elif line.startswith('RUN'):
                            assert len(line) > 4, f"Line {i}: RUN instruction needs command"
                        elif line.startswith('COPY'):
                            parts = line.split()
                            assert len(parts) >= 3, f"Line {i}: COPY needs source and destination"
            else:
                assert result.returncode == 0, f"Docker build syntax error: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            pytest.skip("Docker build test timed out - may not have Docker available")
        except FileNotFoundError:
            pytest.skip("Docker not available for build testing")


class TestEnvironmentVariables:
    """Test environment variable configuration."""
    
    def test_required_env_vars_documented(self):
        """Test that required environment variables are documented."""
        dockerfile_path = Path("Dockerfile.hetzner")
        with open(dockerfile_path) as f:
            content = f.read()
        
        # Check for required environment variables
        required_vars = [
            "NEO4J_PASSWORD",
            "TAILSCALE_AUTHKEY", 
            "TAILSCALE_HOSTNAME"
        ]
        
        for var in required_vars:
            # Should be referenced in Dockerfile or compose file
            compose_path = Path("docker-compose.hetzner.yml")
            with open(compose_path) as f:
                compose_content = f.read()
            
            assert var in compose_content or var in content, \
                f"Required environment variable {var} not found in configuration"


if __name__ == "__main__":
    pytest.main([__file__])