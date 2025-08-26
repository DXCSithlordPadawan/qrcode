#!/usr/bin/env python3
"""
Fixed Bookworm QR Scanner - Addresses silent failure issues
"""

import cv2
import logging
import time
import sys
from pyzbar import pyzbar

try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
    print("PiCamera2 import successful")
except ImportError as e:
    PICAMERA2_AVAILABLE = False
    print(f"PiCamera2 import failed: {e}")

class BookwormQRScanner:
    def __init__(self):
        """Initialize scanner with proper logging"""
        # Setup logging first
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        self.logger = logging.getLogger(__name__)
        
        self.picam2 = None
        self.running = True
        
        print("Scanner initialized")
        self.logger.info("BookwormQRScanner initialized")
    
    def initialize_camera(self):
        """Initialize PiCamera2 with proper error handling"""
        if not PICAMERA2_AVAILABLE:
            self.logger.error("PiCamera2 not available - cannot initialize camera")
            return False
            
        try:
            self.logger.info("Starting PiCamera2 initialization...")
            print("Initializing PiCamera2...")
            
            self.picam2 = Picamera2()
            
            # Check if camera is detected (compatible with different PiCamera2 versions)
            try:
                if hasattr(self.picam2, 'camera_info'):
                    camera_info = self.picam2.camera_info
                    self.logger.info(f"Camera detected: {camera_info}")
                    print(f"Camera info: {camera_info}")
                else:
                    self.logger.info("Camera detected (info not available in this PiCamera2 version)")
                    print("Camera detected")
            except Exception as info_error:
                self.logger.warning(f"Could not get camera info: {info_error}")
                print("Camera detected but info unavailable")
            
            # Configure for QR code scanning
            self.logger.info("Configuring camera...")
            config = self.picam2.create_video_configuration({
                "size": (640, 480),
                "format": "RGB888"
            })
            
            self.picam2.configure(config)
            self.logger.info("Camera configured, starting...")
            
            self.picam2.start()
            self.logger.info("Camera started, waiting for stabilization...")
            
            # Allow camera to stabilize
            time.sleep(3)
            
            # Test frame capture
            test_frame = self.picam2.capture_array()
            if test_frame is not None and test_frame.size > 0:
                self.logger.info(f"Camera test successful - Frame shape: {test_frame.shape}")
                print(f"Camera initialized successfully - Frame: {test_frame.shape}")
                return True
            else:
                raise Exception("Camera started but cannot capture frames")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize PiCamera2: {e}")
            print(f"Camera initialization failed: {e}")
            
            # Cleanup on failure
            if self.picam2:
                try:
                    self.picam2.stop()
                    self.picam2.close()
                except:
                    pass
                self.picam2 = None
            
            return False
    
    def capture_frame(self):
        """Capture frame with error handling"""
        if not self.picam2:
            self.logger.error("Camera not initialized")
            return False, None
            
        try:
            frame = self.picam2.capture_array()
            if frame is not None and frame.size > 0:
                # Convert RGB to BGR for OpenCV
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return True, frame_bgr
            else:
                self.logger.warning("Captured frame is empty")
                return False, None
                
        except Exception as e:
            self.logger.error(f"Frame capture failed: {e}")
            return False, None
    
    def decode_qr_codes(self, frame):
        """Decode QR codes with error handling"""
        try:
            if frame is None:
                return []
                
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            qr_codes = pyzbar.decode(gray)
            
            if qr_codes:
                self.logger.info(f"Found {len(qr_codes)} QR codes")
                for qr in qr_codes:
                    qr_data = qr.data.decode('utf-8')
                    self.logger.info(f"QR Code detected: '{qr_data}'")
                    print(f"QR Code: {qr_data}")
            
            return qr_codes
            
        except Exception as e:
            self.logger.error(f"QR decode failed: {e}")
            return []
    
    def run(self):
        """Main loop with comprehensive error handling"""
        self.logger.info("Starting main scanner loop...")
        print("Starting QR scanner...")
        
        if not self.initialize_camera():
            print("FATAL: Camera initialization failed")
            return
        
        frame_count = 0
        last_status = time.time()
        
        try:
            while self.running:
                try:
                    ret, frame = self.capture_frame()
                    
                    if not ret or frame is None:
                        self.logger.warning("Failed to capture frame")
                        time.sleep(0.5)
                        continue
                    
                    frame_count += 1
                    
                    # Status update every 10 seconds
                    current_time = time.time()
                    if current_time - last_status > 10:
                        self.logger.info(f"Scanner running - processed {frame_count} frames")
                        print(f"Scanner active - {frame_count} frames processed")
                        last_status = current_time
                    
                    # Decode QR codes
                    qr_codes = self.decode_qr_codes(frame)
                    
                    # Show preview if requested
                    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
                        for qr_code in qr_codes:
                            # Draw rectangle around QR code
                            points = qr_code.polygon
                            if len(points) == 4:
                                pts = [(p.x, p.y) for p in points]
                                pts = [(pts[0], pts[1]), (pts[1], pts[2]), 
                                      (pts[2], pts[3]), (pts[3], pts[0])]
                                for i in range(4):
                                    cv2.line(frame, pts[i][0], pts[i][1], (0, 255, 0), 2)
                        
                        cv2.imshow('QR Scanner', frame)
                        key = cv2.waitKey(1) & 0xFF
                        if key == ord('q'):
                            print("Quit key pressed")
                            break
                    
                    time.sleep(0.1)
                    
                except KeyboardInterrupt:
                    self.logger.info("Keyboard interrupt received")
                    print("Stopping scanner...")
                    break
                    
                except Exception as e:
                    self.logger.error(f"Error in main loop: {e}")
                    print(f"Loop error: {e}")
                    time.sleep(1)
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up...")
        print("Cleaning up camera...")
        
        self.running = False
        
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
                self.logger.info("PiCamera2 stopped")
            except Exception as e:
                self.logger.error(f"Error stopping camera: {e}")
        
        try:
            cv2.destroyAllWindows()
        except:
            pass
        
        print("Cleanup complete")

def main():
    """Main function with error handling"""
    print("=" * 50)
    print("Bookworm QR Scanner Starting...")
    print("=" * 50)
    
    try:
        scanner = BookwormQRScanner()
        print("Use --preview argument to show camera preview")
        print("Press Ctrl+C to stop")
        scanner.run()
        
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("Scanner stopped")

if __name__ == "__main__":
    main()