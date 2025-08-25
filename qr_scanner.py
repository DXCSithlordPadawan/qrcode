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
from datetime import datetime
from pyzbar import pyzbar
import threading
import signal
import sys
from typing import Optional, Dict, Any

class QRCodeScanner:
    def __init__(self, config_file: str = 'config.json'):
        """Initialize the QR Code Scanner"""
        self.config = self.load_config(config_file)
        self.current_location = None
        self.last_scans = {}  # To prevent duplicate scans
        self.running = True
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, self.config['scanner_settings']['log_level']),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/var/log/qr_scanner.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
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
    
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error(f"Configuration file {config_file} not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing configuration file: {e}")
            sys.exit(1)
    
    def initialize_camera(self):
        """Initialize the camera"""
        try:
            camera_index = self.config['scanner_settings']['camera_index']
            self.camera = cv2.VideoCapture(camera_index)
            if not self.camera.isOpened():
                raise Exception(f"Cannot open camera at index {camera_index}")
            
            # Set camera properties for better QR code detection
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            
            self.logger.info("Camera initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize camera: {e}")
            sys.exit(1)
    
    def initialize_rabbitmq(self):
        """Initialize RabbitMQ connection"""
        try:
            rabbitmq_config = self.config['rabbitmq']
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
            sys.exit(1)
    
    def decode_qr_codes(self, frame) -> list:
        """Decode QR codes from camera frame"""
        try:
            # Convert to grayscale for better detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect and decode QR codes
            qr_codes = pyzbar.decode(gray)
            return qr_codes
            
        except Exception as e:
            self.logger.error(f"Error decoding QR codes: {e}")
            return []
    
    def process_qr_code(self, qr_data: str) -> Optional[Dict[str, Any]]:
        """Process a detected QR code"""
        try:
            # Check if it's a location QR code
            locations = self.config['qr_codes']['locations']
            if qr_data in locations:
                self.current_location = qr_data
                self.logger.info(f"Location updated to: {locations[qr_data]}")
                return {
                    'type': 'location',
                    'code': qr_data,
                    'description': locations[qr_data]
                }
            
            # Check if it's an object QR code
            objects = self.config['qr_codes']['objects']
            if qr_data in objects:
                if self.current_location:
                    # Create message for RabbitMQ
                    message = self.create_scan_message(qr_data, self.current_location)
                    self.send_rabbitmq_message(message)
                    return {
                        'type': 'object',
                        'code': qr_data,
                        'object_info': objects[qr_data],
                        'location': self.current_location
                    }
                else:
                    self.logger.warning(f"Object {qr_data} scanned but no current location set")
                    return None
            
            # Unknown QR code
            self.logger.warning(f"Unknown QR code detected: {qr_data}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error processing QR code {qr_data}: {e}")
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
        
        scan_interval = self.config['scanner_settings']['scan_interval']
        enable_preview = self.config['scanner_settings']['enable_preview']
        
        while self.running:
            try:
                # Capture frame from camera
                ret, frame = self.camera.read()
                if not ret:
                    self.logger.error("Failed to capture frame from camera")
                    time.sleep(1)
                    continue
                
                # Decode QR codes
                qr_codes = self.decode_qr_codes(frame)
                
                # Process each detected QR code
                for qr_code in qr_codes:
                    qr_data = qr_code.data.decode('utf-8')
                    
                    # Skip duplicate scans
                    if self.is_duplicate_scan(qr_data):
                        continue
                    
                    # Process the QR code
                    result = self.process_qr_code(qr_data)
                    if result:
                        self.logger.info(f"QR Code processed: {result}")
                
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
                    
                    cv2.imshow('QR Scanner', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                time.sleep(scan_interval)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
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
        pass
    finally:
        if 'scanner' in locals():
            scanner.cleanup()

if __name__ == "__main__":
    main()