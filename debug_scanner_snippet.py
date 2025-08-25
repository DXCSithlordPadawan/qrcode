# Add this to your decode_qr_codes method for detailed debugging

def decode_qr_codes(self, frame) -> list:
    """Decode QR codes from camera frame with detailed debugging"""
    try:
        # Convert to grayscale for better detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Add debugging output every 50 frames
        if hasattr(self, 'debug_frame_count'):
            self.debug_frame_count += 1
        else:
            self.debug_frame_count = 1
        
        if self.debug_frame_count % 50 == 0:
            # Analyze image quality
            mean_brightness = gray.mean()
            std_dev = gray.std()
            self.logger.debug(f"Frame {self.debug_frame_count}: brightness={mean_brightness:.1f}, contrast={std_dev:.1f}")
        
        # Try multiple detection approaches
        approaches = [
            ("direct", gray),
            ("enhanced", cv2.equalizeHist(gray)),
            ("blurred", cv2.GaussianBlur(gray, (3, 3), 0))
        ]
        
        all_qr_codes = []
        
        for approach_name, processed_image in approaches:
            qr_codes = pyzbar.decode(processed_image)
            if qr_codes:
                self.logger.info(f"QR codes found using {approach_name} approach: {len(qr_codes)}")
                for qr in qr_codes:
                    qr_data = qr.data.decode('utf-8')
                    self.logger.info(f"  Detected: '{qr_data}' (type: {qr.type})")
                all_qr_codes.extend(qr_codes)
                break  # Use first successful approach
        
        if self.debug_frame_count % 100 == 0 and not all_qr_codes:
            self.logger.info(f"No QR codes detected in last 100 frames (total: {self.debug_frame_count})")
            
        return all_qr_codes
        
    except Exception as e:
        self.logger.error(f"Error decoding QR codes: {e}")
        return []