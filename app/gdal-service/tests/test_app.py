import json
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── /health ───────────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_returns_ok_status(self, client):
        data = json.loads(resp := client.get("/health").data)
        assert data == {"status": "ok"}


# ── /process ──────────────────────────────────────────────────────────────────

def _make_polygon_feature():
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        },
        "properties": {},
    }


def _make_point_feature():
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [10.0, 20.0]},
        "properties": {},
    }


class TestProcess:
    def test_non_json_content_type_returns_415(self, client):
        # Flask 3.0 rejects non-JSON content-type before entering the route
        resp = client.post("/process", data="not-json", content_type="text/plain")
        assert resp.status_code == 415

    def test_empty_json_body_returns_400(self, client):
        # Empty dict is falsy → our handler returns 400
        resp = client.post("/process", data="{}", content_type="application/json")
        assert resp.status_code == 400

    @patch("app.ogr.CreateGeometryFromJson", return_value=None)
    def test_invalid_geometry_returns_400(self, mock_ogr, client):
        resp = client.post(
            "/process",
            data=json.dumps({"type": "Point", "coordinates": []}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "Invalid geometry" in json.loads(resp.data)["error"]

    @patch("app.osr.CoordinateTransformation")
    @patch("app.osr.SpatialReference")
    @patch("app.ogr.CreateGeometryFromJson")
    def test_valid_polygon_returns_metrics(self, mock_create_geom, mock_srs, mock_transform, client):
        mock_geom = MagicMock()
        mock_geom.GetArea.return_value = 12345.678
        mock_geom.Length.return_value = 500.123
        mock_geom.GetEnvelope.return_value = (0.0, 1.0, 0.0, 1.0)
        mock_geom.GetGeometryName.return_value = "POLYGON"
        mock_create_geom.return_value = mock_geom

        resp = client.post(
            "/process",
            data=json.dumps(_make_polygon_feature()),
            content_type="application/json",
        )

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["area_m2"] == 12345.68
        assert data["length_m"] == 500.12
        assert data["geometry_type"] == "POLYGON"
        assert "bbox" in data

    @patch("app.osr.CoordinateTransformation")
    @patch("app.osr.SpatialReference")
    @patch("app.ogr.CreateGeometryFromJson")
    def test_bbox_keys_present(self, mock_create_geom, mock_srs, mock_transform, client):
        mock_geom = MagicMock()
        mock_geom.GetArea.return_value = 0.0
        mock_geom.Length.return_value = 0.0
        mock_geom.GetEnvelope.return_value = (1.1, 2.2, 3.3, 4.4)
        mock_geom.GetGeometryName.return_value = "POINT"
        mock_create_geom.return_value = mock_geom

        resp = client.post(
            "/process",
            data=json.dumps(_make_point_feature()),
            content_type="application/json",
        )

        bbox = json.loads(resp.data)["bbox"]
        assert set(bbox.keys()) == {"xmin", "xmax", "ymin", "ymax"}

    @patch("app.osr.CoordinateTransformation")
    @patch("app.osr.SpatialReference")
    @patch("app.ogr.CreateGeometryFromJson")
    def test_accepts_raw_geometry_without_feature_wrapper(self, mock_create_geom, mock_srs, mock_transform, client):
        mock_geom = MagicMock()
        mock_geom.GetArea.return_value = 0.0
        mock_geom.Length.return_value = 0.0
        mock_geom.GetEnvelope.return_value = (0.0, 1.0, 0.0, 1.0)
        mock_geom.GetGeometryName.return_value = "POINT"
        mock_create_geom.return_value = mock_geom

        raw_geom = {"type": "Point", "coordinates": [10.0, 20.0]}
        resp = client.post(
            "/process",
            data=json.dumps(raw_geom),
            content_type="application/json",
        )

        assert resp.status_code == 200

    @patch("app.ogr.CreateGeometryFromJson", side_effect=Exception("GDAL error"))
    def test_gdal_exception_returns_500(self, mock_create_geom, client):
        resp = client.post(
            "/process",
            data=json.dumps(_make_point_feature()),
            content_type="application/json",
        )
        assert resp.status_code == 500
        assert "error" in json.loads(resp.data)
