import json
import logging
import psycopg
from psycopg import sql


def get_connection(db_config: dict) -> psycopg.Connection:
    """Create a database connection."""
    return psycopg.connect(
        host=db_config["host"],
        port=db_config["port"],
        dbname=db_config["dbname"],
        user=db_config["user"],
        password=db_config["password"],
    )


def load_geojson(geojson: dict, db_config: dict, logger: logging.Logger) -> None:
    """Load a GeoJSON object into RDS PostgreSQL with PostGIS."""

    with get_connection(db_config) as conn:
        with conn.cursor() as cur:
            _ensure_schema(cur)

            if geojson["type"] == "FeatureCollection":
                features = geojson["features"]
            elif geojson["type"] == "Feature":
                features = [geojson]
            else:
                # Plain geometry — wrap in a Feature
                features = [{"type": "Feature", "geometry": geojson, "properties": {}}]

            _insert_features(cur, features, logger)
            logger.info(f"Inserted {len(features)} features into RDS")


def _ensure_schema(cur: psycopg.Cursor) -> None:
    """Create PostGIS extension and table if they don't exist."""

    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    cur.execute("""
                CREATE TABLE IF NOT EXISTS geojson_features (
                                                                id         SERIAL PRIMARY KEY,
                                                                geometry   GEOMETRY,
                                                                properties JSONB,
                                                                created_at TIMESTAMP DEFAULT NOW()
                    );
                """)


def _insert_features(cur: psycopg.Cursor, features: list, logger: logging.Logger) -> None:
    """Bulk insert features into the database."""

    rows = [
        (
            json.dumps(feature.get("geometry")),
            json.dumps(feature.get("properties") or {}),
        )
        for feature in features
    ]

    cur.executemany(
        """
        INSERT INTO geojson_features (geometry, properties)
        VALUES (ST_GeomFromGeoJSON(%s), %s)
        """,
        rows,
    )