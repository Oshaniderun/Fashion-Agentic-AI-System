"""
Image validation and secure file storage utilities.
Prevents path traversal, validates true image headers, and enforces size limits.
"""

import os
import uuid
import io
from pathlib import Path
from typing import Tuple
from PIL import Image
from fastapi import UploadFile, HTTPException, status

from app.core.config import settings
from app.core.logging import logger

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_and_save_image(file: UploadFile) -> Tuple[str, str]:
    """
    Validates the uploaded file:
    1. Checks file extension against whitelist.
    2. Validates actual image binary content and format using Pillow.
    3. Enforces MAX_UPLOAD_SIZE_MB.
    4. Generates a safe, unguessable filename without path traversal risk.
    5. Saves file to isolated storage directory.

    Returns:
        (saved_relative_path, safe_filename)
    """
    # 1. Filename sanitization and extension check
    orig_name = os.path.basename(file.filename or "upload.jpg")
    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type '{ext}'. Allowed: {list(ALLOWED_EXTENSIONS)}"
        )

    # 2. Read file bytes and verify size
    contents = file.file.read()
    file_size_mb = len(contents) / (1024 * 1024)
    if file_size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image size exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    # 3. Verify actual image format via Pillow
    try:
        image_stream = io.BytesIO(contents)
        with Image.open(image_stream) as img:
            img.verify()
            img_format = img.format
            if img_format not in ALLOWED_FORMATS:
                raise ValueError(f"Decoded format '{img_format}' is not an allowed image format.")
    except Exception as e:
        logger.warning(f"Malicious or corrupted image upload attempt: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file or corrupted image data."
        )

    # 4. Generate safe unique filename
    safe_filename = f"{uuid.uuid4().hex}{ext}"
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination_path = upload_dir / safe_filename

    # 5. Save securely to disk
    with open(destination_path, "wb") as f:
        f.write(contents)

    relative_path = f"uploads/{safe_filename}"
    return relative_path, safe_filename
