# QR_SCAN
Use a Raspberry PI Camera to Scan QR Codes

I've created a comprehensive Python script system for your QR code-based asset tracking solution. Here's what I've provided:

## **Complete System Components:**

### 1. **Configuration File (`config.json`)**
- Centralized configuration for all system parameters
- Domain Controller and Certificate Server settings
- RabbitMQ, email, Tencent IES4, and Apache SOLR configurations
- QR code mappings for locations and objects
- Processing rules and scanner settings

### 2. **Raspberry Pi Scanner (`qr_scanner.py`)**
- Camera-based QR code detection using OpenCV and pyzbar
- Location memory management
- Object identification and message generation
- RabbitMQ message publishing
- Duplicate scan prevention
- Graceful shutdown handling

### 3. **Message Processor (`message_processor.py`)**
- RabbitMQ message consumption and processing
- Rule-based message filtering
- Tencent IES4 API integration
- Apache SOLR document updates
- Email notifications for important events
- Error handling and retry mechanisms

### 4. **Database Service (`database_updater.py`)**
- SQLite database for local data storage
- Audit trail maintenance
- Daily reporting and statistics
- Data cleanup and archival
- Health monitoring and alerting
- Scheduled task management

### 5. **Requirements File (`requirements.txt`)**
- All necessary Python dependencies
- Computer vision libraries
- RabbitMQ client
- Web APIs and database support

### 6. **Installation Guide**
- Complete setup instructions
- Service configuration
- Security considerations
- Monitoring and maintenance procedures

## **Key Features:**

✅ **Scalable Architecture**: Modular design with separate services for scanning, processing, and database operations

✅ **External Configuration**: All parameters stored in JSON file for easy modification

✅ **Robust Error Handling**: Comprehensive error handling with logging and retry mechanisms

✅ **Domain Integration**: Ready for Active Directory and Certificate Server integration

✅ **Multiple Data Stores**: Updates both Tencent IES4 and Apache SOLR schemas

✅ **Audit Trail**: Complete tracking of asset movements and system events

✅ **Monitoring**: Health checks, statistics, and automated reporting

✅ **Production Ready**: Systemd services, log rotation, backup scripts

## **Workflow:**

1. **Raspberry Pi** scans QR codes and identifies locations/objects
2. **Scanner** generates RabbitMQ messages for object location updates
3. **Message Processor** consumes messages and applies business rules
4. **External Updates** sent to Tencent IES4 and Apache SOLR
5. **Database Service** maintains local audit trail and generates reports
6. **Notifications** sent for important events via email

The system is designed to be enterprise-ready with proper logging, monitoring, and maintenance procedures. Each script can run as a systemd service for production deployment.
