import json
import logging
import sys
import os

logging.disable(logging.CRITICAL)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.app import create_app
from db import init_db

# Fresh DB — resolve the actual path the app uses
from config import get_data_dir
db_path = os.path.join(get_data_dir(), "nomad.db")
if os.path.exists(db_path):
    os.remove(db_path)

init_db()
app = create_app()
passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name} - {detail}")


def get_json_safe(r):
    try:
        return r.get_json() or {}
    except Exception:
        return {}


with app.test_client() as c:
    H = {"Content-Type": "application/json"}

    # === INVENTORY CRUD ===
    r = c.post("/api/inventory", data=json.dumps({"name": "MRE Case", "category": "food", "quantity": 12, "unit": "cases"}), headers=H)
    test("inv create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")
    inv_id = get_json_safe(r).get("id")

    r = c.get("/api/inventory")
    test("inv list", r.status_code == 200 and len(r.get_json()) == 1)

    r = c.put(f"/api/inventory/{inv_id}", data=json.dumps({"name": "MRE Case Updated", "quantity": 24}), headers=H)
    test("inv update", r.status_code == 200, f"got {r.status_code} body={r.data[:200]}")

    r = c.get("/api/inventory")
    items = r.get_json()
    test("inv updated name", items[0]["name"] == "MRE Case Updated")
    test("inv updated qty", items[0]["quantity"] == 24)

    r = c.delete(f"/api/inventory/{inv_id}")
    test("inv delete", r.status_code in (200, 204), f"got {r.status_code}")

    r = c.get("/api/inventory")
    test("inv empty after delete", len(r.get_json()) == 0)

    # === CONTACTS CRUD ===
    r = c.post("/api/contacts", data=json.dumps({"name": "John Doe", "role": "medic", "phone": "555-1234"}), headers=H)
    test("contact create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")
    ct_id = get_json_safe(r).get("id")

    r = c.put(f"/api/contacts/{ct_id}", data=json.dumps({"name": "Jane Doe", "role": "comms"}), headers=H)
    test("contact update", r.status_code == 200, f"got {r.status_code} body={r.data[:200]}")

    r = c.delete(f"/api/contacts/{ct_id}")
    test("contact delete", r.status_code in (200, 204), f"got {r.status_code}")

    # === NOTES CRUD ===
    r = c.post("/api/notes", data=json.dumps({"title": "Test Note", "content": "Hello world"}), headers=H)
    test("note create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")
    note_id = get_json_safe(r).get("id")

    r = c.put(f"/api/notes/{note_id}", data=json.dumps({"title": "Updated Note", "content": "Updated content"}), headers=H)
    test("note update", r.status_code == 200, f"got {r.status_code} body={r.data[:200]}")

    r = c.delete(f"/api/notes/{note_id}")
    test("note delete", r.status_code in (200, 204), f"got {r.status_code}")

    # === TASKS CRUD ===
    r = c.post("/api/tasks", data=json.dumps({"name": "Test Task", "priority": "high"}), headers=H)
    test("task create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")
    task_id = get_json_safe(r).get("id")

    r = c.put(f"/api/tasks/{task_id}", data=json.dumps({"notes": "updated via test"}), headers=H)
    test("task update", r.status_code == 200, f"got {r.status_code} body={r.data[:200]}")

    r = c.delete(f"/api/tasks/{task_id}")
    test("task delete", r.status_code in (200, 204), f"got {r.status_code}")

    # === CHECKLISTS CRUD ===
    r = c.post("/api/checklists", data=json.dumps({"name": "Bug Out Bag", "items": "[]"}), headers=H)
    test("checklist create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")
    cl_id = get_json_safe(r).get("id")

    r = c.put(f"/api/checklists/{cl_id}", data=json.dumps({"items": '[{"text":"Water","done":false}]'}), headers=H)
    test("checklist update", r.status_code == 200, f"got {r.status_code} body={r.data[:200]}")

    r = c.delete(f"/api/checklists/{cl_id}")
    test("checklist delete", r.status_code in (200, 204), f"got {r.status_code}")

    # === AMMO CRUD ===
    r = c.post("/api/ammo", data=json.dumps({"caliber": "9mm", "quantity": 200, "brand": "Federal"}), headers=H)
    test("ammo create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")
    ammo_id = get_json_safe(r).get("id")

    r = c.put(f"/api/ammo/{ammo_id}", data=json.dumps({"quantity": 150}), headers=H)
    test("ammo update", r.status_code == 200, f"got {r.status_code} body={r.data[:200]}")

    r = c.delete(f"/api/ammo/{ammo_id}")
    test("ammo delete", r.status_code in (200, 204), f"got {r.status_code}")

    # === EQUIPMENT CRUD ===
    r = c.post("/api/equipment", data=json.dumps({"name": "Baofeng UV-5R", "category": "comms", "quantity": 2}), headers=H)
    test("equip create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")
    eq_id = get_json_safe(r).get("id")

    r = c.delete(f"/api/equipment/{eq_id}")
    test("equip delete", r.status_code in (200, 204), f"got {r.status_code}")

    # === FUEL CRUD ===
    r = c.post("/api/fuel", data=json.dumps({"fuel_type": "gasoline", "capacity_gallons": 55, "current_gallons": 40, "location": "Garage"}), headers=H)
    test("fuel create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")
    fuel_id = get_json_safe(r).get("id")

    r = c.delete(f"/api/fuel/{fuel_id}")
    test("fuel delete", r.status_code in (200, 204), f"got {r.status_code}")

    # === RADIATION CRUD ===
    r = c.post("/api/radiation", data=json.dumps({"dose_rate_rem": 0.015, "location": "Front yard"}), headers=H)
    test("radiation create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")

    # === VAULT CRUD ===
    # Vault stores client-side encrypted data — requires encrypted_data, iv, salt fields
    r = c.post("/api/vault", data=json.dumps({
        "title": "WiFi Password",
        "encrypted_data": "dGVzdGVuY3J5cHRlZA==",
        "iv": "aXZkYXRh",
        "salt": "c2FsdGRhdGE="
    }), headers=H)
    test("vault create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")
    vault_id = get_json_safe(r).get("id")

    r = c.get("/api/vault")
    test("vault list", r.status_code == 200)

    r = c.delete(f"/api/vault/{vault_id}")
    test("vault delete", r.status_code in (200, 204), f"got {r.status_code}")

    # === SKILLS CRUD ===
    r = c.post("/api/skills", data=json.dumps({"name": "First Aid", "category": "medical", "proficiency": "intermediate"}), headers=H)
    test("skill create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")
    skill_id = get_json_safe(r).get("id")

    r = c.delete(f"/api/skills/{skill_id}")
    test("skill delete", r.status_code in (200, 204), f"got {r.status_code}")

    # === COMMUNITY CRUD ===
    r = c.post("/api/community", data=json.dumps({"name": "Smith Family", "distance_mi": 0.5, "trust_level": "trusted"}), headers=H)
    test("community create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")
    comm_id = get_json_safe(r).get("id")

    r = c.delete(f"/api/community/{comm_id}")
    test("community delete", r.status_code in (200, 204), f"got {r.status_code}")

    # === LIVESTOCK CRUD ===
    r = c.post("/api/livestock", data=json.dumps({"name": "Backyard Flock", "species": "chicken", "count": 12}), headers=H)
    test("livestock create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")
    ls_id = get_json_safe(r).get("id")

    r = c.delete(f"/api/livestock/{ls_id}")
    test("livestock delete", r.status_code in (200, 204), f"got {r.status_code}")

    # === JOURNAL ===
    r = c.post("/api/journal", data=json.dumps({"entry": "Day 1: Everything is normal.", "mood": "good"}), headers=H)
    test("journal create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")

    # === INCIDENTS ===
    r = c.post("/api/incidents", data=json.dumps({"severity": "info", "category": "security", "description": "Unknown vehicle on road"}), headers=H)
    test("incident create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")

    # === WEATHER ===
    r = c.post("/api/weather", data=json.dumps({"temp_f": 72, "humidity": 45, "pressure_mb": 1013.25, "conditions": "Clear"}), headers=H)
    test("weather create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")

    # === COMMS LOG ===
    r = c.post("/api/comms-log", data=json.dumps({"freq": "146.520", "callsign": "KD0TEST", "direction": "rx", "message": "Net check-in"}), headers=H)
    test("comms log create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")

    # === WAYPOINTS ===
    r = c.post("/api/waypoints", data=json.dumps({"name": "Rally Point Alpha", "lat": 39.7392, "lng": -104.9903}), headers=H)
    test("waypoint create", r.status_code == 201, f"got {r.status_code} body={r.data[:200]}")

    # === SETTINGS ===
    r = c.get("/api/settings")
    test("settings read", r.status_code == 200)

    r = c.put("/api/settings", data=json.dumps({"household_size": "4"}), headers=H)
    test("settings update", r.status_code == 200, f"got {r.status_code} body={r.data[:200]}")

    # === PLANNER ===
    r = c.post("/api/planner/calculate", data=json.dumps({"people": 4, "days": 14, "activity": "moderate"}), headers=H)
    test("planner calculate", r.status_code == 200, f"got {r.status_code} body={r.data[:200]}")

    # Planner validation
    r = c.post("/api/planner/calculate", data=json.dumps({"people": "abc"}), headers=H)
    test("planner validation", r.status_code == 400, f"got {r.status_code} body={r.data[:200]}")

    # === NUTRITION / FOOD SECURITY ===
    r = c.get("/api/inventory/nutrition-summary")
    test("nutrition summary", r.status_code == 200)

    r = c.get("/api/garden/food-security")
    test("food security", r.status_code == 200)

    # === READINESS ===
    r = c.get("/api/readiness-score")
    test("readiness score", r.status_code == 200, f"got {r.status_code} body={r.data[:200]}")

    # === SYSTEM ===
    r = c.get("/api/system")
    test("system info", r.status_code == 200)

    # === CONTENT SUMMARY ===
    r = c.get("/api/content-summary")
    test("content summary", r.status_code == 200, f"got {r.status_code} body={r.data[:200]}")

    # === OFFLINE SNAPSHOT ===
    r = c.get("/api/offline/snapshot")
    test("offline snapshot", r.status_code == 200, f"got {r.status_code} body={r.data[:200]}")

print(f"\n{passed} passed, {failed} failed out of {passed + failed} tests")
if failed > 0:
    sys.exit(1)
