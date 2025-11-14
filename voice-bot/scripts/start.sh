#!/bin/bash
# Voice-Bot startup script with SSL support

set -e

# Build uvicorn command
CMD="uvicorn app.main:app --host 0.0.0.0 --port 8002"

# Add SSL if certificates are configured
if [ -n "$SSL_KEYFILE" ] && [ -n "$SSL_CERTFILE" ]; then
    if [ -f "$SSL_KEYFILE" ] && [ -f "$SSL_CERTFILE" ]; then
        echo "🔐 Starting voice-bot with HTTPS enabled"
        echo "   Key: $SSL_KEYFILE"
        echo "   Cert: $SSL_CERTFILE"
        CMD="$CMD --ssl-keyfile=$SSL_KEYFILE --ssl-certfile=$SSL_CERTFILE"
    else
        echo "❌ SSL certificates not found:"
        echo "   Key: $SSL_KEYFILE (exists: $(test -f "$SSL_KEYFILE" && echo 'yes' || echo 'no'))"
        echo "   Cert: $SSL_CERTFILE (exists: $(test -f "$SSL_CERTFILE" && echo 'yes' || echo 'no'))"
        echo "⚠️  Falling back to HTTP"
    fi
else
    echo "⚠️  Starting voice-bot with HTTP (not HTTPS)"
    echo "   Microphone access requires HTTPS in most browsers"
    echo "   Set SSL_KEYFILE and SSL_CERTFILE environment variables to enable HTTPS"
fi

# Execute command
echo "Starting: $CMD"
exec $CMD
