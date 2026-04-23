"""Water purification reference tables — CE-19 (v7.61).

Static reference library for the water_mgmt module. Covers:

- ``METHODS``              — 10 common purification methods, what each
                             removes / doesn't, equipment, pros/cons
- ``BOIL_TIMES``           — CDC-consistent boil times by altitude band
- ``BLEACH_DOSING``        — drops of 6 % household unscented bleach per
                             volume, by clarity (clear vs cloudy)
- ``IODINE_DOSING``        — 2 % tincture + tablet dosing
- ``CONTAMINANT_RESPONSE`` — which methods handle which contaminant class

Exposed via ``GET /api/water/purification-reference`` in the water_mgmt
blueprint.

Sources: CDC "Make Water Safe in an Emergency", EPA Water Emergency Guide,
WHO Drinking-Water Quality Guidelines (4th ed.), SODIS Manual (Eawag).
"""

# ──────────────────────────────────────────────────────────────────
# Purification methods — 10 common field / household techniques.
# Each record is a dict so new fields can be added without breaking
# consumers. Rows hand-written for clarity, not a csv.
# ──────────────────────────────────────────────────────────────────
METHODS = [
    {
        'name': 'Rolling boil',
        'removes': ['bacteria', 'viruses', 'protozoa', 'helminth cysts'],
        'does_not_remove': ['chemicals', 'heavy metals', 'salts', 'radiological'],
        'equipment': 'Any heat source + pot + lid.',
        'time_to_treat': '1-3 min at rolling boil (longer at altitude; see BOIL_TIMES).',
        'cost_usd': 0,
        'pros': 'Most reliable pathogen kill; no consumables; works on cloudy water after settling.',
        'cons': 'Requires fuel; does not treat chemistry; hot water must cool before drinking; adds no residual protection.',
        'best_for': 'Backcountry water, municipal boil-water advisory, unknown pathogens.',
    },
    {
        'name': 'Household bleach (unscented, 5-9 % NaOCl)',
        'removes': ['bacteria', 'viruses', 'most protozoa'],
        'does_not_remove': ['Cryptosporidium', 'chemicals', 'heavy metals'],
        'equipment': 'Bleach + dropper or teaspoon; clean container.',
        'time_to_treat': '30 min after adding (60 min if water < 10 °C / 50 °F or cloudy).',
        'cost_usd': 3,
        'pros': 'Shelf-stable for ~1 year unopened; cheap; treats large volumes; leaves residual.',
        'cons': 'Does not kill Cryptosporidium; potency drops ~30 %/year opened; scented / thickened bleach unsafe.',
        'best_for': 'Stockpile treatment of tap water, large-batch storage top-off.',
    },
    {
        'name': 'Tincture of iodine 2 %',
        'removes': ['bacteria', 'viruses', 'most protozoa'],
        'does_not_remove': ['Cryptosporidium', 'chemicals', 'heavy metals'],
        'equipment': '2 % tincture + dropper; clean container.',
        'time_to_treat': '30 min (60 min for cold or cloudy water).',
        'cost_usd': 5,
        'pros': 'Lightweight; long shelf life; also a wound antiseptic.',
        'cons': 'Pregnancy / thyroid / iodine-allergy contraindications; taste; does not kill Cryptosporidium.',
        'best_for': 'Personal / small-group field use.',
    },
    {
        'name': 'Iodine purification tablets',
        'removes': ['bacteria', 'viruses', 'most protozoa'],
        'does_not_remove': ['Cryptosporidium', 'chemicals', 'heavy metals'],
        'equipment': 'Tablets only.',
        'time_to_treat': 'Per label — typically 35 min (double for cold / cloudy).',
        'cost_usd': 10,
        'pros': 'Compact; easy to measure; low skill required.',
        'cons': 'Same medical contraindications as tincture; shorter shelf life once bottle opened (~6 mo).',
        'best_for': 'BOB / BOV / 72-hr kit.',
    },
    {
        'name': 'Chlorine dioxide tablets (Aquamira / Katadyn Micropur MP1)',
        'removes': ['bacteria', 'viruses', 'protozoa', 'Cryptosporidium'],
        'does_not_remove': ['chemicals', 'heavy metals'],
        'equipment': 'Tablets; clean container.',
        'time_to_treat': '15 min bacteria/virus, 30 min Giardia, 4 hr Cryptosporidium.',
        'cost_usd': 15,
        'pros': 'Kills Crypto (unlike bleach + iodine); no taste; safe in pregnancy.',
        'cons': 'Slower Crypto kill time; tablets expire (~4 yr sealed); pricier than bleach.',
        'best_for': 'Any water with animal / beaver / livestock exposure (Crypto risk).',
    },
    {
        'name': 'Ceramic filter (0.2-0.5 µm, e.g. Berkey, Doulton)',
        'removes': ['bacteria', 'protozoa', 'sediment', 'some heavy metals (w/ carbon)'],
        'does_not_remove': ['viruses (unless <0.01 µm element)', 'dissolved salts'],
        'equipment': 'Gravity or pumped ceramic housing.',
        'time_to_treat': '1-2 L/min gravity flow typical.',
        'cost_usd': 250,
        'pros': 'Reusable (brushed + backflushed); long life (thousands of gal); no consumables after purchase.',
        'cons': 'Does NOT kill viruses by default — must combine with chem or UV in virus-risk areas (developing countries, floods).',
        'best_for': 'Household primary treatment; long-term sustainment.',
    },
    {
        'name': 'Hollow-fiber filter (0.1-0.2 µm, e.g. Sawyer, LifeStraw)',
        'removes': ['bacteria', 'protozoa', 'Cryptosporidium', 'sediment'],
        'does_not_remove': ['viruses', 'chemicals', 'heavy metals'],
        'equipment': 'Inline filter cartridge.',
        'time_to_treat': 'On-demand flow.',
        'cost_usd': 30,
        'pros': 'Cheap; light; replaceable; Sawyer Mini rated 100k gal; handles cold.',
        'cons': 'Freeze damage voids rating (expand/contract cracks fibers); no virus protection; flow drops as fouled.',
        'best_for': 'BOB, personal hike/camp.',
    },
    {
        'name': 'Reverse osmosis (RO) membrane',
        'removes': ['bacteria', 'viruses', 'protozoa', 'dissolved salts', 'most chemicals', 'heavy metals'],
        'does_not_remove': ['pesticides that bypass RO (few — rare)', 'gases (add CO2 via VOC stripping)'],
        'equipment': 'RO unit + pressure source (household water pressure or hand pump).',
        'time_to_treat': 'Slow: 50-100 gal/day countertop; seconds per liter hand pump.',
        'cost_usd': 300,
        'pros': 'Only field-practical method that handles salt (ocean/brackish); best contaminant coverage.',
        'cons': 'Wastes ~3 gal per gal produced (countertop); membrane fouls without pre-filter; slow.',
        'best_for': 'Ocean / coastal; industrial contamination; grid-down household.',
    },
    {
        'name': 'UV (SteriPen, battery UV-C)',
        'removes': ['bacteria', 'viruses', 'protozoa'],
        'does_not_remove': ['sediment (must pre-filter)', 'chemicals', 'heavy metals'],
        'equipment': 'UV pen + batteries.',
        'time_to_treat': '90 sec per liter typical.',
        'cost_usd': 80,
        'pros': 'Kills everything biological including virus; fast; tasteless.',
        'cons': 'Needs clear water (cloudy water blocks UV); battery-dependent; lamp life ~8000 treatments; fragile.',
        'best_for': 'Solo traveler with access to charged batteries or USB.',
    },
    {
        'name': 'SODIS (solar disinfection)',
        'removes': ['bacteria', 'viruses', 'most protozoa (inconsistent for Crypto)'],
        'does_not_remove': ['chemicals', 'heavy metals', 'sediment'],
        'equipment': 'Clear PET bottles + sun.',
        'time_to_treat': '6 hr full sun / 2 full days overcast.',
        'cost_usd': 0,
        'pros': 'Free; no consumables; proven public-health technique.',
        'cons': 'Cloudy days fail; cloudy water fails (must pre-filter); limited volume; PET plasticizer concern long-term.',
        'best_for': 'Sustained grid-down with clear water + sun; developing-country default.',
    },
    {
        'name': 'Distillation',
        'removes': ['bacteria', 'viruses', 'protozoa', 'salts', 'heavy metals', 'most chemicals'],
        'does_not_remove': ['volatile chemicals with bp < 100 °C (benzene, VOCs — capture separately)'],
        'equipment': 'Distiller or improvised pot-lid condensation rig + heat source.',
        'time_to_treat': '1-2 L / hr countertop; slow improvised.',
        'cost_usd': 100,
        'pros': 'Only method other than RO that handles salt + heavy metals; simple to improvise.',
        'cons': 'Fuel-intensive; captures VOCs too (pre-filter carbon if industrial contamination); low throughput.',
        'best_for': 'Radiological / heavy-metal / saline source.',
    },
]


# ──────────────────────────────────────────────────────────────────
# Boil times by altitude (CDC).
# ──────────────────────────────────────────────────────────────────
BOIL_TIMES = [
    # (altitude_ft, altitude_m, minutes_at_rolling_boil, notes)
    (0,     0,    1, 'At or near sea level — 1 min rolling boil is sufficient per CDC.'),
    (3000,  914,  1, 'Below 6500 ft / 2000 m — 1 min is enough.'),
    (6500,  1981, 1, '6500 ft / 2000 m — cutoff; above this, extend to 3 min.'),
    (7000,  2134, 3, '>6500 ft — boiling point drops below 93 °C; extend to 3 min.'),
    (10000, 3048, 3, 'High alpine — 3 min minimum.'),
    (14000, 4267, 3, 'Extreme altitude — 3 min (pressure cooker preferred if available).'),
]


# ──────────────────────────────────────────────────────────────────
# Bleach dosing — 6 % sodium hypochlorite, unscented household.
# Drops per volume; double for cloudy water; wait 30 min (60 if cold).
# ──────────────────────────────────────────────────────────────────
BLEACH_DOSING = [
    # (volume_label, volume_liters, clear_water_drops, cloudy_water_drops, notes)
    ('1 qt / 1 L',    1,    2, 4,  'Smallest practical unit; use eyedropper.'),
    ('1 gal / 4 L',   4,    8, 16, 'Most common residential container.'),
    ('5 gal',         19,  40, 80, 'Jerry can / water jug. ~1/2 tsp clear / 1 tsp cloudy.'),
    ('55 gal drum',   208, 440, 880, 'Barrel storage. ~3 Tbsp clear / 6 Tbsp cloudy.'),
    ('275 gal IBC',  1041, 2200, 4400, 'IBC tote — use measuring cup.'),
]


# ──────────────────────────────────────────────────────────────────
# Iodine dosing — 2 % tincture. Same volume units as BLEACH_DOSING.
# ──────────────────────────────────────────────────────────────────
IODINE_DOSING = [
    # (volume_label, volume_liters, clear_drops, cloudy_drops, notes)
    ('1 qt / 1 L',  1,  5, 10, 'Wait 30 min clear, 60 min cloudy.'),
    ('1 gal / 4 L', 4, 20, 40, 'Double time if water < 10 °C / 50 °F.'),
    ('5 gal',      19, 95, 190,
     'Iodine dosing becomes impractical at barrel scale — use bleach or chlorine dioxide.'),
]

IODINE_CONTRAINDICATIONS = [
    'Pregnancy (iodine dosing may disrupt fetal thyroid function)',
    'Hyperthyroidism / thyroid disorder',
    'Iodine allergy / shellfish allergy (cross-reactivity possible)',
    'Infants under 6 months',
    'Persons on lithium therapy',
    'Long-term use > 6 weeks (consult physician)',
]


# ──────────────────────────────────────────────────────────────────
# Contaminant-class response matrix.
# Maps each contaminant category to which method(s) from METHODS above
# actually handle it. Used by the UI to recommend a treatment once the
# user identifies the threat (e.g., "flood water → ...").
# ──────────────────────────────────────────────────────────────────
CONTAMINANT_RESPONSE = [
    {
        'class': 'Bacteria (E. coli, Salmonella, Shigella, Cholera)',
        'typical_source': 'Fecal contamination — human or animal. Flood, stagnant pond, downstream of pasture.',
        'symptoms': 'GI upset 24-72 hr after ingestion; watery diarrhea; fever; abdominal cramps.',
        'effective_methods': ['Rolling boil', 'Bleach', 'Iodine', 'Chlorine dioxide', 'Ceramic filter', 'Hollow-fiber filter', 'UV', 'SODIS', 'Distillation'],
        'notes': 'Nearly every method works. Pick the fastest / most available.',
    },
    {
        'class': 'Viruses (Norovirus, Hepatitis A, Rotavirus, Polio)',
        'typical_source': 'Fecal contamination; sewage overflow; developing-country sources.',
        'symptoms': 'Vomiting + diarrhea; hepatitis A has jaundice onset weeks later.',
        'effective_methods': ['Rolling boil', 'Bleach', 'Iodine', 'Chlorine dioxide', 'UV', 'SODIS', 'Distillation', 'RO'],
        'notes': 'Most hollow-fiber + ceramic filters do NOT remove viruses — pair with chemical disinfection if virus risk is elevated (floods, sewage).',
    },
    {
        'class': 'Protozoa — Giardia, Cyclospora, Entamoeba',
        'typical_source': 'Wildlife + livestock fecal contamination in surface water.',
        'symptoms': 'Giardia: explosive diarrhea, bloating, sulfuric belching 1-3 weeks after exposure.',
        'effective_methods': ['Rolling boil', 'Ceramic filter', 'Hollow-fiber filter', 'Chlorine dioxide', 'UV', 'Distillation', 'RO'],
        'notes': 'Regular bleach + iodine kill Giardia (≥ 30 min exposure) but are slow — use filter or CLO2 if available.',
    },
    {
        'class': 'Cryptosporidium (Crypto)',
        'typical_source': 'Any wild / livestock contact — beaver meadows, pasture runoff.',
        'symptoms': 'Profuse watery diarrhea 2-10 d post-exposure; dangerous in immunocompromised.',
        'effective_methods': ['Rolling boil', 'Ceramic filter', 'Hollow-fiber filter (≤ 0.2 µm)', 'Chlorine dioxide (4 hr)', 'UV', 'Distillation', 'RO'],
        'notes': 'BLEACH AND IODINE DO NOT KILL CRYPTO. Use a filter, CLO2 (4 hr!), UV, or boil.',
    },
    {
        'class': 'Heavy metals (lead, arsenic, mercury, chromium)',
        'typical_source': 'Mining / industrial runoff; old pipes; well contamination.',
        'symptoms': 'Chronic exposure → neurological, kidney, developmental damage.',
        'effective_methods': ['Distillation', 'RO', 'Activated-carbon + ceramic combo (partial)'],
        'notes': 'Boiling + disinfection do NOTHING. Distillation or RO are the only reliable field options.',
    },
    {
        'class': 'Dissolved salts (saline / brackish)',
        'typical_source': 'Ocean, coastal aquifers with saltwater intrusion.',
        'symptoms': 'Dehydration; long-term kidney strain.',
        'effective_methods': ['Distillation', 'RO'],
        'notes': 'No filter, chemical, or boil removes salt. Salt stays behind in distillation residue.',
    },
    {
        'class': 'Chemical contamination (VOCs, pesticides, solvents)',
        'typical_source': 'Industrial spill, agricultural runoff, fuel contamination.',
        'symptoms': 'Varies by chemical — headache, GI, neurologic, carcinogenic long-term.',
        'effective_methods': ['Activated carbon (for most)', 'RO (partial)', 'Distillation + carbon (VOCs)'],
        'notes': 'Volatile organics co-distill — need carbon filter BEFORE or AFTER distillation. This is one of the hardest contamination classes to field-treat.',
    },
    {
        'class': 'Radiological (I-131, Cs-137, Sr-90, U-series)',
        'typical_source': 'Nuclear plant release, fallout-contaminated surface water.',
        'symptoms': 'Acute radiation sickness from ingestion; long-term cancer risk.',
        'effective_methods': ['RO', 'Distillation', 'Cation-exchange resin (partial)'],
        'notes': 'Boiling + filters + disinfection do NOTHING. I-131 decays (8-day half-life) — store contaminated water 60 days and it drops by >99 %. Cs-137 (30 yr) and Sr-90 (29 yr) do not decay practically — use RO or distillation.',
    },
    {
        'class': 'Turbidity (silt, clay, organic matter)',
        'typical_source': 'Flood water, rivers in flood stage, post-storm wells.',
        'symptoms': 'Not directly pathogenic but blocks other treatment (UV, SODIS, chem).',
        'effective_methods': ['Sedimentation (settle 24 hr)', 'Cloth pre-filter', 'Alum flocculation (1 tsp alum per 5 gal, stir, settle 30 min)', 'Slow-sand biosand filter'],
        'notes': 'Always pre-filter cloudy water before any other treatment — cloudy water doubles required dose / time for chemical + UV methods.',
    },
]
