# Backup System Setup Guide

This guide explains how to securely configure the backup scripts for production use.

## 🔐 Security Configuration

### 1. Restic Password Configuration

**NEVER hardcode passwords in scripts!** Use one of these secure methods:

#### Option A: Environment File (Recommended for Production)

```bash
# Create secure config directory
sudo mkdir -p /etc/backup
sudo chmod 700 /etc/backup

# Create restic configuration
sudo tee /etc/backup/restic.conf << EOF
RESTIC_PASSWORD="$(openssl rand -base64 32)"
EOF

sudo chmod 600 /etc/backup/restic.conf
```

#### Option B: Environment Variable

```bash
# Add to /etc/environment (system-wide)
echo "RESTIC_PASSWORD=your_secure_password" | sudo tee -a /etc/environment

# Or add to user's .bashrc (user-specific)
echo "export RESTIC_PASSWORD=your_secure_password" >> ~/.bashrc
```

### 2. Telegram Alert Configuration

For monitoring alerts via Telegram:

```bash
# Get your bot token from @BotFather on Telegram
# Get your chat ID from @userinfobot on Telegram

# Create telegram configuration
sudo tee /etc/backup/telegram.conf << EOF
TELEGRAM_BOT_TOKEN="your_bot_token_here"
TELEGRAM_CHAT_ID="your_chat_id_here"
EOF

sudo chmod 600 /etc/backup/telegram.conf
```

### 3. Verify Secure Permissions

```bash
# Check permissions (should be 600 or 700)
ls -la /etc/backup/

# Output should show:
# drwx------  (700 for directory)
# -rw-------  (600 for files)
```

## 📦 Installation

### 1. Copy Scripts to /opt/scripts

```bash
sudo mkdir -p /opt/scripts
sudo cp scripts/backup-*.sh /opt/scripts/
sudo chmod +x /opt/scripts/backup-*.sh
```

### 2. Install Dependencies

```bash
# Install restic
sudo apt-get update
sudo apt-get install -y restic

# Or install latest version
wget https://github.com/restic/restic/releases/download/v0.16.2/restic_0.16.2_linux_amd64.bz2
bunzip2 restic_0.16.2_linux_amd64.bz2
chmod +x restic_0.16.2_linux_amd64
sudo mv restic_0.16.2_linux_amd64 /usr/local/bin/restic
```

### 3. Initialize Restic Repository

```bash
# Source the password
source /etc/backup/restic.conf

# Initialize repository
export RESTIC_REPOSITORY='/backup/restic-repo'
restic init

# Verify
restic snapshots
```

## ⏰ Cron Setup

### Daily Backups

```bash
# Edit crontab
sudo crontab -e

# Add backup jobs
# Daily backup at 2 AM
0 2 * * * /opt/scripts/backup-production-final.sh daily >> /var/log/backup-cron.log 2>&1

# Weekly backup on Sunday at 3 AM
0 3 * * 0 /opt/scripts/backup-production-final.sh weekly >> /var/log/backup-cron.log 2>&1

# Monthly backup on 1st of month at 4 AM
0 4 1 * * /opt/scripts/backup-production-final.sh monthly >> /var/log/backup-cron.log 2>&1

# Backup monitoring at 6 AM daily
0 6 * * * /opt/scripts/backup-monitor.sh >> /var/log/backup-monitor.log 2>&1
```

### Systemd Timer (Alternative to Cron)

Create `/etc/systemd/system/backup-daily.service`:

```ini
[Unit]
Description=Daily Backup Service
After=network.target docker.service

[Service]
Type=oneshot
EnvironmentFile=/etc/backup/restic.conf
EnvironmentFile=/etc/backup/telegram.conf
ExecStart=/opt/scripts/backup-production-final.sh daily
StandardOutput=append:/var/log/backup-cron.log
StandardError=append:/var/log/backup-cron.log
```

Create `/etc/systemd/system/backup-daily.timer`:

```ini
[Unit]
Description=Run daily backup at 2 AM

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable backup-daily.timer
sudo systemctl start backup-daily.timer
sudo systemctl status backup-daily.timer
```

## 🧪 Testing

### Test Configuration

```bash
# Test restic connection
export RESTIC_REPOSITORY='/backup/restic-repo'
source /etc/backup/restic.conf
restic check

# Test backup script (dry run concept)
/opt/scripts/backup-large-volumes.sh list

# Test monitoring script
/opt/scripts/backup-monitor.sh

# Check logs
tail -f /var/log/backup-cron.log
tail -f /var/log/backup-monitor.log
```

### Run Test Suite

```bash
# Install BATS if not already installed
sudo apt-get install bats shellcheck

# Run all tests
cd /path/to/veris-memory
bats tests/scripts/

# Run shellcheck
shellcheck scripts/backup-*.sh
```

## 📊 Monitoring

### Check Backup Status

```bash
# View recent backups
/opt/scripts/backup-large-volumes.sh list

# View backup statistics
/opt/scripts/backup-large-volumes.sh stats

# Check disk usage
df -h /backup

# Review logs
grep ERROR /var/log/backup-cron.log
grep WARN /var/log/backup-cron.log
```

### Telegram Alerts

The monitoring script will send alerts for:
- ⚠️ Disk usage > 90%
- 🚨 Backup failures (>2 in 24 hours)
- 📊 Daily backup summaries

## 🔄 Restore Procedures

### List Available Snapshots

```bash
source /etc/backup/restic.conf
export RESTIC_REPOSITORY='/backup/restic-repo'
restic snapshots
```

### Restore Specific Snapshot

```bash
# Restore to temporary location
restic restore latest --target /tmp/restore

# Or restore specific snapshot
restic restore abc123def --target /tmp/restore

# Or restore specific volume
restic restore latest --target /tmp/restore --path /tmp/restic-mounts/claude-workspace
```

### Restore Docker Volume

```bash
# Stop containers using the volume
docker-compose down

# Restore volume data
docker run --rm \
    -v claude-workspace:/target \
    -v /tmp/restore:/source \
    alpine sh -c "cp -a /source/. /target/"

# Restart containers
docker-compose up -d
```

## 🔒 Security Best Practices

1. **Never commit passwords to Git**
   - Use `.gitignore` for config files
   - Use environment variables or secure config files

2. **Restrict file permissions**
   - `/etc/backup/*` should be 600 (readable only by root)
   - Scripts in `/opt/scripts/` should be 755

3. **Encrypt backups at rest**
   - Restic encrypts by default
   - Store repository password securely

4. **Monitor backup success**
   - Set up Telegram alerts
   - Review logs regularly
   - Test restores periodically

5. **Implement least privilege**
   - Run backups as dedicated backup user
   - Grant minimal Docker permissions

## 📝 Maintenance

### Weekly Tasks

```bash
# Check backup repository integrity
restic check

# Review backup sizes
du -sh /backup/*

# Check for failed backups
grep -i "error\|failed" /var/log/backup-cron.log | tail -20
```

### Monthly Tasks

```bash
# Verify restore capability
restic restore latest --target /tmp/restore-test
diff -r /tmp/restore-test /original/data

# Clean up old logs
find /var/log -name "*backup*.log" -mtime +90 -delete

# Review and update retention policies
```

## 🆘 Troubleshooting

### Common Issues

**"RESTIC_PASSWORD not set" error:**
```bash
# Verify config file exists and is readable
ls -la /etc/backup/restic.conf
sudo cat /etc/backup/restic.conf
```

**"Volume not found" warnings:**
```bash
# List actual Docker volumes
docker volume ls

# Update volume list in scripts/backup-large-volumes.sh
```

**Disk space issues:**
```bash
# Check backup disk usage
df -h /backup

# Clean up old backups manually
sudo find /backup -name "backup-*" -mtime +30 -exec rm -rf {} \;

# Or use restic forget
restic forget --keep-daily 7 --keep-weekly 4 --prune
```

## 📚 References

- [Restic Documentation](https://restic.readthedocs.io/)
- [Docker Volume Backups](https://docs.docker.com/storage/volumes/#back-up-restore-or-migrate-data-volumes)
- [Backup Best Practices](https://www.backblaze.com/blog/the-3-2-1-backup-strategy/)
