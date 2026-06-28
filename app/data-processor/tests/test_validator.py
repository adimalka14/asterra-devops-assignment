import pytest
from validator import validate_geojson


# ── Helpers ──────────────────────────────────────────────────────────────────

def point(lon=10.0, lat=20.0):
    return {"type": "Point", "coordinates": [lon, lat]}

def closed_ring():
    return [[0, 0], [1, 0], [1, 1], [0, 0]]

def polygon(rings=None):
    return {"type": "Polygon", "coordinates": rings or [closed_ring()]}

def feature(geom=None):
    return {"type": "Feature", "geometry": geom or point(), "properties": {}}

def feature_collection(features=None):
    return {"type": "FeatureCollection", "features": features or [feature()]}


# ── Top-level dispatch ────────────────────────────────────────────────────────

class TestTopLevel:
    def test_rejects_non_dict(self):
        with pytest.raises(ValueError, match="JSON object"):
            validate_geojson("string")

    def test_rejects_list(self):
        with pytest.raises(ValueError, match="JSON object"):
            validate_geojson([1, 2, 3])

    def test_rejects_missing_type(self):
        with pytest.raises(ValueError, match="Missing required field: type"):
            validate_geojson({"coordinates": [0, 0]})

    def test_rejects_unknown_type(self):
        with pytest.raises(ValueError, match="Invalid GeoJSON type"):
            validate_geojson({"type": "Galaxy"})


# ── Point ─────────────────────────────────────────────────────────────────────

class TestPoint:
    def test_valid(self):
        validate_geojson(point())

    def test_valid_with_elevation(self):
        validate_geojson({"type": "Point", "coordinates": [10.0, 20.0, 100.0]})

    def test_missing_coordinates(self):
        with pytest.raises(ValueError, match="coordinates"):
            validate_geojson({"type": "Point"})

    def test_longitude_too_high(self):
        with pytest.raises(ValueError, match="Longitude out of range"):
            validate_geojson(point(lon=181))

    def test_longitude_too_low(self):
        with pytest.raises(ValueError, match="Longitude out of range"):
            validate_geojson(point(lon=-181))

    def test_latitude_too_high(self):
        with pytest.raises(ValueError, match="Latitude out of range"):
            validate_geojson(point(lat=91))

    def test_latitude_too_low(self):
        with pytest.raises(ValueError, match="Latitude out of range"):
            validate_geojson(point(lat=-91))

    def test_non_numeric_coordinates(self):
        with pytest.raises(ValueError, match="numbers"):
            validate_geojson({"type": "Point", "coordinates": ["a", "b"]})

    def test_single_value_position(self):
        with pytest.raises(ValueError, match="at least 2"):
            validate_geojson({"type": "Point", "coordinates": [10]})

    def test_boundary_values(self):
        validate_geojson(point(lon=180, lat=90))
        validate_geojson(point(lon=-180, lat=-90))


# ── LineString ────────────────────────────────────────────────────────────────

class TestLineString:
    def test_valid(self):
        validate_geojson({"type": "LineString", "coordinates": [[0, 0], [1, 1]]})

    def test_too_few_positions(self):
        with pytest.raises(ValueError, match="at least 2"):
            validate_geojson({"type": "LineString", "coordinates": [[0, 0]]})

    def test_invalid_position_inside(self):
        with pytest.raises(ValueError, match="Longitude out of range"):
            validate_geojson({"type": "LineString", "coordinates": [[0, 0], [200, 0]]})


# ── Polygon ───────────────────────────────────────────────────────────────────

class TestPolygon:
    def test_valid(self):
        validate_geojson(polygon())

    def test_unclosed_ring(self):
        # 4 positions (passes length check) but first != last
        with pytest.raises(ValueError, match="closed"):
            validate_geojson({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]})

    def test_ring_too_short(self):
        with pytest.raises(ValueError, match="at least 4"):
            validate_geojson({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]})

    def test_empty_rings(self):
        with pytest.raises(ValueError, match="at least one ring"):
            validate_geojson({"type": "Polygon", "coordinates": []})

    def test_hole_ring(self):
        outer = closed_ring()
        inner = [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.1]]
        validate_geojson({"type": "Polygon", "coordinates": [outer, inner]})

    def test_invalid_coordinate_in_ring(self):
        bad_ring = [[0, 0], [200, 0], [1, 1], [0, 0]]
        with pytest.raises(ValueError, match="Longitude out of range"):
            validate_geojson({"type": "Polygon", "coordinates": [bad_ring]})


# ── MultiPoint ────────────────────────────────────────────────────────────────

class TestMultiPoint:
    def test_valid(self):
        validate_geojson({"type": "MultiPoint", "coordinates": [[0, 0], [1, 1]]})

    def test_too_few(self):
        with pytest.raises(ValueError, match="at least 2"):
            validate_geojson({"type": "MultiPoint", "coordinates": [[0, 0]]})


# ── MultiLineString ───────────────────────────────────────────────────────────

class TestMultiLineString:
    def test_valid(self):
        validate_geojson({
            "type": "MultiLineString",
            "coordinates": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]],
        })

    def test_inner_line_too_short(self):
        with pytest.raises(ValueError, match="at least 2"):
            validate_geojson({
                "type": "MultiLineString",
                "coordinates": [[[0, 0]]],
            })


# ── MultiPolygon ──────────────────────────────────────────────────────────────

class TestMultiPolygon:
    def test_valid(self):
        validate_geojson({
            "type": "MultiPolygon",
            "coordinates": [[closed_ring()], [closed_ring()]],
        })

    def test_inner_polygon_unclosed(self):
        # 4 positions but first != last
        with pytest.raises(ValueError, match="closed"):
            validate_geojson({
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 1]]]],
            })


# ── GeometryCollection ────────────────────────────────────────────────────────

class TestGeometryCollection:
    def test_valid(self):
        validate_geojson({
            "type": "GeometryCollection",
            "geometries": [point(), polygon()],
        })

    def test_missing_geometries(self):
        with pytest.raises(ValueError, match="geometries"):
            validate_geojson({"type": "GeometryCollection"})

    def test_nested_invalid_geometry(self):
        with pytest.raises(ValueError, match="Longitude out of range"):
            validate_geojson({
                "type": "GeometryCollection",
                "geometries": [point(lon=999)],
            })


# ── Feature ───────────────────────────────────────────────────────────────────

class TestFeature:
    def test_valid(self):
        validate_geojson(feature())

    def test_null_geometry_allowed(self):
        validate_geojson({"type": "Feature", "geometry": None, "properties": {}})

    def test_missing_geometry_field(self):
        with pytest.raises(ValueError, match="geometry"):
            validate_geojson({"type": "Feature", "properties": {}})

    def test_wrong_type_value(self):
        # _validate_feature is reached via FeatureCollection — checks Feature.type
        with pytest.raises(ValueError, match="Feature.type"):
            validate_geojson({
                "type": "FeatureCollection",
                "features": [{"type": "NotAFeature", "geometry": point(), "properties": {}}],
            })

    def test_invalid_nested_geometry(self):
        with pytest.raises(ValueError, match="Latitude out of range"):
            validate_geojson(feature(geom=point(lat=100)))


# ── FeatureCollection ─────────────────────────────────────────────────────────

class TestFeatureCollection:
    def test_valid(self):
        validate_geojson(feature_collection())

    def test_missing_features_field(self):
        with pytest.raises(ValueError, match="features"):
            validate_geojson({"type": "FeatureCollection"})

    def test_features_not_list(self):
        with pytest.raises(ValueError, match="must be an array"):
            validate_geojson({"type": "FeatureCollection", "features": "bad"})

    def test_empty_features(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_geojson({"type": "FeatureCollection", "features": []})

    def test_invalid_feature_reports_index(self):
        bad = feature(geom=point(lon=999))
        with pytest.raises(ValueError, match="index 1"):
            validate_geojson(feature_collection([feature(), bad]))

    def test_multiple_valid_features(self):
        validate_geojson(feature_collection([feature(), feature(geom=polygon())]))
