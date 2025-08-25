#!/usr/bin/env python3
"""
Raspberry Pi Camera Fix
Alternative camera initialization methods for different Pi setups
"""

import cv2
import subprocess
import time

class PiCameraManager:
    def __init__(self):
        self.camera = None
        self.method_used = None
    
    def initialize_camera(self):
        """Try multiple camera initialization methods"""
        
        methods = [
            self._try_standard_opencv,
            self._try_v4l2_backend,
            self._try_gstreamer_libcamera,
            self._try_gstreamer_v4l2,
            self._try_different_indices,
        ]
        
        for method in methods:
            try:
                if method():
                    return True
            except Exception as e:
                print(f"Method failed: {e}")
                continue
        
        return False
    
    def _try_standard_opencv(self):
        """Try standard OpenCV VideoCapture"""
        print("Trying: Standard OpenCV VideoCapture(0)")
        
        self.camera = cv2.VideoCapture(0)
        if self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret and frame is not None:
                print(f"SUCCESS: Standard method - Frame: {frame.shape}")
                self.method_used = "Standard OpenCV"
                return True
        
        if self.camera:
            self.camera.release()
        return False
    
    def _try_v4l2_backend(self):
        """Try V4L2 backend specifically"""
        print("Trying: V4L2 backend")
        
        self.camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
        if self.camera.isOpened():
            # Set properties before testing
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            ret, frame = self.camera.read()
            if ret and frame is not None:
                print(f"SUCCESS: V4L2 backend - Frame: {frame.shape}")
                self.method_used = "V4L2 Backend"
                return True
        
        if self.camera:
            self.camera.release()
        return False
    
    def _try_gstreamer_libcamera(self):
        """Try GStreamer with libcamera (newer Pi OS)"""
        print("Trying: GStreamer with libcamera")
        
        pipeline = "libcamerasrc ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! appsink"
        
        self.camera = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret and frame is not None:
                print(f"SUCCESS: GStreamer libcamera - Frame: {frame.shape}")
                self.method_used = "GStreamer libcamera"
                return True
        
        if self.camera:
            self.camera.release()
        return False
    
    def _try_gstreamer_v4l2(self):
        """Try GStreamer with v4l2"""
        print("Trying: GStreamer with v4l2")
        
        pipeline = "v4l2src device=/dev/video0 ! video/x-raw,width=640,height=480 ! videoconvert ! appsink"
        
        self.camera = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret and frame is not None:
                print(f"SUCCESS: GStreamer v4l2 - Frame: {frame.shape}")
                self.method_used = "GStreamer v4l2"
                return True
        
        if self.camera:
            self.camera.release()
        return False
    
    def _try_different_indices(self):
        """Try different camera indices"""
        print("Trying: Different camera indices")
        
        for i in range(5):  # Try indices 0-4
            print(f"  Testing index {i}...")
            self.camera = cv2.VideoCapture(i)
            
            if self.camera.isOpened():
                ret, frame = self.camera.read()
                if ret and frame is not None:
                    print(f"SUCCESS: Camera index {i} - Frame: {frame.shape}")
                    self.method_used = f"Index {i}"
                    return True
            
            if self.camera:
                self.camera.release()
        
        return False
    
    def test_sustained_capture(self, duration=5):
        """Test sustained frame capture"""
        if not self.camera:
            print("No camera initialized")
            return False
        
        print(f"Testing sustained capture for {duration} seconds...")
        
        frame_count = 0
        failed_reads = 0
        start_time = time.time()
        
        while time.time() - start_time < duration:
            ret, frame = self.camera.read()
            if ret:
                frame_count += 1
            else:
                failed_reads += 1
            
            time.sleep(0.1)
        
        elapsed = time.time() - start_time
        success_rate = frame_count / (frame_count + failed_reads) * 100
        
        print(f"Results:")
        print(f"  Frames captured: {frame_count}")
        print(f"  Failed reads: {failed_reads}")
        print(f"  Success rate: {success_rate:.1f}%")
        print(f"  Effective FPS: {frame_count/elapsed:.1f}")
        
        return success_rate > 80  # Consider 80%+ success rate as good
    
    def get_camera_info(self):
        """Get camera properties"""
        if not self.camera:
            return None
        
        info = {
            'method': self.method_used,
            'width': int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': self.camera.get(cv2.CAP_PROP_FPS),
            'backend': self.camera.getBackendName()
        }
        
        return info
    
    def release(self):
        """Release camera resources"""
        if self.camera:
            self.camera.release()
            self.camera = None

def test_camera_fix():
    """Test the camera fix"""
    print("Raspberry Pi Camera Fix Test")
    print("=" * 40)
    
    manager = PiCameraManager()
    
    # Try to initialize camera
    if manager.initialize_camera():
        print(f"\n✓ Camera initialized successfully!")
        
        # Get camera info
        info = manager.get_camera_info()
        if info:
            print(f"  Method: {info['method']}")
            print(f"  Resolution: {info['width']}x{info['height']}")
            print(f"  FPS: {info['fps']}")
            print(f"  Backend: {info['backend']}")
        
        # Test sustained capture
        if manager.test_sustained_capture():
            print("✓ Sustained capture test passed!")
            
            # Create working code template
            print("\n" + "="*50)
            print("WORKING CAMERA CODE:")
            print("="*50)
            
            if "GStreamer" in manager.method_used:
                if "libcamera" in manager.method_used:
                    pipeline = "libcamerasrc ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! appsink"
                else:
                    pipeline = "v4l2src device=/dev/video0 ! video/x-raw,width=640,height=480 ! videoconvert ! appsink"
                
                print(f"""
# Use this in your QR scanner:
def initialize_camera(self):
    pipeline = "{pipeline}"
    self.camera = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    if not self.camera.isOpened():
        raise Exception("Cannot open camera")
""")
            else:
                index = manager.method_used.split()[-1] if "Index" in manager.method_used else "0"
                backend = "cv2.CAP_V4L2" if "V4L2" in manager.method_used else "cv2.CAP_ANY"
                
                print(f"""
# Use this in your QR scanner:
def initialize_camera(self):
    self.camera = cv2.VideoCapture({index}, {backend})
    if not self.camera.isOpened():
        raise Exception("Cannot open camera")
    
    # Set properties
    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
""")
        else:
            print("⚠ Camera works but sustained capture has issues")
    
    else:
        print("✗ Failed to initialize camera")
        print("\nTroubleshooting steps:")
        print("1. Check camera connection")
        print("2. Enable camera: sudo raspi-config")
        print("3. Reboot: sudo reboot")
        print("4. Check permissions: ls -l /dev/video*")
        print("5. Install packages: sudo apt-get install v4l-utils")
    
    # Cleanup
    manager.release()

if __name__ == "__main__":
    test_camera_fix()