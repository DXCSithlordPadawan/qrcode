#!/usr/bin/env python3
"""
Raspberry Pi OS Bookworm (64-bit) Camera Fix
Addresses libcamera changes and new camera stack in Bookworm
"""

import cv2
import subprocess
import time
import os
import sys

class BookwormCameraManager:
    def __init__(self):
        self.camera = None
        self.method_used = None
        self.is_bookworm = self._check_bookworm()
    
    def _check_bookworm(self):
        """Check if running on Bookworm"""
        try:
            with open('/etc/os-release', 'r') as f:
                content = f.read()
                return 'bookworm' in content.lower()
        except:
            return False
    
    def check_camera_status(self):
        """Check camera status on Bookworm"""
        print("=== BOOKWORM CAMERA STATUS ===")
        
        # Check libcamera detection
        print("1. Checking libcamera detection:")
        try:
            result = subprocess.run(['libcamera-hello', '--list-cameras'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("   ✓ libcamera detected cameras:")
                print(f"     {result.stdout}")
            else:
                print(f"   ✗ libcamera failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("   ⚠ libcamera-hello timed out")
        except FileNotFoundError:
            print("   ✗ libcamera-hello not found")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # Check camera configuration
        print("\n2. Checking camera configuration:")
        config_files = ['/boot/firmware/config.txt', '/boot/config.txt']
        
        for config_file in config_files:
            if os.path.exists(config_file):
                print(f"   Checking {config_file}:")
                try:
                    with open(config_file, 'r') as f:
                        lines = f.readlines()
                        camera_related = [line.strip() for line in lines 
                                        if 'camera' in line.lower() and not line.startswith('#')]
                        if camera_related:
                            for line in camera_related:
                                print(f"     {line}")
                        else:
                            print("     No camera settings found")
                except Exception as e:
                    print(f"     Error reading config: {e}")
                break
        
        # Check V4L2 devices
        print("\n3. Checking V4L2 devices:")
        video_devices = []
        for i in range(10):
            device_path = f"/dev/video{i}"
            if os.path.exists(device_path):
                video_devices.append(i)
                print(f"   Found: {device_path}")
        
        if not video_devices:
            print("   No V4L2 devices found")
        
        return len(video_devices) > 0
    
    def initialize_bookworm_camera(self):
        """Initialize camera using Bookworm-specific methods"""
        print("\n=== BOOKWORM CAMERA INITIALIZATION ===")
        
        methods = [
            self._try_picamera2,
            self._try_libcamera_gstreamer,
            self._try_opencv_direct,
            self._try_v4l2_bookworm,
        ]
        
        for method in methods:
            try:
                if method():
                    return True
            except Exception as e:
                print(f"Method failed with error: {e}")
                continue
        
        return False
    
    def _try_picamera2(self):
        """Try using PiCamera2 (recommended for Bookworm)"""
        print("Trying: PiCamera2 library")
        
        try:
            # Import PiCamera2 (Bookworm's preferred camera library)
            from picamera2 import Picamera2
            import numpy as np
            
            picam2 = Picamera2()
            
            # Configure for low resolution to reduce memory usage
            camera_config = picam2.create_video_configuration({
                "size": (640, 480),
                "format": "RGB888"
            })
            picam2.configure(camera_config)
            
            # Start camera
            picam2.start()
            time.sleep(2)  # Allow camera to stabilize
            
            # Capture test frame
            frame = picam2.capture_array()
            
            if frame is not None and frame.size > 0:
                print(f"SUCCESS: PiCamera2 - Frame: {frame.shape}")
                self.method_used = "PiCamera2"
                
                # Convert PiCamera2 to OpenCV-compatible format
                self.picam2_instance = picam2
                return True
            
            picam2.stop()
            return False
            
        except ImportError:
            print("   PiCamera2 not installed. Install with:")
            print("   sudo apt install -y python3-picamera2")
            return False
        except Exception as e:
            print(f"   PiCamera2 failed: {e}")
            return False
    
    def _try_libcamera_gstreamer(self):
        """Try libcamera with GStreamer pipeline"""
        print("Trying: libcamera + GStreamer")
        
        # Bookworm-specific libcamera pipelines
        pipelines = [
            # Basic libcamera pipeline
            "libcamerasrc ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! appsink",
            
            # With explicit camera selection
            "libcamerasrc camera-name=\"/base/soc/i2c0mux/i2c@1/imx219@10\" ! video/x-raw,width=640,height=480 ! videoconvert ! appsink",
            
            # Lower resolution for memory constraints
            "libcamerasrc ! video/x-raw,width=320,height=240,framerate=15/1 ! videoconvert ! appsink drop=true max-buffers=1",
        ]
        
        for i, pipeline in enumerate(pipelines):
            try:
                print(f"   Testing pipeline {i+1}...")
                
                self.camera = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
                
                if self.camera.isOpened():
                    ret, frame = self.camera.read()
                    if ret and frame is not None:
                        print(f"SUCCESS: libcamera GStreamer - Frame: {frame.shape}")
                        self.method_used = f"libcamera GStreamer {i+1}"
                        return True
                
                if self.camera:
                    self.camera.release()
                    self.camera = None
                    
            except Exception as e:
                print(f"   Pipeline {i+1} failed: {e}")
                continue
        
        return False
    
    def _try_opencv_direct(self):
        """Try direct OpenCV (might work with USB cameras)"""
        print("Trying: Direct OpenCV VideoCapture")
        
        for device_id in range(3):
            try:
                print(f"   Testing device {device_id}...")
                
                self.camera = cv2.VideoCapture(device_id)
                
                if self.camera.isOpened():
                    # Set reasonable properties
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    
                    ret, frame = self.camera.read()
                    if ret and frame is not None:
                        print(f"SUCCESS: OpenCV direct device {device_id} - Frame: {frame.shape}")
                        self.method_used = f"OpenCV Direct {device_id}"
                        return True
                
                if self.camera:
                    self.camera.release()
                    self.camera = None
                    
            except Exception as e:
                print(f"   Device {device_id} failed: {e}")
                continue
        
        return False
    
    def _try_v4l2_bookworm(self):
        """Try V4L2 with Bookworm-specific settings"""
        print("Trying: V4L2 with Bookworm settings")
        
        try:
            # First, try to configure V4L2 device
            v4l2_commands = [
                # Set format for device 0
                'v4l2-ctl -d /dev/video0 --set-fmt-video=width=640,height=480,pixelformat=YUYV',
                
                # Try device 1 (sometimes Pi camera appears here in Bookworm)
                'v4l2-ctl -d /dev/video1 --set-fmt-video=width=640,height=480,pixelformat=YUYV',
            ]
            
            working_device = None
            for i, cmd in enumerate(v4l2_commands):
                try:
                    result = subprocess.run(cmd.split(), capture_output=True, 
                                          text=True, timeout=5)
                    if result.returncode == 0:
                        working_device = i
                        print(f"   V4L2 configuration successful for /dev/video{i}")
                        break
                except:
                    continue
            
            if working_device is not None:
                self.camera = cv2.VideoCapture(working_device, cv2.CAP_V4L2)
                
                if self.camera.isOpened():
                    ret, frame = self.camera.read()
                    if ret and frame is not None:
                        print(f"SUCCESS: V4L2 Bookworm device {working_device} - Frame: {frame.shape}")
                        self.method_used = f"V4L2 Bookworm {working_device}"
                        return True
                
                if self.camera:
                    self.camera.release()
                    self.camera = None
            
            return False
            
        except Exception as e:
            print(f"   V4L2 Bookworm failed: {e}")
            return False
    
    def create_opencv_adapter(self):
        """Create OpenCV adapter for PiCamera2"""
        if self.method_used == "PiCamera2" and hasattr(self, 'picam2_instance'):
            
            class PiCamera2Adapter:
                def __init__(self, picam2_instance):
                    self.picam2 = picam2_instance
                    self.backend_name = "PiCamera2"
                
                def read(self):
                    try:
                        frame = self.picam2.capture_array()
                        # Convert RGB to BGR for OpenCV compatibility
                        if frame is not None:
                            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                            return True, frame_bgr
                        return False, None
                    except Exception:
                        return False, None
                
                def isOpened(self):
                    return True  # PiCamera2 doesn't have an isOpened method
                
                def release(self):
                    try:
                        self.picam2.stop()
                    except:
                        pass
                
                def set(self, prop, value):
                    # PiCamera2 doesn't use the same property system
                    pass
                
                def get(self, prop):
                    # Return default values for common properties
                    if prop == cv2.CAP_PROP_FRAME_WIDTH:
                        return 640
                    elif prop == cv2.CAP_PROP_FRAME_HEIGHT:
                        return 480
                    elif prop == cv2.CAP_PROP_FPS:
                        return 30
                    return 0
                
                def getBackendName(self):
                    return "PiCamera2"
            
            # Replace the camera object with the adapter
            self.camera = PiCamera2Adapter(self.picam2_instance)
    
    def generate_bookworm_qr_code(self):
        """Generate QR scanner code optimized for Bookworm"""
        if not self.camera or not self.method_used:
            return None
        
        if "PiCamera2" in self.method_used:
            code = '''
# Bookworm QR Scanner - PiCamera2 Method
import cv2
from picamera2 import Picamera2
from pyzbar import pyzbar
import time

class BookwormQRScanner:
    def __init__(self):
        self.picam2 = None
    
    def initialize_camera(self):
        """Initialize PiCamera2 for Bookworm"""
        try:
            self.picam2 = Picamera2()
            
            # Configure for QR code scanning
            config = self.picam2.create_video_configuration({
                "size": (640, 480),
                "format": "RGB888"
            })
            self.picam2.configure(config)
            self.picam2.start()
            
            # Allow camera to stabilize
            time.sleep(2)
            
            self.logger.info("PiCamera2 initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize PiCamera2: {e}")
            raise
    
    def capture_frame(self):
        """Capture frame from PiCamera2"""
        try:
            frame = self.picam2.capture_array()
            # Convert RGB to BGR for OpenCV
            if frame is not None:
                return True, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return False, None
        except Exception as e:
            self.logger.error(f"Frame capture failed: {e}")
            return False, None
    
    def decode_qr_codes(self, frame):
        """Decode QR codes - same as before"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            qr_codes = pyzbar.decode(gray)
            return qr_codes
        except Exception as e:
            self.logger.error(f"QR decode failed: {e}")
            return []
    
    def run(self):
        """Main loop for Bookworm"""
        while self.running:
            try:
                ret, frame = self.capture_frame()
                if ret:
                    qr_codes = self.decode_qr_codes(frame)
                    # Process QR codes as before...
                    
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(1)
    
    def cleanup(self):
        """Cleanup PiCamera2"""
        if self.picam2:
            self.picam2.stop()
'''

        elif "libcamera GStreamer" in self.method_used:
            # Determine which pipeline worked
            pipeline_num = self.method_used.split()[-1]
            pipelines = [
                "libcamerasrc ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! appsink",
                "libcamerasrc camera-name=\"/base/soc/i2c0mux/i2c@1/imx219@10\" ! video/x-raw,width=640,height=480 ! videoconvert ! appsink",
                "libcamerasrc ! video/x-raw,width=320,height=240,framerate=15/1 ! videoconvert ! appsink drop=true max-buffers=1"
            ]
            
            try:
                pipeline = pipelines[int(pipeline_num) - 1]
            except:
                pipeline = pipelines[0]
            
            code = f'''
# Bookworm QR Scanner - libcamera GStreamer Method
def initialize_camera(self):
    """Initialize camera with libcamera GStreamer pipeline"""
    try:
        pipeline = "{pipeline}"
        self.camera = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        
        if not self.camera.isOpened():
            raise Exception("Cannot open libcamera GStreamer pipeline")
        
        self.logger.info("libcamera GStreamer pipeline initialized")
        
    except Exception as e:
        self.logger.error(f"libcamera initialization failed: {{e}}")
        raise

# Use the rest of your QR scanner code as-is
# The main difference is just the camera initialization
'''

        else:
            # Standard OpenCV or V4L2
            device_id = self.method_used.split()[-1] if any(char.isdigit() for char in self.method_used) else "0"
            backend = "cv2.CAP_V4L2" if "V4L2" in self.method_used else "cv2.CAP_ANY"
            
            code = f'''
# Bookworm QR Scanner - OpenCV Method  
def initialize_camera(self):
    """Initialize camera with OpenCV for Bookworm"""
    try:
        self.camera = cv2.VideoCapture({device_id}, {backend})
        
        if not self.camera.isOpened():
            raise Exception("Cannot open camera")
        
        # Configure camera
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        self.logger.info("OpenCV camera initialized for Bookworm")
        
    except Exception as e:
        self.logger.error(f"Camera initialization failed: {{e}}")
        raise
'''
        
        return code
    
    def test_sustained_operation(self, duration=30):
        """Test sustained operation"""
        if not self.camera:
            return False
        
        print(f"\nTesting sustained operation for {duration} seconds...")
        
        frame_count = 0
        failed_count = 0
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                if hasattr(self.camera, 'capture_array'):
                    # PiCamera2 method
                    frame = self.camera.capture_array()
                    ret = frame is not None
                else:
                    # OpenCV method
                    ret, frame = self.camera.read()
                
                if ret:
                    frame_count += 1
                else:
                    failed_count += 1
                
                time.sleep(0.1)
                
            except Exception as e:
                failed_count += 1
                time.sleep(0.1)
        
        success_rate = frame_count / (frame_count + failed_count) * 100
        print(f"Results: {frame_count} frames captured, {failed_count} failures")
        print(f"Success rate: {success_rate:.1f}%")
        
        return success_rate > 90
    
    def release(self):
        """Release camera resources"""
        if hasattr(self, 'picam2_instance'):
            try:
                self.picam2_instance.stop()
            except:
                pass
        
        if self.camera and hasattr(self.camera, 'release'):
            self.camera.release()
        
        self.camera = None

def main():
    """Test Bookworm camera fixes"""
    print("Raspberry Pi OS Bookworm Camera Fix")
    print("=" * 50)
    
    manager = BookwormCameraManager()
    
    if not manager.is_bookworm:
        print("Warning: This script is optimized for Bookworm OS")
    
    # Check camera status
    has_cameras = manager.check_camera_status()
    
    if not has_cameras:
        print("\n⚠ No cameras detected!")
        print("Install PiCamera2: sudo apt install -y python3-picamera2")
        print("Enable camera: Add 'camera_auto_detect=1' to /boot/firmware/config.txt")
        print("Reboot: sudo reboot")
        return
    
    # Try to initialize
    if manager.initialize_bookworm_camera():
        print(f"\n✓ Camera working with method: {manager.method_used}")
        
        # Create OpenCV adapter if needed
        manager.create_opencv_adapter()
        
        # Test sustained operation
        if manager.test_sustained_operation(duration=15):
            print("✓ Sustained operation test passed!")
            
            # Generate code
            code = manager.generate_bookworm_qr_code()
            if code:
                print("\n" + "="*60)
                print("BOOKWORM QR SCANNER CODE:")
                print("="*60)
                print(code)
                
                with open("bookworm_qr_scanner.py", "w") as f:
                    f.write(code)
                print("\nCode saved to: bookworm_qr_scanner.py")
        
    else:
        print("\n✗ All camera initialization methods failed")
        print("\nBookworm-specific troubleshooting:")
        print("1. Install PiCamera2: sudo apt install -y python3-picamera2")
        print("2. Update system: sudo apt update && sudo apt upgrade")
        print("3. Check config: Add 'camera_auto_detect=1' to /boot/firmware/config.txt")
        print("4. Reboot: sudo reboot")
    
    manager.release()

if __name__ == "__main__":
    main()