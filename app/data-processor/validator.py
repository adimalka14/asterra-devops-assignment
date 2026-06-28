import json
from typing import Any

VALID_GEOMETRY_TYPES = {
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
    "GeometryCollection",
}

def validate_geojson(data: Any) -> None:
    """
    Validate a GeoJSON object against RFC 7946.
    Raises ValueError if the GeoJSON is invalid.
    """

    if not isinstance(data, dict):
        raise ValueError("GeoJSON must be a JSON object")

    _validate_type(data)

    geojson_type = data["type"]

    if geojson_type == "FeatureCollection":
        _validate_feature_collection(data)
    elif geojson_type == "Feature":
        _validate_feature(data)
    elif geojson_type in VALID_GEOMETRY_TYPES:
        _validate_geometry(data)
    else:
        raise ValueError(f"Invalid GeoJSON type: {geojson_type}")


def _validate_type(data: dict) -> None:
    if "type" not in data:
        raise ValueError("Missing required field: type")


def _validate_feature_collection(data: dict) -> None:
    if "features" not in data:
        raise ValueError("FeatureCollection missing required field: features")

    if not isinstance(data["features"], list):
        raise ValueError("FeatureCollection.features must be an array")

    if len(data["features"]) == 0:
        raise ValueError("FeatureCollection.features must not be empty")

    for i, feature in enumerate(data["features"]):
        try:
            _validate_feature(feature)
        except ValueError as e:
            raise ValueError(f"Invalid feature at index {i}: {e}")


def _validate_feature(data: dict) -> None:
    if data.get("type") != "Feature":
        raise ValueError("Feature.type must be 'Feature'")

    if "geometry" not in data:
        raise ValueError("Feature missing required field: geometry")

    if data["geometry"] is not None:
        _validate_geometry(data["geometry"])


def _validate_geometry(data: dict) -> None:
    if "type" not in data:
        raise ValueError("Geometry missing required field: type")

    if data["type"] not in VALID_GEOMETRY_TYPES:
        raise ValueError(f"Invalid geometry type: {data['type']}")

    if data["type"] == "GeometryCollection":
        if "geometries" not in data:
            raise ValueError("GeometryCollection missing required field: geometries")
        for geometry in data["geometries"]:
            _validate_geometry(geometry)
        return

    if "coordinates" not in data:
        raise ValueError(f"Geometry missing required field: coordinates")

    _validate_coordinates(data["coordinates"], data["type"])


def _validate_coordinates(coords: Any, geometry_type: str) -> None:
    if geometry_type == "Point":
        _validate_position(coords)
    elif geometry_type in ("MultiPoint", "LineString"):
        if not isinstance(coords, list) or len(coords) < 2:
            raise ValueError(f"{geometry_type} must have at least 2 positions")
        for pos in coords:
            _validate_position(pos)
    elif geometry_type == "Polygon":
        _validate_polygon(coords)
    elif geometry_type == "MultiLineString":
        for line in coords:
            _validate_coordinates(line, "LineString")
    elif geometry_type == "MultiPolygon":
        for polygon in coords:
            _validate_polygon(polygon)


def _validate_position(pos: Any) -> None:
    if not isinstance(pos, list) or len(pos) < 2:
        raise ValueError("Position must be an array of at least 2 numbers")
    if not all(isinstance(n, (int, float)) for n in pos):
        raise ValueError("Position values must be numbers")
    if not (-180 <= pos[0] <= 180):
        raise ValueError(f"Longitude out of range: {pos[0]}")
    if not (-90 <= pos[1] <= 90):
        raise ValueError(f"Latitude out of range: {pos[1]}")


def _validate_polygon(coords: Any) -> None:
    if not isinstance(coords, list) or len(coords) < 1:
        raise ValueError("Polygon must have at least one ring")
    for ring in coords:
        if not isinstance(ring, list) or len(ring) < 4:
            raise ValueError("Polygon ring must have at least 4 positions")
        if ring[0] != ring[-1]:
            raise ValueError("Polygon ring must be closed (first and last position must be equal)")
        for pos in ring:
            _validate_position(pos)