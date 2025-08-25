#!/usr/bin/env python3
"""
RabbitMQ Message Processor
Consumes messages from RabbitMQ, processes according to rules, and sends updates to Tencent IES4 and Apache SOLR
"""

import json
import pika
import logging
import requests
import time
from datetime import datetime
from typing import Dict, Any, Optional
import signal
import sys
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

class MessageProcessor:
    def __init__(self, config_file: str = 'config.json'):
        """Initialize the Message Processor"""
        self.config = self.load_config(config_file)
        self.running = True
        self.processing_stats = {
            'messages_processed': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'start_time': datetime.now()
        }
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, self.config['scanner_settings']['log_level']),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/var/log/message_processor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize connections
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        self.initialize_rabbitmq()
        
        # Setup signal handlers
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
            
            # Declare queues
            for queue_name in [rabbitmq_config['queue_scan_results'], rabbitmq_config['queue_location_updates']]:
                self.rabbitmq_channel.queue_declare(queue=queue_name, durable=True)
            
            # Set QoS to process one message at a time
            self.rabbitmq_channel.basic_qos(prefetch_count=1)
            
            self.logger.info("RabbitMQ connection established")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize RabbitMQ: {e}")
            sys.exit(1)
    
    def process_scan_message(self, ch, method, properties, body):
        """Process incoming scan messages"""
        try:
            message = json.loads(body.decode('utf-8'))
            self.logger.info(f"Processing scan message: {message['object_code']}")
            
            # Apply processing rules
            if not self.should_process_message(message):
                self.logger.info(f"Message filtered by processing rules: {message['object_code']}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            # Process the message
            success = self.process_location_update(message)
            
            if success:
                self.processing_stats['successful_updates'] += 1
                self.logger.info(f"Successfully processed message: {message['object_code']}")
                
                # Send notification if required
                if self.should_send_notification(message):
                    self.send_notification(message)
                
                # Generate location update message
                self.generate_location_update_message(message)
                
            else:
                self.processing_stats['failed_updates'] += 1
                self.logger.error(f"Failed to process message: {message['object_code']}")
            
            self.processing_stats['messages_processed'] += 1
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def should_process_message(self, message: Dict[str, Any]) -> bool:
        """Apply processing rules to determine if message should be processed"""
        try:
            rules = self.config['processing_rules']
            
            # Check if auto-update is enabled
            if not rules.get('auto_update_location', True):
                self.logger.info("Auto-update disabled, skipping message")
                return False
            
            # Check for duplicate within notification threshold
            threshold_minutes = rules.get('notification_threshold_minutes', 5)
            message_time = datetime.fromisoformat(message['timestamp'])
            current_time = datetime.now()
            
            time_diff = (current_time - message_time).total_seconds() / 60
            if time_diff > threshold_minutes:
                self.logger.warning(f"Message is {time_diff:.1f} minutes old, processing anyway")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error applying processing rules: {e}")
            return True  # Process by default if rules fail
    
    def should_send_notification(self, message: Dict[str, Any]) -> bool:
        """Determine if notification should be sent"""
        # Add logic here for when to send notifications
        # For example, for certain object types or locations
        object_info = message.get('object_info', {})
        object_type = object_info.get('type', '')
        
        # Send notifications for high-value items
        high_value_types = ['Computer', 'Network Equipment']
        return object_type in high_value_types
    
    def process_location_update(self, message: Dict[str, Any]) -> bool:
        """Process location update by sending to IES4 and SOLR"""
        ies4_success = self.update_tencent_ies4(message)
        solr_success = self.update_apache_solr(message)
        
        return ies4_success and solr_success
    
    def update_tencent_ies4(self, message: Dict[str, Any]) -> bool:
        """Update Tencent IES4 schema"""
        try:
            ies4_config = self.config['tencent_ies4']
            
            # Prepare IES4 payload
            payload = {
                'tenant_id': ies4_config['tenant_id'],
                'entity_id': message['object_code'],
                'entity_type': 'asset',
                'location_id': message['location_code'],
                'timestamp': message['timestamp'],
                'attributes': {
                    'name': message['object_info'].get('name', ''),
                    'type': message['object_info'].get('type', ''),
                    'serial': message['object_info'].get('serial', ''),
                    'owner': message['object_info'].get('owner', ''),
                    'scanner_id': message.get('scanner_id', ''),
                    'location_description': message.get('location_info', '')
                },
                'event_type': 'location_update',
                'source': 'qr_scanner_system'
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {ies4_config['api_key']}",
                'User-Agent': 'QR-Scanner-System/1.0'
            }
            
            response = requests.post(
                f"{ies4_config['api_endpoint']}/entities/location",
                json=payload,
                headers=headers,
                timeout=ies4_config['timeout']
            )
            
            if response.status_code in [200, 201, 202]:
                self.logger.info(f"Successfully updated IES4 for {message['object_code']}")
                return True
            else:
                self.logger.error(f"IES4 update failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error updating IES4: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error updating IES4: {e}")
            return False
    
    def update_apache_solr(self, message: Dict[str, Any]) -> bool:
        """Update Apache SOLR schema"""
        try:
            solr_config = self.config['apache_solr']
            
            # Prepare SOLR document
            doc = {
                'id': f"{message['object_code']}_{int(time.time())}",
                'object_id': message['object_code'],
                'object_name': message['object_info'].get('name', ''),
                'object_type': message['object_info'].get('type', ''),
                'object_serial': message['object_info'].get('serial', ''),
                'object_owner': message['object_info'].get('owner', ''),
                'location_id': message['location_code'],
                'location_description': message.get('location_info', ''),
                'scanner_id': message.get('scanner_id', ''),
                'timestamp': message['timestamp'],
                'event_type': message.get('event_type', 'location_update')
            }
            
            # Update current location (upsert)
            current_location_doc = {
                'id': message['object_code'],  # Use object_code as ID for current location
                'object_id': message['object_code'],
                'object_name': message['object_info'].get('name', ''),
                'object_type': message['object_info'].get('type', ''),
                'object_serial': message['object_info'].get('serial', ''),
                'object_owner': message['object_info'].get('owner', ''),
                'current_location_id': message['location_code'],
                'current_location_description': message.get('location_info', ''),
                'last_seen': message['timestamp'],
                'last_scanner_id': message.get('scanner_id', ''),
                'last_updated': datetime.now().isoformat()
            }
            
            # Prepare SOLR update request
            update_data = [doc, current_location_doc]
            
            auth = None
            if solr_config.get('username') and solr_config.get('password'):
                auth = (solr_config['username'], solr_config['password'])
            
            headers = {'Content-Type': 'application/json'}
            
            # Send to SOLR
            response = requests.post(
                f"{solr_config['base_url']}/{solr_config['collection']}/update/json/docs",
                json=update_data,
                headers=headers,
                auth=auth,
                timeout=solr_config['timeout']
            )
            
            if response.status_code == 200:
                # Commit the changes
                commit_response = requests.post(
                    f"{solr_config['base_url']}/{solr_config['collection']}/update",
                    data='{"commit":{}}',
                    headers=headers,
                    auth=auth,
                    timeout=solr_config['timeout']
                )
                
                if commit_response.status_code == 200:
                    self.logger.info(f"Successfully updated SOLR for {message['object_code']}")
                    return True
                else:
                    self.logger.error(f"SOLR commit failed: {commit_response.status_code}")
                    return False
            else:
                self.logger.error(f"SOLR update failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error updating SOLR: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error updating SOLR: {e}")
            return False
    
    def generate_location_update_message(self, original_message: Dict[str, Any]):
        """Generate a location update message for other systems"""
        try:
            update_message = {
                'timestamp': datetime.now().isoformat(),
                'original_timestamp': original_message['timestamp'],
                'object_code': original_message['object_code'],
                'object_info': original_message['object_info'],
                'previous_location': self.get_previous_location(original_message['object_code']),
                'new_location_code': original_message['location_code'],
                'new_location_info': original_message['location_info'],
                'processed_by': 'message_processor',
                'processing_status': 'completed',
                'event_type': 'location_update_processed'
            }
            
            rabbitmq_config = self.config['rabbitmq']
            
            self.rabbitmq_channel.basic_publish(
                exchange=rabbitmq_config['exchange'],
                routing_key=rabbitmq_config['routing_key_update'],
                body=json.dumps(update_message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    timestamp=int(time.time())
                )
            )
            
            self.logger.info(f"Location update message sent for {original_message['object_code']}")
            
        except Exception as e:
            self.logger.error(f"Error generating location update message: {e}")
    
    def get_previous_location(self, object_code: str) -> Optional[str]:
        """Get previous location from SOLR (if available)"""
        try:
            solr_config = self.config['apache_solr']
            
            auth = None
            if solr_config.get('username') and solr_config.get('password'):
                auth = (solr_config['username'], solr_config['password'])
            
            # Query SOLR for current location
            params = {
                'q': f'object_id:{object_code}',
                'fl': 'current_location_id,current_location_description',
                'rows': 1,
                'sort': 'last_updated desc'
            }
            
            response = requests.get(
                f"{solr_config['base_url']}/{solr_config['collection']}/select",
                params=params,
                auth=auth,
                timeout=solr_config['timeout']
            )
            
            if response.status_code == 200:
                data = response.json()
                docs = data.get('response', {}).get('docs', [])
                if docs:
                    return docs[0].get('current_location_id')
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting previous location: {e}")
            return None
    
    def send_notification(self, message: Dict[str, Any]):
        """Send email notification for important updates"""
        try:
            email_config = self.config['email']
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = email_config['from_address']
            msg['To'] = ', '.join(email_config['alert_recipients'])
            msg['Subject'] = f"Asset Location Update: {message['object_info'].get('name', message['object_code'])}"
            
            # Email body
            body = f"""
Asset Location Update Alert

Object: {message['object_info'].get('name', 'Unknown')}
Code: {message['object_code']}
Type: {message['object_info'].get('type', 'Unknown')}
Serial: {message['object_info'].get('serial', 'Unknown')}
Owner: {message['object_info'].get('owner', 'Unknown')}

New Location: {message['location_info']} ({message['location_code']})
Scanner: {message.get('scanner_id', 'Unknown')}
Timestamp: {message['timestamp']}

This is an automated notification from the QR Scanner System.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            if email_config.get('use_tls', True):
                server.starttls()
            
            if email_config.get('username') and email_config.get('password'):
                server.login(email_config['username'], email_config['password'])
            
            server.send_message(msg)
            server.quit()
            
            self.logger.info(f"Notification sent for {message['object_code']}")
            
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
    
    def start_consuming(self):
        """Start consuming messages from RabbitMQ"""
        try:
            rabbitmq_config = self.config['rabbitmq']
            
            self.rabbitmq_channel.basic_consume(
                queue=rabbitmq_config['queue_scan_results'],
                on_message_callback=self.process_scan_message
            )
            
            self.logger.info("Starting message consumption...")
            self.rabbitmq_channel.start_consuming()
            
        except Exception as e:
            self.logger.error(f"Error in message consumption: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        if self.rabbitmq_channel:
            self.rabbitmq_channel.stop_consuming()
    
    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up resources...")
        
        if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
            self.rabbitmq_connection.close()
        
        # Log final statistics
        runtime = datetime.now() - self.processing_stats['start_time']
        self.logger.info(f"Processing Statistics:")
        self.logger.info(f"  Runtime: {runtime}")
        self.logger.info(f"  Messages Processed: {self.processing_stats['messages_processed']}")
        self.logger.info(f"  Successful Updates: {self.processing_stats['successful_updates']}")
        self.logger.info(f"  Failed Updates: {self.processing_stats['failed_updates']}")
        
        self.logger.info("Cleanup complete")

def main():
    """Main function"""
    try:
        processor = MessageProcessor()
        processor.start_consuming()
    except KeyboardInterrupt:
        pass
    finally:
        if 'processor' in locals():
            processor.cleanup()

if __name__ == "__main__":
    main()