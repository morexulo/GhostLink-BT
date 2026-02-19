import io
import os
import base64
from PIL import Image
from typing import Optional, Tuple
from .logger import setup_logger
from .config import IMAGE_MAX_WIDTH, IMAGE_MAX_HEIGHT, IMAGE_QUALITY

logger = setup_logger("image_handler")

# Extensions allowed
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}

def compress_image(image_bytes: bytes) -> Optional[bytes]:
    """
    Takes raw image bytes, resizes if too large, and compresses to JPEG.
    Returns the compressed bytes.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Convert to RGB if needed (e.g. from RGBA PNG) for JPEG
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Resize logic (maintain aspect ratio)
            width, height = img.size
            if width > IMAGE_MAX_WIDTH or height > IMAGE_MAX_HEIGHT:
                img.thumbnail((IMAGE_MAX_WIDTH, IMAGE_MAX_HEIGHT))
                logger.debug(f"Image resized from {width}x{height} to {img.size}")
            
            # Save to buffer
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=IMAGE_QUALITY, optimize=True)
            compressed_data = buffer.getvalue()
            
            logger.info(f"Image compressed: {len(image_bytes)} -> {len(compressed_data)} bytes")
            return compressed_data
            
    except Exception as e:
        logger.error(f"Failed to compress image: {e}")
        return None

def validate_image_file(file_path: str) -> bool:
    """
    Checks if a file is a valid image based on extension and content.
    """
    if not os.path.exists(file_path):
        return False
        
    _, ext = os.path.splitext(file_path)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return False
    
    try:
        with Image.open(file_path) as img:
            img.verify() # quick check
        return True
    except Exception:
        return False

def load_image_bytes(file_path: str) -> Optional[bytes]:
    """
    Reads an image file and returns its bytes (compressed).
    """
    if validate_image_file(file_path):
        try:
            with open(file_path, "rb") as f:
                raw_data = f.read()
            return compress_image(raw_data)
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            return None
    return None

def save_image_from_bytes(data: bytes, output_path: str) -> bool:
    """
    Saves bytes to a file.
    """
    try:
        with open(output_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        logger.error(f"Failed to save image: {e}")
        return False
