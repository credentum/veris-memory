# SSL Certificates Directory

This directory contains SSL certificates for the voice-bot HTTPS service.

## Setup

### Option 1: Self-Signed Certificates (Development/Testing)

Generate self-signed certificates:

```bash
bash scripts/generate-ssl-certs.sh self-signed localhost 365
```

This creates:
- `key.pem` - Private key
- `cert.pem` - Self-signed certificate
- `csr.pem` - Certificate signing request

⚠️ **Self-signed certificates will show browser warnings.** This is normal for development.

### Option 2: Let's Encrypt (Production)

For production with a public domain:

```bash
sudo bash scripts/generate-ssl-certs.sh letsencrypt your-domain.com
```

Requirements:
- Domain points to this server's public IP
- Port 80 accessible from internet
- No other service using port 80

## Required Files

Before deploying voice services, ensure these files exist:

```
voice-bot/certs/
├── key.pem    # Private key (keep secret!)
└── cert.pem   # SSL certificate
```

## Security

- **Never commit key.pem to git!** (It's in .gitignore)
- Permissions: key.pem should be 600, cert.pem should be 644
- For production, use certificates from a trusted CA

## Deployment

After generating certificates:

```bash
# Deploy voice services with SSL
docker compose -f docker-compose.yml -f docker-compose.voice.yml up -d

# Access voice-bot
https://localhost:8443  # or https://your-domain.com:8443
```

## Troubleshooting

### "Certificate not found" error

```bash
# Check files exist
ls -l voice-bot/certs/

# Should see:
# -rw------- key.pem
# -rw-r--r-- cert.pem
```

### Browser "Not Secure" warning (self-signed only)

This is expected with self-signed certificates. Click "Advanced" → "Proceed" to continue.

### Let's Encrypt renewal

Certificates auto-renew. To manually renew:

```bash
sudo certbot renew
sudo bash scripts/generate-ssl-certs.sh letsencrypt your-domain.com
```

## References

- [Let's Encrypt](https://letsencrypt.org/)
- [OpenSSL Documentation](https://www.openssl.org/docs/)
- [Nginx SSL Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)
