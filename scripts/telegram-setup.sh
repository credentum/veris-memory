#!/bin/bash
# Telegram Configuration Setup Script
# This script ensures Telegram secrets are properly configured

set -e

echo "📱 Telegram Configuration Setup"
echo "==============================="

# Function to validate Telegram token format
validate_telegram_token() {
    local token=$1
    # Telegram bot tokens are typically in format: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
    if [[ $token =~ ^[0-9]+:[A-Za-z0-9_-]{35}$ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to validate Telegram chat ID format
validate_telegram_chat_id() {
    local chat_id=$1
    # Chat IDs are typically negative numbers for groups or positive for users
    if [[ $chat_id =~ ^-?[0-9]+$ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to test Telegram connection
test_telegram_connection() {
    local token=$1
    local chat_id=$2
    
    echo -n "Testing Telegram connection... "
    
    # Send a test message
    response=$(curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        -H "Content-Type: application/json" \
        -d "{\"chat_id\": \"${chat_id}\", \"text\": \"🔔 Veris Memory Telegram Alert Test\\n✅ Connection successful!\\n🕐 $(date)\"}" 2>&1)
    
    if echo "$response" | grep -q '"ok":true'; then
        echo "✅ SUCCESS - Test message sent!"
        return 0
    else
        echo "❌ FAILED"
        echo "  Response: $response"
        return 1
    fi
}

# Main logic
echo ""

# Check if running in GitHub Actions
if [ -n "$GITHUB_ACTIONS" ]; then
    echo "🤖 Running in GitHub Actions environment"
    
    # In GitHub Actions, secrets are passed as environment variables
    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
        echo "⚠️  Telegram secrets not provided in GitHub Actions"
        echo "   To enable Telegram alerting, add these secrets in GitHub:"
        echo "   - TELEGRAM_BOT_TOKEN"
        echo "   - TELEGRAM_CHAT_ID"
        exit 0  # Not an error, just optional feature
    fi
else
    echo "🖥️  Running in manual/local environment"
    
    # Check environment variables first
    if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
        # Try to read from .env file
        if [ -f .env ] && grep -q "^TELEGRAM_BOT_TOKEN=" .env; then
            export TELEGRAM_BOT_TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" .env | cut -d'=' -f2-)
        fi
    fi
    
    if [ -z "$TELEGRAM_CHAT_ID" ]; then
        # Try to read from .env file
        if [ -f .env ] && grep -q "^TELEGRAM_CHAT_ID=" .env; then
            export TELEGRAM_CHAT_ID=$(grep "^TELEGRAM_CHAT_ID=" .env | cut -d'=' -f2-)
        fi
    fi
    
    # If still not found, prompt user (if not in CI)
    if [ -z "$CI" ] && [ -z "$TELEGRAM_BOT_TOKEN" ]; then
        echo ""
        echo "📝 Telegram Bot Token not found."
        echo "   To create a bot:"
        echo "   1. Message @BotFather on Telegram"
        echo "   2. Send /newbot and follow instructions"
        echo "   3. Copy the token provided"
        echo ""
        read -p "Enter Telegram Bot Token (or press Enter to skip): " TELEGRAM_BOT_TOKEN
    fi
    
    if [ -z "$CI" ] && [ -z "$TELEGRAM_CHAT_ID" ] && [ -n "$TELEGRAM_BOT_TOKEN" ]; then
        echo ""
        echo "📝 Telegram Chat ID not found."
        echo "   To get your chat ID:"
        echo "   1. Message your bot"
        echo "   2. Visit: https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates"
        echo "   3. Look for 'chat':{'id': YOUR_CHAT_ID}"
        echo ""
        read -p "Enter Telegram Chat ID (or press Enter to skip): " TELEGRAM_CHAT_ID
    fi
fi

# Validate and configure if tokens are available
if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    echo ""
    echo "🔍 Validating Telegram configuration..."
    
    # Validate token format
    if ! validate_telegram_token "$TELEGRAM_BOT_TOKEN"; then
        echo "❌ ERROR: Invalid Telegram bot token format"
        echo "   Expected format: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        exit 1
    fi
    echo "  ✅ Bot token format valid"
    
    # Validate chat ID format
    if ! validate_telegram_chat_id "$TELEGRAM_CHAT_ID"; then
        echo "❌ ERROR: Invalid Telegram chat ID format"
        echo "   Expected format: -123456789 (negative for groups) or 123456789 (positive for users)"
        exit 1
    fi
    echo "  ✅ Chat ID format valid"
    
    # Test connection
    echo ""
    if test_telegram_connection "$TELEGRAM_BOT_TOKEN" "$TELEGRAM_CHAT_ID"; then
        echo ""
        echo "✅ Telegram configuration validated successfully!"
        
        # Update .env file
        echo ""
        echo "📝 Updating .env file..."
        
        # Remove existing Telegram entries
        if [ -f .env ]; then
            grep -v "^TELEGRAM_BOT_TOKEN=" .env > .env.tmp || true
            grep -v "^TELEGRAM_CHAT_ID=" .env.tmp > .env || true
            rm -f .env.tmp
        fi
        
        # Add new entries
        {
            echo "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}"
            echo "TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}"
        } >> .env
        
        echo "  ✅ .env file updated"
        
        # Export for current session
        export TELEGRAM_BOT_TOKEN
        export TELEGRAM_CHAT_ID
        
        echo ""
        echo "🎉 Telegram alerting is now configured!"
        echo "   Bot Token: ${TELEGRAM_BOT_TOKEN:0:10}...${TELEGRAM_BOT_TOKEN: -4}"
        echo "   Chat ID: $TELEGRAM_CHAT_ID"
        
    else
        echo ""
        echo "❌ Telegram connection test failed"
        echo "   Please check:"
        echo "   1. Bot token is correct"
        echo "   2. Chat ID is correct"
        echo "   3. Bot has been messaged at least once"
        echo "   4. Bot is not blocked"
        exit 1
    fi
else
    echo ""
    echo "⚠️  Telegram configuration skipped"
    echo "   Telegram alerting will not be available"
    echo "   To enable later, set these environment variables:"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - TELEGRAM_CHAT_ID"
fi

echo ""
echo "✅ Telegram setup complete"