import json
import logging
import pytest
from unittest.mock import MagicMock, patch, call

from loader import load_geojson, _ensure_schema, _insert_features


@pytest.fixture
def logger():
    return logging.getLogger("test")


@pytest.fixture
def db_config():
    return {
        "host": "localhost",
        "port": 5432,
        "dbname": "testdb",
        "user": "user",
        "password": "pass",
    }


@pytest.fixture
def mock_conn():
    cur = MagicMock()
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cur


# ── _ensure_schema ────────────────────────────────────────────────────────────

class TestEnsureSchema:
    def test_creates_postgis_extension(self):
        cur = MagicMock()
        _ensure_schema(cur)
        first_call_sql = cur.execute.call_args_list[0][0][0]
        assert "postgis" in first_call_sql.lower()

    def test_creates_table(self):
        cur = MagicMock()
        _ensure_schema(cur)
        second_call_sql = cur.execute.call_args_list[1][0][0]
        assert "geojson_features" in second_call_sql.lower()
        assert "geometry" in second_call_sql.lower()

    def test_called_twice(self):
        cur = MagicMock()
        _ensure_schema(cur)
        assert cur.execute.call_count == 2


# ── _insert_features ──────────────────────────────────────────────────────────

class TestInsertFeatures:
    def _make_feature(self, lon=10.0, lat=20.0):
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"name": "test"},
        }

    def test_inserts_single_feature(self, logger):
        cur = MagicMock()
        features = [self._make_feature()]
        _insert_features(cur, features, logger)
        cur.executemany.assert_called_once()

    def test_inserts_multiple_features(self, logger):
        cur = MagicMock()
        features = [self._make_feature(i, i) for i in range(3)]
        _insert_features(cur, features, logger)
        rows = cur.executemany.call_args[0][1]
        assert len(rows) == 3

    def test_row_contains_geometry_json(self, logger):
        cur = MagicMock()
        feature = self._make_feature()
        _insert_features(cur, [feature], logger)
        rows = cur.executemany.call_args[0][1]
        geom_str, props_str = rows[0]
        assert json.loads(geom_str) == feature["geometry"]

    def test_row_contains_properties_json(self, logger):
        cur = MagicMock()
        feature = self._make_feature()
        _insert_features(cur, [feature], logger)
        rows = cur.executemany.call_args[0][1]
        _, props_str = rows[0]
        assert json.loads(props_str) == {"name": "test"}

    def test_null_properties_become_empty_dict(self, logger):
        cur = MagicMock()
        feature = {"type": "Feature", "geometry": None, "properties": None}
        _insert_features(cur, [feature], logger)
        rows = cur.executemany.call_args[0][1]
        _, props_str = rows[0]
        assert json.loads(props_str) == {}


# ── load_geojson ──────────────────────────────────────────────────────────────

class TestLoadGeoJSON:
    def _point_feature(self):
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [10.0, 20.0]},
            "properties": {},
        }

    @patch("loader.get_connection")
    def test_feature_collection_loads_all_features(self, mock_get_conn, db_config, logger, mock_conn):
        conn, cur = mock_conn
        mock_get_conn.return_value = conn

        geojson = {
            "type": "FeatureCollection",
            "features": [self._point_feature(), self._point_feature()],
        }
        load_geojson(geojson, db_config, logger)

        rows = cur.executemany.call_args[0][1]
        assert len(rows) == 2

    @patch("loader.get_connection")
    def test_single_feature_wrapped_in_list(self, mock_get_conn, db_config, logger, mock_conn):
        conn, cur = mock_conn
        mock_get_conn.return_value = conn

        load_geojson(self._point_feature(), db_config, logger)

        rows = cur.executemany.call_args[0][1]
        assert len(rows) == 1

    @patch("loader.get_connection")
    def test_plain_geometry_wrapped_in_feature(self, mock_get_conn, db_config, logger, mock_conn):
        conn, cur = mock_conn
        mock_get_conn.return_value = conn

        geojson = {"type": "Point", "coordinates": [10.0, 20.0]}
        load_geojson(geojson, db_config, logger)

        rows = cur.executemany.call_args[0][1]
        assert len(rows) == 1

    @patch("loader.get_connection")
    def test_schema_ensured_before_insert(self, mock_get_conn, db_config, logger, mock_conn):
        conn, cur = mock_conn
        mock_get_conn.return_value = conn

        load_geojson(self._point_feature(), db_config, logger)

        # execute called twice for schema, executemany for insert
        assert cur.execute.call_count == 2
        assert cur.executemany.call_count == 1

    @patch("loader.get_connection")
    def test_passes_correct_db_config(self, mock_get_conn, db_config, logger, mock_conn):
        conn, _ = mock_conn
        mock_get_conn.return_value = conn

        load_geojson(self._point_feature(), db_config, logger)

        mock_get_conn.assert_called_once_with(db_config)
