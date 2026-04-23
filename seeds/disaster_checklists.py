"""Expanded disaster preparation checklists — CE-11 (v7.63).

Replaces the 5-items-per-disaster stubs that shipped in
``web/blueprints/disaster_modules.DEFAULT_CHECKLISTS`` with 20-25 items
each. Each row is a dict with the same shape the existing code expects:

    {'item': str, 'checked': bool, 'priority': 'high'|'medium'|'low', 'notes': str}

Priorities are tuned toward high-impact / life-safety first, then
continuity / comfort. Items are sequenced in the order a user would
realistically execute them (e.g. evacuation kits before fortifying,
fortifying before organizing).

Scope is **preparation before the event**; response-phase items live in
`web/checklist_templates_data.py` and remain separate.

Sources: FEMA Ready.gov family guides; National Preparedness Goal PPD-8;
Red Cross Disaster-Specific Checklists; CDC Emergency Preparedness and
Response; NFPA 1600; USGS / NWS / NOAA hazard-specific advisories.
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────────
# Helper to keep the data below scannable.
# ──────────────────────────────────────────────────────────────────
def _c(item, priority='medium', notes=''):
    return {'item': item, 'checked': False, 'priority': priority, 'notes': notes}


EXPANDED_CHECKLISTS = {
    # ═══════════════════════════════════════════════════════════
    # EARTHQUAKE
    # ═══════════════════════════════════════════════════════════
    'earthquake': [
        _c('Secure bookcases + tall furniture to wall studs', 'high'),
        _c('Install latches on kitchen cabinets (stops flying dishes)', 'high'),
        _c('Strap water heater to studs with 2 seismic straps', 'high',
           'Gas leak + flood risk if it tips.'),
        _c('Flexible gas connector installed on all gas appliances', 'high'),
        _c('Store emergency water: 1 gal/person/day × 7 days minimum', 'high'),
        _c('Identify one "safe spot" in each room (under sturdy desk / interior wall)', 'high'),
        _c('Gas shutoff wrench attached to meter', 'high'),
        _c('Learn water main shutoff procedure + keep tool nearby', 'high'),
        _c('Store shoes + flashlight + gloves next to each bed', 'high',
           'Glass-strewn floor is the #1 post-quake injury.'),
        _c('Fire extinguisher (5 lb ABC) on each floor', 'high'),
        _c('Two independent escape routes from each room', 'high'),
        _c('Practice drop / cover / hold as full-family drill', 'medium',
           'Every 6 months. Time from "drop" to cover < 10 sec.'),
        _c('Neighborhood assembly point agreed + marked', 'medium'),
        _c('Out-of-area family contact (phone lines may be local-only after quake)', 'medium'),
        _c('Photograph rooms + valuables for insurance claims', 'medium'),
        _c('Review homeowners / renters policy for earthquake rider', 'medium'),
        _c('Stock N95 masks (drywall dust post-quake is irritating)', 'medium'),
        _c('Wind-up / battery AM/FM/NOAA radio tested', 'medium'),
        _c('Two weeks of prescription meds stockpiled', 'medium'),
        _c('Cash: $200-500 in small bills for when ATMs fail', 'medium'),
        _c('Backup of critical documents stored in separate location', 'low'),
        _c('Know nearest Red Cross shelter location', 'low'),
        _c('Identify neighbors with medical / elderly / mobility needs', 'medium',
           'First-responder resources will be overwhelmed for days.'),
    ],

    # ═══════════════════════════════════════════════════════════
    # HURRICANE
    # ═══════════════════════════════════════════════════════════
    'hurricane': [
        _c('Pre-cut + labeled plywood panels for every window', 'high',
           '5/8-inch minimum, marked by room.'),
        _c('Track + identify NOAA VHF + local emergency broadcast freq', 'high'),
        _c('Review official evacuation zones + map primary + alternate route', 'high'),
        _c('Fuel vehicles to full tank as soon as named storm approaches', 'high'),
        _c('Cash on hand ($500+) — ATMs crash at landfall', 'high'),
        _c('Fill all water storage: bathtubs (WaterBOB), 5-gal jugs, bottles', 'high',
           '1 gal/person/day × 7-10 days.'),
        _c('Harvest / secure perishable food before power loss', 'medium'),
        _c('Freeze water bottles to extend freezer cold-hold', 'medium'),
        _c('Secure loose yard objects: furniture, grills, toys, umbrellas', 'high'),
        _c('Trim weak branches near structure 30+ days before season', 'medium'),
        _c('Generator tested + fuel (30-gal rotation) + extension cord pre-staged', 'high'),
        _c('CO detectors tested (generator use kills people every year)', 'high'),
        _c('Medical refills: 30-day Rx stockpile + EpiPen / insulin / oxygen', 'high'),
        _c('Pet carriers + 7 days pet food + vaccine records', 'medium'),
        _c('Sandbag supply staged for low-ground entry points', 'medium'),
        _c('Important documents in waterproof container + photos to cloud', 'high'),
        _c('Identify safe interior room on lowest floor (if not evacuating)', 'high'),
        _c('Multiple N95 masks (mold remediation after flooding)', 'medium'),
        _c('Food: 7 days shelf-stable + manual can opener', 'high'),
        _c('Charge all devices + 2 × 20k mAh power banks', 'high'),
        _c('Know which neighbors are staying vs evacuating', 'medium'),
        _c('Unplug sensitive electronics when storm within 50 mi', 'medium'),
        _c('Post-storm kit: tarp + roofing nails + chain saw (if trained)', 'medium'),
        _c('Insurance policy info + adjuster contact in go-bag', 'medium'),
    ],

    # ═══════════════════════════════════════════════════════════
    # TORNADO
    # ═══════════════════════════════════════════════════════════
    'tornado': [
        _c('Identify shelter: storm cellar > basement > lowest interior room', 'high',
           'No windows; mattresses + helmets staged nearby.'),
        _c('Weather radio with battery backup + SAME county programming', 'high'),
        _c('Subscribe to Wireless Emergency Alerts on phone', 'high'),
        _c('Monitor local NWS issuance during watch days', 'high'),
        _c('Helmets (bike / construction) staged at shelter — head trauma #1 killer', 'high'),
        _c('Shoes + gloves + flashlight in shelter spot', 'high'),
        _c('Mattress or heavy blanket pre-positioned at shelter', 'high'),
        _c('Whistle on lanyard in shelter (to signal rescuers under debris)', 'high'),
        _c('Small first aid kit in shelter', 'medium'),
        _c('Battery lantern + spare batteries in shelter', 'medium'),
        _c('Drinking water in sealed containers at shelter (1 gal/person)', 'medium'),
        _c('Practice tornado drill 2×/year with full family', 'medium'),
        _c('Mobile home: have safer-shelter destination within 5 min drive', 'high',
           'Mobile homes cannot survive EF2+.'),
        _c('Apartment / office: know stairwell + windowless interior hallway', 'high'),
        _c('School / child-care: verify their shelter plan', 'medium'),
        _c('Vehicle plan: DO NOT take shelter under overpass (wind-tunnel effect)', 'high',
           'Ditch + low-lying area better than overpass.'),
        _c('ID + phone + cash in pocket, not in go-bag, during watches', 'medium'),
        _c('Post-tornado: know utility shutoffs (gas leak risk in debris)', 'high'),
        _c('Pet carrier in shelter (pets panic + flee damaged homes)', 'medium'),
        _c('After event: photograph damage before cleanup for insurance', 'medium'),
        _c('Assistance animals documentation in shelter kit', 'low'),
        _c('Medication 72-hr supply in shelter kit', 'high'),
    ],

    # ═══════════════════════════════════════════════════════════
    # WILDFIRE
    # ═══════════════════════════════════════════════════════════
    'wildfire': [
        _c('Clear 30-foot defensible space: no combustibles within 30 ft', 'high'),
        _c('Zone 2 (30-100 ft): trim trees + remove ladder fuels', 'high'),
        _c('Roof + gutters cleared of leaves / needles in dry season', 'high'),
        _c('Vent covers: 1/8-inch wire mesh on all attic + crawlspace vents', 'high',
           'Stops ember ingress — #1 house ignition cause.'),
        _c('Ember-resistant roof + siding (Class A roof if replacing)', 'medium'),
        _c('Outdoor garden hoses connected + reachable at all corners', 'high'),
        _c('Exterior water source (pool / cistern / hydrant) GPS-marked', 'medium'),
        _c('Evacuation routes primary + alternate + tertiary mapped', 'high',
           'Fire moves faster than you think — plan for closed roads.'),
        _c('Go-bags packed + in vehicles (every vehicle, every season)', 'high'),
        _c('N95 / P100 masks stocked for smoke (months of inhalation risk)', 'high'),
        _c('HEPA air purifier for "clean room" during smoke event', 'medium'),
        _c('Vehicle gas tank ≥ half full from July → November', 'high'),
        _c('Important documents + photos in fireproof safe + cloud backup', 'high'),
        _c('Fire extinguishers: 2A:10BC on each floor + garage', 'medium'),
        _c('Livestock + pet evacuation plan + trailer fueled', 'medium'),
        _c('Insurance policy review for wildfire coverage + defensible-space premium', 'medium'),
        _c('Neighborhood notification tree / Nextdoor alerts subscribed', 'medium'),
        _c('Ready-alert level: subscribe to CalFire / Watch Duty / state agency', 'high'),
        _c('Garden hose mister or sprinkler system for structure wetting', 'low'),
        _c('Propane + fuel tanks ≥ 30 ft from structure', 'medium'),
        _c('Firewood stack ≥ 30 ft from structure in fire season', 'high'),
        _c('Lighting: LED headlamps for night evacuation through smoke', 'medium'),
        _c('Skill: know how to open garage door manually (power out)', 'medium'),
        _c('Special-needs family: evacuate at "Ready" level — don\'t wait', 'high'),
    ],

    # ═══════════════════════════════════════════════════════════
    # FLOOD
    # ═══════════════════════════════════════════════════════════
    'flood': [
        _c('Know your flood zone (FEMA flood map)', 'high'),
        _c('Flood insurance policy active (30-day waiting period — purchase well ahead)', 'high'),
        _c('Sandbag supply staged (10-15 bags per low entry)', 'high'),
        _c('Sump pump tested monthly + battery-backup pump installed', 'high'),
        _c('Generator with battery-op transfer + 2 weeks fuel', 'high'),
        _c('Utility shutoff locations + tools accessible above flood line', 'high'),
        _c('Valuables / electronics elevated ≥ 4 ft above basement floor', 'high'),
        _c('Valuable documents in waterproof box on upper floor', 'high'),
        _c('Backup photos + records to cloud', 'medium'),
        _c('Vehicle parked on high ground when watch issued', 'high'),
        _c('NEVER drive through moving water — 6 in moves cars', 'high'),
        _c('Family muster point on high ground + out-of-area contact', 'medium'),
        _c('Water + food 7 days (municipal water often contaminated)', 'high'),
        _c('Extra water purification (bleach / CLO2 / filter)', 'high'),
        _c('Waterproof footwear at entries (contaminated water = infection)', 'medium'),
        _c('Tetanus vaccine current for all household', 'medium'),
        _c('N95 masks for mold remediation (starts within 24 hr)', 'high'),
        _c('Bleach + cleaning supplies for post-flood decon', 'medium'),
        _c('Battery-powered dehumidifier rental plan', 'low'),
        _c('Neighborhood "check-in tree" for welfare after crest', 'medium'),
        _c('Inventory of basement contents + photos for insurance', 'medium'),
        _c('Gutter + downspout clearing before rainy season', 'medium'),
        _c('Sump pump discharge points ≥ 20 ft from foundation', 'medium'),
    ],

    # ═══════════════════════════════════════════════════════════
    # PANDEMIC
    # ═══════════════════════════════════════════════════════════
    'pandemic': [
        _c('90-day supply of prescription medications', 'high'),
        _c('N95 / P100 masks: 2 weeks × 2 per day × household size', 'high'),
        _c('Nitrile gloves (box of 100) + safety glasses / goggles', 'high'),
        _c('Thermometer (non-contact preferred) + pulse oximeter', 'high'),
        _c('OTC fever / cough / GI meds stocked 30 days', 'high'),
        _c('Isolation room designated (ensuite bathroom if possible)', 'high'),
        _c('Dedicated caregiver identified (lowest-risk household member)', 'medium'),
        _c('Isolation supplies: plates / utensils / bedding for sick person', 'medium'),
        _c('Disinfection supplies (bleach, 70 % alcohol wipes, peroxide)', 'high'),
        _c('Hand sanitizer (60%+ alcohol) at every entry + workstation', 'medium'),
        _c('14 days food minimum (no restocking runs during surge)', 'high'),
        _c('14 days water minimum', 'high'),
        _c('Home work setup: laptop + VPN + wired backup internet', 'medium'),
        _c('School plan: hybrid / remote / unschooling backup', 'medium'),
        _c('Entertainment for isolation: books, puzzles, streaming downloads', 'low'),
        _c('Communication plan if internet / cell networks degrade', 'medium'),
        _c('Oxygen concentrator (if household has respiratory risk)', 'medium'),
        _c('COVID / flu / standard vaccines current', 'medium'),
        _c('Telehealth app installed + accounts set up ahead of need', 'medium'),
        _c('Funeral / DNR / will documents accessible', 'medium'),
        _c('Pet / livestock 30-day supply (emergency vet access uncertain)', 'medium'),
        _c('Special-needs household: elderly / immunocompromised / pregnancy plans', 'high'),
        _c('Delivery accounts pre-set (Instacart / Amazon / local grocer)', 'low'),
    ],

    # ═══════════════════════════════════════════════════════════
    # EMP / SOLAR EVENT
    # ═══════════════════════════════════════════════════════════
    'emp_solar': [
        _c('Faraday cage built + tested with a phone (no service inside = passes)', 'high'),
        _c('Backup radios (AM/FM/SW/scanner) in Faraday', 'high'),
        _c('Spare laptop / tablet with offline survival docs in Faraday', 'medium'),
        _c('Backup solar controller + inverter in Faraday', 'medium'),
        _c('LED flashlights + spare batteries (alkaline + lithium) in Faraday', 'medium'),
        _c('Hand-crank NOAA / AM / FM radio (outside Faraday — primary)', 'high'),
        _c('Old vehicle (pre-1980s carburetor, no electronics) if possible', 'low',
           'Extreme-prep; ignore if not already owned.'),
        _c('Cash + precious metals for post-grid barter economy', 'high'),
        _c('Paper maps of local, regional, and state area', 'high'),
        _c('Manual tools: non-electric saw / drill / grinder alternatives', 'medium'),
        _c('Manual can opener, hand-crank flour mill / coffee grinder', 'medium'),
        _c('Solid-state chargers stored in Faraday', 'medium'),
        _c('Handheld 2m/70cm / GMRS radios in Faraday + spare batteries', 'high'),
        _c('Amateur radio license (GROL / Technician / General)', 'medium'),
        _c('Critical medications: 90-day supply (no pharmacy post-event)', 'high'),
        _c('Water filtration independent of pumps (gravity / squeeze)', 'high'),
        _c('Seed bank for zone-appropriate food crops (heirloom, non-hybrid)', 'medium'),
        _c('Skill cross-train: everyone in household knows basics', 'medium'),
        _c('Community coordination: neighborhood amateur radio net schedule', 'medium'),
        _c('Printed copies of reference material (medical, agriculture, repair)', 'medium'),
        _c('Manual fuel siphon pump (electric pumps fail)', 'medium'),
        _c('Mechanical wristwatch (cell clocks fail without sync)', 'low'),
        _c('Library of physical / paper books (Kindle fails)', 'low'),
    ],

    # ═══════════════════════════════════════════════════════════
    # ECONOMIC COLLAPSE
    # ═══════════════════════════════════════════════════════════
    'economic_collapse': [
        _c('Cash reserve: 1 month expenses minimum, 3-6 months ideal', 'high'),
        _c('Small bills: $1s, $5s, $20s (large bills hard to change)', 'high'),
        _c('Precious metals: 1 oz silver rounds × 20 + some gold', 'medium',
           'Fractional silver for daily barter; gold for large-value preservation.'),
        _c('Eliminate high-interest consumer debt', 'high'),
        _c('Consolidate emergency fund in stable institution / multiple banks', 'medium'),
        _c('Barter inventory: shelf-stable food, hygiene, alcohol, coffee, ammunition', 'high'),
        _c('Skill development that provides services: repair, medical, food, security', 'medium'),
        _c('Reduce monthly fixed expenses (subscriptions, utilities)', 'medium'),
        _c('Garden + food production ramp-up', 'high'),
        _c('Community mutual-aid network identified + relationships built', 'high'),
        _c('Pantry: 90-day food minimum + 30-day water', 'high'),
        _c('Home security upgrades (property-crime spikes during downturns)', 'medium'),
        _c('Vehicle maintenance up to date (can\'t afford major repair)', 'medium'),
        _c('Home maintenance deferred-item list prioritized', 'low'),
        _c('Income diversification: ≥ 2 independent income sources', 'medium'),
        _c('Digital presence scrubbed of unnecessary personal data', 'low'),
        _c('Identity protection: credit freeze + monitoring', 'medium'),
        _c('Title / deed / ownership docs originals in safe', 'high'),
        _c('Local food-producer relationships (CSA, farmers market)', 'medium'),
        _c('Alternative / local currencies: scrip, time-banks, LETS', 'low'),
        _c('Professional network maintained (jobs found through network)', 'medium'),
        _c('Food storage that your household actually eats (rotation)', 'high'),
    ],

    # ═══════════════════════════════════════════════════════════
    # VOLCANIC ASHFALL
    # ═══════════════════════════════════════════════════════════
    'volcanic': [
        _c('N95 / P100 respirators: 2/person × 14 days', 'high',
           'Ash is like powdered glass to lungs.'),
        _c('Sealed goggles / swim goggles for every household member', 'high'),
        _c('Plastic sheeting (6 mil) + tape for sealing windows + vents', 'high'),
        _c('HEPA air purifier + spare filters', 'medium'),
        _c('Disposable dust covers / shower caps for electronics', 'medium'),
        _c('Vehicle cabin filter replacement stock', 'medium'),
        _c('Bicycle / mountaineering goggles for outdoor movement', 'medium'),
        _c('Roof inspection plan — ash + rain = 10× weight (structural collapse)', 'high'),
        _c('Roof clearing tools: wide shovel + push broom + safety harness', 'high'),
        _c('All water storage covered (ash contaminates water)', 'high'),
        _c('Rainwater collection DIVERTED / shut off during ashfall', 'medium'),
        _c('Livestock shelter with ventilation + feed covered', 'medium'),
        _c('Garden crop protection plan (sheeting / wash-off plan)', 'medium'),
        _c('Vehicle: if ashfall is in progress, DO NOT drive (engine kill)', 'high'),
        _c('Vehicle air filter spares + shop vacuum for cleaning', 'medium'),
        _c('Long-sleeve clothing + caps for all (skin protection)', 'medium'),
        _c('Ash cleanup: NEVER wet-hose (makes concrete) — shovel + sweep', 'high'),
        _c('Emergency 7-day food + water (supply trucks stop during fall)', 'high'),
        _c('Pet paw protection + eye rinsing plan', 'medium'),
        _c('Heavy-duty contractor trash bags for ash collection', 'medium'),
        _c('Medical concerns: asthma / COPD plan, nebulizers + meds', 'high'),
        _c('Know evacuation routes in advance (gas, breathing, water)', 'high'),
    ],

    # ═══════════════════════════════════════════════════════════
    # DROUGHT
    # ═══════════════════════════════════════════════════════════
    'drought': [
        _c('Rainwater collection system + storage (≥ 2500 gal if possible)', 'high'),
        _c('Low-flow fixtures / aerators on every tap + showerhead', 'medium'),
        _c('Leak audit: toilet dye test + meter read at night', 'medium'),
        _c('Greywater recycling plan (shower + sink to irrigation)', 'medium'),
        _c('Drought-resistant landscaping + xeriscape transition', 'medium'),
        _c('Garden: drip irrigation on timer for dawn / dusk only', 'medium'),
        _c('Mulch all beds heavy (4 in+) to retain soil moisture', 'medium'),
        _c('Plant drought-hardy crops: amaranth, millet, sunflower, sorghum', 'medium'),
        _c('Cover crops reduce evaporation in fallow beds', 'low'),
        _c('Water storage capacity: 30-day supply minimum for household', 'high'),
        _c('Water testing kit if using well (drawdown concerns)', 'medium'),
        _c('Know local water restrictions + penalties', 'medium'),
        _c('Pool cover to reduce evaporation', 'low'),
        _c('Car wash only at commercial sites that recycle water', 'low'),
        _c('Inventory non-drinking uses: laundry, toilet, dishes', 'medium'),
        _c('Prioritize 1 gal/person/day absolute-minimum water rationing plan', 'high'),
        _c('Community well / spring access agreements with neighbors', 'medium'),
        _c('Livestock water: reduce stock size OR secure alternate source', 'high'),
        _c('Fire risk: drought = wildfire — review wildfire checklist', 'high'),
        _c('Generator + fuel if relying on well pump (grid load rises)', 'medium'),
        _c('Composting toilet / waterless urinal plan (long droughts)', 'low'),
        _c('Legal check: water rights + riparian use laws for your parcel', 'low'),
    ],
}
