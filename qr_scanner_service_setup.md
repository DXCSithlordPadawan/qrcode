# QR Scanner Service Setup Guide for Raspberry Pi Zero W 1.1

## Prerequisites

### 1. System Updates
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Enable Camera Interface
```bash
sudo raspi-config
```
- Navigate to **Interface Options** → **Camera** → **Enable**
- Reboot: `sudo reboot`

### 3. Install Required System Packages
```bash
sudo apt install -y python3-pip python3-venv python3-dev
sudo apt install -y libzbar0 libzbar-dev
sudo apt install -y libopencv-dev python3-opencv
sudo apt install -v libatlas-base-dev libjasper-dev libqtgui4 libqt4-test
```

## Directory Setup

### 1. Create and Navigate to Project Directory
```bash
cd /opt/qrcode
```

### 2. Create Python Virtual Environment
```bash
sudo python3 -m venv venv
sudo chown -R pi:pi venv  # Change ownership to pi user
source venv/bin/activate
```

### 3. Install Python Dependencies
```bash
pip install --upgrade pip
pip install opencv-python
pip install pyzbar
pip install pika
pip install picamera2
pip install pathlib
```

## Configuration Files

### 1. Create Sample Configuration File
Create `/opt/qrcode/config.json`:

```json
{
  "qr_codes": {
    "locations": {
      "LOC001": "Living Room",
      "LOC002": "Kitchen", 
      "LOC003": "Bedroom",
      "LOC004": "Office"
    },
    "objects": {
      "OBJ001": {"name": "Remote Control", "category": "electronics"},
      "OBJ002": {"name": "Keys", "category": "personal"},
      "OBJ003": {"name": "Wallet", "category": "personal"},
      "OBJ004": {"name": "Phone Charger", "category": "electronics"}
    }
  },
  "scanner_settings": {
    "camera_resolution": [640, 480],
    "frame_rate": 20
  },
  "processing_rules": {
    "duplicate_scan_window_seconds": 5
  },
  "rabbitmq": {
    "host": "localhost",
    "port": 5672,
    "username": "guest",
    "password": "guest",
    "virtual_host": "/",
    "exchange": "qr_scanner",
    "queue_scan_results": "scan_results",
    "routing_key_scan": "scan.object.location"
  }
}
```

### 2. Set Proper Permissions
```bash
sudo chown -R pi:pi /opt/qrcode
sudo chmod +x /opt/qrcode/complete_rabbitmq_scanner.py
```

## Service Configuration

### 1. Create Systemd Service File
Create `/etc/systemd/system/qr-scanner.service`:

```ini
[Unit]
Description=QR Code Scanner Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/qrcode
Environment=PATH=/opt/qrcode/venv/bin
ExecStart=/opt/qrcode/venv/bin/python /opt/qrcode/complete_rabbitmq_scanner.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Resource limits for Pi Zero
MemoryLimit=256M
CPUQuota=80%

[Install]
WantedBy=multi-user.target
```

### 2. Create Service Management Script
Create `/opt/qrcode/service-control.sh`:

```bash
#!/bin/bash

SERVICE_NAME="qr-scanner"

case "$1" in
    start)
        echo "Starting QR Scanner service..."
        sudo systemctl start $SERVICE_NAME
        ;;
    stop)
        echo "Stopping QR Scanner service..."
        sudo systemctl stop $SERVICE_NAME
        ;;
    restart)
        echo "Restarting QR Scanner service..."
        sudo systemctl restart $SERVICE_NAME
        ;;
    status)
        sudo systemctl status $SERVICE_NAME
        ;;
    enable)
        echo "Enabling QR Scanner service to start at boot..."
        sudo systemctl enable $SERVICE_NAME
        ;;
    disable)
        echo "Disabling QR Scanner service from starting at boot..."
        sudo systemctl disable $SERVICE_NAME
        ;;
    logs)
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    logs-all)
        sudo journalctl -u $SERVICE_NAME --no-pager
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|enable|disable|logs|logs-all}"
        exit 1
        ;;
esac
```

Make it executable:
```bash
sudo chmod +x /opt/qrcode/service-control.sh
```

## Service Installation and Configuration

### 1. Reload Systemd and Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable qr-scanner.service
```

### 2. Test the Service
```bash
# Start the service
sudo systemctl start qr-scanner.service

# Check status
sudo systemctl status qr-scanner.service

# View logs
sudo journalctl -u qr-scanner.service -f
```

## Testing and Troubleshooting

### 1. Manual Testing First
Before running as a service, test manually:
```bash
cd /opt/qrcode
source venv/bin/activate
python complete_rabbitmq_scanner.py
```

### 2. Common Issues and Solutions

**Camera Permission Issues:**
```bash
sudo usermod -a -G video pi
sudo reboot
```

**Memory Issues on Pi Zero:**
Add to `/boot/config.txt`:
```
gpu_mem=128
```

**Service Won't Start:**
```bash
# Check service logs
sudo journalctl -u qr-scanner.service --no-pager

# Check if script is executable
ls -la /opt/qrcode/complete_rabbitmq_scanner.py

# Test dependencies
cd /opt/qrcode && source venv/bin/activate && python -c "import cv2, pyzbar, pika, picamera2; print('All imports OK')"
```

**RabbitMQ Connection Issues:**
```bash
# Test network connectivity to RabbitMQ server
ping 192.168.0.200

# Test if RabbitMQ port is accessible
nc -zv 192.168.0.200 5672

# Check firewall settings (if needed)
sudo ufw status
```

### 3. Service Management Commands
```bash
# Using the control script
/opt/qrcode/service-control.sh start
/opt/qrcode/service-control.sh stop
/opt/qrcode/service-control.sh status
/opt/qrcode/service-control.sh logs

# Or direct systemctl commands
sudo systemctl start qr-scanner
sudo systemctl stop qr-scanner  
sudo systemctl restart qr-scanner
sudo systemctl status qr-scanner
```

## Optional: RabbitMQ Setup (if needed)

### 1. Install RabbitMQ Server
```bash
sudo apt install rabbitmq-server
sudo systemctl enable rabbitmq-server
sudo systemctl start rabbitmq-server
```

### 2. Configure RabbitMQ
```bash
sudo rabbitmq-plugins enable rabbitmq_management
sudo rabbitmqctl add_user scanner scanner_password
sudo rabbitmqctl set_user_tags scanner administrator
sudo rabbitmqctl set_permissions -p / scanner ".*" ".*" ".*"
```

## Performance Optimization for Pi Zero

### 1. Reduce CPU Usage
Add to service file under `[Service]`:
```ini
Nice=10
IOSchedulingClass=2
IOSchedulingPriority=6
```

### 2. Limit Memory Usage
The service file already includes:
```ini
MemoryLimit=256M
CPUQuota=80%
```

### 3. GPU Memory Split
Add to `/boot/config.txt`:
```
gpu_mem=64
```

## Monitoring and Logs

### 1. View Real-time Logs
```bash
sudo journalctl -u qr-scanner.service -f
```

### 2. View Historical Logs
```bash
sudo journalctl -u qr-scanner.service --since "2 hours ago"
```

### 3. Log Rotation Configuration
Create `/etc/logrotate.d/qr-scanner`:
```
/var/log/qr-scanner.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 644 pi pi
}
```

## Final Steps

### 1. Start Service at Boot
```bash
sudo systemctl enable qr-scanner.service
```

### 2. Verify Installation
```bash
sudo systemctl is-enabled qr-scanner.service
sudo systemctl is-active qr-scanner.service
```

### 3. Reboot Test
```bash
sudo reboot
# Wait for reboot, then check:
sudo systemctl status qr-scanner.service
```

Your QR scanner should now be running as a system service and will automatically start when the Raspberry Pi boots up!