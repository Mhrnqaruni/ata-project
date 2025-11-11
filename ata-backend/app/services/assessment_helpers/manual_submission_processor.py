# /ata-backend/app/services/assessment_helpers/manual_submission_processor.py

import os
import uuid
from typing import List, Dict, Tuple
from fastapi import UploadFile, Form

from .. import pdf_service

ASSESSMENT_UPLOADS_DIR = "assessment_uploads"

def _process_manual_submissions(job_id: str, files: List[UploadFile]) -> List[Dict[str, str]]:
    """
    Processes manually uploaded files from a FormData object.

    Groups images by entity, compresses and merges them into a PDF for each,
    and saves them to the job's directory.

    Args:
        job_id: The unique ID for the assessment job.
        files: A list of UploadFile objects from the request.

    Returns:
        A list of dictionaries, where each dictionary represents a saved
        answer sheet PDF and contains its path and content type.
    """
    # Create a mapping from entity ID to a list of their image files
    entity_files: Dict[str, List[UploadFile]] = {}
    for file in files:
        # The key from the frontend is formatted as 'student_1_files' or 'outsider_xyz_files'
        # We need to extract the entity ID from the field name
        field_name = file.filename
        if not field_name.endswith('_files'):
            continue

        entity_id = field_name.removesuffix('_files')

        if entity_id not in entity_files:
            entity_files[entity_id] = []
        entity_files[entity_id].append(file)

    saved_pdfs = []
    job_dir = os.path.join(ASSESSMENT_UPLOADS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    for entity_id, image_files in entity_files.items():
        if not image_files:
            continue

        # Read, compress, and merge images into a single PDF
        image_bytes_list = [img.file.read() for img in image_files]
        compressed_images = [pdf_service.compress_image(data) for data in image_bytes_list]
        pdf_bytes = pdf_service.merge_images_to_pdf(compressed_images)

        # Save the generated PDF
        pdf_filename = f"manual_{entity_id}_{uuid.uuid4().hex[:8]}.pdf"
        pdf_path = os.path.join(job_dir, pdf_filename)
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        saved_pdfs.append({
            "path": pdf_path,
            "contentType": "application/pdf",
            "originalName": f"{entity_id}_submission.pdf",
            "entityId": entity_id # Pass the entityId for matching
        })

    return saved_pdfs