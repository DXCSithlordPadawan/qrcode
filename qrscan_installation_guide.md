# QRScan Complete Installation Guide for Raspberry Pi Zero W V1.1

This guide rationalizes all instructions from repository Markdown files and provides a unified step-by-step process, using `complete_rabbitmq_scanner.py` as the primary file, for installing the QRScan solution to `/opt/qrscan` on a Raspberry Pi Zero W V1.1.

---

## 1. Prerequisites

- Raspberry Pi Zero W V1.1 (running Raspberry Pi OS Bookworm recommended)
- Internet connection
- Camera module enabled and connected
- Optional: RabbitMQ server running and accessible

---

## 2. Dependencies

Install all required dependencies (from `requirements.txt`, code inspection, and referenced guides):

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-opencv python3-picamera2 python3-pyzbar rabbitmq-server
sudo pip3 install opencv-python pika pyzbar picamera2
```

> _Note_: Some packages (e.g., `picamera2`) may require the latest Raspberry Pi OS. If you encounter issues, refer to [debugpicam.md](https://github.com/DXCSithlordPadawan/qrcode/blob/main/debugpicam.md) and [cameradiag.md](https://github.com/DXCSithlordPadawan/qrcode/blob/main/cameradiag.md) for troubleshooting.

---

## 3. Download and Install QRScan

```bash
# Create installation folder
sudo mkdir -p /opt/qrscan
sudo chown $USER /opt/qrscan

# Clone the repository
git clone https://github.com/DXCSithlordPadawan/qrcode /opt/qrscan

# Enter the directory
cd /opt/qrscan
```

---

## 4. Configuration

Ensure your configuration files exist:

- `config.json` (must be in `/opt/qrscan`)
  - Contains settings for QR codes, scanner, RabbitMQ, etc.
  - Sample required sections: `"qr_codes"`, `"scanner_settings"`, `"processing_rules"`, optional `"rabbitmq"`

If missing, create or copy from a template. See references in [README.md](https://github.com/DXCSithlordPadawan/qrcode/blob/main/README.md) and [installation_guide.md](https://github.com/DXCSithlordPadawan/qrcode/blob/main/installation_guide.md).

---

## 5. Running the Scanner

Basic usage:

```bash
python3 complete_rabbitmq_scanner.py
```

With camera preview window:

```bash
python3 complete_rabbitmq_scanner.py --preview
```

_Requirements_:
- Camera enabled and connected
- RabbitMQ server running (optional; if not configured, messages are logged locally)
- `config.json` present

---

## 6. Troubleshooting

- For camera issues: see [debugpicam.md](https://github.com/DXCSithlordPadawan/qrcode/blob/main/debugpicam.md) and [cameradiag.md](https://github.com/DXCSithlordPadawan/qrcode/blob/main/cameradiag.md)
- For RabbitMQ problems: ensure server is running and credentials in `config.json` are correct
- For dependency errors: rerun installation steps or consult [installation_guide.md](https://github.com/DXCSithlordPadawan/qrcode/blob/main/installation_guide.md)

---

## 7. References and Further Help

- [README.md](https://github.com/DXCSithlordPadawan/qrcode/blob/main/README.md): Project summary and major usage notes
- [installation_guide.md](https://github.com/DXCSithlordPadawan/qrcode/blob/main/installation_guide.md): Additional manual steps for legacy Pi OS
- [debugpicam.md](https://github.com/DXCSithlordPadawan/qrcode/blob/main/debugpicam.md): Camera debugging tips
- [cameradiag.md](https://github.com/DXCSithlordPadawan/qrcode/blob/main/cameradiag.md): Camera diagnostic tool usage

---

## Summary

This guide consolidates all Markdown instructions, configures dependencies, and details installation and usage for `/opt/qrscan` on a Raspberry Pi Zero W V1.1 with `complete_rabbitmq_scanner.py` as the primary executable.