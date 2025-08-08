#!/bin/bash
set -euo pipefail

# Secure Credential Setup for Context Store
# Replaces hardcoded passwords with systemd credentials
# Includes password complexity validation for production security

INSTALL_DIR=${INSTALL_DIR:-/opt/context-store}
CREDENTIALS_DIR="$INSTALL_DIR/credentials"
SERVICE_USER="context-store"
SERVICE_GROUP="context-store"

# Password complexity requirements
MIN_PASSWORD_LENGTH=12
REQUIRE_UPPERCASE=true
REQUIRE_LOWERCASE=true
REQUIRE_DIGITS=true
REQUIRE_SPECIAL=true
FORBIDDEN_PATTERNS=("password" "admin" "neo4j" "context" "store" "123456" "qwerty")

validate_password_complexity() {
    local password="$1"
    local errors=()
    
    # Check length
    if [ ${#password} -lt $MIN_PASSWORD_LENGTH ]; then
        errors+=("Password must be at least $MIN_PASSWORD_LENGTH characters long")
    fi
    
    # Check uppercase
    if [ "$REQUIRE_UPPERCASE" = true ] && ! echo "$password" | grep -q '[A-Z]'; then
        errors+=("Password must contain at least one uppercase letter")
    fi
    
    # Check lowercase  
    if [ "$REQUIRE_LOWERCASE" = true ] && ! echo "$password" | grep -q '[a-z]'; then
        errors+=("Password must contain at least one lowercase letter")
    fi
    
    # Check digits
    if [ "$REQUIRE_DIGITS" = true ] && ! echo "$password" | grep -q '[0-9]'; then
        errors+=("Password must contain at least one digit")
    fi
    
    # Check special characters
    if [ "$REQUIRE_SPECIAL" = true ] && ! echo "$password" | grep -q '[!@#$%^&*()_+\-=\[\]{};:,.<>?]'; then
        errors+=("Password must contain at least one special character (!@#\$%^&*()_+-=[]{}|;:,.<>?)")
    fi
    
    # Check forbidden patterns
    local password_lower=$(echo "$password" | tr '[:upper:]' '[:lower:]')
    for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
        if echo "$password_lower" | grep -q "$pattern"; then
            errors+=("Password must not contain common patterns like '$pattern'")
        fi
    done
    
    # Check for consecutive characters
    if echo "$password" | grep -q -E '(.)\1{2,}'; then
        errors+=("Password must not contain more than 2 consecutive identical characters")
    fi
    
    # Check for sequential patterns (123, abc, etc.)
    if echo "$password" | grep -q -E '(012|123|234|345|456|567|678|789|abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)'; then
        errors+=("Password must not contain sequential characters (123, abc, etc.)")
    fi
    
    # Return results
    if [ ${#errors[@]} -eq 0 ]; then
        return 0
    else
        echo "❌ Password complexity validation failed:" >&2
        for error in "${errors[@]}"; do
            echo "   - $error" >&2
        done
        return 1
    fi
}

generate_secure_password() {
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        # Generate password with mixed character types
        local password=$(openssl rand -base64 32 | tr -d "=+/" | head -c 16)
        
        # Ensure we have at least one of each required type by inserting them
        local uppercase=$(echo {A..Z} | tr -d ' ' | fold -w1 | shuf -n1)
        local lowercase=$(echo {a..z} | tr -d ' ' | fold -w1 | shuf -n1)  
        local digit=$(echo {0..9} | tr -d ' ' | fold -w1 | shuf -n1)
        local special=$(echo '!@#$%^&*()_+-=' | fold -w1 | shuf -n1)
        
        # Insert required characters at random positions
        password="${password:0:4}${uppercase}${password:4:4}${lowercase}${password:8:4}${digit}${password:12}${special}"
        
        # Shuffle the password to randomize positions
        password=$(echo "$password" | fold -w1 | shuf | tr -d '\n')
        
        if validate_password_complexity "$password" 2>/dev/null; then
            echo "$password"
            return 0
        fi
        
        ((attempt++))
    done
    
    # Fallback to simpler generation if complex generation fails
    echo "W3lcome@$(openssl rand -base64 12 | tr -d '=+/' | head -c 8)!"
}

echo "🔐 Setting up secure credentials for Context Store..."

# Create dedicated service user and group
if ! getent group "$SERVICE_GROUP" > /dev/null 2>&1; then
    sudo groupadd --system "$SERVICE_GROUP"
    echo "✅ Created service group: $SERVICE_GROUP"
fi

if ! getent passwd "$SERVICE_USER" > /dev/null 2>&1; then
    sudo useradd --system --gid "$SERVICE_GROUP" --home-dir "$INSTALL_DIR" \
        --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
    echo "✅ Created service user: $SERVICE_USER"
else
    echo "✅ Service user already exists: $SERVICE_USER"
fi

# Create and secure install directory structure
sudo mkdir -p "$INSTALL_DIR/logs" "$INSTALL_DIR/data"
sudo chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
sudo chmod 755 "$INSTALL_DIR"

# Create credentials directory with secure permissions
if [ ! -d "$CREDENTIALS_DIR" ]; then
    sudo mkdir -p "$CREDENTIALS_DIR"
    sudo chmod 700 "$CREDENTIALS_DIR"
    sudo chown root:root "$CREDENTIALS_DIR"
    echo "✅ Created secure credentials directory: $CREDENTIALS_DIR"
fi

# Setup NEO4J password
NEO4J_PASSWORD_FILE="$CREDENTIALS_DIR/neo4j_password"

if [ ! -f "$NEO4J_PASSWORD_FILE" ]; then
    echo "📝 Setting up NEO4J password..."
    
    # Check if password provided as environment variable
    if [ -n "${NEO4J_PASSWORD:-}" ]; then
        echo "Using NEO4J_PASSWORD from environment"
        
        # Validate provided password
        if validate_password_complexity "$NEO4J_PASSWORD"; then
            echo "✅ Provided password meets complexity requirements"
            echo -n "$NEO4J_PASSWORD" | sudo tee "$NEO4J_PASSWORD_FILE" > /dev/null
        else
            echo "⚠️  Provided password does not meet complexity requirements"
            echo "   Using secure generated password instead..."
            GENERATED_PASSWORD=$(generate_secure_password)
            echo -n "$GENERATED_PASSWORD" | sudo tee "$NEO4J_PASSWORD_FILE" > /dev/null
            echo "✅ Generated secure NEO4J password: $GENERATED_PASSWORD"
            echo "   (Save this password - you'll need it for NEO4J configuration)"
        fi
    else
        # Generate secure password that meets complexity requirements
        echo "Generating secure password with complexity validation..."
        GENERATED_PASSWORD=$(generate_secure_password)
        echo -n "$GENERATED_PASSWORD" | sudo tee "$NEO4J_PASSWORD_FILE" > /dev/null
        echo "✅ Generated secure NEO4J password: $GENERATED_PASSWORD"
        echo "   (Save this password - you'll need it for NEO4J configuration)"
        
        # Verify the generated password
        if validate_password_complexity "$GENERATED_PASSWORD" 2>/dev/null; then
            echo "✅ Generated password meets all complexity requirements"
        else
            echo "⚠️  Warning: Generated password may not meet all complexity requirements"
        fi
    fi
    
    # Set secure permissions
    sudo chmod 600 "$NEO4J_PASSWORD_FILE"
    sudo chown root:root "$NEO4J_PASSWORD_FILE"
    echo "✅ NEO4J password credential secured with proper permissions"
else
    echo "✅ NEO4J password credential already exists"
    
    # Validate existing password if possible (optional check)
    if [ -r "$NEO4J_PASSWORD_FILE" ]; then
        EXISTING_PASSWORD=$(sudo cat "$NEO4J_PASSWORD_FILE")
        if validate_password_complexity "$EXISTING_PASSWORD" 2>/dev/null; then
            echo "✅ Existing password meets complexity requirements"
        else
            echo "⚠️  Warning: Existing password may not meet current complexity requirements"
            echo "   Consider regenerating with: rm $NEO4J_PASSWORD_FILE && $0"
        fi
    fi
fi

# Update application to read from systemd credentials
echo "📋 Creating credential helper script..."

cat > "$INSTALL_DIR/load-credentials.py" << 'EOF'
#!/usr/bin/env python3
"""
Credential loader for systemd credentials
Reads passwords from CREDENTIALS_DIRECTORY set by systemd
"""
import os
import sys

def load_neo4j_password():
    """Load NEO4J password from systemd credentials"""
    credentials_dir = os.environ.get('CREDENTIALS_DIRECTORY')
    
    if credentials_dir:
        # Running under systemd with credentials
        password_file = os.path.join(credentials_dir, 'neo4j_password')
        if os.path.exists(password_file):
            with open(password_file, 'r') as f:
                return f.read().strip()
    
    # Fallback to environment variable (for development)
    password = os.environ.get('NEO4J_PASSWORD')
    if password:
        return password
    
    # Fallback to .env.local file
    env_local = os.path.join(os.path.dirname(__file__), '.env.local')
    if os.path.exists(env_local):
        with open(env_local, 'r') as f:
            for line in f:
                if line.startswith('NEO4J_PASSWORD='):
                    return line.split('=', 1)[1].strip()
    
    raise ValueError("NEO4J_PASSWORD not found in systemd credentials, environment, or .env.local")

if __name__ == "__main__":
    try:
        password = load_neo4j_password()
        print(password)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
EOF

chmod +x "$INSTALL_DIR/load-credentials.py"

echo "✅ Credential setup complete!"
echo ""
echo "🔧 Next Steps:"
echo "   1. Update your NEO4J instance with the password shown above"
echo "   2. Restart the context-store service: sudo systemctl restart context-store"
echo "   3. Verify connection: sudo journalctl -u context-store -f"
echo ""
echo "🔐 Password Complexity Requirements:"
echo "   - Minimum length: $MIN_PASSWORD_LENGTH characters"
echo "   - Must contain: uppercase, lowercase, digits, special characters"
echo "   - Must not contain: common patterns (password, admin, 123456, etc.)"
echo "   - Must not have: sequential or repetitive characters"
echo ""
echo "💡 For local development:"
echo "   Create $INSTALL_DIR/.env.local with: NEO4J_PASSWORD=your_secure_password"
echo "   (Password must meet complexity requirements listed above)"

# Verify credentials setup
if [ -f "$NEO4J_PASSWORD_FILE" ]; then
    echo "🔍 Credential verification:"
    echo "   NEO4J password file: $(ls -la "$NEO4J_PASSWORD_FILE")"
    echo "   Can read credential: $(sudo test -r "$NEO4J_PASSWORD_FILE" && echo "✅ Yes" || echo "❌ No")"
fi