"""Interactive Kit Builder — deterministic rule engine for personalized kits.

The existing `_INVENTORY_TEMPLATES` in `inventory.py` is a set of static
starter lists (72-hour kit, family 30-day, vehicle, medical bag, etc).
A family of 5 in Phoenix and a solo hiker in Seattle deserve different
water and clothing loadouts from a single "72-hour kit" template — so
this module takes the user's actual mission parameters and emits a
tailored item list with real quantities.

Design principles:

  1. DETERMINISTIC — no LLM. Every item in the output is directly
     traceable to an input rule so users can understand *why* an item
     was recommended. Rule engines that can't be explained are worse
     than checklists.

  2. EXPLAINABLE — every item carries a ``reason`` field that cites
     the input that caused it to be added.

  3. INVENTORY-AWARE — cross-references the user's current inventory
     by normalized item name and marks each recommended item as
     ``have`` / ``partial`` / ``gap`` so the UI can highlight what's
     actually missing.

  4. SMALL SURFACE — one POST endpoint for planning, one POST endpoint
     for committing the gaps to the shopping list. No ORM layer, no
     config files — the rules are just Python.
"""

from flask import Blueprint, request, jsonify
from db import db_session

kit_builder_bp = Blueprint('kit_builder', __name__)


# ─── Mission / climate constants ─────────────────────────────────────
#
# Water requirement (litres per person per day) scales by climate and
# activity level. These are conservative field-op numbers drawn from
# USACE TB MED 507 and common preparedness references:
#   - temperate sedentary:  2 L/day
#   - temperate active:     3 L/day
#   - hot sedentary:        4 L/day
#   - hot active:           6 L/day

_WATER_L_PER_PERSON_PER_DAY = {
    ('temperate', 'shelter_in_place'): 2.0,
    ('temperate', 'bug_out'):          3.0,
    ('temperate', 'vehicle'):          2.5,
    ('cold',      'shelter_in_place'): 2.0,
    ('cold',      'bug_out'):          3.0,
    ('cold',      'vehicle'):          2.5,
    ('hot',       'shelter_in_place'): 3.5,
    ('hot',       'bug_out'):          6.0,
    ('hot',       'vehicle'):          4.0,
    ('tropical',  'shelter_in_place'): 3.0,
    ('tropical',  'bug_out'):          5.0,
    ('tropical',  'vehicle'):          3.5,
}

# Calorie requirement (kcal per person per day) — base + activity bump.
_KCAL_PER_PERSON_PER_DAY = {
    'shelter_in_place': 2200,
    'bug_out':          3500,
    'vehicle':          2500,
    'medical_bag':      0,  # medical bags don't hold food
}

_MISSIONS = {'shelter_in_place', 'bug_out', 'vehicle', 'medical_bag'}
_CLIMATES = {'temperate', 'cold', 'hot', 'tropical'}
_MOBILITIES = {'foot', 'vehicle', 'mixed'}


def _coerce_inputs(payload):
    """Validate + normalize wizard inputs. Raises ValueError on bad input."""
    mission = (payload.get('mission') or 'bug_out').lower().replace('-', '_')
    if mission not in _MISSIONS:
        raise ValueError(f'Unknown mission: {mission}. Expected one of {sorted(_MISSIONS)}')
    climate = (payload.get('climate') or 'temperate').lower()
    if climate not in _CLIMATES:
        raise ValueError(f'Unknown climate: {climate}')
    mobility = (payload.get('mobility') or 'mixed').lower()
    if mobility not in _MOBILITIES:
        raise ValueError(f'Unknown mobility: {mobility}')
    try:
        people = max(1, min(int(payload.get('people', 1)), 50))
    except (TypeError, ValueError):
        people = 1
    try:
        # Cap at 90 days — anything longer is really a storage program,
        # not a portable kit, and the weight estimates get absurd.
        duration_hrs = max(1, min(int(payload.get('duration_hrs', 72)), 90 * 24))
    except (TypeError, ValueError):
        duration_hrs = 72
    return {
        'mission': mission, 'climate': climate, 'mobility': mobility,
        'people': people, 'duration_hrs': duration_hrs,
    }


def _build_items(params):
    """Return the full list of recommended items with reasons + weights.

    Each item is a dict:
        {'name', 'category', 'quantity', 'unit', 'weight_kg', 'reason'}

    The ``reason`` field is free-form but should cite the specific input
    that caused this item to be included so the UI can show it to the
    user when they ask "why is this in my list?".
    """
    mission = params['mission']
    climate = params['climate']
    mobility = params['mobility']
    people = params['people']
    days = max(1, round(params['duration_hrs'] / 24, 1))

    items = []

    # --- Water ---
    if mission != 'medical_bag':
        water_l = _WATER_L_PER_PERSON_PER_DAY.get((climate, mission), 3.0)
        total_l = round(water_l * people * days, 1)
        items.append({
            'name': 'Potable water', 'category': 'water',
            'quantity': total_l, 'unit': 'L',
            'weight_kg': round(total_l * 1.0, 1),  # 1L water = 1kg
            'reason': f'{water_l} L/person/day × {people} people × {days} days ({climate} climate, {mission.replace("_", " ")})',
        })
        # Purification as a backup regardless — you can't carry multi-week
        # water on foot, so filtration covers the gap beyond day 3.
        if days > 3 or mobility == 'foot':
            items.append({
                'name': 'Water filter (hollow fiber)', 'category': 'water',
                'quantity': max(1, (people + 3) // 4), 'unit': 'ea',
                'weight_kg': 0.2,
                'reason': 'Multi-day or foot mobility — resupply from natural sources',
            })
            items.append({
                'name': 'Water purification tablets', 'category': 'water',
                'quantity': max(1, (people * int(days)) // 20 + 1), 'unit': 'pack',
                'weight_kg': 0.05,
                'reason': 'Backup for filter failure',
            })

    # --- Food (kcal-driven) ---
    if mission != 'medical_bag':
        kcal = _KCAL_PER_PERSON_PER_DAY.get(mission, 2500)
        total_kcal = kcal * people * days
        # Rough field-food density: ~4 kcal/gram for dehydrated/ration food
        total_food_kg = round(total_kcal / 4000.0, 1)
        if mobility == 'foot' and days <= 3:
            items.append({
                'name': 'Energy bars / trail mix', 'category': 'food',
                'quantity': people * int(days) * 4, 'unit': 'ea',
                'weight_kg': round(total_food_kg * 0.5, 1),
                'reason': f'Foot mobility — lightweight, ready-to-eat ({kcal} kcal/person/day)',
            })
            items.append({
                'name': 'MRE / freeze-dried meal', 'category': 'food',
                'quantity': people * int(days) * 2, 'unit': 'ea',
                'weight_kg': round(total_food_kg * 0.5, 1),
                'reason': 'Hot meal once per day for morale + warmth',
            })
        elif mission == 'shelter_in_place':
            items.append({
                'name': 'Shelf-stable food (canned + dry)', 'category': 'food',
                'quantity': int(total_food_kg), 'unit': 'kg',
                'weight_kg': round(total_food_kg, 1),
                'reason': f'{kcal} kcal/person/day × {people} people × {days} days — shelter-in-place pantry',
            })
        else:
            items.append({
                'name': 'MRE / freeze-dried meal', 'category': 'food',
                'quantity': people * int(days) * 3, 'unit': 'ea',
                'weight_kg': round(total_food_kg, 1),
                'reason': f'{kcal} kcal/person/day × {people} people × {days} days',
            })

    # --- Shelter / warmth ---
    if mission != 'medical_bag':
        items.append({
            'name': 'Emergency blanket (mylar)', 'category': 'shelter',
            'quantity': people * 2, 'unit': 'ea',
            'weight_kg': 0.06 * people * 2,
            'reason': '2 per person — primary + backup for hypothermia prevention',
        })
        if climate == 'cold':
            items.append({
                'name': 'Sleeping bag (rated to climate)', 'category': 'shelter',
                'quantity': people, 'unit': 'ea', 'weight_kg': 1.5 * people,
                'reason': 'Cold climate — passive warmth overnight',
            })
            items.append({
                'name': 'Insulated base layer + socks', 'category': 'clothing',
                'quantity': people, 'unit': 'sets', 'weight_kg': 0.4 * people,
                'reason': 'Cold climate — layering against cold-weather injury',
            })
        if mission == 'bug_out':
            items.append({
                'name': 'Tarp / bivy shelter', 'category': 'shelter',
                'quantity': max(1, (people + 1) // 2), 'unit': 'ea',
                'weight_kg': 0.7,
                'reason': 'Bug-out — need overhead protection when you stop',
            })
        if climate in ('tropical', 'hot'):
            items.append({
                'name': 'Sun hat / UV buff', 'category': 'clothing',
                'quantity': people, 'unit': 'ea', 'weight_kg': 0.1 * people,
                'reason': f'{climate} climate — UV + heat exhaustion mitigation',
            })
        if climate == 'tropical':
            items.append({
                'name': 'Insect repellent (DEET)', 'category': 'medical',
                'quantity': max(1, (people + 1) // 2), 'unit': 'bottle',
                'weight_kg': 0.1,
                'reason': 'Tropical climate — vector-borne disease prevention',
            })

    # --- Medical ---
    if mission == 'medical_bag':
        base_meds = [
            ('Tourniquet (CAT)', 'medical', 2, 'ea', 0.1),
            ('Hemostatic gauze', 'medical', 2, 'pack', 0.05),
            ('Compressed gauze', 'medical', 4, 'pack', 0.05),
            ('Pressure bandage (Israeli)', 'medical', 2, 'ea', 0.1),
            ('Chest seal (occlusive)', 'medical', 2, 'pair', 0.05),
            ('Nasopharyngeal airway + lube', 'medical', 2, 'ea', 0.03),
            ('SAM splint', 'medical', 2, 'ea', 0.2),
            ('Trauma shears', 'medical', 1, 'ea', 0.1),
            ('Nitrile gloves', 'medical', 8, 'pair', 0.04),
            ('Ibuprofen 200mg', 'medical', 50, 'tablets', 0.05),
            ('Acetaminophen 500mg', 'medical', 50, 'tablets', 0.05),
            ('Benadryl 25mg', 'medical', 24, 'tablets', 0.02),
            ('Antibiotic ointment', 'medical', 2, 'tube', 0.05),
            ('Alcohol prep pads', 'medical', 20, 'ea', 0.02),
            ('Adhesive bandages (assorted)', 'medical', 30, 'ea', 0.05),
        ]
        for n, c, q, u, w in base_meds:
            items.append({'name': n, 'category': c, 'quantity': q, 'unit': u,
                          'weight_kg': w, 'reason': 'IFAK+ medical bag baseline'})
    else:
        items.append({
            'name': 'First aid kit', 'category': 'medical',
            'quantity': max(1, (people + 3) // 4), 'unit': 'ea', 'weight_kg': 0.5,
            'reason': '1 per 4 people — minimum field trauma coverage',
        })
        items.append({
            'name': 'Personal medications (Rx)', 'category': 'medical',
            'quantity': people * int(days), 'unit': 'doses',
            'weight_kg': 0.05 * people,
            'reason': f'{int(days)}-day supply × {people} people — chronic medications',
        })

    # --- Tools / comms ---
    if mission != 'medical_bag':
        items.append({'name': 'Flashlight (LED)', 'category': 'tools',
                      'quantity': people, 'unit': 'ea', 'weight_kg': 0.1 * people,
                      'reason': '1 per person — don\'t share light in a crisis'})
        items.append({'name': 'Headlamp', 'category': 'tools',
                      'quantity': people, 'unit': 'ea', 'weight_kg': 0.08 * people,
                      'reason': 'Hands-free work — 1 per person'})
        items.append({'name': 'Batteries (primary size for flashlights)', 'category': 'tools',
                      'quantity': people * 8, 'unit': 'ea', 'weight_kg': 0.02 * people * 8,
                      'reason': '8 per person — enough for lights + radio'})
        items.append({'name': 'Multi-tool', 'category': 'tools',
                      'quantity': max(1, people // 2), 'unit': 'ea', 'weight_kg': 0.2,
                      'reason': '1 per 2 people — general utility'})
        items.append({'name': 'Paracord 50ft', 'category': 'tools',
                      'quantity': max(1, people // 3), 'unit': 'hank', 'weight_kg': 0.15,
                      'reason': 'General cordage — 1 hank per 3 people'})
        items.append({'name': 'Lighter + waterproof matches', 'category': 'tools',
                      'quantity': max(2, people), 'unit': 'ea', 'weight_kg': 0.02 * people,
                      'reason': 'Fire starting — redundant per person'})

        if mission == 'bug_out':
            items.append({'name': 'Topographic map + compass', 'category': 'tools',
                          'quantity': max(1, people // 2), 'unit': 'set', 'weight_kg': 0.15,
                          'reason': 'Bug-out — navigation without electronics'})
        items.append({'name': 'Handheld radio (GMRS/FRS)', 'category': 'comms',
                      'quantity': max(2, (people + 1) // 2), 'unit': 'ea', 'weight_kg': 0.25 * ((people + 1) // 2),
                      'reason': 'Team comms — 1 per 2 people minimum'})
        items.append({'name': 'Hand-crank AM/FM/weather radio', 'category': 'comms',
                      'quantity': 1, 'unit': 'ea', 'weight_kg': 0.4,
                      'reason': 'Incoming information — does not require batteries'})

    # --- Hygiene ---
    if mission != 'medical_bag' and days >= 1:
        items.append({'name': 'Toilet paper / wet wipes', 'category': 'hygiene',
                      'quantity': max(1, int(people * days / 3)), 'unit': 'roll/pack',
                      'weight_kg': 0.2 * max(1, int(people * days / 3)),
                      'reason': 'Sanitation — scaled to duration'})
        items.append({'name': 'Hand sanitizer', 'category': 'hygiene',
                      'quantity': max(1, (people + 1) // 2), 'unit': 'bottle', 'weight_kg': 0.1,
                      'reason': 'Field hygiene — 1 per 2 people'})
        if days >= 3:
            items.append({'name': 'Soap + travel hygiene kit', 'category': 'hygiene',
                          'quantity': people, 'unit': 'kit', 'weight_kg': 0.15 * people,
                          'reason': '3+ day trip — dental + body hygiene'})

    # --- Documents / money ---
    if mission in ('bug_out', 'vehicle'):
        items.append({'name': 'Cash (small bills)', 'category': 'other',
                      'quantity': 200 * people, 'unit': 'USD', 'weight_kg': 0.05,
                      'reason': f'$200 per person — bug-out / vehicle: card systems may be down'})
        items.append({'name': 'Document copies (waterproof bag)', 'category': 'other',
                      'quantity': 1, 'unit': 'ea', 'weight_kg': 0.2,
                      'reason': 'IDs, insurance, medical — waterproofed'})

    return items


def _normalize_name(s):
    """Lowercase + collapse whitespace for fuzzy inventory matching."""
    return ' '.join((s or '').lower().split())


def _match_against_inventory(items, db):
    """Annotate each item with ``status`` and ``owned_quantity`` by matching
    recommended items against the user's current inventory on normalized
    name. Status is:
        - ``have``    — owned quantity >= recommended
        - ``partial`` — owned quantity > 0 but less than recommended
        - ``gap``     — no match or owned quantity == 0
    """
    rows = db.execute('SELECT id, name, quantity, unit FROM inventory LIMIT 5000').fetchall()
    inv = {}
    for r in rows:
        key = _normalize_name(r['name'])
        if key:
            inv[key] = dict(r)
    for item in items:
        key = _normalize_name(item['name'])
        hit = inv.get(key)
        if hit:
            owned = hit['quantity'] or 0
            item['owned_quantity'] = owned
            item['matched_inventory_id'] = hit['id']
            if owned >= item['quantity']:
                item['status'] = 'have'
            elif owned > 0:
                item['status'] = 'partial'
            else:
                item['status'] = 'gap'
        else:
            item['status'] = 'gap'
            item['owned_quantity'] = 0
    return items


# ─── Routes ─────────────────────────────────────────────────────────

@kit_builder_bp.route('/api/kit-builder/plan', methods=['POST'])
def api_kit_builder_plan():
    """Generate a personalized kit plan from wizard inputs.

    Body:
        {mission, climate, mobility, people, duration_hrs}
    Returns:
        {params, items: [...], totals: {weight_kg, gaps, have, partial}}
    """
    try:
        params = _coerce_inputs(request.get_json() or {})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    items = _build_items(params)
    with db_session() as db:
        items = _match_against_inventory(items, db)

    totals = {
        'weight_kg': round(sum(i.get('weight_kg', 0) or 0 for i in items), 1),
        'gaps':     sum(1 for i in items if i['status'] == 'gap'),
        'partial':  sum(1 for i in items if i['status'] == 'partial'),
        'have':     sum(1 for i in items if i['status'] == 'have'),
        'item_count': len(items),
    }
    return jsonify({'params': params, 'items': items, 'totals': totals})


@kit_builder_bp.route('/api/kit-builder/add-to-shopping-list', methods=['POST'])
def api_kit_builder_add_to_shopping():
    """Commit a list of kit-builder items to the shopping list.

    Body:
        {items: [{name, category, quantity, unit}, ...]}
    Only gap / partial items should be sent; this endpoint doesn't
    filter by status (the UI chooses what to commit) but does enforce
    a hard cap to prevent runaway inserts.
    """
    data = request.get_json() or {}
    raw_items = data.get('items') or []
    if not isinstance(raw_items, list):
        return jsonify({'error': 'items must be a list'}), 400
    # Bound input size — the wizard itself emits < 50 items.
    raw_items = raw_items[:200]
    added = 0
    with db_session() as db:
        for it in raw_items:
            if not isinstance(it, dict): continue
            name = (it.get('name') or '').strip()
            if not name: continue
            try:
                qty = float(it.get('quantity', 1))
            except (TypeError, ValueError):
                qty = 1.0
            category = (it.get('category') or 'other').strip() or 'other'
            unit = (it.get('unit') or 'ea').strip() or 'ea'
            inv_id = it.get('matched_inventory_id')
            db.execute(
                'INSERT OR IGNORE INTO shopping_list (name, category, quantity_needed, unit, inventory_id) '
                'VALUES (?, ?, ?, ?, ?)',
                (name, category, qty, unit, inv_id if isinstance(inv_id, int) else None),
            )
            added += 1
        db.commit()
    return jsonify({'status': 'ok', 'added': added}), 201
