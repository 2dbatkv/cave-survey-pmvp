"""
OCR utilities for extracting cave survey data from images
"""
import re
import io
from typing import Dict, List, Any, Tuple, Optional
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess image for better OCR accuracy

    Args:
        image: PIL Image object

    Returns:
        Preprocessed PIL Image
    """
    # Convert to grayscale
    image = image.convert('L')

    # Increase contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)

    # Sharpen
    image = image.filter(ImageFilter.SHARPEN)

    # Resize if image is too small (OCR works better on larger images)
    width, height = image.size
    if width < 1000 or height < 1000:
        scale_factor = max(1000 / width, 1000 / height)
        new_size = (int(width * scale_factor), int(height * scale_factor))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    return image


def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Extract text from image using OCR

    Args:
        image_bytes: Image file bytes

    Returns:
        Extracted text
    """
    import subprocess
    import shutil
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Check if tesseract is installed
        tesseract_cmd = shutil.which('tesseract')
        logger.info(f"Tesseract command path: {tesseract_cmd}")

        if tesseract_cmd:
            # Try to get tesseract version
            try:
                result = subprocess.run(['tesseract', '--version'],
                                      capture_output=True, text=True, timeout=5)
                logger.info(f"Tesseract version info: {result.stdout}")
            except Exception as ve:
                logger.error(f"Failed to get tesseract version: {ve}")
        else:
            logger.error("Tesseract not found in PATH")
            # List what's in PATH
            import os
            logger.error(f"PATH: {os.environ.get('PATH', 'NOT SET')}")

        # Open image
        image = Image.open(io.BytesIO(image_bytes))
        logger.info(f"Image opened: size={image.size}, mode={image.mode}")

        # Preprocess for better OCR
        processed_image = preprocess_image(image)
        logger.info(f"Image preprocessed: size={processed_image.size}")

        # Run OCR
        text = pytesseract.image_to_string(processed_image)
        logger.info(f"OCR completed: extracted {len(text)} characters")

        return text
    except Exception as e:
        logger.error(f"OCR failed with error: {str(e)}")
        logger.exception("Full traceback:")
        raise ValueError(f"OCR failed: {str(e)}")


def parse_survey_line(line: str, shot_id: int) -> Optional[Dict[str, Any]]:
    """
    Parse a single line of text to extract survey shot data

    Supports multiple formats:
    - FROM TO DIST AZIM CLINO (e.g., "L1 L2 7.32 317.2 -72.5")
    - FROM-TO DIST/AZIM/CLINO (e.g., "L1-L2 7.32/317.2/-72.5")
    - Tabular format with whitespace separation

    Args:
        line: Text line to parse
        shot_id: Sequential shot ID

    Returns:
        Shot dictionary or None if line doesn't match
    """
    line = line.strip()

    # Skip empty lines or header lines
    if not line or any(header in line.lower() for header in ['from', 'to', 'station', 'distance', 'azimuth', 'compass', 'bearing', 'clino', 'incl']):
        return None

    # Try different parsing patterns

    # Pattern 1: Space/tab separated (most common)
    # Example: "L1  L2  7.32  317.2  -72.5"
    parts = re.split(r'\s+', line)
    if len(parts) >= 5:
        try:
            from_station = parts[0]
            to_station = parts[1] if parts[1] != '-' else None
            distance = float(parts[2])
            compass = float(parts[3])
            clino = float(parts[4])

            # Validate ranges
            if 0 < distance < 1000 and 0 <= compass < 360 and -90 <= clino <= 90:
                return create_shot_dict(shot_id, from_station, to_station, distance, compass, clino)
        except (ValueError, IndexError):
            pass

    # Pattern 2: Slash separated
    # Example: "L1-L2 7.32/317.2/-72.5"
    slash_match = re.match(r'(\S+)[-\s]+(\S+)\s+([\d.]+)/([\d.]+)/([-\d.]+)', line)
    if slash_match:
        try:
            from_station = slash_match.group(1)
            to_station = slash_match.group(2) if slash_match.group(2) != '-' else None
            distance = float(slash_match.group(3))
            compass = float(slash_match.group(4))
            clino = float(slash_match.group(5))

            if 0 < distance < 1000 and 0 <= compass < 360 and -90 <= clino <= 90:
                return create_shot_dict(shot_id, from_station, to_station, distance, compass, clino)
        except (ValueError, AttributeError):
            pass

    # Pattern 3: Mixed comma/space separated
    # Example: "L1, L2, 7.32, 317.2, -72.5"
    comma_parts = [p.strip() for p in re.split(r'[,\s]+', line)]
    if len(comma_parts) >= 5:
        try:
            from_station = comma_parts[0]
            to_station = comma_parts[1] if comma_parts[1] != '-' else None
            distance = float(comma_parts[2])
            compass = float(comma_parts[3])
            clino = float(comma_parts[4])

            if 0 < distance < 1000 and 0 <= compass < 360 and -90 <= clino <= 90:
                return create_shot_dict(shot_id, from_station, to_station, distance, compass, clino)
        except (ValueError, IndexError):
            pass

    return None


def create_shot_dict(shot_id: int, from_station: str, to_station: Optional[str],
                     distance: float, compass: float, clino: float) -> Dict[str, Any]:
    """
    Create standardized shot dictionary

    Args:
        shot_id: Sequential shot ID
        from_station: From station name
        to_station: To station name (None for splays)
        distance: Shot distance
        compass: Azimuth/compass reading
        clino: Inclination/clino reading

    Returns:
        Shot dictionary
    """
    # Clean station names (remove special characters)
    from_station = re.sub(r'[^\w\d-]', '', from_station)
    if to_station:
        to_station = re.sub(r'[^\w\d-]', '', to_station)

    shot_type = "splay" if to_station is None else "survey"

    return {
        "id": shot_id,
        "from": from_station,
        "to": to_station,
        "distance": round(distance, 2),
        "compass": round(compass, 1),
        "clino": round(clino, 1),
        "type": shot_type,
        "edited": False,
        "errors": [],
        "source": "ocr"
    }


def parse_survey_text(text: str) -> Dict[str, Any]:
    """
    Parse OCR-extracted text to find survey data

    Args:
        text: OCR-extracted text from image

    Returns:
        Dictionary with metadata and shots array
    """
    lines = text.split('\n')
    shots = []
    shot_id = 1

    # Try to extract metadata
    metadata = {
        "survey_name": None,
        "units": {
            "distance": "feet",  # Default assumption
            "angle": "degrees"
        },
        "declination": "undefined",
        "source": "ocr"
    }

    # Look for survey name in first few lines
    for line in lines[:5]:
        if line.strip() and len(line.strip()) > 3 and not any(char.isdigit() for char in line):
            # Likely a title/name
            if metadata["survey_name"] is None:
                metadata["survey_name"] = line.strip()
            break

    # Parse each line for shot data
    for line in lines:
        shot = parse_survey_line(line, shot_id)
        if shot:
            shots.append(shot)
            shot_id += 1

    return {
        "metadata": metadata,
        "shots": shots
    }


def process_image_to_draft(image_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Complete pipeline: Image → OCR → Parsed draft data

    Args:
        image_bytes: Image file bytes
        filename: Original filename

    Returns:
        Draft data dictionary (same format as CSV parser)
    """
    try:
        # Extract text from image
        text = extract_text_from_image(image_bytes)

        if not text or len(text.strip()) < 10:
            raise ValueError("No text could be extracted from the image. Please ensure the image is clear and contains survey data.")

        # Parse text to extract survey data
        draft_data = parse_survey_text(text)

        # Add filename to metadata
        draft_data["metadata"]["filename"] = filename
        draft_data["metadata"]["ocr_text"] = text  # Store raw OCR text for debugging

        if len(draft_data["shots"]) == 0:
            raise ValueError(
                "No survey shots could be extracted from the image. "
                "Please ensure the image contains survey data in a tabular format "
                "(FROM TO DISTANCE AZIMUTH CLINO)."
            )

        return draft_data

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to process image: {str(e)}")


def combine_multiple_images(image_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Combine results from multiple OCR'd images into single draft

    Args:
        image_results: List of draft data dictionaries from individual images

    Returns:
        Combined draft data dictionary
    """
    if not image_results:
        raise ValueError("No image results to combine")

    # Use metadata from first image
    combined_metadata = image_results[0]["metadata"].copy()
    combined_metadata["source"] = "ocr_multiple"
    combined_metadata["num_images"] = len(image_results)

    # Combine all shots with renumbered IDs
    all_shots = []
    shot_id = 1

    for result in image_results:
        for shot in result["shots"]:
            shot_copy = shot.copy()
            shot_copy["id"] = shot_id
            all_shots.append(shot_copy)
            shot_id += 1

    return {
        "metadata": combined_metadata,
        "shots": all_shots
    }
