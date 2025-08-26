#!/usr/bin/env python3
"""
Version-Compatible Bookworm QR Scanner
Handles different PiCamera2 versions and provides better error diagnostics
"""

import cv2
import logging
import time
import sys
import subprocess
from pyzbar import pyzbar

# Check PiCamera2 availability and version
try:
    from picamera2 import Picamera2
    import picamera2
    PICAMERA2_AVAILABLE = True
    PICAMERA2_VERSION = getattr(picamera2, '__version__', 'unknown')
    print(f"PiCamera2 version {PICAMERA2_VERSION} imported successfully")
except ImportError as e:
    PICAMERA2_AVAILABLE = False
    PICAMERA2_VERSION = None
    print(f"PiCamera2 import failed: {e}")

class CompatibleBookwormScanner:
    def __init__(self):
        """Initialize scanner with version compatibility"""
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        self.logger = logging.getLogger(__name__)
        
        self.picam2 = None
        self.running = True
        
        print(f"Scanner initialized - PiCamera2 available: {PICAMERA2_AVAILABLE}")
        if PICAMERA2_AVAILABLE:
            print(f"PiCamera2 version: {PICAMERA2_VERSION}")
        
        self.logger.info("CompatibleBookwormScanner initialized")
    
    def check_camera_status(self):
        """Check camera status using system tools"""
        print("\n=== Camera Status Check ===")
        
        # Check libcamera detection
        try:
            result = subprocess.run(['libcamera-hello', '--list-cameras'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("libcamera detected cameras:")
                print(result.stdout)
                return True
            else:
                print(f"libcamera error: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print("libcamera-hello timed out")
            return False
        except FileNotFoundError:
            print("libcamera-hello not found - camera may not be properly configured")
            return False
        except Exception as e:
            print(f"Error checking camera status: {e}")
            return False
    
    def initialize_camera(self):
        """Initialize camera with version-compatible approach"""
        if not PICAMERA2_AVAILABLE:
            self.logger.error("PiCamera2 not available")
            return False
        
        if not self.check_camera_status():
            print("Camera status check failed - camera may not be available")
            return False
        
        try:
            self.logger.info(f"Initializing PiCamera2 version {PICAMERA2_VERSION}")
            print(f"Initializing PiCamera2...")
            
            # Create Picamera2 instance
            self.picam2 = Picamera2()
            
            # Get camera information (version-compatible)
            self._log_camera_info()
            
            # Create configuration
            self.logger.info("Creating camera configuration...")
            
            # Try different configuration methods based on version
            config = self._create_compatible_config()
            
            if config is None:
                raise Exception("Failed to create camera configuration")
            
            # Configure camera
            self.logger.info("Applying camera configuration...")
            self.picam2.configure(config)
            
            # Start camera
            self.logger.info("Starting camera...")
            self.picam2.start()
            
            # Wait for camera to stabilize
            self.logger.info("Waiting for camera stabilization...")
            time.sleep(3)
            
            # Test frame capture
            return self._test_frame_capture()
            
        except Exception as e:
            self.logger.error(f"Camera initialization failed: {e}")
            print(f"DETAILED ERROR: {str(e)}")
            
            # Print troubleshooting info
            self._print_troubleshooting_info()
            
            self._cleanup_failed_camera()
            return False
    
    def _log_camera_info(self):
        """Log camera information in a version-compatible way"""
        try:
            # Try different methods to get camera info
            info_methods = [
                ('camera_info', lambda: getattr(self.picam2, 'camera_info', None)),
                ('sensor_modes', lambda: getattr(self.picam2, 'sensor_modes', None)),
                ('camera_properties', lambda: getattr(self.picam2, 'camera_properties', None)),
            ]
            
            found_info = False
            for method_name, method_func in info_methods:
                try:
                    info = method_func()
                    if info:
                        self.logger.info(f"Camera {method_name}: {info}")
                        print(f"Camera {method_name}: {info}")
                        found_info = True
                        break
                except Exception as e:
                    self.logger.debug(f"Could not get {method_name}: {e}")
            
            if not found_info:
                self.logger.info("Camera detected but detailed info not available")
                print("Camera detected (detailed info not available)")
                
        except Exception as e:
            self.logger.warning(f"Could not get camera info: {e}")
            print("Camera info unavailable")
    
    def _create_compatible_config(self):
        """Create camera configuration compatible with different versions"""
        config_methods = [
            # Method 1: Modern create_video_configuration
            lambda: self.picam2.create_video_configuration({
                "size": (640, 480),
                "format": "RGB888"
            }),
            
            # Method 2: create_preview_configuration (alternative)
            lambda: self.picam2.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"}
            ),
            
            # Method 3: Direct configuration dict
            lambda: {
                "main": {"size": (640, 480), "format": "RGB888"},
                "controls": {"FrameDurationLimits": (33333, 33333)}
            }
        ]
        
        for i, method in enumerate(config_methods):
            try:
                self.logger.info(f"Trying configuration method {i+1}")
                config = method()
                if config:
                    self.logger.info(f"Configuration method {i+1} successful")
                    return config
            except Exception as e:
                self.logger.debug(f"Configuration method {i+1} failed: {e}")
                continue
        
        self.logger.error("All configuration methods failed")
        return None
    
    def _test_frame_capture(self):
        """Test frame capture capability"""
        try:
            self.logger.info("Testing frame capture...")
            
            # Try multiple capture attempts
            for attempt in range(3):
                try:
                    frame = self.picam2.capture_array()
                    if frame is not None and frame.size > 0:
                        self.logger.info(f"Frame capture successful - Shape: {frame.shape}, dtype: {frame.dtype}")
                        print(f"Camera test successful - Frame: {frame.shape}")
                        return True
                    else:
                        self.logger.warning(f"Capture attempt {attempt+1} returned empty frame")
                except Exception as capture_error:
                    self.logger.warning(f"Capture attempt {attempt+1} failed: {capture_error}")
                
                time.sleep(0.5)
            
            raise Exception("All frame capture attempts failed")
            
        except Exception as e:
            self.logger.error(f"Frame capture test failed: {e}")
            return False
    
    def _cleanup_failed_camera(self):
        """Cleanup camera resources after failed initialization"""
        if self.picam2:
            try:
                self.picam2.stop()
            except:
                pass
            try:
                self.picam2.close()
            except:
                pass
            self.picam2 = None
    
    def _print_troubleshooting_info(self):
        """Print troubleshooting information"""
        print("\n=== TROUBLESHOOTING INFO ===")
        print("1. Check camera is enabled:")
        print("   sudo raspi-config -> Interface Options -> Camera -> Enable")
        print("\n2. Check camera detection:")
        print("   libcamera-hello --list-cameras")
        print("\n3. Update system:")
        print("   sudo apt update && sudo apt upgrade")
        print("\n4. Reinstall PiCamera2:")
        print("   sudo apt install --reinstall python3-picamera2")
        print("\n5. Check camera cable connection")
        print("\n6. Reboot system:")
        print("   sudo reboot")
    
    def capture_frame(self):
        """Capture frame with error handling"""
        if not self.picam2:
            return False, None
        
        try:
            frame = self.picam2.capture_array()
            if frame is not None and frame.size > 0:
                # Handle different frame formats
                if len(frame.shape) == 3:
                    if frame.shape[2] == 3:  # RGB
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    elif frame.shape[2] == 4:  # RGBA
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                    else:
                        frame_bgr = frame
                else:
                    frame_bgr = frame
                
                return True, frame_bgr
            else:
                return False, None
                
        except Exception as e:
            self.logger.error(f"Frame capture error: {e}")
            return False, None
    
    def decode_qr_codes(self, frame):
        """Decode QR codes with enhanced detection"""
        try:
            if frame is None:
                return []
            
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Try multiple detection approaches
            detection_methods = [
                ("direct", gray),
                ("enhanced", cv2.equalizeHist(gray)),
                ("gaussian", cv2.GaussianBlur(gray, (3, 3), 0)),
            ]
            
            for method_name, processed_frame in detection_methods:
                qr_codes = pyzbar.decode(processed_frame)
                if qr_codes:
                    self.logger.info(f"QR codes found using {method_name} method: {len(qr_codes)}")
                    for qr in qr_codes:
                        qr_data = qr.data.decode('utf-8')
                        print(f"QR Code detected: '{qr_data}'")
                    return qr_codes
            
            return []
            
        except Exception as e:
            self.logger.error(f"QR decode failed: {e}")
            return []
    
    def run(self):
        """Main scanner loop"""
        print("\n=== STARTING SCANNER ===")
        
        if not self.initialize_camera():
            print("FATAL: Camera initialization failed")
            return False
        
        print("Scanner running successfully!")
        print("Hold QR codes in front of camera...")
        print("Press Ctrl+C to stop")
        
        frame_count = 0
        qr_count = 0
        last_status = time.time()
        
        try:
            while self.running:
                ret, frame = self.capture_frame()
                
                if not ret or frame is None:
                    self.logger.warning("Frame capture failed")
                    time.sleep(0.5)
                    continue
                
                frame_count += 1
                
                # Decode QR codes
                qr_codes = self.decode_qr_codes(frame)
                if qr_codes:
                    qr_count += len(qr_codes)
                
                # Status update every 10 seconds
                current_time = time.time()
                if current_time - last_status > 10:
                    print(f"Status: {frame_count} frames processed, {qr_count} QR codes found")
                    last_status = current_time
                
                # Preview mode
                if len(sys.argv) > 1 and sys.argv[1] == "--preview":
                    # Draw QR code boundaries
                    for qr_code in qr_codes:
                        points = qr_code.polygon
                        if len(points) >= 4:
                            try:
                                pts = [(p.x, p.y) for p in points]
                                for i in range(len(pts)):
                                    cv2.line(frame, pts[i], pts[(i+1) % len(pts)], (0, 255, 0), 2)
                            except:
                                pass
                    
                    cv2.imshow('QR Scanner', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nStopping scanner...")
        except Exception as e:
            print(f"Scanner error: {e}")
            self.logger.error(f"Scanner error: {e}")
        
        finally:
            self.cleanup()
            return True
    
    def cleanup(self):
        """Cleanup all resources"""
        print("Cleaning up...")
        self.running = False
        
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
                print("Camera stopped")
            except Exception as e:
                print(f"Error stopping camera: {e}")
        
        try:
            cv2.destroyAllWindows()
        except:
            pass
        
        print("Cleanup complete")

def main():
    """Main function"""
    print("=" * 60)
    print("Compatible Bookworm QR Scanner")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print("Usage:")
        print("  python3 compatible_bookworm_scanner.py          # Basic mode")
        print("  python3 compatible_bookworm_scanner.py --preview # With camera preview")
        return
    
    try:
        scanner = CompatibleBookwormScanner()
        success = scanner.run()
        
        if success:
            print("Scanner completed successfully")
        else:
            print("Scanner failed to run")
            
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()