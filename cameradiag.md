The camera initializes but no frames are detected - this is a common issue on Raspberry Pi. Let's diagnose and fix this step by step:## Run the Diagnostic Tool

```bash
python3 camera_diagnostic_tool.py
```

This will:
1. **Detect available cameras** (USB, Pi camera module, etc.)
2. **Test different OpenCV backends** to find what works
3. **Try GStreamer pipelines** (common on Pi)
4. **Generate working camera code** for your specific setup

## Common Raspberry Pi Camera Issues

### **Issue 1: Pi Camera Module Not Enabled**
```bash
sudo raspi-config
# Navigate to: Interface Options -> Camera -> Enable
sudo reboot
```

### **Issue 2: Wrong Camera Index**
Try different camera indices:
```python
# Test cameras 0, 1, 2
for i in range(3):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"Camera {i} works!")
        cap.release()
```

### **Issue 3: USB Camera Power/Permissions**
```bash
# Check USB devices
lsusb

# Add user to video group
sudo usermod -a -G video $USER
# Logout and login again

# Install video utilities
sudo apt-get install v4l-utils
v4l2-ctl --list-devices
```

### **Issue 4: GStreamer Pipeline (Modern Pi)**
For newer Raspberry Pi OS, try this approach:## Quick Test Commands

Run these in order:

1. **Run full diagnostic:**
   ```bash
   python3 camera_diagnostic_tool.py
   ```

2. **Test Pi-specific fixes:**
   ```bash
   python3 pi_camera_fix.py
   ```

3. **Manual camera checks:**
   ```bash
   # Check if camera is detected
   ls -l /dev/video*
   
   # Test with fswebcam (if available)
   fswebcam test.jpg
   
   # Check camera status (Pi camera)
   vcgencmd get_camera
   ```

4. **Enable Pi camera if needed:**
   ```bash
   sudo raspi-config
   # Go to Interface Options -> Camera -> Enable
   sudo reboot
   ```

The diagnostic tools will identify exactly what's wrong and generate working camera code for your specific setup. Run the first diagnostic tool and share the output - that will tell us exactly what needs to be fixed!