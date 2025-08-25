# QR Code Asset Tracking System - Installation Guide

## Overview
This system consists of multiple Python scripts that work together to provide comprehensive QR code-based asset tracking:

1. **Raspberry Pi Scanner** (`qr_scanner.py`) - Scans QR codes and sends messages to RabbitMQ
2. **Message Processor** (`message_processor.py`) - Processes messages and updates external systems
3. **Database Service** (`database_updater.py`) - Handles local database operations and reporting
4. **Configuration** (`config.json`) - Centralized configuration file

## Prerequisites

### Hardware Requirements
- Raspberry Pi 4 (recommended) with camera module or USB webcam
- Network connectivity for all components
- Sufficient storage for database and logs

### Software Requirements
- Python 3.8 or higher
- RabbitMQ Server
- Domain Controller (Active Directory)
- Certificate Authority Server
- Email Server (SMTP)
- Tencent IES4 API access
- Apache SOLR instance

## Installation Steps

### 1. System Preparation

#### On Raspberry Pi:
```bash
# Copy configuration template
cp config.json /opt/qr_scanner/config.json

# Edit configuration with your settings
nano /opt/qr_scanner/config.json
```

#### Key Configuration Items to Update:

- **Domain Controller**: Update server address, credentials, and base DN
- **RabbitMQ**: Configure host, credentials, and queue names
- **Email Settings**: SMTP server configuration
- **Tencent IES4**: API endpoint and credentials
- **Apache SOLR**: Base URL and collection settings
- **QR Codes**: Add your location and object codes

### 4. RabbitMQ Setup

```bash
# Install RabbitMQ (on message broker server)
sudo apt install rabbitmq-server -y

# Enable RabbitMQ management plugin
sudo rabbitmq-plugins enable rabbitmq_management

# Create user and virtual host
sudo rabbitmqctl add_user qr_scanner_user your_password
sudo rabbitmqctl add_vhost /
sudo rabbitmqctl set_permissions -p / qr_scanner_user ".*" ".*" ".*"

# Access management interface at http://your-server:15672
```

### 5. Database Initialization

The SQLite database will be automatically created when the database service starts. To manually initialize:

```bash
# Run database service once to create tables
python3 database_updater.py
# Press Ctrl+C after initialization message appears
```

### 6. Service Installation

#### Create Systemd Service Files

**Scanner Service** (`/etc/systemd/system/qr-scanner.service`):
```ini
[Unit]
Description=QR Code Scanner Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/qr_scanner
Environment=PATH=/opt/qr_scanner/qr_scanner_env/bin
ExecStart=/opt/qr_scanner/qr_scanner_env/bin/python3 /opt/qr_scanner/qr_scanner.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Message Processor Service** (`/etc/systemd/system/qr-message-processor.service`):
```ini
[Unit]
Description=QR Message Processor Service
After=network.target rabbitmq.service
Wants=network.target

[Service]
Type=simple
User=qr_scanner
Group=qr_scanner
WorkingDirectory=/opt/qr_scanner
Environment=PATH=/opt/qr_scanner/qr_scanner_env/bin
ExecStart=/opt/qr_scanner/qr_scanner_env/bin/python3 /opt/qr_scanner/message_processor.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Database Service** (`/etc/systemd/system/qr-database.service`):
```ini
[Unit]
Description=QR Database Update Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=qr_scanner
Group=qr_scanner
WorkingDirectory=/opt/qr_scanner
Environment=PATH=/opt/qr_scanner/qr_scanner_env/bin
ExecStart=/opt/qr_scanner/qr_scanner_env/bin/python3 /opt/qr_scanner/database_updater.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable qr-scanner.service
sudo systemctl enable qr-message-processor.service
sudo systemctl enable qr-database.service

# Start services
sudo systemctl start qr-scanner.service
sudo systemctl start qr-message-processor.service
sudo systemctl start qr-database.service

# Check status
sudo systemctl status qr-scanner.service
sudo systemctl status qr-message-processor.service
sudo systemctl status qr-database.service
```

### 7. Log Rotation Setup

Create logrotate configuration (`/etc/logrotate.d/qr-scanner`):
```
/var/log/qr_scanner.log
/var/log/message_processor.log
/var/log/database_updater.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 qr_scanner qr_scanner
    postrotate
        systemctl reload qr-scanner.service
        systemctl reload qr-message-processor.service
        systemctl reload qr-database.service
    endscript
}
```

### 8. Directory Structure

Create the recommended directory structure:
```
/opt/qr_scanner/
├── config.json
├── qr_scanner.py
├── message_processor.py
├── database_updater.py
├── requirements.txt
├── qr_scanner_env/         # Python virtual environment
├── logs/                   # Application logs
├── data/                   # Database and data files
│   └── asset_tracking.db
└── scripts/                # Utility scripts
    ├── backup.sh
    ├── restore.sh
    └── health_check.sh
```

### 9. Security Considerations

#### File Permissions
```bash
# Set appropriate permissions
sudo chown -R qr_scanner:qr_scanner /opt/qr_scanner
sudo chmod 755 /opt/qr_scanner
sudo chmod 644 /opt/qr_scanner/*.py
sudo chmod 600 /opt/qr_scanner/config.json  # Protect credentials
```

#### Firewall Configuration
```bash
# Allow necessary ports
sudo ufw allow 5672/tcp   # RabbitMQ
sudo ufw allow 8983/tcp   # SOLR (if local)
sudo ufw allow 587/tcp    # SMTP
sudo ufw allow 443/tcp    # HTTPS for APIs
```

### 10. Testing and Validation

#### Test Individual Components

**Test Scanner (without camera)**:
```bash
# Activate environment
source /opt/qr_scanner/qr_scanner_env/bin/activate

# Test configuration loading
python3 -c "
import json
with open('config.json', 'r') as f:
    config = json.load(f)
print('Configuration loaded successfully')
print(f'Found {len(config[\"qr_codes\"][\"locations\"])} locations')
print(f'Found {len(config[\"qr_codes\"][\"objects\"])} objects')
"
```

**Test RabbitMQ Connection**:
```bash
python3 -c "
import pika
import json

with open('config.json', 'r') as f:
    config = json.load(f)

rabbitmq_config = config['rabbitmq']
credentials = pika.PlainCredentials(
    rabbitmq_config['username'],
    rabbitmq_config['password']
)

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=rabbitmq_config['host'],
        port=rabbitmq_config['port'],
        credentials=credentials
    )
)
print('RabbitMQ connection successful')
connection.close()
"
```

**Test Database Connection**:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/opt/qr_scanner/data/asset_tracking.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type=\"table\"')
tables = cursor.fetchall()
print(f'Database contains {len(tables)} tables')
for table in tables:
    print(f'  - {table[0]}')
conn.close()
"
```

### 11. Monitoring and Maintenance

#### Create Health Check Script (`/opt/qr_scanner/scripts/health_check.sh`):
```bash
#!/bin/bash

echo "=== QR Scanner System Health Check ==="
echo "Timestamp: $(date)"
echo

# Check services
echo "=== Service Status ==="
for service in qr-scanner qr-message-processor qr-database; do
    if systemctl is-active --quiet $service; then
        echo "✓ $service: RUNNING"
    else
        echo "✗ $service: STOPPED"
    fi
done

echo

# Check disk space
echo "=== Disk Usage ==="
df -h /opt/qr_scanner
echo

# Check recent log entries
echo "=== Recent Errors ==="
journalctl -u qr-scanner -u qr-message-processor -u qr-database --since "1 hour ago" -p err --no-pager -q

echo
echo "=== Database Stats ==="
sqlite3 /opt/qr_scanner/data/asset_tracking.db "
SELECT 
    'Total scans today: ' || COUNT(*) 
FROM asset_locations 
WHERE DATE(scan_timestamp) = DATE('now');

SELECT 
    'Active assets: ' || COUNT(*) 
FROM current_asset_positions;

SELECT 
    'Processing success rate: ' || 
    ROUND(
        (COUNT(CASE WHEN processing_status = 'success' THEN 1 END) * 100.0 / COUNT(*)), 2
    ) || '%'
FROM asset_locations 
WHERE DATE(scan_timestamp) = DATE('now');
"
```

#### Create Backup Script (`/opt/qr_scanner/scripts/backup.sh`):
```bash
#!/bin/bash

BACKUP_DIR="/opt/qr_scanner/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
sqlite3 /opt/qr_scanner/data/asset_tracking.db ".backup $BACKUP_DIR/asset_tracking_$DATE.db"

# Backup configuration
cp /opt/qr_scanner/config.json $BACKUP_DIR/config_$DATE.json

# Backup logs
tar -czf $BACKUP_DIR/logs_$DATE.tar.gz /var/log/qr_scanner.log /var/log/message_processor.log /var/log/database_updater.log 2>/dev/null

# Clean old backups (keep 30 days)
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

#### Schedule Regular Maintenance

Add to crontab (`crontab -e`):
```bash
# Daily backup at 2 AM
0 2 * * * /opt/qr_scanner/scripts/backup.sh >> /var/log/qr_backup.log 2>&1

# Health check every 15 minutes
*/15 * * * * /opt/qr_scanner/scripts/health_check.sh >> /var/log/qr_health.log 2>&1

# Weekly log cleanup
0 3 * * 0 find /var/log -name "qr_*.log" -mtime +7 -delete
```

## Troubleshooting

### Common Issues

1. **Camera not detected**:
   - Check camera connection
   - Verify camera is enabled in raspi-config
   - Test with `raspistill -o test.jpg`

2. **RabbitMQ connection failed**:
   - Verify RabbitMQ service is running
   - Check network connectivity
   - Validate credentials in config.json

3. **High CPU usage**:
   - Increase scan_interval in config
   - Disable preview mode
   - Check for memory leaks

4. **Messages not being processed**:
   - Check RabbitMQ queue status
   - Verify external API connectivity
   - Review processing logs

### Log Locations
- Scanner: `/var/log/qr_scanner.log`
- Message Processor: `/var/log/message_processor.log`
- Database Service: `/var/log/database_updater.log`
- System logs: `journalctl -u qr-scanner`

### Performance Tuning

1. **Scanner Optimization**:
   - Adjust camera resolution
   - Tune detection parameters
   - Implement frame skipping

2. **Database Optimization**:
   - Regular VACUUM operations
   - Index optimization
   - Archival of old data

3. **Network Optimization**:
   - Connection pooling
   - Retry mechanisms
   - Circuit breakers for external APIs

## Security Best Practices

1. **Credential Management**:
   - Use environment variables for sensitive data
   - Implement credential rotation
   - Restrict config file access

2. **Network Security**:
   - Use TLS for all connections
   - Implement VPN for remote access
   - Regular security updates

3. **Access Control**:
   - Dedicated service accounts
   - Minimal required permissions
   - Regular access reviews

## Support and Maintenance

For ongoing support:
1. Monitor system logs regularly
2. Keep dependencies updated
3. Test backup and restore procedures
4. Document any customizations
5. Maintain configuration version control

This concludes the installation and setup guide for the QR Code Asset Tracking System. Update system
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install python3 python3-pip python3-venv -y

# Install system dependencies
sudo apt install libzbar0 libopencv-dev python3-opencv -y

# Enable camera (if using Pi camera)
sudo raspi-config
# Navigate to Interface Options -> Camera -> Enable
```

#### On Processing Servers:
```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv sqlite3 -y

# CentOS/RHEL
sudo yum update -y
sudo yum install python3 python3-pip sqlite -y
```

### 2. Python Environment Setup

```bash
# Create virtual environment
python3 -m venv qr_scanner_env

# Activate virtual environment
source qr_scanner_env/bin/activate

# Install Python packages
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configuration Setup

1. Copy `config.json` to your installation directory
2. Edit the configuration file with your specific settings:

```bash
#