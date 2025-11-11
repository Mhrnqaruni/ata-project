import io
from PIL import Image
from PyPDF2 import PdfMerger, PdfReader

def compress_image(image_bytes: bytes, max_size_kb: int = 150) -> bytes:
    """
    Compresses an image to be under a specified size in kilobytes.
    Converts the image to JPEG for effective compression.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Start with high quality and decrease until the size is acceptable
    quality = 95
    # Use a buffer to hold the compressed image data in memory
    buffer = io.BytesIO()

    while quality > 10:
        buffer.seek(0)
        buffer.truncate()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        if len(buffer.getvalue()) / 1024 <= max_size_kb:
            return buffer.getvalue()
        quality -= 5
        
    return buffer.getvalue()

def merge_images_to_pdf(image_bytes_list: list[bytes]) -> bytes:
    """
    Merges a list of image bytes into a single PDF file in memory.
    """
    if not image_bytes_list:
        raise ValueError("Cannot create a PDF from an empty list of images.")

    # Convert image bytes to PIL Image objects
    try:
        images = [Image.open(io.BytesIO(img_bytes)).convert("RGB") for img_bytes in image_bytes_list]
    except Exception as e:
        raise ValueError(f"Failed to read one of the images. Error: {e}")

    # Get the first image to use as the base for the PDF
    first_image = images[0]
    other_images = images[1:]

    pdf_buffer = io.BytesIO()
    try:
        first_image.save(
            pdf_buffer,
            format="PDF",
            save_all=True,
            append_images=other_images
        )
    except Exception as e:
        raise IOError(f"Failed to save images to PDF. Error: {e}")

    return pdf_buffer.getvalue()

def merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
    """
    Merges a list of PDF files (as bytes) into a single PDF file in memory.
    """
    if not pdf_bytes_list:
        raise ValueError("Cannot merge an empty list of PDFs.")

    merger = PdfMerger()

    try:
        for pdf_bytes in pdf_bytes_list:
            pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
            merger.append(pdf_reader)

        output_buffer = io.BytesIO()
        merger.write(output_buffer)
        merger.close()

        return output_buffer.getvalue()
    except Exception as e:
        raise IOError(f"Failed to merge PDFs. Error: {e}")