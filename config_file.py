{
    "domain_controller": {
        "server": "dc.picluster.local",
        "port": 389,
        "use_ssl": True,
        "base_dn": "DC=picluster,DC=local",
        "service_account": "svc_qr_scanner",
        "service_password": "your_service_password"
    },
    "certificate_server": {
        "server": "ca.yourdomain.com",
        "web_enrollment_url": "https://picluster.local/certsrv",
        "template_name": "WebServer"
    },
    "rabbitmq": {
        "host": "localhost",
        "port": 5672,
        "username": "odin",
        "password": "BobTheBigRedBus-0",
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
        "use_tls": True,
        "username": "notifications@yourdomain.com",
        "password": "your_email_password",
        "from_address": "qr-scanner@yourdomain.com",
        "alert_recipients": ["admin@yourdomain.com", "security@yourdomain.com"]
    },
    "qr_codes": {
        "locations": {
            "OP1": "Donetsk Oblas",
            "OP2": "Dnipropetrovsk Oblas",
            "OP3": "Zaporizhzhia",
            "OP4": "Kyiv Oblas",
            "OP5": "Kirovohrad Oblas",
            "OP6": "Mykolaivk Oblas",
            "OP7": "Odessa Oblas",
            "OP8": "Sumy Oblas"
        },
        "objects": {
            "SADrone": {
                "name": "SADrone",
                "type": "Unmanned Aircraft",
                "serial": "Russian Federation",
                "owner": "Sokol Altius Dron"
            },
            "KA50": {
                "name": "KA50",
                "type": "AV Equipment",
                "serial": "Russian Federation",
                "owner": "Ka-50 Helicoptert"
            },
            "S500": {
                "name": "S500",
                "type": "Vehicle",
                "serial": "Russian Federation",
                "owner": "S-500 Prometheus"
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
        "enable_preview": False
    },
    "processing_rules": {
        "notification_threshold_minutes": 5,
        "duplicate_scan_window_seconds": 30,
        "auto_update_location": True,
        "require_confirmation": False,
        "enable_audit_trail": True
    }
}
