"""Planting calendar seed data — CE-01 (v7.61).

Generates ``planting_calendar`` rows for every USDA hardiness zone 3-10
from a per-crop base timing (calibrated to zone 7, the climate of the
Mid-Atlantic / southern Midwest) plus a zone offset table.

Schema (from db.py):
    (crop, zone, month, action, notes, yield_per_sqft,
     calories_per_lb, days_to_harvest)

Actions:
    start_indoor  — sow seeds indoors under lights
    transplant    — move started seedlings outdoors
    direct_sow    — sow seeds straight into garden bed
    harvest       — pick mature crop

A month value is 1-12. Rows are expanded per zone by shifting the base
month with a zone-specific offset (colder zones later in spring,
earlier in fall; warmer zones the reverse). Crop × zone combinations
that can't realistically happen (e.g., long-season sweet potato in zone 3)
are filtered out automatically.

Yield + calorie values are rule-of-thumb averages — biointensive /
vigorous varieties can double these, poor soil halves them.

Sources: Cornell Home Gardening, Eliot Coleman "Four-Season Harvest",
John Jeavons "How to Grow More Vegetables", Territorial Seed growers'
guide, USDA plant hardiness zone map.
"""

# ──────────────────────────────────────────────────────────────────
# Zone offsets from zone 7 (baseline).
#
# spring_offset shifts spring-side activities (months 1-6: start_indoor,
# transplant, direct_sow). Cold zones get POSITIVE offset (later start);
# warm zones get NEGATIVE (earlier start).
#
# fall_offset shifts fall-side activities (months 7-12: late sowing,
# harvest). Cold zones get NEGATIVE (shorter season ends sooner); warm
# zones get POSITIVE (longer season extends later).
# ──────────────────────────────────────────────────────────────────
ZONE_OFFSETS = {
    # zone: (spring_offset, fall_offset)
    '3':  (+2, -2),    # coldest — latest spring start, earliest fall end
    '4':  (+1, -1),
    '5':  (+1, -1),
    '6':   (0,  0),
    '7':   (0,  0),    # baseline
    '8':  (-1, +1),
    '9':  (-2, +2),
    '10': (-3, +3),    # warmest — year-round potential
}


# ──────────────────────────────────────────────────────────────────
# Per-crop base timing (calibrated to zone 7).
#
#   'actions' is a list of (month, action, notes) for the baseline zone.
#   'min_zone' gates very-long-season crops out of cold zones.
#
# Yield + calorie data is best-available averages (per sqft, per lb).
# Long-season crops like sweet potato are restricted to ≥ zone 6.
# ──────────────────────────────────────────────────────────────────
CROPS = [
    # ─────────────── Brassicas ───────────────
    {
        'crop': 'Broccoli', 'min_zone': 3,
        'yield_per_sqft': 0.6, 'calories_per_lb': 155, 'days_to_harvest': 70,
        'actions': [
            (2, 'start_indoor', 'Start 6-8 wk before last frost. 2 true leaves → pot up.'),
            (4, 'transplant',   'Set out after hardening when soil ≥ 45 °F.'),
            (6, 'harvest',      'Cut main head when tight + dark green. Side shoots continue 4-6 wk.'),
            (8, 'direct_sow',   'Fall crop — sow 12-14 wk before first frost.'),
            (11, 'harvest',     'Fall harvest — cold-sweetens flavor.'),
        ],
    },
    {
        'crop': 'Cabbage', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 112, 'days_to_harvest': 80,
        'actions': [
            (2, 'start_indoor', 'Start 6-8 wk before last frost.'),
            (4, 'transplant',   'Transplant when soil ≥ 45 °F.'),
            (7, 'harvest',      'Head firm to thumb pressure. Cut + leave stump for side heads.'),
            (7, 'start_indoor', 'Start fall crop indoors.'),
            (11, 'harvest',     'Fall/winter storage crop — keeps months in root cellar.'),
        ],
    },
    {
        'crop': 'Kale', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 228, 'days_to_harvest': 55,
        'actions': [
            (3, 'direct_sow', 'Sow 4 wk before last frost. Frost-tolerant.'),
            (5, 'harvest',    'Pick outer leaves; center continues producing.'),
            (8, 'direct_sow', 'Fall sow — sweetest after frost.'),
            (11, 'harvest',   'Fall/winter harvest. Row cover extends to -10 °F.'),
        ],
    },
    {
        'crop': 'Cauliflower', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 113, 'days_to_harvest': 75,
        'actions': [
            (2, 'start_indoor', 'Start 6 wk before last frost. Fussy — even temps.'),
            (4, 'transplant',   'Set out at 45 °F soil.'),
            (7, 'harvest',      'Blanch heads by tying outer leaves over when size of egg.'),
        ],
    },
    {
        'crop': 'Brussels Sprouts', 'min_zone': 3,
        'yield_per_sqft': 1.5, 'calories_per_lb': 195, 'days_to_harvest': 95,
        'actions': [
            (4, 'start_indoor', 'Start indoors; long season.'),
            (6, 'transplant',   'Set out with cages — they get tall.'),
            (10, 'harvest',     'Bottom sprouts first; frost sweetens.'),
            (12, 'harvest',     'Through early winter with row cover.'),
        ],
    },
    {
        'crop': 'Collards', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 150, 'days_to_harvest': 60,
        'actions': [
            (3, 'direct_sow', 'Very cold-hardy; direct sow early spring.'),
            (5, 'harvest',    'Pick outer leaves continuously.'),
            (8, 'direct_sow', 'Fall crop.'),
            (12, 'harvest',   'Frost-improved flavor.'),
        ],
    },
    {
        'crop': 'Radish', 'min_zone': 3,
        'yield_per_sqft': 1.5, 'calories_per_lb': 77, 'days_to_harvest': 25,
        'actions': [
            (3, 'direct_sow', 'Sow 4 wk before last frost; fastest veg in the garden.'),
            (4, 'harvest',    'Pull before flowering or they turn woody.'),
            (4, 'direct_sow', 'Succession sow every 2 wk.'),
            (9, 'direct_sow', 'Fall crop — best flavor.'),
            (10, 'harvest',   'Fall harvest.'),
        ],
    },
    {
        'crop': 'Turnip', 'min_zone': 3,
        'yield_per_sqft': 1.5, 'calories_per_lb': 127, 'days_to_harvest': 45,
        'actions': [
            (3, 'direct_sow', 'Cool-season; both greens + roots edible.'),
            (5, 'harvest',    'Pick at 2-3 in for sweet roots.'),
            (8, 'direct_sow', 'Fall crop.'),
            (11, 'harvest',   'Fall harvest.'),
        ],
    },

    # ─────────────── Leafy greens ───────────────
    {
        'crop': 'Lettuce', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 68, 'days_to_harvest': 50,
        'actions': [
            (3, 'direct_sow', 'Sow 4-6 wk before last frost. Shade cloth above 75 °F.'),
            (5, 'harvest',    'Cut-and-come-again leaf; head at maturity.'),
            (5, 'direct_sow', 'Succession sow every 2 wk through spring.'),
            (8, 'direct_sow', 'Fall sow; cold-tolerant varieties for winter.'),
            (11, 'harvest',   'With row cover, harvest into December in mid-zones.'),
        ],
    },
    {
        'crop': 'Spinach', 'min_zone': 3,
        'yield_per_sqft': 1.5, 'calories_per_lb': 104, 'days_to_harvest': 45,
        'actions': [
            (3, 'direct_sow', 'Sow 4-6 wk before last frost; bolt-resistant varieties for late spring.'),
            (5, 'harvest',    'Cut outer leaves or pick whole plant.'),
            (9, 'direct_sow', 'Fall crop — overwinters under row cover.'),
            (11, 'harvest',   'Fall harvest; resume Mar if overwintered.'),
        ],
    },
    {
        'crop': 'Swiss Chard', 'min_zone': 3,
        'yield_per_sqft': 1.5, 'calories_per_lb': 86, 'days_to_harvest': 55,
        'actions': [
            (4, 'direct_sow', 'Sow 2 wk before last frost.'),
            (6, 'harvest',    'Cut outer leaves; plant produces until hard freeze.'),
            (12, 'harvest',   'Heavy mulch overwinters for early spring comeback.'),
        ],
    },
    {
        'crop': 'Arugula', 'min_zone': 3,
        'yield_per_sqft': 1.5, 'calories_per_lb': 113, 'days_to_harvest': 30,
        'actions': [
            (3, 'direct_sow', 'Very fast-growing. Succession every 2 wk.'),
            (5, 'harvest',    'Cut outer leaves at 3-4 in.'),
            (9, 'direct_sow', 'Fall crop — cold sweetens.'),
        ],
    },

    # ─────────────── Alliums ───────────────
    {
        'crop': 'Onion', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 181, 'days_to_harvest': 105,
        'actions': [
            (1, 'start_indoor', 'Start from seed 10-12 wk before transplant.'),
            (4, 'transplant',   'Sets or transplants 4 in apart.'),
            (8, 'harvest',      'Tops fall over — lift + cure 2 wk in shade + airflow.'),
        ],
    },
    {
        'crop': 'Garlic', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 653, 'days_to_harvest': 240,
        'actions': [
            (10, 'direct_sow', 'Plant cloves 4-6 wk before ground freezes. Hardneck for cold zones.'),
            (6, 'harvest',     'Harvest scapes May-June for pesto.'),
            (7, 'harvest',     'Harvest bulbs when 3-4 lower leaves brown. Cure 3 wk in shade.'),
        ],
    },
    {
        'crop': 'Leek', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 277, 'days_to_harvest': 100,
        'actions': [
            (2, 'start_indoor', 'Start 10-12 wk before last frost.'),
            (5, 'transplant',   'Trench plant 6 in deep; hill as they grow for blanched shanks.'),
            (10, 'harvest',     'Extremely hardy — mulch heavy + harvest through winter.'),
        ],
    },

    # ─────────────── Root crops ───────────────
    {
        'crop': 'Carrot', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 186, 'days_to_harvest': 70,
        'actions': [
            (4, 'direct_sow', 'Sow 2 wk before last frost. Thin to 2-3 in.'),
            (7, 'harvest',    'Pull when shoulder ≥ 3/4 in.'),
            (8, 'direct_sow', 'Fall crop — sweetens in cold.'),
            (11, 'harvest',   'Mulch heavy + harvest through winter.'),
        ],
    },
    {
        'crop': 'Beet', 'min_zone': 3,
        'yield_per_sqft': 1.5, 'calories_per_lb': 195, 'days_to_harvest': 60,
        'actions': [
            (4, 'direct_sow', 'Soak seed overnight; sow 2 wk before last frost.'),
            (6, 'harvest',    'Greens edible anytime; roots at 2-3 in.'),
            (8, 'direct_sow', 'Fall crop.'),
            (11, 'harvest',   'Store in damp sand for months.'),
        ],
    },
    {
        'crop': 'Potato', 'min_zone': 3,
        'yield_per_sqft': 2.0, 'calories_per_lb': 346, 'days_to_harvest': 95,
        'actions': [
            (4, 'direct_sow', 'Plant seed potatoes 2 wk before last frost. Hill as they grow.'),
            (7, 'harvest',    'New potatoes when flowers open.'),
            (9, 'harvest',    'Main harvest when tops die back. Cure 10 d in dark 60 °F.'),
        ],
    },
    {
        'crop': 'Sweet Potato', 'min_zone': 6,
        'yield_per_sqft': 2.0, 'calories_per_lb': 399, 'days_to_harvest': 120,
        'actions': [
            (4, 'start_indoor', 'Slip production from roots indoors 6 wk ahead.'),
            (5, 'transplant',   'Set slips out 2 wk after last frost. Needs 75 °F soil.'),
            (10, 'harvest',     'Before first frost kills leaves. Cure 7-10 d 80 °F + humid.'),
        ],
    },
    {
        'crop': 'Parsnip', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 340, 'days_to_harvest': 120,
        'actions': [
            (4, 'direct_sow', 'Slow germinator (3+ wk). Use fresh seed.'),
            (10, 'harvest',   'Flavor improves after hard frost; overwinter in ground.'),
        ],
    },
    {
        'crop': 'Rutabaga', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 168, 'days_to_harvest': 90,
        'actions': [
            (6, 'direct_sow', 'Sow midsummer for fall harvest.'),
            (10, 'harvest',   'Cold-sweetens. Store in root cellar all winter.'),
        ],
    },
    {
        'crop': 'Jerusalem Artichoke', 'min_zone': 3,
        'yield_per_sqft': 2.5, 'calories_per_lb': 327, 'days_to_harvest': 180,
        'actions': [
            (4, 'direct_sow', 'Plant tubers after last frost; spreads aggressively — contain.'),
            (10, 'harvest',   'After first frost; dig as needed through winter.'),
        ],
    },

    # ─────────────── Nightshades ───────────────
    {
        'crop': 'Tomato', 'min_zone': 3,
        'yield_per_sqft': 2.0, 'calories_per_lb': 82, 'days_to_harvest': 80,
        'actions': [
            (3, 'start_indoor', 'Start 6-8 wk before last frost under lights.'),
            (5, 'transplant',   'Harden off 7-10 d; plant deep (buries lower stems).'),
            (7, 'harvest',      'First ripe fruit; continues until frost.'),
            (10, 'harvest',     'Pick green at first frost warning; ripen on counter.'),
        ],
    },
    {
        'crop': 'Pepper', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 137, 'days_to_harvest': 85,
        'actions': [
            (2, 'start_indoor', 'Start 8-10 wk before last frost; heat mat helps germination.'),
            (5, 'transplant',   'Harden off; plant when soil ≥ 60 °F.'),
            (7, 'harvest',      'Green at first; allow to ripen for red/yellow/orange.'),
            (10, 'harvest',     'Before first frost.'),
        ],
    },
    {
        'crop': 'Eggplant', 'min_zone': 5,
        'yield_per_sqft': 1.5, 'calories_per_lb': 113, 'days_to_harvest': 85,
        'actions': [
            (2, 'start_indoor', 'Very heat-loving; start 8 wk before last frost.'),
            (5, 'transplant',   'Plant when nights ≥ 55 °F — flea beetle magnet; row cover.'),
            (8, 'harvest',      'Skin still glossy — dulls when over-ripe.'),
        ],
    },
    {
        'crop': 'Tomatillo', 'min_zone': 3,
        'yield_per_sqft': 1.5, 'calories_per_lb': 145, 'days_to_harvest': 75,
        'actions': [
            (3, 'start_indoor', 'Start with tomatoes.'),
            (5, 'transplant',   'Plant 2 for pollination — self-sterile.'),
            (8, 'harvest',      'Husks split; fruit fills the husk.'),
        ],
    },

    # ─────────────── Cucurbits ───────────────
    {
        'crop': 'Cucumber', 'min_zone': 3,
        'yield_per_sqft': 2.5, 'calories_per_lb': 68, 'days_to_harvest': 55,
        'actions': [
            (5, 'direct_sow', 'Sow after soil ≥ 65 °F. Trellising doubles production.'),
            (7, 'harvest',    'Pick daily — skipped cucumbers stop production.'),
        ],
    },
    {
        'crop': 'Zucchini', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 77, 'days_to_harvest': 50,
        'actions': [
            (5, 'direct_sow', 'Sow 1-2 wk after last frost. One plant feeds a family.'),
            (7, 'harvest',    'Pick at 6-8 in. Skipped = softball overnight.'),
        ],
    },
    {
        'crop': 'Summer Squash', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 77, 'days_to_harvest': 55,
        'actions': [
            (5, 'direct_sow', 'Same as zucchini.'),
            (7, 'harvest',    'Harvest small for tenderness.'),
        ],
    },
    {
        'crop': 'Butternut Squash', 'min_zone': 3,
        'yield_per_sqft': 1.5, 'calories_per_lb': 204, 'days_to_harvest': 110,
        'actions': [
            (5, 'direct_sow', 'Sow when soil ≥ 70 °F.'),
            (9, 'harvest',    'Harvest when stem corks + skin resists fingernail. Cure 2 wk at 80 °F. Stores 6+ months.'),
        ],
    },
    {
        'crop': 'Pumpkin', 'min_zone': 3,
        'yield_per_sqft': 1.5, 'calories_per_lb': 118, 'days_to_harvest': 100,
        'actions': [
            (5, 'direct_sow', 'Sow after soil ≥ 70 °F. Needs sprawl space.'),
            (10, 'harvest',   'Hard rind + corked stem. Cure 10 d in sun.'),
        ],
    },
    {
        'crop': 'Watermelon', 'min_zone': 4,
        'yield_per_sqft': 1.5, 'calories_per_lb': 136, 'days_to_harvest': 85,
        'actions': [
            (5, 'direct_sow', 'Wants soil ≥ 75 °F; use black plastic mulch in cold zones.'),
            (8, 'harvest',    'Ground spot yellow + tendril near stem brown + hollow sound when tapped.'),
        ],
    },
    {
        'crop': 'Cantaloupe', 'min_zone': 4,
        'yield_per_sqft': 1.5, 'calories_per_lb': 154, 'days_to_harvest': 85,
        'actions': [
            (5, 'direct_sow', 'Same as watermelon.'),
            (8, 'harvest',    'Slips from vine with gentle pressure; fragrant.'),
        ],
    },

    # ─────────────── Legumes ───────────────
    {
        'crop': 'Bush Bean', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 155, 'days_to_harvest': 55,
        'actions': [
            (5, 'direct_sow', 'Sow after last frost when soil ≥ 60 °F.'),
            (5, 'direct_sow', 'Succession sow every 2 wk until 8 wk before first frost.'),
            (7, 'harvest',    'Pick daily to keep producing.'),
        ],
    },
    {
        'crop': 'Pole Bean', 'min_zone': 3,
        'yield_per_sqft': 1.5, 'calories_per_lb': 155, 'days_to_harvest': 65,
        'actions': [
            (5, 'direct_sow', 'At base of 8 ft trellis after last frost.'),
            (7, 'harvest',    'Pick every 2-3 days through frost.'),
        ],
    },
    {
        'crop': 'Pea', 'min_zone': 3,
        'yield_per_sqft': 1.0, 'calories_per_lb': 381, 'days_to_harvest': 65,
        'actions': [
            (3, 'direct_sow', 'Sow 4-6 wk before last frost; trellis up 4 ft.'),
            (6, 'harvest',    'Shell peas: pods full. Snap: pods firm + bright.'),
            (8, 'direct_sow', 'Fall crop; bolt resistance iffy above zone 7.'),
        ],
    },
    {
        'crop': 'Soy Bean', 'min_zone': 3,
        'yield_per_sqft': 0.5, 'calories_per_lb': 1490, 'days_to_harvest': 100,
        'actions': [
            (5, 'direct_sow', 'Sow after last frost.'),
            (9, 'harvest',    'Edamame: pods plump + bright green. Dry: pods brown + rattle.'),
        ],
    },
    {
        'crop': 'Lentil', 'min_zone': 3,
        'yield_per_sqft': 0.5, 'calories_per_lb': 1539, 'days_to_harvest': 110,
        'actions': [
            (4, 'direct_sow', 'Direct sow as soon as soil workable. Cool-season legume.'),
            (8, 'harvest',    'Plants yellow + pods rattle. Threshing required.'),
        ],
    },

    # ─────────────── Grains ───────────────
    {
        'crop': 'Corn', 'min_zone': 3,
        'yield_per_sqft': 0.6, 'calories_per_lb': 1633, 'days_to_harvest': 85,
        'actions': [
            (5, 'direct_sow', 'Block plant (≥ 4 × 4) for wind pollination. Soil ≥ 60 °F.'),
            (8, 'harvest',    'Sweet: kernels milky when punctured. Dent: kernels dry + dented.'),
        ],
    },
    {
        'crop': 'Winter Wheat', 'min_zone': 3,
        'yield_per_sqft': 0.2, 'calories_per_lb': 1488, 'days_to_harvest': 240,
        'actions': [
            (9, 'direct_sow', 'Sow 6-8 wk before first hard freeze.'),
            (7, 'harvest',    'Heads golden + kernels dent with fingernail but don\'t smash.'),
        ],
    },
    {
        'crop': 'Oats', 'min_zone': 3,
        'yield_per_sqft': 0.15, 'calories_per_lb': 1792, 'days_to_harvest': 100,
        'actions': [
            (4, 'direct_sow', 'Cool-season grain; sow as soon as soil workable.'),
            (8, 'harvest',    'When kernels in "soft dough" stage.'),
        ],
    },

    # ─────────────── Herbs ───────────────
    {
        'crop': 'Basil', 'min_zone': 3,
        'yield_per_sqft': 0.3, 'calories_per_lb': 104, 'days_to_harvest': 60,
        'actions': [
            (3, 'start_indoor', 'Start with tomatoes; heat lover.'),
            (5, 'transplant',   'Plant when nights ≥ 55 °F.'),
            (7, 'harvest',      'Pinch tips continuously; remove flowers to extend.'),
        ],
    },
    {
        'crop': 'Cilantro / Coriander', 'min_zone': 3,
        'yield_per_sqft': 0.3, 'calories_per_lb': 104, 'days_to_harvest': 50,
        'actions': [
            (3, 'direct_sow', 'Cool-season; bolts fast above 80 °F.'),
            (5, 'harvest',    'Pick young leaves.'),
            (6, 'harvest',    'Coriander seed when heads dry + brown.'),
            (9, 'direct_sow', 'Fall crop.'),
        ],
    },
    {
        'crop': 'Dill', 'min_zone': 3,
        'yield_per_sqft': 0.3, 'calories_per_lb': 191, 'days_to_harvest': 55,
        'actions': [
            (5, 'direct_sow', 'Direct sow — tap root hates transplant.'),
            (7, 'harvest',    'Leafy fronds anytime; seeds when heads brown.'),
        ],
    },
    {
        'crop': 'Parsley', 'min_zone': 3,
        'yield_per_sqft': 0.3, 'calories_per_lb': 163, 'days_to_harvest': 75,
        'actions': [
            (3, 'start_indoor', 'Slow germinator — soak seed overnight.'),
            (5, 'transplant',   'Set out after hardening.'),
            (6, 'harvest',      'Cut outer stems continuously; biennial — flowers year 2.'),
        ],
    },
    {
        'crop': 'Chives', 'min_zone': 3,
        'yield_per_sqft': 0.3, 'calories_per_lb': 136, 'days_to_harvest': 80,
        'actions': [
            (4, 'transplant', 'Divide established clumps + set out.'),
            (5, 'harvest',    'Snip continuously; flowers edible.'),
        ],
    },
    {
        'crop': 'Oregano', 'min_zone': 5,
        'yield_per_sqft': 0.3, 'calories_per_lb': 1220, 'days_to_harvest': 80,
        'actions': [
            (4, 'transplant', 'Perennial — from division or transplant.'),
            (6, 'harvest',    'Best flavor just before flowers open.'),
        ],
    },
]


def planting_rows():
    """Yield (crop, zone, month, action, notes, yield_per_sqft,
    calories_per_lb, days_to_harvest) tuples for every zone × crop combo."""
    for crop_spec in CROPS:
        crop = crop_spec['crop']
        min_zone = crop_spec.get('min_zone', 3)
        ypsf = crop_spec['yield_per_sqft']
        cpl = crop_spec['calories_per_lb']
        dth = crop_spec['days_to_harvest']
        for zone_key, (spring_off, fall_off) in ZONE_OFFSETS.items():
            if int(zone_key) < min_zone:
                continue
            for (base_month, action, notes) in crop_spec['actions']:
                # Use fall offset for months 7-12 (second half = fall-oriented).
                offset = fall_off if base_month >= 7 else spring_off
                month = base_month + offset
                # Wrap month 1-12; if it goes negative for cold zones'
                # early actions, that action is effectively skipped (can't
                # do January sowing outdoors in zone 3).
                if month < 1:
                    # Cold-zone skip — crop can't use this action.
                    continue
                if month > 12:
                    # Overflow into next year — represent as month
                    # modulo with a note so consumers know.
                    month -= 12
                yield (crop, zone_key, month, action, notes, ypsf, cpl, dth)
