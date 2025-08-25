The camera initializes and RabbitMQ connects, but QR codes aren't being recognized. Let's troubleshoot this systematically:

## Common QR Code Recognition Issues

### 1. **Test QR Code Detection First**

Let me create a simple QR code test script to isolate the issue:### 2. **Image Analysis Tool**

Let me also create a tool to analyze your specific QR codes from the images you uploaded:## Troubleshooting Steps

### **Step 1: Run the QR Detection Test**
```bash
python3 qr_test_script.py
```
This will show you:
- Whether QR codes are being detected at all
- Raw data from detected codes
- Frame processing statistics

### **Step 2: Test with Known QR Codes**
Create simple test QR codes:
```bash
pip install qrcode[pil]
python3 qr_image_analyzer.py --create-test
```

### **Step 3: Common Issues to Check**

**Distance and Focus:**
- QR codes need to be 6-12 inches from camera
- Ensure camera can focus (some Pi cameras have fixed focus)
- Try different distances and angles

**Lighting:**
- Ensure good, even lighting
- Avoid shadows or glare on the QR code
- Try with room lights on

**QR Code Quality:**
- Print QR codes at higher resolution
- Ensure sharp, crisp edges
- Black on white background works best

**Camera Settings:**
```python
# Try adding these to your camera initialization:
camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
camera.set(cv2.CAP_PROP_EXPOSURE, -6)
camera.set(cv2.CAP_PROP_AUTOFOCUS, 0)
```

### **Step 4: Debug Your Specific QR Codes**

If you saved your QR codes as image files, test them:
```bash
python3 qr_image_analyzer.py your_qr_code.png
```

### **Step 5: Enable Detailed Logging**

Add this to your main scanner to see what's happening:## Quick Test Commands

Run these in order to isolate the issue:

1. **Test basic detection:** `python3 qr_test_script.py`
2. **Test with your config:** Check that `S500` and `OP7` are in your config.json exactly as shown
3. **Set log level to DEBUG** in config.json: `"log_level": "DEBUG"`
4. **Test distance/lighting:** Hold QR codes at different distances (6-18 inches)

**Most likely causes:**
- QR codes too close/far from camera
- Poor lighting conditions
- Camera focus issues
- QR code print quality

Try the test script first and let me know what output you get!