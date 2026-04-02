"""Build the shared offline atlas bundle used by NukeMap and VIPTrack.

The atlas is sourced from Natural Earth 1:50m GeoJSON layers so it can ship
with the app and still render a real offline basemap with:

- land polygons
- coastlines
- country borders
- admin-1 state/province borders
- lakes
- rivers
- major populated place labels
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path


ATLAS_VERSION = "2026-04-02.3"
REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "web" / "nukemap" / "data" / "offline_atlas.json"
SOURCE_BASE = "https://raw.githubusercontent.com/martynafford/natural-earth-geojson/master/"
SOURCE_PATHS = {
    "land": "50m/physical/ne_50m_land.json",
    "coastlines": "50m/physical/ne_50m_coastline.json",
    "countryBorders": "50m/cultural/ne_50m_admin_0_boundary_lines_land.json",
    "admin1Borders": "50m/cultural/ne_50m_admin_1_states_provinces_lines.json",
    "lakes": "50m/physical/ne_50m_lakes.json",
    "rivers": "50m/physical/ne_50m_rivers_lake_centerlines.json",
    "places": "50m/cultural/ne_50m_populated_places_simple.json",
}


def fetch_geojson(path: str) -> dict:
    with urllib.request.urlopen(SOURCE_BASE + path, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def quantize(value: float) -> float:
    return round(float(value), 3)


def encode_line(coords: list[list[float]]) -> tuple[list[float], list[float]]:
    flat_points: list[float] = []
    min_lng = min_lat = 999.0
    max_lng = max_lat = -999.0
    for lng, lat in coords:
        q_lng = quantize(lng)
        q_lat = quantize(lat)
        flat_points.extend((q_lng, q_lat))
        min_lng = min(min_lng, q_lng)
        min_lat = min(min_lat, q_lat)
        max_lng = max(max_lng, q_lng)
        max_lat = max(max_lat, q_lat)
    return flat_points, [min_lng, min_lat, max_lng, max_lat]


def polygon_features(feature_collection: dict) -> list[dict]:
    features: list[dict] = []
    for feature in feature_collection["features"]:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        min_zoom = feature.get("properties", {}).get("min_zoom")
        if geometry["type"] == "Polygon":
            rings = geometry["coordinates"][:1]
        elif geometry["type"] == "MultiPolygon":
            rings = [polygon[0] for polygon in geometry["coordinates"] if polygon]
        else:
            continue
        for ring in rings:
            if len(ring) < 4:
                continue
            points, bbox = encode_line(ring)
            features.append({"minZoom": min_zoom, "bbox": bbox, "points": points})
    return features


def line_features(feature_collection: dict, keep_props: tuple[str, ...] = ()) -> list[dict]:
    features: list[dict] = []
    for feature in feature_collection["features"]:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        props = feature.get("properties", {})
        min_zoom = props.get("min_zoom")
        if geometry["type"] == "LineString":
            parts = [geometry["coordinates"]]
        elif geometry["type"] == "MultiLineString":
            parts = geometry["coordinates"]
        else:
            continue
        for part in parts:
            if len(part) < 2:
                continue
            points, bbox = encode_line(part)
            item = {"minZoom": min_zoom, "bbox": bbox, "points": points}
            for key in keep_props:
                value = props.get(key)
                if value not in (None, ""):
                    item[key] = value
            features.append(item)
    return features


def place_features(feature_collection: dict) -> list[dict]:
    features: list[dict] = []
    for feature in feature_collection["features"]:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        props = feature.get("properties", {})
        name = props.get("name")
        if not name:
            continue
        pop = int(props.get("pop_max") or 0)
        world = bool(props.get("worldcity"))
        capital = bool(props.get("adm0cap"))
        label_rank = props.get("labelrank") or props.get("scalerank") or 5
        if not (capital or world or pop >= 250_000 or label_rank <= 3):
            continue
        lng, lat = geometry["coordinates"]
        features.append(
            {
                "name": name,
                "lat": quantize(lat),
                "lng": quantize(lng),
                "pop": pop,
                "capital": capital,
                "world": world,
                "rank": label_rank,
                "minZoom": props.get("min_zoom"),
                "adm0": props.get("adm0name"),
            }
        )
    features.sort(key=lambda item: (-item["world"], -item["capital"], item["rank"], -item["pop"], item["name"]))
    return features


def build_atlas() -> dict:
    raw = {name: fetch_geojson(path) for name, path in SOURCE_PATHS.items()}
    return {
        "version": ATLAS_VERSION,
        "source": {
            "dataset": "Natural Earth 1:50m",
            "license": "Public domain / CC0",
            "layers": list(SOURCE_PATHS.values()),
        },
        "land": polygon_features(raw["land"]),
        "lakes": polygon_features(raw["lakes"]),
        "coastlines": line_features(raw["coastlines"]),
        "countryBorders": line_features(raw["countryBorders"], ("name",)),
        "admin1Borders": line_features(raw["admin1Borders"], ("name", "adm0_name")),
        "rivers": [
            feature
            for feature in line_features(raw["rivers"], ("name",))
            if (feature.get("minZoom") or 99) <= 6
        ],
        "places": place_features(raw["places"]),
    }


def main() -> None:
    atlas = build_atlas()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(atlas, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
