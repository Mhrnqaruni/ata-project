# /tests/test_ocr_service_standalone.py

import time
import os
import sys

# --- [CRITICAL SETUP] ---
# This is a standalone script, not a pytest test. To allow it to import
# modules from our main application (like 'app.services.ocr_service'),
# we need to temporarily add the project's root directory to the Python path.
# This mimics how the main application's environment is set up.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --- [END OF SETUP] ---

# Now we can import our application's service directly.
from app.services import ocr_service

# --- Configuration ---
IMAGE_PATH = "a.pdf"
# We must provide the correct MIME type, just like FastAPI would.
CONTENT_TYPE = "application/pdf"

def run_ocr_service_test(image_path: str, content_type: str):
    """
    Performs a standalone test of our application's ocr_service module
    on a single image file and reports the results.
    """
    print("--- Starting Standalone OCR Service Test ---")
    
    # 1. Verify that the image file exists.
    if not os.path.exists(image_path):
        print(f"\n[ERROR] Test image not found at path: '{image_path}'")
        print("Please make sure 'test_image.png' is inside the '/tests/' directory.")
        return

    print(f"Found test image: '{image_path}'")
    
    try:
        # 2. Read the file into in-memory bytes, mimicking an UploadFile.
        print("Reading image file into memory...")
        with open(image_path, "rb") as f:
            file_bytes = f.read()

        # 3. Record the start time.
        start_time = time.time()
        
        # 4. Call our application's service function.
        # This is the core test.
        print(f"Calling ocr_service.extract_text_from_file with content_type='{content_type}'...")
        extracted_text = ocr_service.extract_text_from_file(file_bytes, content_type)
        
        # 5. Record the end time and calculate the duration.
        end_time = time.time()
        duration = end_time - start_time
        
        # 6. Print the results.
        print("\n--- OCR Service Test Complete ---")
        print(f"Total time taken: {duration:.2f} seconds")
        print("\n--- Extracted Text ---")
        
        if extracted_text.strip():
            print(extracted_text)
        else:
            print("[No text was extracted from the image.]")
            
        print("--- End of Text ---")

    except ImportError as e:
        print(f"\n[IMPORT ERROR] A required library is missing: {e}")
        print("Please ensure all dependencies from requirements.txt are installed in your venv.")
    except Exception as e:
        # This will catch the ValueError from our service if the file type is unsupported.
        print(f"\n[UNEXPECTED ERROR] An error occurred during the service call: {e}")


if __name__ == "__main__":
    run_ocr_service_test(IMAGE_PATH, CONTENT_TYPE)