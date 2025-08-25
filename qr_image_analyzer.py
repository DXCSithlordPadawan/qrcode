#!/usr/bin/env python3
"""
QR Code Image Analyzer
Analyzes QR codes from image files to understand their exact content and format
"""

import cv2
from pyzbar import pyzbar
import sys
import numpy as np

def analyze_qr_image(image_path):
    """Analyze QR codes in an image file"""
    
    try:
        print(f"Analyzing image: {image_path}")
        
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            print(f"ERROR: Could not load image {image_path}")
            return
        
        print(f"Image dimensions: {image.shape}")
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Try different approaches to decode
        approaches = [
            ("Original grayscale", gray),
            ("Histogram equalization", cv2.equalizeHist(gray)),
            ("Gaussian blur", cv2.GaussianBlur(gray, (3, 3), 0)),
            ("Bilateral filter", cv2.bilateralFilter(gray, 9, 75, 75)),
        ]
        
        found_qr = False
        
        for approach_name, processed_image in approaches:
            print(f"\nTrying: {approach_name}")
            qr_codes = pyzbar.decode(processed_image)
            
            if qr_codes:
                found_qr = True
                print(f"SUCCESS with {approach_name}!")
                
                for i, qr_code in enumerate(qr_codes):
                    print(f"\nQR Code {i+1}:")
                    print(f"  Raw data: {qr_code.data}")
                    print(f"  Decoded text: '{qr_code.data.decode('utf-8')}'")
                    print(f"  Type: {qr_code.type}")
                    print(f"  Rectangle: {qr_code.rect}")
                    print(f"  Quality: {qr_code.quality if hasattr(qr_code, 'quality') else 'N/A'}")
                    
                    # Analyze the content
                    qr_text = qr_code.data.decode('utf-8')
                    print(f"  Content analysis:")
                    print(f"    Length: {len(qr_text)} characters")
                    print(f"    Contains numbers: {'Yes' if any(c.isdigit() for c in qr_text) else 'No'}")
                    print(f"    Contains letters: {'Yes' if any(c.isalpha() for c in qr_text) else 'No'}")
                    print(f"    Contains special chars: {'Yes' if any(not c.isalnum() for c in qr_text) else 'No'}")
                    print(f"    First 10 chars: '{qr_text[:10]}...' ")
                break
        
        if not found_qr:
            print("\nNo QR codes detected with any approach")
            print("This might indicate:")
            print("  - Image quality issues")
            print("  - QR code damage or distortion")
            print("  - Unsupported QR code format")
            
            # Try some additional debugging
            print(f"\nImage statistics:")
            print(f"  Mean brightness: {np.mean(gray):.2f}")
            print(f"  Std deviation: {np.std(gray):.2f}")
            print(f"  Min/Max values: {np.min(gray)}/{np.max(gray)}")
    
    except Exception as e:
        print(f"Error analyzing image: {e}")
        import traceback
        traceback.print_exc()

def create_test_qr_codes():
    """Create test QR codes for comparison"""
    try:
        import qrcode
        
        # Create test QR codes with the same content as your uploaded ones
        test_data = ["S500", "OP7"]
        
        for data in test_data:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            filename = f"test_qr_{data}.png"
            img.save(filename)
            print(f"Created test QR code: {filename}")
            
    except ImportError:
        print("qrcode library not installed. Install with: pip install qrcode[pil]")
    except Exception as e:
        print(f"Error creating test QR codes: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python qr_image_analyzer.py <image_path> [<image_path2> ...]")
        print("Or: python qr_image_analyzer.py --create-test")
        return
    
    if sys.argv[1] == "--create-test":
        create_test_qr_codes()
        return
    
    for image_path in sys.argv[1:]:
        analyze_qr_image(image_path)
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()