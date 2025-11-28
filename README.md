# Sonatype IQ Server Version Checker

A Python script that monitors the Sonatype IQ Server release notes page for new versions and sends automated notifications via email and/or Slack when updates are detected.

## Features

- 🔍 Automatically checks for new Sonatype IQ Server versions
- 📧 Email notifications via SMTP
- 💬 Slack notifications via webhooks
- 🔄 Automatic retry logic with exponential backoff
- 🔐 Secure credential management via environment variables or .env files
- 🧪 Dry-run mode for testing without sending notifications
- 📝 Comprehensive logging with configurable verbosity
- ⚙️ Flexible configuration via command-line arguments, environment variables, or .env files
- 🛡️ Input sanitization and security best practices

## Requirements

- Python 3.6+
- `requests` library
- `python-dotenv` (optional, for .env file support)

## Installation

1. **Clone or download the script**
   ```bash
   git clone <repository-url>
   cd sonatype-version-checker
   ```

2. **Install required dependencies**
   ```bash
   pip install requests
   
   # Optional: for .env file support
   pip install python-dotenv
   ```

3. **Set up your configuration** (see Configuration section below)

## Configuration

The script supports three configuration methods (in order of precedence):

1. **Command-line arguments** (highest priority)
2. **Environment variables**
3. **.env file** (requires python-dotenv)

### Quick Start with .env File

1. **Copy the example configuration**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env with your credentials**
   ```bash
   nano .env
   ```

3. **Secure the file**
   ```bash
   chmod 600 .env
   ```

### Configuration Options

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SMTP_SERVER` | SMTP server hostname | smtp.office365.com | No |
| `SMTP_PORT` | SMTP server port | 587 | No |
| `EMAIL_USERNAME` | Email account username | - | If email enabled |
| `EMAIL_PASSWORD` | Email account password | - | If email enabled |
| `EMAIL_FROM` | From email address | - | If email enabled |
| `EMAIL_TO` | To email address | - | If email enabled |
| `SLACK_WEBHOOK_URL` | Slack webhook URL | - | If Slack enabled |
| `ENABLE_EMAIL` | Enable email notifications | false | No |
| `ENABLE_SLACK` | Enable Slack notifications | false | No |
| `VERSION_FILE` | Path to version tracking file | sonatype_last_version.txt | No |
| `DRY_RUN` | Test mode (no notifications sent) | false | No |

### Example .env File

```bash
# Email Configuration
EMAIL_USERNAME=alerts@yourcompany.com
EMAIL_PASSWORD=your_secure_password
EMAIL_FROM=sonatype-alerts@yourcompany.com
EMAIL_TO=devops-team@yourcompany.com
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587

# Slack Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Enable Notifications (false by default)
ENABLE_EMAIL=true
ENABLE_SLACK=true

# Optional Settings
VERSION_FILE=sonatype_last_version.txt
DRY_RUN=false
```

## Usage

### Basic Usage

**Enable email notifications:**
```bash
python sonatype_version_checker.py --enable-email
```

**Enable Slack notifications:**
```bash
python sonatype_version_checker.py --enable-slack
```

**Enable both:**
```bash
python sonatype_version_checker.py --enable-email --enable-slack
```

### Using Command-Line Arguments

**Provide credentials via command line:**
```bash
python sonatype_version_checker.py \
  --enable-email \
  --email-username "user@company.com" \
  --email-password "secret" \
  --email-from "alerts@company.com" \
  --email-to "team@company.com"
```

**Use Slack with command-line webhook:**
```bash
python sonatype_version_checker.py \
  --enable-slack \
  --slack-webhook "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### Testing

**Dry-run mode (no notifications sent):**
```bash
python sonatype_version_checker.py --dry-run --enable-email --enable-slack
```

**Verbose logging:**
```bash
python sonatype_version_checker.py --verbose --enable-email
```

**Test with dry-run and verbose:**
```bash
python sonatype_version_checker.py --dry-run --verbose --enable-email --enable-slack
```

### Get Help

```bash
python sonatype_version_checker.py --help
```

## Scheduling with Cron

### Method 1: Using .env File (Recommended)

```bash
# Edit crontab
crontab -e

# Add this line to check every hour
0 * * * * cd /path/to/script && /usr/bin/python3 sonatype_version_checker.py >> /var/log/sonatype_checker.log 2>&1
```

### Method 2: Using Environment Variables in Crontab

```bash
# Edit crontab
crontab -e

# Add environment variables at the top
EMAIL_USERNAME=user@company.com
EMAIL_PASSWORD=your_password
ENABLE_EMAIL=true
ENABLE_SLACK=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Add the cron job
0 * * * * /usr/bin/python3 /path/to/sonatype_version_checker.py >> /var/log/sonatype_checker.log 2>&1
```

### Method 3: Source Credentials File

```bash
# Create credentials file
cat > ~/.sonatype_credentials << 'EOF'
export EMAIL_USERNAME="user@company.com"
export EMAIL_PASSWORD="your_password"
export ENABLE_EMAIL="true"
export ENABLE_SLACK="true"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
EOF

# Secure it
chmod 600 ~/.sonatype_credentials

# In crontab
0 * * * * . ~/.sonatype_credentials && /usr/bin/python3 /path/to/sonatype_version_checker.py >> /var/log/sonatype_checker.log 2>&1
```

### Common Cron Schedules

```bash
# Every hour
0 * * * * <command>

# Every 6 hours
0 */6 * * * <command>

# Every day at 9 AM
0 9 * * * <command>

# Every Monday at 8 AM
0 8 * * 1 <command>

# Every 30 minutes
*/30 * * * * <command>
```

## How It Works

1. **Fetches** the Sonatype IQ Server release notes page
2. **Extracts** the latest version number using regex pattern matching
3. **Compares** with the last known version stored in a local file
4. **Notifies** via configured channels (email/Slack) if a new version is detected
5. **Updates** the version tracking file with the new version
6. **Retries** automatically on transient failures (up to 3 attempts)

### First Run Behavior

On the first run, the script will:
- Detect the current version
- Store it in the version file
- **NOT send any notifications** (to avoid false alerts)

Subsequent runs will compare against this stored version.

## Security Best Practices

### Credential Storage

✅ **DO:**
- Use `.env` files with `chmod 600` permissions
- Store credentials in environment variables
- Use secrets managers (AWS Secrets Manager, Azure Key Vault, HashiCorp Vault) in production
- Add `.env` to `.gitignore`
- Use `.env.example` as a template (committed to git)
- Rotate credentials regularly

❌ **DON'T:**
- Hardcode credentials in the script
- Commit `.env` files to version control
- Use world-readable permissions on credential files
- Share credentials via email or chat
- Log passwords in output

### File Permissions

```bash
# Secure your credentials file
chmod 600 .env

# Secure any credential files
chmod 600 ~/.sonatype_credentials

# Script itself can be executable
chmod 755 sonatype_version_checker.py
```

### .gitignore Setup

Add these lines to `.gitignore`:

```gitignore
# Environment variables
.env
.env.local
.env.*.local

# Credential files
*_credentials
*_credentials.txt

# Version tracking
sonatype_last_version.txt

# Python
__pycache__/
*.pyc
venv/
```

## Troubleshooting

### Script exits with "Configuration validation failed"

**Problem:** Required credentials are missing.

**Solution:** Ensure you've either:
- Set environment variables, OR
- Created a `.env` file with required values, OR
- Provided credentials via command-line arguments

AND enabled at least one notification method with `--enable-email` or `--enable-slack`.

### Email authentication fails

**Problem:** `Email authentication failed - check EMAIL_USERNAME and EMAIL_PASSWORD`

**Solutions:**
- Verify credentials are correct
- Check if your email provider requires an app-specific password
- Ensure SMTP server and port are correct for your provider
- Check if 2FA is enabled (may need app password)

### Slack webhook fails

**Problem:** `Failed to send Slack notification: 404` or `invalid_token`

**Solutions:**
- Verify webhook URL is complete and correct
- Check if webhook was revoked in Slack settings
- Ensure webhook URL starts with `https://hooks.slack.com/`

### Cron job not running

**Problem:** Script works manually but not via cron.

**Solutions:**
- Use absolute paths: `/usr/bin/python3` and `/full/path/to/script.py`
- Add `cd /path/to/script &&` before the command if using `.env` file
- Check cron logs: `grep CRON /var/log/syslog`
- Verify environment variables are set in crontab
- Test with: `* * * * * /usr/bin/env > /tmp/env.txt` to see cron's environment

### No version found

**Problem:** `No version found in page content`

**Solutions:**
- Check if the Sonatype URL is still valid
- Verify internet connectivity
- Check if page structure changed (may need to update regex pattern)
- Try with `--verbose` flag to see what's being fetched

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (no new version or notification sent successfully) |
| 1 | Failure (configuration error, network error, or notification failed) |

## Logging

The script logs to stdout/stderr with timestamps. To capture logs:

```bash
# Redirect to file
python sonatype_version_checker.py --enable-email >> sonatype.log 2>&1

# View logs in real-time
tail -f sonatype.log

# With cron, specify log file in crontab
0 * * * * /usr/bin/python3 /path/to/script.py >> /var/log/sonatype_checker.log 2>&1
```

## Getting Slack Webhook URL

1. Go to your Slack workspace
2. Navigate to **Apps** → **Manage** → **Custom Integrations** → **Incoming Webhooks**
3. Click **Add to Slack**
4. Choose a channel and click **Add Incoming WebHooks integration**
5. Copy the **Webhook URL**
6. Add it to your `.env` file or use via `--slack-webhook` argument

## Advanced Usage

### Call from Another Python Script

```python
import subprocess
import os

# Set up environment
env = os.environ.copy()
env['EMAIL_USERNAME'] = 'user@company.com'
env['EMAIL_PASSWORD'] = get_from_secure_store()
env['ENABLE_EMAIL'] = 'true'

# Run checker
result = subprocess.run(
    ['python3', 'sonatype_version_checker.py'],
    env=env,
    capture_output=True
)

if result.returncode == 0:
    print("Check completed successfully")
else:
    print(f"Check failed: {result.stderr.decode()}")
```

### Custom Version File Location

```bash
python sonatype_version_checker.py \
  --version-file /custom/path/version.txt \
  --enable-email
```

### Multiple Configurations

Run separate checks for different teams:

```bash
# Team A
EMAIL_TO=team-a@company.com VERSION_FILE=team_a_version.txt \
python sonatype_version_checker.py --enable-email

# Team B
EMAIL_TO=team-b@company.com VERSION_FILE=team_b_version.txt \
python sonatype_version_checker.py --enable-email
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

[Specify your license here]

## Support

For issues, questions, or feature requests, please:
- Open an issue on GitHub
- Contact: [your-contact-info]

## Changelog

### Version 2.0
- Added command-line argument support for all configuration options
- Added .env file support
- Changed default notification settings to disabled (must explicitly enable)
- Improved error handling and logging
- Added retry logic with exponential backoff
- Added dry-run mode
- Enhanced security with input sanitization
- Improved documentation

### Version 1.1
- Fixed shebang line
- Removed test assertions from main code
- Added proper SMTP_SERVER definition

### Version 1.0
- Initial release
- Basic version checking
- Email and Slack notifications