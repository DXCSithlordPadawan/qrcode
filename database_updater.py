#!/usr/bin/env python3
"""
Database Update Service
Additional service for handling database operations, audit trails, and reporting
"""

import json
import sqlite3
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import signal
import sys
import threading
import schedule
import requests
from contextlib import contextmanager

class DatabaseUpdateService:
    def __init__(self, config_file: str = 'config.json', db_file: str = 'asset_tracking.db'):
        """Initialize the Database Update Service"""
        self.config = self.load_config(config_file)
        self.db_file = db_file
        self.running = True
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, self.config['scanner_settings']['log_level']),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/var/log/database_updater.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize database
        self.initialize_database()
        
        # Setup scheduled tasks
        self.setup_scheduler()
        
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
    
    def initialize_database(self):
        """Initialize SQLite database with required tables"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Create tables
                cursor.executescript("""
                    -- Asset tracking table
                    CREATE TABLE IF NOT EXISTS asset_locations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        object_code TEXT NOT NULL,
                        object_name TEXT,
                        object_type TEXT,
                        object_serial TEXT,
                        object_owner TEXT,
                        location_code TEXT NOT NULL,
                        location_description TEXT,
                        scanner_id TEXT,
                        scan_timestamp DATETIME NOT NULL,
                        processed_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        processing_status TEXT DEFAULT 'pending',
                        ies4_updated BOOLEAN DEFAULT 0,
                        solr_updated BOOLEAN DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    -- Current asset positions (latest location for each asset)
                    CREATE TABLE IF NOT EXISTS current_asset_positions (
                        object_code TEXT PRIMARY KEY,
                        object_name TEXT,
                        object_type TEXT,
                        object_serial TEXT,
                        object_owner TEXT,
                        current_location_code TEXT NOT NULL,
                        current_location_description TEXT,
                        last_scanner_id TEXT,
                        last_scan_timestamp DATETIME NOT NULL,
                        first_seen DATETIME NOT NULL,
                        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                        total_moves INTEGER DEFAULT 1
                    );
                    
                    -- Audit trail
                    CREATE TABLE IF NOT EXISTS audit_trail (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        object_code TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        old_location_code TEXT,
                        new_location_code TEXT,
                        scanner_id TEXT,
                        timestamp DATETIME NOT NULL,
                        details TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    -- System errors and alerts
                    CREATE TABLE IF NOT EXISTS system_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        alert_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        message TEXT NOT NULL,
                        details TEXT,
                        resolved BOOLEAN DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        resolved_at DATETIME
                    );
                    
                    -- Processing statistics
                    CREATE TABLE IF NOT EXISTS processing_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date DATE NOT NULL,
                        total_scans INTEGER DEFAULT 0,
                        successful_updates INTEGER DEFAULT 0,
                        failed_updates INTEGER DEFAULT 0,
                        unique_objects INTEGER DEFAULT 0,
                        unique_locations INTEGER DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(date)
                    );
                    
                    -- Create indexes for better performance
                    CREATE INDEX IF NOT EXISTS idx_asset_locations_object_code ON asset_locations(object_code);
                    CREATE INDEX IF NOT EXISTS idx_asset_locations_timestamp ON asset_locations(scan_timestamp);
                    CREATE INDEX IF NOT EXISTS idx_current_positions_location ON current_asset_positions(current_location_code);
                    CREATE INDEX IF NOT EXISTS idx_audit_trail_object ON audit_trail(object_code);
                    CREATE INDEX IF NOT EXISTS idx_audit_trail_timestamp ON audit_trail(timestamp);
                """)
                
                conn.commit()
                self.logger.info("Database initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            sys.exit(1)
    
    @contextmanager
    def get_db_connection(self):
        """Get database connection with context manager"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_file, timeout=30.0)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def record_asset_scan(self, scan_data: Dict[str, Any]) -> bool:
        """Record a new asset scan"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Insert scan record
                cursor.execute("""
                    INSERT INTO asset_locations (
                        object_code, object_name, object_type, object_serial, object_owner,
                        location_code, location_description, scanner_id, scan_timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scan_data['object_code'],
                    scan_data.get('object_info', {}).get('name'),
                    scan_data.get('object_info', {}).get('type'),
                    scan_data.get('object_info', {}).get('serial'),
                    scan_data.get('object_info', {}).get('owner'),
                    scan_data['location_code'],
                    scan_data.get('location_info'),
                    scan_data.get('scanner_id'),
                    scan_data['timestamp']
                ))
                
                # Get previous location for audit trail
                cursor.execute("""
                    SELECT current_location_code FROM current_asset_positions 
                    WHERE object_code = ?
                """, (scan_data['object_code'],))
                
                result = cursor.fetchone()
                old_location = result['current_location_code'] if result else None
                
                # Update current position
                cursor.execute("""
                    INSERT OR REPLACE INTO current_asset_positions (
                        object_code, object_name, object_type, object_serial, object_owner,
                        current_location_code, current_location_description, last_scanner_id,
                        last_scan_timestamp, first_seen, total_moves
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        COALESCE((SELECT first_seen FROM current_asset_positions WHERE object_code = ?), ?),
                        COALESCE((SELECT total_moves FROM current_asset_positions WHERE object_code = ?) + 1, 1)
                    )
                """, (
                    scan_data['object_code'],
                    scan_data.get('object_info', {}).get('name'),
                    scan_data.get('object_info', {}).get('type'),
                    scan_data.get('object_info', {}).get('serial'),
                    scan_data.get('object_info', {}).get('owner'),
                    scan_data['location_code'],
                    scan_data.get('location_info'),
                    scan_data.get('scanner_id'),
                    scan_data['timestamp'],
                    scan_data['object_code'], scan_data['timestamp'],
                    scan_data['object_code']
                ))
                
                # Record audit trail if location changed
                if old_location != scan_data['location_code']:
                    cursor.execute("""
                        INSERT INTO audit_trail (
                            object_code, event_type, old_location_code, new_location_code,
                            scanner_id, timestamp, details
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        scan_data['object_code'],
                        'location_change',
                        old_location,
                        scan_data['location_code'],
                        scan_data.get('scanner_id'),
                        scan_data['timestamp'],
                        json.dumps(scan_data)
                    ))
                
                conn.commit()
                self.logger.info(f"Recorded scan for {scan_data['object_code']}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error recording asset scan: {e}")
            return False
    
    def update_processing_status(self, object_code: str, timestamp: str, 
                               ies4_success: bool, solr_success: bool) -> bool:
        """Update processing status for a scan"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                status = 'success' if (ies4_success and solr_success) else 'partial' if (ies4_success or solr_success) else 'failed'
                
                cursor.execute("""
                    UPDATE asset_locations 
                    SET processing_status = ?, ies4_updated = ?, solr_updated = ?,
                        processed_timestamp = CURRENT_TIMESTAMP
                    WHERE object_code = ? AND scan_timestamp = ?
                """, (status, ies4_success, solr_success, object_code, timestamp))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating processing status: {e}")
            return False
    
    def get_asset_history(self, object_code: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get location history for an asset"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM asset_locations 
                    WHERE object_code = ? AND scan_timestamp >= datetime('now', '-{} days')
                    ORDER BY scan_timestamp DESC
                """.format(days), (object_code,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Error getting asset history: {e}")
            return []
    
    def get_location_contents(self, location_code: str) -> List[Dict[str, Any]]:
        """Get all assets currently at a location"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM current_asset_positions 
                    WHERE current_location_code = ?
                    ORDER BY last_scan_timestamp DESC
                """, (location_code,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Error getting location contents: {e}")
            return []
    
    def generate_daily_report(self, date: str = None) -> Dict[str, Any]:
        """Generate daily activity report"""
        try:
            if not date:
                date = datetime.now().strftime('%Y-%m-%d')
            
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get daily statistics
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_scans,
                        COUNT(DISTINCT object_code) as unique_objects,
                        COUNT(DISTINCT location_code) as unique_locations,
                        SUM(CASE WHEN processing_status = 'success' THEN 1 ELSE 0 END) as successful_updates,
                        SUM(CASE WHEN processing_status IN ('failed', 'partial') THEN 1 ELSE 0 END) as failed_updates
                    FROM asset_locations 
                    WHERE DATE(scan_timestamp) = ?
                """, (date,))
                
                stats = dict(cursor.fetchone())
                
                # Get most active locations
                cursor.execute("""
                    SELECT location_code, location_description, COUNT(*) as scan_count
                    FROM asset_locations 
                    WHERE DATE(scan_timestamp) = ?
                    GROUP BY location_code, location_description
                    ORDER BY scan_count DESC
                    LIMIT 10
                """, (date,))
                
                active_locations = [dict(row) for row in cursor.fetchall()]
                
                # Get most moved objects
                cursor.execute("""
                    SELECT object_code, object_name, COUNT(*) as move_count
                    FROM asset_locations 
                    WHERE DATE(scan_timestamp) = ?
                    GROUP BY object_code, object_name
                    ORDER BY move_count DESC
                    LIMIT 10
                """, (date,))
                
                most_moved = [dict(row) for row in cursor.fetchall()]
                
                report = {
                    'date': date,
                    'statistics': stats,
                    'most_active_locations': active_locations,
                    'most_moved_objects': most_moved,
                    'generated_at': datetime.now().isoformat()
                }
                
                # Store statistics
                cursor.execute("""
                    INSERT OR REPLACE INTO processing_stats (
                        date, total_scans, successful_updates, failed_updates,
                        unique_objects, unique_locations
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    date, stats['total_scans'], stats['successful_updates'],
                    stats['failed_updates'], stats['unique_objects'], stats['unique_locations']
                ))
                
                conn.commit()
                return report
                
        except Exception as e:
            self.logger.error(f"Error generating daily report: {e}")
            return {}
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """Clean up old data from database"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
            
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Clean up old asset_locations records (keep audit trail longer)
                cursor.execute("""
                    DELETE FROM asset_locations 
                    WHERE DATE(scan_timestamp) < ? AND processing_status = 'success'
                """, (cutoff_date,))
                
                deleted_scans = cursor.rowcount
                
                # Clean up old resolved alerts
                cursor.execute("""
                    DELETE FROM system_alerts 
                    WHERE DATE(created_at) < ? AND resolved = 1
                """, (cutoff_date,))
                
                deleted_alerts = cursor.rowcount
                
                conn.commit()
                self.logger.info(f"Cleaned up {deleted_scans} old scan records and {deleted_alerts} resolved alerts")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
    
    def setup_scheduler(self):
        """Setup scheduled tasks"""
        # Daily report generation
        schedule.every().day.at("23:59").do(self.generate_daily_report)
        
        # Weekly cleanup
        schedule.every().week.do(self.cleanup_old_data)
        
        # Hourly health check
        schedule.every().hour.do(self.health_check)
    
    def health_check(self):
        """Perform system health check"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check for recent activity
                cursor.execute("""
                    SELECT COUNT(*) as recent_scans
                    FROM asset_locations 
                    WHERE scan_timestamp >= datetime('now', '-1 hour')
                """)
                
                recent_scans = cursor.fetchone()['recent_scans']
                
                # Check for failed processing
                cursor.execute("""
                    SELECT COUNT(*) as failed_processing
                    FROM asset_locations 
                    WHERE processing_status = 'failed' 
                    AND scan_timestamp >= datetime('now', '-1 hour')
                """)
                
                failed_processing = cursor.fetchone()['failed_processing']
                
                # Create alerts if needed
                if failed_processing > 5:  # More than 5 failures in an hour
                    cursor.execute("""
                        INSERT INTO system_alerts (alert_type, severity, message, details)
                        VALUES (?, ?, ?, ?)
                    """, (
                        'processing_failure',
                        'high',
                        f'High number of processing failures: {failed_processing} in the last hour',
                        json.dumps({'failed_count': failed_processing, 'time_window': '1 hour'})
                    ))
                
                conn.commit()
                self.logger.info(f"Health check completed: {recent_scans} recent scans, {failed_processing} failures")
                
        except Exception as e:
            self.logger.error(f"Error in health check: {e}")
    
    def run_scheduler(self):
        """Run the scheduler in a separate thread"""
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def start_service(self):
        """Start the database update service"""
        self.logger.info("Starting Database Update Service")
        
        # Start scheduler in separate thread
        scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        scheduler_thread.start()
        
        # Keep the service running
        try:
            while self.running:
                time.sleep(10)
        except KeyboardInterrupt:
            pass
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Database Update Service cleanup complete")

def main():
    """Main function"""
    try:
        service = DatabaseUpdateService()
        service.start_service()
    except KeyboardInterrupt:
        pass
    finally:
        if 'service' in locals():
            service.cleanup()

if __name__ == "__main__":
    main()