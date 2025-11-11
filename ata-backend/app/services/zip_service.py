# /app/services/zip_service.py

# --- Core Imports ---
import io
import zipfile
from typing import List, Tuple

# --- Core Public Function ---
def create_zip_archive(files_in_memory: List[Tuple[str, bytes]]) -> bytes:
    """
    Creates a ZIP archive in memory from a list of files.
    Each file is provided as a tuple of (filename, file_bytes).
    This is a synchronous, CPU-bound function that should be called via asyncio.to_thread.

    Args:
        files_in_memory: A list where each item is a tuple containing the desired
                         filename (e.g., "Report_Alice.pdf") and the file's raw
                         binary content.

    Returns:
        The raw binary content of the generated ZIP archive as a bytes object.
    """
    # Create an in-memory binary stream to act as the ZIP file.
    zip_buffer = io.BytesIO()

    # Create a ZipFile object that writes to our in-memory buffer.
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        # Iterate through the list of files to be added.
        for file_name, data in files_in_memory:
            # Write the binary data to the archive with the specified filename.
            zip_file.writestr(file_name, data)

    # Move the buffer's cursor to the beginning.
    zip_buffer.seek(0)
    
    # Read the complete binary content of the in-memory ZIP file.
    zip_bytes = zip_buffer.getvalue()
    zip_buffer.close()
    
    return zip_bytes