"""
Claude API-based OCR for cave survey notes
Uses Claude's vision capabilities to extract and parse survey data from images
"""
import base64
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from anthropic import Anthropic

logger = logging.getLogger(__name__)

# Try models in order of preference (newest/best first)
CLAUDE_MODELS = [
    "claude-3-5-sonnet-20241022",  # Claude 3.5 Sonnet v2 (Oct 2024) - newest
    "claude-3-5-sonnet-20240620",  # Claude 3.5 Sonnet v1 (June 2024)
    "claude-3-opus-20240229",      # Claude 3 Opus (Feb 2024)
    "claude-3-haiku-20240307",     # Claude 3 Haiku (Mar 2024) - fallback
]


def extract_raw_text_with_claude(
    image_bytes: bytes,
    filename: str,
    api_key: str
) -> Tuple[str, str]:
    """
    Extract raw text from cave survey image using Claude's vision.

    This is the NEW workflow - just extract text, don't parse.
    User can edit the text and then parse it.

    Args:
        image_bytes: Image file bytes
        filename: Original filename
        api_key: Anthropic API key

    Returns:
        Tuple of (raw_text, model_used)
    """
    try:
        client = Anthropic(api_key=api_key)
        image_base64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        media_type = get_media_type(filename)

        logger.info(f"Extracting raw text with Claude: {filename}, size={len(image_bytes)} bytes")

        # Simple prompt - just extract the text as-is
        prompt = """Extract ALL text from this cave survey data sheet exactly as it appears.

Preserve:
- All numbers and measurements
- Station names/labels
- Column headers
- All data rows
- Any notes or annotations

Format the output as plain text, keeping the tabular structure as clear as possible.
Use spaces or tabs to maintain column alignment.

Return ONLY the extracted text, nothing else."""

        # Try models in order until one works
        model_used = None
        for model in CLAUDE_MODELS:
            try:
                logger.info(f"Trying model: {model}")
                message = client.messages.create(
                    model=model,
                    max_tokens=4096,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": image_base64,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": prompt
                                }
                            ],
                        }
                    ],
                )

                model_used = model
                logger.info(f"✅ Successfully used model: {model}")
                break

            except Exception as e:
                error_str = str(e)
                if "not_found_error" in error_str:
                    logger.warning(f"Model {model} not available, trying next...")
                    continue
                else:
                    raise

        if not model_used:
            raise ValueError("No Claude models available for your API key")

        # Extract raw text
        raw_text = message.content[0].text.strip()
        logger.info(f"Extracted {len(raw_text)} characters of text")

        return raw_text, model_used

    except Exception as e:
        logger.error(f"Claude OCR failed: {str(e)}")
        raise ValueError(f"Failed to extract text with Claude: {str(e)}")


def extract_survey_data_with_claude(
    image_bytes: bytes,
    filename: str,
    api_key: str
) -> Dict[str, Any]:
    """
    Use Claude API to extract cave survey data from an image.

    Claude is much better than Tesseract at:
    - Reading handwritten text
    - Understanding context and layout
    - Handling various formats and messy notes
    - Extracting structured data from unstructured images

    Args:
        image_bytes: Image file bytes
        filename: Original filename for metadata
        api_key: Anthropic API key

    Returns:
        Dict with metadata and shots array
    """
    try:
        # Initialize Claude client
        client = Anthropic(api_key=api_key)

        # Encode image to base64
        image_base64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        # Determine media type from filename
        media_type = get_media_type(filename)

        logger.info(f"Processing image with Claude: {filename}, size={len(image_bytes)} bytes")

        # Create the prompt for Claude
        prompt = """CRITICAL: You must respond with ONLY a valid JSON object. No explanations, no markdown, no extra text.

You are analyzing a cave survey data sheet. Extract all survey shots from this image.

Cave survey shots typically contain these 5 values in order:
1. FROM station (e.g., "A1", "S0", "1")
2. TO station (e.g., "A2", "S1", "2") - or "-" for splays
3. DISTANCE/LENGTH in feet or meters (e.g., "12.5", "7.32")
4. COMPASS/AZIMUTH in degrees 0-360 (e.g., "317.2", "90")
5. CLINO/INCLINATION in degrees -90 to +90 (e.g., "-72.5", "0", "+15")

Additional notes:
- Splays (side shots) have "-" as the TO station
- Station names can be alphanumeric (A1, S0, L1, etc.)
- Look for tabular data, even if handwritten or messy
- Ignore headers, titles, dates, and notes
- Distance must be positive
- Compass must be 0-360
- Clino must be -90 to +90

Return ONLY a JSON object in this exact format:
{
  "metadata": {
    "survey_name": "extracted survey name if visible, otherwise null",
    "units": {"distance": "feet", "angle": "degrees"},
    "declination": "undefined",
    "source": "claude_ocr"
  },
  "shots": [
    {
      "id": 1,
      "from": "A1",
      "to": "A2",
      "distance": 12.5,
      "compass": 317.2,
      "clino": -72.5,
      "type": "survey",
      "edited": false,
      "errors": [],
      "source": "claude_ocr"
    }
  ]
}

IMPORTANT:
- Return ONLY the JSON object, no other text
- If no survey data found, return empty shots array
- For splays, set "to": null and "type": "splay"
- For centerline shots, set "type": "survey"
- Preserve all decimal precision from the image"""

        # Call Claude API
        # Using Claude 3 Haiku for fast, cost-effective vision processing
        message = client.messages.create(
            model="claude-3-haiku-20240307",  # Claude 3 Haiku - available to all tiers
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                }
            ],
        )

        # Extract the response text
        response_text = message.content[0].text
        logger.info(f"Claude response length: {len(response_text)} characters")

        # Parse JSON from response
        # Claude might wrap JSON in markdown code blocks or add extra text
        response_text = response_text.strip()

        # Try to extract JSON from the response
        draft_data = None

        # Method 1: Try direct parsing
        try:
            draft_data = json.loads(response_text)
            logger.info("Parsed JSON directly from response")
        except json.JSONDecodeError:
            pass

        # Method 2: Remove markdown code blocks
        if draft_data is None:
            cleaned = response_text
            if "```json" in cleaned:
                # Extract content between ```json and ```
                start = cleaned.find("```json") + 7
                end = cleaned.find("```", start)
                if end > start:
                    cleaned = cleaned[start:end].strip()
            elif "```" in cleaned:
                # Extract content between ``` and ```
                start = cleaned.find("```") + 3
                end = cleaned.find("```", start)
                if end > start:
                    cleaned = cleaned[start:end].strip()

            try:
                draft_data = json.loads(cleaned)
                logger.info("Parsed JSON after removing markdown")
            except json.JSONDecodeError:
                pass

        # Method 3: Find JSON object by looking for { and }
        if draft_data is None:
            try:
                # Find first { and last }
                start = response_text.find('{')
                end = response_text.rfind('}')
                if start >= 0 and end > start:
                    json_str = response_text[start:end+1]
                    draft_data = json.loads(json_str)
                    logger.info("Parsed JSON by extracting { } block")
            except json.JSONDecodeError:
                pass

        # If all methods failed, log the response and raise error
        if draft_data is None:
            logger.error(f"Failed to parse Claude response as JSON")
            logger.error(f"Full response text:\n{response_text}")
            logger.error(f"Response preview (first 500 chars): {response_text[:500]}")
            raise ValueError(f"Could not extract valid JSON from Claude response. Response length: {len(response_text)}")

        # Validate structure
        if not isinstance(draft_data, dict):
            raise ValueError("Claude response is not a dictionary")

        if "shots" not in draft_data:
            raise ValueError("Claude response missing 'shots' key")

        if "metadata" not in draft_data:
            draft_data["metadata"] = {
                "survey_name": None,
                "units": {"distance": "feet", "angle": "degrees"},
                "declination": "undefined",
                "source": "claude_ocr"
            }

        # Ensure metadata has required fields
        draft_data["metadata"]["filename"] = filename
        draft_data["metadata"]["source"] = "claude_ocr"

        # Validate shots
        shots = draft_data["shots"]
        if not isinstance(shots, list):
            raise ValueError("'shots' must be a list")

        # Clean up and validate each shot
        cleaned_shots = []
        for i, shot in enumerate(shots, 1):
            cleaned_shot = clean_shot(shot, i)
            if cleaned_shot:
                cleaned_shots.append(cleaned_shot)

        draft_data["shots"] = cleaned_shots

        logger.info(f"Successfully extracted {len(cleaned_shots)} shots from image")

        return draft_data

    except Exception as e:
        logger.error(f"Claude OCR failed: {str(e)}")
        logger.exception("Full traceback:")
        raise ValueError(f"Failed to process image with Claude: {str(e)}")


def clean_shot(shot: Dict[str, Any], shot_id: int) -> Optional[Dict[str, Any]]:
    """
    Clean and validate a shot extracted by Claude.

    Args:
        shot: Raw shot dictionary from Claude
        shot_id: Sequential ID to assign

    Returns:
        Cleaned shot dictionary or None if invalid
    """
    try:
        # Extract and validate fields
        from_station = str(shot.get("from", "")).strip()
        to_station = shot.get("to")

        # Handle null/None for to_station (splays)
        if to_station is None or str(to_station).strip() in ["", "-", "null"]:
            to_station = None
            shot_type = "splay"
        else:
            to_station = str(to_station).strip()
            shot_type = "survey"

        # Validate required fields
        if not from_station:
            logger.warning(f"Shot {shot_id}: Missing from station")
            return None

        # Parse numeric values
        distance = float(shot.get("distance", 0))
        compass = float(shot.get("compass", 0))
        clino = float(shot.get("clino", 0))

        # Validate ranges
        if distance <= 0 or distance > 1000:
            logger.warning(f"Shot {shot_id}: Invalid distance {distance}")
            return None

        if compass < 0 or compass >= 360:
            logger.warning(f"Shot {shot_id}: Invalid compass {compass}")
            return None

        if clino < -90 or clino > 90:
            logger.warning(f"Shot {shot_id}: Invalid clino {clino}")
            return None

        # Create cleaned shot
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
            "source": "claude_ocr"
        }

    except (ValueError, TypeError) as e:
        logger.warning(f"Shot {shot_id}: Failed to parse - {str(e)}")
        return None


def get_media_type(filename: str) -> str:
    """
    Determine media type from filename.

    Args:
        filename: Image filename

    Returns:
        Media type string for Claude API
    """
    filename_lower = filename.lower()

    if filename_lower.endswith(('.jpg', '.jpeg')):
        return "image/jpeg"
    elif filename_lower.endswith('.png'):
        return "image/png"
    elif filename_lower.endswith('.gif'):
        return "image/gif"
    elif filename_lower.endswith('.webp'):
        return "image/webp"
    else:
        # Default to JPEG
        return "image/jpeg"


def combine_multiple_images(image_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Combine results from multiple images processed by Claude.

    Args:
        image_results: List of draft data dictionaries

    Returns:
        Combined draft data dictionary
    """
    if not image_results:
        raise ValueError("No image results to combine")

    # Use metadata from first image
    combined_metadata = image_results[0]["metadata"].copy()
    combined_metadata["source"] = "claude_ocr_multiple"
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
