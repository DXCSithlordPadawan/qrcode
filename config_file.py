{
    "domain_controller": {
        "server": "dc.yourdomain.com",
        "port": 389,
        "use_ssl": true,
        "base_dn": "DC=yourdomain,DC=com",
        "service_account": "svc_qr_scanner",
        "service_password": "your_service_password"
    },
    "certificate_server": {
        "server": "ca.yourdomain.com",
        "web_enrollment_url": "https://ca.yourdomain.com/certsrv",
        "template_name": "WebServer"
    },
    "rabbitmq": {
        "host": "rabbitmq.yourdomain.com",
        "port": 5672,
        "username": "qr_scanner_user",
        "password": "your_rabbitmq_password",
        "virtual_host": "/",
        "exchange": "asset_tracking",
        "queue_scan_results": "scan_results",
        "queue_location_updates": "location_updates",
        "routing_key_scan": "qr.scan.result",
        "routing_key_update": "asset.location.update"
    },
    "email": {
        "smtp_server": "mail.yourdomain.com",
        "smtp_port": 587,
        "use_tls": true,
        "username": "notifications@yourdomain.com",
        "password": "your_email_password",
        "from_address": "qr-scanner@yourdomain.com",
        "alert_recipients": ["admin@yourdomain.com", "security@yourdomain.com"]
    },
    "qr_codes": {
        "locations": {
            "LOC001": "Building A - Floor 1 - Room 101",
            "LOC002": "Building A - Floor 1 - Room 102",
            "LOC003": "Building A - Floor 2 - Room 201",
            "LOC004": "Building B - Warehouse - Section A",
            "LOC005": "Building B - Warehouse - Section B",
            "LOC006": "Parking Lot - North Side",
            "LOC007": "Reception Area",
            "LOC008": "Server Room"
        },
        "objects": {
            "OBJ001": {
                "name": "Laptop - Dell Latitude 5520",
                "type": "Computer",
                "serial": "DL123456789",
                "owner": "John Smith"
            },
            "OBJ002": {
                "name": "Projector - Epson PowerLite",
                "type": "AV Equipment",
                "serial": "EP987654321",
                "owner": "IT Department"
            },
            "OBJ003": {
                "name": "Network Switch - Cisco 2960",
                "type": "Network Equipment",
                "serial": "CS456789123",
                "owner": "Network Team"
            },
            "OBJ004": {
                "name": "Fire Extinguisher",
                "type": "Safety Equipment",
                "serial": "FE789123456",
                "owner": "Facilities"
            }
        }
    },
    "tencent_ies4": {
        "api_endpoint": "https://ies4-api.yourdomain.com/v1",
        "api_key": "your_tencent_ies4_api_key",
        "tenant_id": "your_tenant_id",
        "timeout": 30
    },
    "apache_solr": {
        "base_url": "http://solr.yourdomain.com:8983/solr",
        "collection": "asset_tracking",
        "username": "solr_user",
        "password": "your_solr_password",
        "timeout": 30
    },
    "scanner_settings": {
        "camera_index": 0,
        "scan_interval": 2,
        "qr_detection_timeout": 5,
        "max_retry_attempts": 3,
        "log_level": "INFO",
        "enable_preview": false
    },
    "processing_rules": {
        "notification_threshold_minutes": 5,
        "duplicate_scan_window_seconds": 30,
        "auto_update_location": true,
        "require_confirmation": false,
        "enable_audit_trail": true
    }
}