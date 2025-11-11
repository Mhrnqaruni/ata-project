# /app/services/ocr_service.py

# --- Core Imports ---
import io

# --- Third-Party Library Imports for OCR ---
import fitz  # PyMuPDF for handling PDFs
import pytesseract
from PIL import Image
import docx # <<< NEW IMPORT for handling .docx files

# --- The Core Function (Upgraded) ---
def extract_text_from_file(file_bytes: bytes, content_type: str) -> str:
    """
    Extracts raw text from a file (PDF, image, or .docx). This upgraded version
    can handle text-based PDFs, image-based (scanned) PDFs, and Word documents.
    """
    text = ""
    
    # --- Logic Branch for PDF Files (Unchanged) ---
    if content_type == 'application/pdf':
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            
            for page in doc:
                text += page.get_text() + "\n"
            
            if len(text.strip()) < 100:
                print("INFO: Low text yield from PDF. Attempting image-based OCR on each page.")
                scanned_text = ""
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap(dpi=300) 
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    scanned_text += pytesseract.image_to_string(img) + "\n"
                
                if len(scanned_text.strip()) > len(text.strip()):
                    text = scanned_text

            doc.close()
            return text.strip()
        except Exception as e:
            print(f"ERROR processing PDF with PyMuPDF/Tesseract: {e}")
            return ""

    # --- Logic Branch for Image Files (Unchanged) ---
    elif content_type.startswith('image/'):
        try:
            image = Image.open(io.BytesIO(file_bytes))
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            print(f"ERROR processing image with Tesseract: {e}")
            return ""

    # --- [START] NEW Logic Branch for DOCX Files ---
    elif content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        try:
            # Open the .docx file from the in-memory bytes
            doc = docx.Document(io.BytesIO(file_bytes))
            
            # Extract text from each paragraph in the document
            full_text = [para.text for para in doc.paragraphs]
            text = '\n'.join(full_text)
            return text.strip()
        except Exception as e:
            print(f"ERROR processing .docx file: {e}")
            return ""
    # --- [END] NEW Logic Branch ---

    # --- Logic Branch for Unsupported Files (Updated) ---
    else:
        error_message = f"Unsupported file type for OCR: '{content_type}'"
        raise ValueError(error_message)