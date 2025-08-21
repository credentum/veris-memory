#!/bin/bash
# Setup Sentinel Watchdog Cron Job
# Run this script once to install the external Sentinel monitor

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WATCHDOG_SCRIPT="$SCRIPT_DIR/sentinel-watchdog.sh"

echo "Setting up Sentinel Watchdog cron job..."

# Create cron job entry (runs every 2 minutes)
CRON_ENTRY="*/2 * * * * $WATCHDOG_SCRIPT"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "sentinel-watchdog.sh"; then
    echo "Sentinel watchdog cron job already exists"
else
    # Add cron job
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    echo "✅ Sentinel watchdog cron job installed: runs every 2 minutes"
fi

# Create log directory
sudo mkdir -p /var/log
sudo touch /var/log/sentinel-watchdog.log
sudo chmod 666 /var/log/sentinel-watchdog.log

echo "✅ Sentinel Watchdog setup complete!"
echo ""
echo "🛡️ Security monitoring layers:"
echo "  1. Sentinel monitors 11 security checks"
echo "  2. Docker health check monitors Sentinel"
echo "  3. External watchdog monitors Docker health check"
echo "  4. Telegram alerts for critical failures"
echo ""
echo "To remove: crontab -e and delete the sentinel-watchdog.sh line"