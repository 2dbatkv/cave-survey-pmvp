"""
Utilities for parsing and validating survey draft data
"""
import re
import csv
import io
from typing import Dict, List, Any, Tuple
from datetime import datetime


def parse_topodroid_csv(csv_content: str) -> Dict[str, Any]:
    """
    Parse TopoDroid CSV format and return structured draft data

    Args:
        csv_content: String content of CSV file

    Returns:
        Dictionary with metadata and shots array
    """
    lines = csv_content.strip().split('\n')

    # Parse header comments
    metadata = {
        "created_date": None,
        "survey_name": None,
        "units": {
            "distance": "feet",
            "angle": "degrees"
        },
        "declination": "undefined",
        "topodroid_version": None
    }

    shots = []
    shot_id = 1

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Parse header comments
        if line.startswith('#'):
            # Extract date
            if 'created by TopoDroid' in line:
                date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', line)
                version_match = re.search(r'v ([\d.]+)', line)
                if date_match:
                    metadata["created_date"] = date_match.group(1)
                if version_match:
                    metadata["topodroid_version"] = version_match.group(1)

            # Extract survey name (second comment line)
            elif metadata["survey_name"] is None and not any(key in line for key in ['from', 'to', 'tape', 'compass', 'clino', 'units']):
                metadata["survey_name"] = line.replace('#', '').strip()

            # Extract units
            elif 'units tape' in line:
                units_match = re.search(r'units tape (\w+)', line)
                if units_match:
                    metadata["units"]["distance"] = units_match.group(1)

            # Extract declination
            elif 'declination' in line:
                if 'undefined' in line:
                    metadata["declination"] = "undefined"
                else:
                    decl_match = re.search(r'declination ([-\d.]+)', line)
                    if decl_match:
                        metadata["declination"] = float(decl_match.group(1))

            continue

        # Parse data lines
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 5:
            continue

        try:
            from_station = parts[0].replace('@' + metadata.get("survey_name", ""), "")
            to_station = parts[1].replace('@' + metadata.get("survey_name", ""), "") if parts[1] and parts[1] != '-' else None
            distance = float(parts[2]) if parts[2] else 0.0
            compass = float(parts[3]) if parts[3] else 0.0
            clino = float(parts[4]) if parts[4] else 0.0

            # Determine shot type based on to_station
            shot_type = "splay" if to_station is None or to_station == '-' else "survey"

            shot = {
                "id": shot_id,
                "from": from_station,
                "to": to_station,
                "distance": distance,
                "compass": compass,
                "clino": clino,
                "type": shot_type,
                "edited": False,
                "errors": []
            }

            shots.append(shot)
            shot_id += 1

        except (ValueError, IndexError) as e:
            # Skip malformed lines
            continue

    return {
        "metadata": metadata,
        "shots": shots
    }


def validate_shot(shot: Dict[str, Any]) -> List[str]:
    """
    Validate a single shot and return list of errors

    Args:
        shot: Shot dictionary

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Validate from station
    if not shot.get("from"):
        errors.append("Missing 'from' station")

    # Validate to station for survey shots
    if shot.get("type") == "survey" and not shot.get("to"):
        errors.append("Survey shots must have a 'to' station")

    # Validate distance
    distance = shot.get("distance", 0)
    if not isinstance(distance, (int, float)):
        errors.append("Distance must be a number")
    elif distance <= 0:
        errors.append("Distance must be greater than 0")
    elif distance > 1000:  # Reasonable max for cave surveys (in feet/meters)
        errors.append(f"Distance {distance} seems unusually large")

    # Validate compass
    compass = shot.get("compass")
    if compass is None:
        errors.append("Missing compass reading")
    elif not isinstance(compass, (int, float)):
        errors.append("Compass must be a number")
    elif compass < 0 or compass >= 360:
        errors.append(f"Compass {compass} must be between 0 and 360")

    # Validate clino
    clino = shot.get("clino")
    if clino is None:
        errors.append("Missing clino reading")
    elif not isinstance(clino, (int, float)):
        errors.append("Clino must be a number")
    elif clino < -90 or clino > 90:
        errors.append(f"Clino {clino} must be between -90 and 90")

    return errors


def validate_draft_data(draft_data: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validate entire draft data structure

    Args:
        draft_data: Draft data dictionary with metadata and shots

    Returns:
        Tuple of (is_valid, list of validation issues)
    """
    issues = []

    # Validate structure
    if "metadata" not in draft_data:
        issues.append({"type": "structure", "message": "Missing metadata"})

    if "shots" not in draft_data:
        issues.append({"type": "structure", "message": "Missing shots array"})
        return False, issues

    shots = draft_data["shots"]

    if not isinstance(shots, list):
        issues.append({"type": "structure", "message": "Shots must be an array"})
        return False, issues

    if len(shots) == 0:
        issues.append({"type": "data", "message": "No shots found in data"})
        return False, issues

    # Validate each shot
    for idx, shot in enumerate(shots):
        shot_errors = validate_shot(shot)
        if shot_errors:
            for error in shot_errors:
                issues.append({
                    "type": "shot",
                    "shot_id": shot.get("id", idx + 1),
                    "shot_index": idx,
                    "message": error
                })

    # Check for duplicate stations in survey shots
    survey_shots = [s for s in shots if s.get("type") == "survey"]
    station_pairs = set()
    for shot in survey_shots:
        pair = (shot.get("from"), shot.get("to"))
        if pair in station_pairs:
            issues.append({
                "type": "duplicate",
                "shot_id": shot.get("id"),
                "message": f"Duplicate shot: {pair[0]} to {pair[1]}"
            })
        station_pairs.add(pair)

    is_valid = len([i for i in issues if i["type"] == "shot"]) == 0

    return is_valid, issues


def convert_draft_to_survey_data(draft_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert validated draft data to survey format for final storage

    Args:
        draft_data: Draft data dictionary

    Returns:
        Survey data dictionary ready for storage
    """
    metadata = draft_data.get("metadata", {})
    shots = draft_data.get("shots", [])

    # Filter to only survey shots for centerline
    survey_shots = [s for s in shots if s.get("type") == "survey"]

    # Convert to survey format
    survey_data = {
        "metadata": {
            "name": metadata.get("survey_name", "Unnamed Survey"),
            "date": metadata.get("created_date"),
            "units": metadata.get("units", {"distance": "feet", "angle": "degrees"}),
            "declination": metadata.get("declination"),
            "shot_count": len(survey_shots),
            "splay_count": len([s for s in shots if s.get("type") == "splay"])
        },
        "stations": extract_stations(shots),
        "shots": survey_shots,
        "splays": [s for s in shots if s.get("type") == "splay"]
    }

    return survey_data


def extract_stations(shots: List[Dict[str, Any]]) -> List[str]:
    """
    Extract unique station names from shots

    Args:
        shots: List of shot dictionaries

    Returns:
        Sorted list of unique station names
    """
    stations = set()

    for shot in shots:
        if shot.get("from"):
            stations.add(shot["from"])
        if shot.get("to") and shot.get("type") == "survey":
            stations.add(shot["to"])

    return sorted(list(stations))
