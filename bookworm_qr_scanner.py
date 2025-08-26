
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
