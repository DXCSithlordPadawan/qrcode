#!/usr/bin/env python3
"""
Complete Bookworm QR Scanner with RabbitMQ Integration
"""

import cv2
import json
import pika
import logging
import time
import sys
import subprocess
from datetime import datetime
from pyzbar import pyzbar
from pathlib import Path

try:
    from picamera2 import Picamera2
    import picamera2
    PICAMERA2_AVAILABLE = True
    PICAMERA2_VERSION = getattr(picamera2, '__version__', 'unknown')
except ImportError:
    PICAMERA2_AVAILABLE = False
    PICAMERA2_VERSION = None

class CompleteBookwormScanner:
    def __init__(self, config_file='config.json'):
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.config = self.load_config(config_file)
        
        # Initialize state
        self.picam2 = None
        self.running = True
        self.current_location = None
        self.last_scans = {}
        
        # RabbitMQ components
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        
        print(f"Scanner initialized with config from {config_file}")
    
    def load_config(self, config_file):
        """Load configuration file"""
        try:
            config_path = Path(config_file)
            if not config_path.exists():
                print(f"ERROR: Configuration file {config_file} not found")
                print("Make sure your config.json file exists in the current directory")
                sys.exit(1)
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Validate required sections
            required = ['qr_codes', 'scanner_settings', 'processing_rules']
            missing = [section for section in required if section not in config]
            
            if missing:
                print(f"ERROR: Missing required config sections: {missing}")
                sys.exit(1)
            
            print(f"Configuration loaded: {len(config['qr_codes']['locations'])} locations, {len(config['qr_codes']['objects'])} objects")
            
            if 'rabbitmq' in config:
                print("RabbitMQ configuration found")
            else:
                print("WARNING: No RabbitMQ configuration - will run in local mode")
            
            return config
            
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in config file: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Failed to load config: {e}")
            sys.exit(1)
    
    def initialize_camera(self):
        """Initialize camera with compatibility handling"""
        if not PICAMERA2_AVAILABLE:
            print("ERROR: PiCamera2 not available")
            return False
        
        try:
            print("Initializing PiCamera2...")
            self.picam2 = Picamera2()
            
            # Create configuration (try multiple methods for compatibility)
            config_methods = [
                lambda: self.picam2.create_video_configuration({"size": (640, 480), "format": "RGB888"}),
                lambda: self.picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"}),
            ]
            
            config = None
            for method in config_methods:
                try:
                    config = method()
                    if config:
                        break
                except Exception as e:
                    continue
            
            if not config:
                raise Exception("Failed to create camera configuration")
            
            self.picam2.configure(config)
            self.picam2.start()
            time.sleep(2)
            
            # Test capture
            test_frame = self.picam2.capture_array()
            if test_frame is None or test_frame.size == 0:
                raise Exception("Camera started but cannot capture frames")
            
            print(f"Camera initialized successfully - Frame: {test_frame.shape}")
            return True
            
        except Exception as e:
            print(f"Camera initialization failed: {e}")
            if self.picam2:
                try:
                    self.picam2.stop()
                    self.picam2.close()
                except:
                    pass
                self.picam2 = None
            return False
    
    def initialize_rabbitmq(self):
        """Initialize RabbitMQ connection"""
        if 'rabbitmq' not in self.config:
            print("No RabbitMQ config - running in local mode")
            return True
        
        try:
            rabbitmq_config = self.config['rabbitmq']
            print(f"Connecting to RabbitMQ at {rabbitmq_config['host']}:{rabbitmq_config['port']}")
            
            credentials = pika.PlainCredentials(
                rabbitmq_config['username'],
                rabbitmq_config['password']
            )
            
            parameters = pika.ConnectionParameters(
                host=rabbitmq_config['host'],
                port=rabbitmq_config['port'],
                virtual_host=rabbitmq_config['virtual_host'],
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            self.rabbitmq_connection = pika.BlockingConnection(parameters)
            self.rabbitmq_channel = self.rabbitmq_connection.channel()
            
            # Declare exchange and queues
            self.rabbitmq_channel.exchange_declare(
                exchange=rabbitmq_config['exchange'],
                exchange_type='topic',
                durable=True
            )
            
            self.rabbitmq_channel.queue_declare(
                queue=rabbitmq_config['queue_scan_results'],
                durable=True
            )
            
            self.rabbitmq_channel.queue_bind(
                exchange=rabbitmq_config['exchange'],
                queue=rabbitmq_config['queue_scan_results'],
                routing_key=rabbitmq_config['routing_key_scan']
            )
            
            print("RabbitMQ connection established successfully")
            return True
            
        except Exception as e:
            print(f"RabbitMQ initialization failed: {e}")
            print("Will continue in local mode - messages will be logged only")
            self.rabbitmq_connection = None
            self.rabbitmq_channel = None
            return True  # Continue without RabbitMQ
    
    def capture_frame(self):
        """Capture frame from camera"""
        if not self.picam2:
            return False, None
        
        try:
            frame = self.picam2.capture_array()
            if frame is not None and frame.size > 0:
                # Convert RGB to BGR for OpenCV
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return True, frame_bgr
            return False, None
        except Exception as e:
            self.logger.error(f"Frame capture failed: {e}")
            return False, None
    
    def decode_qr_codes(self, frame):
        """Decode QR codes from frame"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            qr_codes = pyzbar.decode(gray)
            return qr_codes
        except Exception as e:
            self.logger.error(f"QR decode failed: {e}")
            return []
    
    def process_qr_code(self, qr_data):
    """Process detected QR code and handle location/object logic"""
    try:
        # Normalize the QR data - remove whitespace and convert to uppercase
        qr_data_normalized = qr_data.strip().upper()
        
        print(f"\n--- Processing QR Code: '{qr_data}' (normalized: '{qr_data_normalized}') ---")
        
        # Check if it's a location QR code
        locations = self.config['qr_codes']['locations']
        
        # Check both original and normalized versions
        location_key = None
        if qr_data in locations:
            location_key = qr_data
        elif qr_data_normalized in locations:
            location_key = qr_data_normalized
        
        if location_key:
            self.current_location = location_key
            location_info = locations[location_key]
            
            # Handle both dictionary and string formats safely
            if isinstance(location_info, dict):
                description = location_info.get('description', location_info.get('name', location_key))
            else:
                description = str(location_info)
            
            print(f"✓ LOCATION SET: {location_key} - {description}")
            print(f"DEBUG: location_info type: {type(location_info)}")
            print(f"DEBUG: location_info content: {location_info}")
            self.logger.info(f"Location updated to: {location_key} - {description}")
            
            return {
                'type': 'location',
                'code': location_key,
                'description': description
            }
        
        # Check if it's an object QR code
        objects = self.config['qr_codes']['objects']
        
        # Check both original and normalized versions
        object_key = None
        if qr_data in objects:
            object_key = qr_data
        elif qr_data_normalized in objects:
            object_key = qr_data_normalized
        
        if object_key:
            object_info = objects[object_key]
            
            if self.current_location:
                # Create and send message
                message = self.create_scan_message(object_key, self.current_location)
                success = self.send_rabbitmq_message(message)
                
                print(f"✓ OBJECT SCANNED: {object_key} at location {self.current_location}")
                print(f"✓ MESSAGE SENT: {'RabbitMQ' if success else 'Local Log'}")
                
                return {
                    'type': 'object',
                    'code': object_key,
                    'object_info': object_info,
                    'location': self.current_location,
                    'message_sent': success
                }
            else:
                print(f"⚠ OBJECT DETECTED: {object_key} but NO LOCATION SET")
                print("Please scan a location QR code first")
                return {
                    'type': 'object_no_location',
                    'code': object_key,
                    'object_info': object_info
                }
        
        # Unknown QR code
        print(f"? UNKNOWN QR CODE: '{qr_data}' (normalized: '{qr_data_normalized}')")
        print(f"Available locations: {list(locations.keys())}")
        print(f"Available objects: {list(objects.keys())}")
        return None
        
    except Exception as e:
        print(f"ERROR processing QR code: {e}")
        self.logger.error(f"Error processing QR code {qr_data}: {e}")
        return None
    
    def create_scan_message(self, object_code, location_code):
        """Create message for RabbitMQ"""
        message = {
            'timestamp': datetime.now().isoformat(),
            'scanner_id': f"bookworm_pi_{self.get_device_id()}",
            'object_code': object_code,
            'object_info': self.config['qr_codes']['objects'].get(object_code, {}),
            'location_code': location_code,
            'location_info': self.config['qr_codes']['locations'].get(location_code, ''),
            'event_type': 'object_location_update',
            'source': 'bookworm_qr_scanner'
        }
        
        print(f"Created message: {object_code} -> {location_code}")
        return message
    
    def get_device_id(self):
        """Get device identifier"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        return line.split(':')[1].strip()
            return 'unknown_bookworm'
        except:
            return 'unknown_bookworm'
    
    def send_rabbitmq_message(self, message):
        """Send message to RabbitMQ or log locally"""
        try:
            if self.rabbitmq_channel:
                rabbitmq_config = self.config['rabbitmq']
                
                self.rabbitmq_channel.basic_publish(
                    exchange=rabbitmq_config['exchange'],
                    routing_key=rabbitmq_config['routing_key_scan'],
                    body=json.dumps(message, indent=2),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Persistent
                        timestamp=int(time.time())
                    )
                )
                
                print(f"📤 RabbitMQ Message Sent Successfully")
                self.logger.info(f"RabbitMQ: {message['object_code']} at {message['location_code']}")
                return True
            else:
                print("📝 LOCAL MODE - Message logged:")
                print(json.dumps(message, indent=2))
                self.logger.info(f"LOCAL: {message['object_code']} at {message['location_code']}")
                return False
                
        except Exception as e:
            print(f"❌ Message sending failed: {e}")
            print("📝 Logging message locally:")
            print(json.dumps(message, indent=2))
            self.logger.error(f"Message send failed: {e}")
            return False
    
    def is_duplicate_scan(self, qr_data):
        """Check for duplicate scans"""
        current_time = time.time()
        window = self.config['processing_rules']['duplicate_scan_window_seconds']
        
        if qr_data in self.last_scans:
            if current_time - self.last_scans[qr_data] < window:
                return True
        
        self.last_scans[qr_data] = current_time
        return False
    
    def run(self):
        """Main scanner loop"""
        print("\n" + "="*60)
        print("COMPLETE BOOKWORM QR SCANNER WITH RABBITMQ")
        print("="*60)
        
        # Initialize components
        if not self.initialize_camera():
            print("FATAL: Camera initialization failed")
            return False
        
        if not self.initialize_rabbitmq():
            print("FATAL: Could not initialize messaging system")
            return False
        
        print(f"\n🎯 SCANNER READY!")
        print(f"📍 Current location: {self.current_location or 'Not set - scan a location QR first'}")
        print(f"🔗 RabbitMQ: {'Connected' if self.rabbitmq_channel else 'Local mode'}")
        print(f"⏱️  Duplicate scan window: {self.config['processing_rules']['duplicate_scan_window_seconds']}s")
        print("\nHold QR codes in front of camera...")
        print("Press Ctrl+C to stop\n")
        
        frame_count = 0
        qr_count = 0
        message_count = 0
        last_status = time.time()
        
        try:
            while self.running:
                # Capture frame
                ret, frame = self.capture_frame()
                if not ret or frame is None:
                    time.sleep(0.1)
                    continue
                
                frame_count += 1
                
                # Decode QR codes
                qr_codes = self.decode_qr_codes(frame)
                
                # Process each QR code
                for qr_code in qr_codes:
                    qr_data = qr_code.data.decode('utf-8')
                    
                    # Skip duplicates
                    if self.is_duplicate_scan(qr_data):
                        print(f"⏭️  Duplicate scan skipped: {qr_data}")
                        continue
                    
                    # Process QR code
                    result = self.process_qr_code(qr_data)
                    if result:
                        qr_count += 1
                        if result.get('message_sent'):
                            message_count += 1
                
                # Status update every 30 seconds
                current_time = time.time()
                if current_time - last_status > 30:
                    print(f"\n📊 STATUS: {frame_count} frames | {qr_count} QR codes | {message_count} messages sent")
                    print(f"📍 Current location: {self.current_location or 'Not set'}")
                    last_status = current_time
                
                # Preview mode
                if len(sys.argv) > 1 and sys.argv[1] == "--preview":
                    for qr_code in qr_codes:
                        points = qr_code.polygon
                        if len(points) >= 4:
                            try:
                                pts = [(p.x, p.y) for p in points]
                                for i in range(len(pts)):
                                    cv2.line(frame, pts[i], pts[(i+1) % len(pts)], (0, 255, 0), 2)
                                # Add QR data as text
                                qr_text = qr_code.data.decode('utf-8')
                                cv2.putText(frame, qr_text, (pts[0][0], pts[0][1]-10), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                            except:
                                pass
                    
                    # Add status overlay
                    status_text = f"Location: {self.current_location or 'Not Set'}"
                    cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                    
                    cv2.imshow('Complete QR Scanner', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                time.sleep(0.05)  # 20 FPS
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping scanner...")
        except Exception as e:
            print(f"❌ Scanner error: {e}")
        finally:
            self.cleanup()
            print(f"\n📊 FINAL STATS: {qr_count} QR codes processed, {message_count} messages sent")
            return True
    
    def cleanup(self):
        """Cleanup resources"""
        print("🧹 Cleaning up...")
        self.running = False
        
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
                print("📷 Camera stopped")
            except:
                pass
        
        if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
            try:
                self.rabbitmq_connection.close()
                print("🔗 RabbitMQ disconnected")
            except:
                pass
        
        try:
            cv2.destroyAllWindows()
        except:
            pass
        
        print("✅ Cleanup complete")

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print("Usage:")
        print("  python3 complete_rabbitmq_scanner.py           # Basic mode")
        print("  python3 complete_rabbitmq_scanner.py --preview # With camera preview")
        print("")
        print("Requirements:")
        print("  - config.json file in current directory")
        print("  - Camera enabled and connected")
        print("  - RabbitMQ server running (optional)")
        return
    
    try:
        scanner = CompleteBookwormScanner()
        scanner.run()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
