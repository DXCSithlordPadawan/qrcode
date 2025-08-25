#!/usr/bin/env python3
"""
Raspberry Pi QR Code Scanner
Scans QR codes using camera, identifies locations and objects, sends messages to RabbitMQ
"""

import cv2
import json
import pika
import logging
import time
import traceback
from datetime import datetime
from pyzbar import pyzbar
import threading
import signal
import sys
from typing import Optional, Dict, Any

class QRCodeScanner:
    def __init__(self, config_file: str = 'config.json'):
        """Initialize the QR Code Scanner"""
        # Initialize logger first, before loading config
        self.setup_basic_logging()
        
        self.config = self.load_config(config_file)
        self.current_location = None
        self.last_scans = {}  # To prevent duplicate scans
        self.running = True
        
        # Setup proper logging after config is loaded
        self.setup_logging()
        
        # Initialize camera
        self.camera = None
        self.initialize_camera()
        
        # Initialize RabbitMQ connection
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        self.initialize_rabbitmq()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def setup_basic_logging(self):
        """Setup basic logging before config is loaded"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_logging(self):
        """Setup full logging after config is loaded"""
        try:
            # Clear existing handlers
            self.logger.handlers.clear()
            
            log_level = self.config.get('scanner_settings', {}).get('log_level', 'INFO')
            
            logging.basicConfig(
                level=getattr(logging, log_level),
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler('/var/log/qr_scanner.log'),
                    logging.StreamHandler()
                ]
            )
            self.logger = logging.getLogger(__name__)
        except Exception as e:
            self.logger.error(f"Failed to setup full logging: {e}")
    
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """Load configuration from JSON file with better error handling"""
        try:
            # Check if file exists
            import os
            if not os.path.exists(config_file):
                self.logger.error(f"Configuration file {config_file} not found")
                self.logger.info("Please ensure the config.json file exists in the same directory as this script")
                sys.exit(1)
            
            # Load and parse JSON
            with open(config_file, 'r') as f:
                content = f.read()
                self.logger.debug(f"Config file content length: {len(content)} characters")
                
                # Try to parse JSON
                config = json.loads(content)
                
                # Validate required sections
                required_sections = ['qr_codes', 'scanner_settings', 'processing_rules']
                for section in required_sections:
                    if section not in config:
                        self.logger.error(f"Missing required configuration section: {section}")
                        sys.exit(1)
                
                # Validate QR codes section
                if 'locations' not in config['qr_codes'] or 'objects' not in config['qr_codes']:
                    self.logger.error("QR codes section must contain 'locations' and 'objects'")
                    sys.exit(1)
                
                self.logger.info("Configuration loaded successfully")
                self.logger.info(f"Loaded {len(config['qr_codes']['locations'])} locations and {len(config['qr_codes']['objects'])} objects")
                
                return config
                
        except FileNotFoundError:
            self.logger.error(f"Configuration file {config_file} not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing configuration file: {e}")
            self.logger.error(f"JSON Error at line {e.lineno}, column {e.colno}: {e.msg}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Unexpected error loading configuration: {e}")
            self.logger.error(traceback.format_exc())
            sys.exit(1)
    
    def initialize_camera(self):
        """Initialize the camera with better error handling"""
        try:
            camera_index = self.config['scanner_settings']['camera_index']
            self.logger.info(f"Attempting to initialize camera at index {camera_index}")
            
            self.camera = cv2.VideoCapture(camera_index)
            if not self.camera.isOpened():
                raise Exception(f"Cannot open camera at index {camera_index}")
            
            # Set camera properties for better QR code detection
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            
            # Test camera by reading a frame
            ret, frame = self.camera.read()
            if not ret:
                raise Exception("Camera opened but cannot read frames")
            
            self.logger.info(f"Camera initialized successfully - Frame size: {frame.shape}")
        except Exception as e:
            self.logger.error(f"Failed to initialize camera: {e}")
            self.logger.error("Please check if camera is connected and accessible")
            self.logger.error("You can test camera access with: v4l2-ctl --list-devices")
            sys.exit(1)
    
    def initialize_rabbitmq(self):
        """Initialize RabbitMQ connection with better error handling"""
        try:
            if 'rabbitmq' not in self.config:
                self.logger.warning("RabbitMQ configuration not found, skipping RabbitMQ initialization")
                return
                
            rabbitmq_config = self.config['rabbitmq']
            self.logger.info(f"Connecting to RabbitMQ at {rabbitmq_config['host']}:{rabbitmq_config['port']}")
            
            credentials = pika.PlainCredentials(
                rabbitmq_config['username'],
                rabbitmq_config['password']
            )
            
            parameters = pika.ConnectionParameters(
                host=rabbitmq_config['host'],
                port=rabbitmq_config['port'],
                virtual_host=rabbitmq_config['virtual_host'],
                credentials=credentials
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
            
            self.logger.info("RabbitMQ connection established")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize RabbitMQ: {e}")
            self.logger.warning("Continuing without RabbitMQ - messages will be logged only")
            self.rabbitmq_connection = None
            self.rabbitmq_channel = None
    
    def decode_qr_codes(self, frame) -> list:
        """Decode QR codes from camera frame"""
        try:
            # Convert to grayscale for better detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect and decode QR codes
            qr_codes = pyzbar.decode(gray)
            
            if qr_codes:
                self.logger.debug(f"Found {len(qr_codes)} QR codes in frame")
                
            return qr_codes
            
        except Exception as e:
            self.logger.error(f"Error decoding QR codes: {e}")
            return []
    
    def process_qr_code(self, qr_data: str) -> Optional[Dict[str, Any]]:
        """Process a detected QR code with improved matching logic"""
        try:
            self.logger.info(f"Processing QR code: '{qr_data}'")
            
            # Check if it's a location QR code
            locations = self.config['qr_codes']['locations']
            
            # Try direct match first
            if qr_data in locations:
                self.current_location = qr_data
                location_info = locations[qr_data]
                location_desc = location_info.get('description', qr_data) if isinstance(location_info, dict) else str(location_info)
                self.logger.info(f"Location updated to: {qr_data} - {location_desc}")
                return {
                    'type': 'location',
                    'code': qr_data,
                    'description': location_desc
                }
            
            # Try pattern matching for locations (handle various formats)
            for location_key in locations.keys():
                if qr_data in location_key or location_key.endswith(f":{qr_data}") or location_key.endswith(f"|{qr_data}"):
                    self.current_location = qr_data
                    location_info = locations[location_key]
                    location_desc = location_info.get('description', qr_data) if isinstance(location_info, dict) else str(location_info)
                    self.logger.info(f"Location updated to: {qr_data} - {location_desc} (matched via pattern)")
                    return {
                        'type': 'location',
                        'code': qr_data,
                        'description': location_desc
                    }
            
            # Check if it's an object QR code
            objects = self.config['qr_codes']['objects']
            
            # Try direct match first
            object_info = None
            object_key = None
            
            if qr_data in objects:
                object_info = objects[qr_data]
                object_key = qr_data
            else:
                # Try pattern matching for objects
                for obj_key in objects.keys():
                    if qr_data in obj_key or obj_key.endswith(f"|{qr_data}") or obj_key.startswith(f"{qr_data}|"):
                        object_info = objects[obj_key]
                        object_key = qr_data
                        break
            
            if object_info:
                if self.current_location:
                    # Create message for RabbitMQ
                    message = self.create_scan_message(qr_data, self.current_location)
                    self.send_rabbitmq_message(message)
                    return {
                        'type': 'object',
                        'code': qr_data,
                        'object_info': object_info,
                        'location': self.current_location
                    }
                else:
                    self.logger.warning(f"Object {qr_data} scanned but no current location set")
                    self.logger.warning("Please scan a location QR code first")
                    return None
            
            # Unknown QR code
            self.logger.warning(f"Unknown QR code detected: '{qr_data}'")
            self.logger.info(f"Available locations: {list(locations.keys())}")
            self.logger.info(f"Available objects: {list(objects.keys())}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error processing QR code {qr_data}: {e}")
            self.logger.error(traceback.format_exc())
            return None
    
    def create_scan_message(self, object_code: str, location_code: str) -> Dict[str, Any]:
        """Create a message for RabbitMQ"""
        timestamp = datetime.now().isoformat()
        
        message = {
            'timestamp': timestamp,
            'scanner_id': f"raspberry_pi_{self.get_device_id()}",
            'object_code': object_code,
            'object_info': self.config['qr_codes']['objects'].get(object_code, {}),
            'location_code': location_code,
            'location_info': self.config['qr_codes']['locations'].get(location_code, ''),
            'event_type': 'object_location_update',
            'source': 'qr_scanner'
        }
        
        return message
    
    def get_device_id(self) -> str:
        """Get a unique device identifier"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        return line.split(':')[1].strip()
            return 'unknown'
        except:
            return 'unknown'
    
    def send_rabbitmq_message(self, message: Dict[str, Any]):
        """Send message to RabbitMQ"""
        try:
            if not self.rabbitmq_channel:
                self.logger.warning("RabbitMQ not available, logging message instead")
                self.logger.info(f"SCAN EVENT: {message}")
                return
                
            rabbitmq_config = self.config['rabbitmq']
            
            self.rabbitmq_channel.basic_publish(
                exchange=rabbitmq_config['exchange'],
                routing_key=rabbitmq_config['routing_key_scan'],
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    timestamp=int(time.time())
                )
            )
            
            self.logger.info(f"Message sent to RabbitMQ: {message['object_code']} at {message['location_code']}")
            
        except Exception as e:
            self.logger.error(f"Failed to send RabbitMQ message: {e}")
            self.logger.info(f"SCAN EVENT (failed to send): {message}")
    
    def is_duplicate_scan(self, qr_data: str) -> bool:
        """Check if this is a duplicate scan within the time window"""
        current_time = time.time()
        window = self.config['processing_rules']['duplicate_scan_window_seconds']
        
        if qr_data in self.last_scans:
            if current_time - self.last_scans[qr_data] < window:
                return True
        
        self.last_scans[qr_data] = current_time
        return False
    
    def run(self):
        """Main scanning loop"""
        self.logger.info("Starting QR Code Scanner")
        self.logger.info(f"Current location: {self.current_location}")
        self.logger.info("Scan a location QR code first, then scan object QR codes")
        
        scan_interval = self.config['scanner_settings']['scan_interval']
        enable_preview = self.config['scanner_settings']['enable_preview']
        
        frame_count = 0
        last_status_log = time.time()
        
        while self.running:
            try:
                # Capture frame from camera
                ret, frame = self.camera.read()
                if not ret:
                    self.logger.error("Failed to capture frame from camera")
                    time.sleep(1)
                    continue
                
                frame_count += 1
                
                # Log status every 30 seconds
                current_time = time.time()
                if current_time - last_status_log > 30:
                    self.logger.info(f"Scanner running - processed {frame_count} frames, current location: {self.current_location}")
                    last_status_log = current_time
                
                # Decode QR codes
                qr_codes = self.decode_qr_codes(frame)
                
                # Process each detected QR code
                for qr_code in qr_codes:
                    qr_data = qr_code.data.decode('utf-8')
                    
                    # Skip duplicate scans
                    if self.is_duplicate_scan(qr_data):
                        self.logger.debug(f"Skipping duplicate scan: {qr_data}")
                        continue
                    
                    # Process the QR code
                    result = self.process_qr_code(qr_data)
                    if result:
                        self.logger.info(f"QR Code processed successfully: {result['type']} - {result['code']}")
                
                # Show preview if enabled
                if enable_preview:
                    # Draw rectangles around detected QR codes
                    for qr_code in qr_codes:
                        points = qr_code.polygon
                        if len(points) > 4:
                            hull = cv2.convexHull(points)
                            cv2.polylines(frame, [hull], True, (0, 255, 0), 2)
                        else:
                            cv2.polylines(frame, [points], True, (0, 255, 0), 2)
                        
                        # Add text label
                        qr_data = qr_code.data.decode('utf-8')
                        cv2.putText(frame, qr_data, (points[0].x, points[0].y - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    
                    # Add status text
                    status_text = f"Location: {self.current_location or 'Not Set'}"
                    cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    
                    cv2.imshow('QR Scanner', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                time.sleep(scan_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                self.logger.error(traceback.format_exc())
                time.sleep(5)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up resources...")
        
        if self.camera:
            self.camera.release()
        
        if cv2:
            cv2.destroyAllWindows()
        
        if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
            self.rabbitmq_connection.close()
        
        self.logger.info("Cleanup complete")

def main():
    """Main function"""
    try:
        scanner = QRCodeScanner()
        scanner.run()
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
    finally:
        if 'scanner' in locals():
            scanner.cleanup()

if __name__ == "__main__":
    main()