#!/usr/bin/env python3
"""
Simple QR Code Detection Test
Tests basic QR code detection without the full scanner logic
"""

import cv2
from pyzbar import pyzbar
import time

def test_qr_detection():
    """Test QR code detection with detailed output"""
    
    # Initialize camera
    print("Initializing camera...")
    camera = cv2.VideoCapture(0)
    
    if not camera.isOpened():
        print("ERROR: Cannot open camera")
        return
    
    # Set camera properties
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 30)
    
    print("Camera initialized successfully")
    print("Hold QR codes in front of camera...")
    print("Press 'q' to quit, 's' to save current frame for debugging")
    
    frame_count = 0
    qr_found_count = 0
    
    while True:
        ret, frame = camera.read()
        
        if not ret:
            print("Failed to read frame")
            break
        
        frame_count += 1
        
        # Test different image processing approaches
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Method 1: Direct detection on grayscale
        qr_codes = pyzbar.decode(gray)
        
        # Method 2: Try with different image enhancements
        if not qr_codes:
            # Enhance contrast
            enhanced = cv2.equalizeHist(gray)
            qr_codes = pyzbar.decode(enhanced)
            
            if qr_codes:
                print("QR codes found with contrast enhancement!")
        
        # Method 3: Try with blur reduction (sharpen)
        if not qr_codes:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
            sharpened = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
            qr_codes = pyzbar.decode(sharpened)
            
            if qr_codes:
                print("QR codes found with morphological processing!")
        
        # Process any found QR codes
        if qr_codes:
            qr_found_count += 1
            print(f"\n=== QR CODE DETECTED (Frame {frame_count}) ===")
            
            for i, qr_code in enumerate(qr_codes):
                print(f"QR Code {i+1}:")
                print(f"  Data: '{qr_code.data.decode('utf-8')}'")
                print(f"  Type: {qr_code.type}")
                print(f"  Quality: {qr_code.quality if hasattr(qr_code, 'quality') else 'N/A'}")
                print(f"  Rectangle: {qr_code.rect}")
                print(f"  Polygon points: {len(qr_code.polygon)} points")
                
                # Draw rectangle around QR code
                points = qr_code.polygon
                if len(points) == 4:
                    cv2.polylines(frame, [points], True, (0, 255, 0), 3)
                else:
                    # Fallback to bounding rectangle
                    x, y, w, h = qr_code.rect
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
                
                # Add text
                qr_data = qr_code.data.decode('utf-8')
                cv2.putText(frame, qr_data, (qr_code.rect.left, qr_code.rect.top - 10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        
        # Add status information to frame
        status_text = f"Frames: {frame_count} | QR Found: {qr_found_count}"
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Show frame
        cv2.imshow('QR Code Test', frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            # Save current frame for debugging
            timestamp = int(time.time())
            filename = f"debug_frame_{timestamp}.jpg"
            cv2.imwrite(filename, frame)
            print(f"Saved debug frame: {filename}")
            
            # Also save grayscale version
            gray_filename = f"debug_gray_{timestamp}.jpg"
            cv2.imwrite(gray_filename, gray)
            print(f"Saved grayscale frame: {gray_filename}")
        
        # Print status every 100 frames
        if frame_count % 100 == 0:
            print(f"Processed {frame_count} frames, found QR codes in {qr_found_count} frames")
    
    # Cleanup
    camera.release()
    cv2.destroyAllWindows()
    
    print(f"\nTest completed:")
    print(f"  Total frames processed: {frame_count}")
    print(f"  Frames with QR codes: {qr_found_count}")
    print(f"  Detection rate: {(qr_found_count/frame_count)*100:.2f}%" if frame_count > 0 else "No frames processed")

if __name__ == "__main__":
    try:
        test_qr_detection()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()