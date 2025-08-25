#!/usr/bin/env python3
"""
Camera Diagnostic Tool
Diagnoses camera issues and tests different approaches
"""

import cv2
import subprocess
import os
import time
import sys

def run_system_command(command):
    """Run a system command and return the output"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)

def check_camera_devices():
    """Check available camera devices"""
    print("=== CAMERA DEVICE DETECTION ===")
    
    # Method 1: Check /dev/video* devices
    print("\n1. Checking /dev/video* devices:")
    video_devices = []
    for i in range(10):
        device_path = f"/dev/video{i}"
        if os.path.exists(device_path):
            video_devices.append(i)
            print(f"   Found: {device_path}")
    
    if not video_devices:
        print("   No /dev/video* devices found")
    
    # Method 2: Use v4l2-ctl if available
    print("\n2. Using v4l2-ctl (if available):")
    returncode, stdout, stderr = run_system_command("v4l2-ctl --list-devices")
    if returncode == 0:
        print(stdout)
    else:
        print(f"   v4l2-ctl not available or failed: {stderr}")
    
    # Method 3: Check lsusb for USB cameras
    print("\n3. Checking USB devices:")
    returncode, stdout, stderr = run_system_command("lsusb")
    if returncode == 0:
        usb_lines = stdout.split('\n')
        camera_keywords = ['camera', 'webcam', 'video', 'capture']
        for line in usb_lines:
            if any(keyword in line.lower() for keyword in camera_keywords):
                print(f"   Possible camera: {line}")
    
    # Method 4: Check for Raspberry Pi camera
    print("\n4. Checking Raspberry Pi camera:")
    returncode, stdout, stderr = run_system_command("vcgencmd get_camera")
    if returncode == 0:
        print(f"   Camera status: {stdout.strip()}")
    
    # Check if camera is enabled in config
    returncode, stdout, stderr = run_system_command("grep 'camera' /boot/config.txt")
    if returncode == 0:
        print(f"   Config.txt camera settings: {stdout.strip()}")
    
    return video_devices

def test_opencv_backends():
    """Test different OpenCV backends"""
    print("\n=== OPENCV BACKEND TESTING ===")
    
    backends = [
        (cv2.CAP_V4L2, "V4L2 (Linux)"),
        (cv2.CAP_GSTREAMER, "GStreamer"),
        (cv2.CAP_ANY, "Any available"),
    ]
    
    # If OpenCV has these backends
    additional_backends = []
    if hasattr(cv2, 'CAP_LIBV4L'):
        additional_backends.append((cv2.CAP_LIBV4L, "LibV4L"))
    
    for backend_id, backend_name in backends + additional_backends:
        print(f"\nTesting {backend_name} backend:")
        for device_id in range(3):  # Test devices 0, 1, 2
            try:
                print(f"  Trying device {device_id}...")
                cap = cv2.VideoCapture(device_id, backend_id)
                
                if cap.isOpened():
                    # Try to read a frame
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        height, width = frame.shape[:2]
                        print(f"    SUCCESS: Device {device_id} with {backend_name}")
                        print(f"    Frame size: {width}x{height}")
                        
                        # Get camera properties
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
                        print(f"    FPS: {fps}, FOURCC: {fourcc}")
                        
                        cap.release()
                        return device_id, backend_id, backend_name
                    else:
                        print(f"    Device {device_id} opened but cannot read frames")
                else:
                    print(f"    Device {device_id} failed to open")
                
                cap.release()
                
            except Exception as e:
                print(f"    Error testing device {device_id}: {e}")
    
    return None, None, None

def test_gstreamer_pipeline():
    """Test GStreamer pipeline for Raspberry Pi camera"""
    print("\n=== GSTREAMER PIPELINE TEST ===")
    
    # Common GStreamer pipelines for Raspberry Pi
    pipelines = [
        # Raspberry Pi camera module
        "libcamerasrc ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! appsink",
        
        # Legacy raspivid approach
        "v4l2src device=/dev/video0 ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! appsink",
        
        # USB camera
        "v4l2src device=/dev/video0 ! videoconvert ! appsink",
        
        # Test pattern (should always work if GStreamer is installed)
        "videotestsrc ! video/x-raw,width=640,height=480 ! videoconvert ! appsink"
    ]
    
    for i, pipeline in enumerate(pipelines):
        print(f"\nTesting pipeline {i+1}: {pipeline}")
        try:
            cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"    SUCCESS: Pipeline works!")
                    print(f"    Frame size: {frame.shape[1]}x{frame.shape[0]}")
                    cap.release()
                    return pipeline
                else:
                    print(f"    Pipeline opened but no frames")
            else:
                print(f"    Pipeline failed to open")
            
            cap.release()
            
        except Exception as e:
            print(f"    Error: {e}")
    
    return None

def test_basic_camera_access():
    """Test basic camera access with multiple methods"""
    print("\n=== BASIC CAMERA ACCESS TEST ===")
    
    # Find working device and backend
    device_id, backend_id, backend_name = test_opencv_backends()
    
    if device_id is not None:
        print(f"\nFound working camera: Device {device_id} with {backend_name}")
        
        # Test sustained frame capture
        print("Testing sustained frame capture...")
        try:
            cap = cv2.VideoCapture(device_id, backend_id)
            
            # Set some basic properties
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            
            frame_count = 0
            start_time = time.time()
            
            print("Capturing frames for 5 seconds...")
            while time.time() - start_time < 5:
                ret, frame = cap.read()
                if ret:
                    frame_count += 1
                else:
                    print(f"Frame read failed at frame {frame_count}")
                    break
                
                time.sleep(0.1)  # Small delay
            
            cap.release()
            
            elapsed = time.time() - start_time
            fps = frame_count / elapsed
            
            print(f"Captured {frame_count} frames in {elapsed:.2f} seconds")
            print(f"Effective FPS: {fps:.2f}")
            
            return True
            
        except Exception as e:
            print(f"Error during sustained capture: {e}")
            return False
    
    else:
        print("No working camera found with OpenCV backends")
        
        # Try GStreamer as last resort
        pipeline = test_gstreamer_pipeline()
        if pipeline:
            print(f"Found working GStreamer pipeline: {pipeline}")
            return True
    
    return False

def create_working_camera_code(device_id=None, backend_id=None, pipeline=None):
    """Generate working camera code based on test results"""
    print("\n=== GENERATING WORKING CAMERA CODE ===")
    
    if pipeline:
        # GStreamer pipeline
        code = f'''
# Working camera initialization (GStreamer pipeline):
import cv2

def initialize_camera():
    pipeline = "{pipeline}"
    camera = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    
    if not camera.isOpened():
        raise Exception("Cannot open camera with GStreamer pipeline")
    
    return camera

# Usage:
camera = initialize_camera()
ret, frame = camera.read()
if ret:
    print(f"Frame captured: {{frame.shape}}")
camera.release()
'''
    elif device_id is not None and backend_id is not None:
        # OpenCV with specific backend
        backend_name = {
            cv2.CAP_V4L2: "cv2.CAP_V4L2",
            cv2.CAP_GSTREAMER: "cv2.CAP_GSTREAMER",
            cv2.CAP_ANY: "cv2.CAP_ANY"
        }.get(backend_id, f"Backend ID {backend_id}")
        
        code = f'''
# Working camera initialization (OpenCV backend):
import cv2

def initialize_camera():
    camera = cv2.VideoCapture({device_id}, {backend_name})
    
    if not camera.isOpened():
        raise Exception("Cannot open camera")
    
    # Set properties
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 30)
    
    return camera

# Usage:
camera = initialize_camera()
ret, frame = camera.read()
if ret:
    print(f"Frame captured: {{frame.shape}}")
camera.release()
'''
    else:
        code = '''
# No working camera configuration found
# Try these troubleshooting steps:
# 1. Check camera connections
# 2. Enable camera in raspi-config (for Pi camera)
# 3. Install camera drivers
# 4. Try different USB ports (for USB cameras)
'''
    
    print(code)
    
    # Save to file
    with open("working_camera_code.py", "w") as f:
        f.write(code)
    
    print("\nCode saved to: working_camera_code.py")

def main():
    """Main diagnostic function"""
    print("Camera Diagnostic Tool")
    print("=" * 50)
    
    # Check OpenCV version
    print(f"OpenCV version: {cv2.__version__}")
    
    # Step 1: Find camera devices
    video_devices = check_camera_devices()
    
    # Step 2: Test camera access
    camera_working = test_basic_camera_access()
    
    if not camera_working:
        print("\n" + "=" * 50)
        print("CAMERA ISSUES DETECTED")
        print("=" * 50)
        print("\nCommon solutions:")
        print("1. For Raspberry Pi camera module:")
        print("   sudo raspi-config -> Interface Options -> Camera -> Enable")
        print("   sudo reboot")
        print("\n2. For USB cameras:")
        print("   Try different USB ports")
        print("   Check USB power supply")
        print("   Install: sudo apt-get install fswebcam")
        print("\n3. Check camera permissions:")
        print("   sudo usermod -a -G video $USER")
        print("   Then logout and login again")
        print("\n4. Install additional packages:")
        print("   sudo apt-get install v4l-utils")
        print("   sudo apt-get install libv4l-dev")
    else:
        print("\n" + "=" * 50)
        print("CAMERA WORKING!")
        print("=" * 50)
    
    # Step 3: Generate working code
    # This is a simplified version - you'd need to capture the actual working parameters
    create_working_camera_code()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDiagnostic interrupted by user")
    except Exception as e:
        print(f"Error during diagnostic: {e}")
        import traceback
        traceback.print_exc()