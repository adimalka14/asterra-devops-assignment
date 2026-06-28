from flask import Flask, request, jsonify
from osgeo import ogr, osr
import json

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/process", methods=["POST"])
def process():
    """Accept a GeoJSON Feature and return spatial metrics."""

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        geometry_json = json.dumps(data.get("geometry", data))
        geom = ogr.CreateGeometryFromJson(geometry_json)

        if geom is None:
            return jsonify({"error": "Invalid geometry"}), 400

        # Reproject to EPSG:3857 for metric units
        source = osr.SpatialReference()
        source.ImportFromEPSG(4326)

        target = osr.SpatialReference()
        target.ImportFromEPSG(3857)

        transform = osr.CoordinateTransformation(source, target)
        geom.Transform(transform)

        envelope = geom.GetEnvelope()

        return jsonify({
            "area_m2":   round(geom.GetArea(), 2),
            "length_m":  round(geom.Length(), 2),
            "bbox": {
                "xmin": round(envelope[0], 6),
                "xmax": round(envelope[1], 6),
                "ymin": round(envelope[2], 6),
                "ymax": round(envelope[3], 6),
            },
            "geometry_type": geom.GetGeometryName(),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)