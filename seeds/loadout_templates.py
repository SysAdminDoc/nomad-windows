"""Loadout bag templates — CE-10 (v7.61).

Curated bag templates for common preparedness scenarios. Each template
bundles a bag-level config (name, type, season, target weight) with an
item list (name, category, quantity, weight in oz, notes).

These are *templates* — not pre-created user records. The loadout
blueprint exposes them via ``GET /api/loadout/templates`` so the UI can
offer "create bag from template" which posts to the existing bag /
item create endpoints with the template's data.

Categories match the ``loadout_items.category`` field in db.py:
    water, food, shelter, fire, medical, comms, navigation, tools,
    clothing, hygiene, documents, other

Weight estimates come from typical manufacturer specs + field
experience. Actual pack weight will vary ±15 % based on brand choices.

Sources: Dave Canterbury's 10 Cs / 5 Cs, ITS Tactical EDC surveys,
Mountaineers' "Freedom of the Hills" 10 essentials, REI cold-weather
packing checklists, TC 4-02.1 (US Army medical).
"""

LOADOUT_TEMPLATES = [
    # ───────────────────────── 72-hr — Adult ─────────────────────────
    {
        'name': '72-Hour Bag — Adult',
        'bag_type': '72hour',
        'season': 'all',
        'target_weight_lb': 25,
        'description':
            'Classic 72-hour self-sufficiency bag for one adult. Assumes '
            'shelter-in-place OR evacuation up to 3 days. Season-neutral '
            '— add winter layer kit or desert sun kit as needed.',
        'use_case':
            'Disaster displacement, evacuation to shelter, or grid-down '
            'first 72 hr while situation stabilizes.',
        'items': [
            # water
            ('Water bladder (3 L)',          'water', 1, 120, 'Empty weight 4 oz; filled 108 oz.'),
            ('Collapsible bottle (1 L)',     'water', 1, 2,   ''),
            ('Sawyer Mini water filter',     'water', 1, 2,   'Rated 100,000 gal. Keep from freezing.'),
            ('Water purification tablets (20)', 'water', 1, 1, 'CLO2 preferred over iodine for Crypto.'),
            # food — 3 days × ~2000 cal/day
            ('Datrex 2400 kcal ration bar',  'food',  2, 17,  '7-yr shelf life. Split 1/day.'),
            ('Trail mix / GORP (1 lb)',      'food',  1, 16,  'Protein + fat + quick sugar.'),
            ('Jerky (beef/turkey)',          'food',  1, 8,   'Long shelf life, protein-dense.'),
            ('Mountain House freeze-dried entree', 'food', 3, 15, 'Needs boiling water; 30-yr shelf.'),
            ('Instant coffee / tea bags',    'food',  1, 2,   'Morale.'),
            # shelter
            ('Tarp (8x10 ft ripstop)',       'shelter', 1, 24, 'Multi-config shelter material.'),
            ('Emergency bivy (SOL Escape)',  'shelter', 1, 8,  'Breathable — prevents condensation unlike mylar.'),
            ('Mylar space blanket',          'shelter', 2, 2,  'Redundant warmth + signaling.'),
            ('Paracord (50 ft, 550 lb)',     'shelter', 1, 8,  'Rigging, improvised repairs.'),
            # fire
            ('Bic lighter',                  'fire',    2, 1,  'Primary. Wrap stem in gorilla tape.'),
            ('Storm-proof matches',          'fire',    1, 2,  'Backup.'),
            ('Ferro rod + striker',          'fire',    1, 2,  'Last-resort ignition.'),
            ('Tinder quik / Vaseline cotton', 'fire',   10, 2, '1 piece = 2-3 min of hot flame.'),
            # medical
            ('IFAK compact (tourniquet, gauze, tape, shears)', 'medical', 1, 12, ''),
            ('Personal medication kit',      'medical', 1, 4,   '2-week Rx supply minimum.'),
            ('Ibuprofen 200 mg (20 ct)',     'medical', 1, 1,   ''),
            ('Benadryl (diphenhydramine 25 mg, 12 ct)', 'medical', 1, 1, ''),
            # comms
            ('Baofeng UV-5R + extra battery', 'comms',  1, 10,  'GMRS if licensed; monitor-only otherwise.'),
            ('Hand-crank AM/FM/NOAA radio',  'comms',   1, 12,  'No battery required.'),
            ('Whistle (pealess)',            'comms',   1, 1,   'Fox 40 style. 3 short = distress.'),
            ('Signal mirror',                'comms',   1, 2,   '5-mile visibility in clear conditions.'),
            # navigation
            ('Compass (baseplate w/ declination)', 'navigation', 1, 2, ''),
            ('Local topo map (laminated)',   'navigation', 1, 3, 'Waterproofed or Tyvek.'),
            ('Pen + Rite-in-Rain notebook',  'navigation', 1, 3, ''),
            # tools
            ('Headlamp (300 lm) + spare batteries', 'tools', 1, 4, ''),
            ('Multi-tool (Leatherman Wave equivalent)', 'tools', 1, 9, ''),
            ('Fixed-blade knife (4 in)',     'tools',   1, 8,   'Full tang. Mora Garberg / Bravo 1.'),
            ('Duct tape (10 yd flat pack)',  'tools',   1, 3,   ''),
            # clothing
            ('Wool / synthetic socks (pair)', 'clothing', 2, 4, 'Never cotton.'),
            ('Base layer top + bottom',      'clothing', 1, 10, 'Merino or polypro.'),
            ('Rain shell',                   'clothing', 1, 12, 'Packable, hood.'),
            ('Wool beanie',                  'clothing', 1, 3,  ''),
            ('Work gloves',                  'clothing', 1, 4,  ''),
            # hygiene
            ('Hygiene kit (TP, toothbrush, floss, soap sheets)', 'hygiene', 1, 4, ''),
            ('Hand sanitizer (2 oz)',        'hygiene', 1, 2,  ''),
            # documents
            ('Cash ($200 small bills)',      'documents', 1, 1, ''),
            ('Copies of ID + insurance + medical',  'documents', 1, 2, 'In waterproof ziplock.'),
            ('Emergency contact card',       'documents', 1, 1, 'Laminated.'),
        ],
    },

    # ───────────────────────── 72-hr — Child ─────────────────────────
    {
        'name': '72-Hour Bag — Child (age 5-10)',
        'bag_type': '72hour',
        'season': 'all',
        'target_weight_lb': 10,
        'description':
            'Scaled-down 72-hour bag sized for a school-age child to carry '
            'themselves. Parent carries the heavy / sharp / medical items.',
        'use_case':
            'School-day evacuation, family-bugout partner bag, or '
            'grab-and-go for a caregiver.',
        'items': [
            ('Water bottle (0.75 L)',       'water', 1, 24, ''),
            ('Water filter straw (LifeStraw)', 'water', 1, 2, 'Kid-safe — no small parts.'),
            ('Kid calorie bars',            'food',  6, 12, '400 cal each.'),
            ('Snack pack (trail mix, crackers)', 'food', 3, 6, ''),
            ('Emergency bivy (SOL)',        'shelter', 1, 4, ''),
            ('Mylar blanket',               'shelter', 1, 2, ''),
            ('Small flashlight + spare AAAs', 'tools', 1, 3, ''),
            ('Whistle on lanyard',          'comms', 1, 1, 'Worn around neck. 3 short = distress.'),
            ('Pocket notebook + pencil',    'documents', 1, 2, 'For drawing/notes to caregiver.'),
            ('Comfort item (small plush / photo)', 'other', 1, 4, 'Critical for stress management.'),
            ('Pair of socks + underwear',   'clothing', 2, 3, ''),
            ('Rain jacket (kid size)',      'clothing', 1, 8, ''),
            ('Winter hat + gloves',         'clothing', 1, 3, ''),
            ('Bandaids + kid Tylenol chewables', 'medical', 1, 2, ''),
            ('ID card (name, parents, allergies, meds, phone)', 'documents', 1, 1,
             'Laminated. Write info large + clear. Include "If lost, call..." script.'),
            ('Allergy meds (if prescribed)', 'medical', 1, 1, 'EpiPen if applicable.'),
            ('Small cash ($20 in smalls)',  'documents', 1, 1, ''),
            ('Hand sanitizer',              'hygiene', 1, 1, ''),
            ('Toothbrush + toothpaste',     'hygiene', 1, 2, ''),
        ],
    },

    # ───────────────────────── EDC ───────────────────────────────────
    {
        'name': 'Everyday Carry (EDC) Pocket Kit',
        'bag_type': 'edc',
        'season': 'all',
        'target_weight_lb': 1,
        'description':
            'Minimum tools that fit on-person every day. Weight measured '
            'in ounces, not pounds. Complements — does not replace — a '
            'get-home bag in the car or office.',
        'use_case':
            'Daily carry for first-5-minute problem solving before '
            'reaching deeper kit.',
        'items': [
            ('Pocket knife (folder, locking)', 'tools', 1, 3, 'Kizer Deminishivi, Benchmade Bugout, Spyderco.'),
            ('Mini flashlight (90+ lumens)', 'tools', 1, 2, 'Olight, Fenix, or Streamlight.'),
            ('Bic lighter',                  'fire',  1, 1,  ''),
            ('Paracord bracelet (10 ft 550 cord)', 'shelter', 1, 2, ''),
            ('Multi-tool (keychain size)',   'tools', 1, 2,  'Leatherman Micra or Gerber Dime.'),
            ('Space pen or Rite-in-Rain mini', 'tools', 1, 1, ''),
            ('Duct tape flat pack (2 ft)',   'tools', 1, 1,  'Wrap around lighter.'),
            ('Tourniquet (packable, e.g. SWAT-T or TMT)', 'medical', 1, 4, 'Optional for pocket; mandatory if belt-carry.'),
            ('Cash ($40 + coin)',            'documents', 1, 1, ''),
            ('Emergency whistle (keychain)', 'comms', 1, 1,  ''),
            ('Hand sanitizer mini',          'hygiene', 1, 1, ''),
            ('Band-aids (5-10)',             'medical', 1, 1, ''),
            ('Ibuprofen travel pack',        'medical', 1, 1, '6-count sleeve.'),
            ('USB-C charging cable (mini)',  'tools', 1, 1,  'For phone emergency power-share.'),
        ],
    },

    # ───────────────────────── Get-Home Bag — Short ──────────────────
    {
        'name': 'Get-Home Bag — Short (< 10 mi)',
        'bag_type': 'get-home',
        'season': 'all',
        'target_weight_lb': 12,
        'description':
            'For the commuter who works within walking distance. Priority: '
            'move fast, stay anonymous, not survive 72 hr. Keep in desk drawer '
            'or vehicle.',
        'use_case':
            'Grid-down midday. Walk home in normal weather on paved routes.',
        'items': [
            ('Water bottle (0.75 L)',        'water', 1, 24, ''),
            ('Energy bar (high-cal)',        'food',  3, 6,  '300+ cal each.'),
            ('Headlamp (small)',             'tools', 1, 3,  ''),
            ('Pocket knife',                 'tools', 1, 3,  ''),
            ('Small first aid (bandages, meds)', 'medical', 1, 4, ''),
            ('Dust/smoke mask (N95)',        'clothing', 2, 1, ''),
            ('Gloves (leather or mechanix)', 'clothing', 1, 4, 'Grip + protection from debris.'),
            ('Rain shell',                   'clothing', 1, 8, 'Packable.'),
            ('Comfortable walking shoes',    'clothing', 1, 24, 'Replacement if in heels/dress shoes.'),
            ('Socks (wool/synthetic)',       'clothing', 1, 3, ''),
            ('Phone charger + 10k mAh battery pack', 'tools', 1, 8, ''),
            ('Cash ($80 small bills)',       'documents', 1, 1, ''),
            ('Local paper map',              'navigation', 1, 2, 'Pre-marked with home + alternates.'),
            ('Compass (button type)',        'navigation', 1, 1, ''),
        ],
    },

    # ───────────────────────── Get-Home Bag — Long ───────────────────
    {
        'name': 'Get-Home Bag — Long (10-50 mi, overnight)',
        'bag_type': 'get-home',
        'season': 'all',
        'target_weight_lb': 22,
        'description':
            'For the commuter who works outside walking-in-a-day range. '
            'Plans for an overnight en route. Adds shelter, expanded food '
            'and water, and redundant lighting.',
        'use_case':
            'Grid-down or road blockage. Walk/hitchhike/bike 10-50 mi home '
            'with possible overnight.',
        'items': [
            ('Water bladder (2 L)',          'water', 1, 72, ''),
            ('Sawyer Mini filter',           'water', 1, 2, ''),
            ('CLO2 tablets (20)',            'water', 1, 1, ''),
            ('Energy bars (600+ cal each)',  'food',  4, 10, 'Datrex or similar.'),
            ('Freeze-dried meal',            'food',  1, 5,  'Stove needed — include cold-soak option.'),
            ('Jerky',                        'food',  1, 4,  ''),
            ('Emergency bivy',               'shelter', 1, 8, ''),
            ('Mylar blanket',                'shelter', 1, 2, ''),
            ('Tarp (6×8)',                   'shelter', 1, 16, 'Lean-to or A-frame.'),
            ('Paracord (50 ft)',             'shelter', 1, 8, ''),
            ('Headlamp + spare batteries',   'tools', 1, 4, ''),
            ('Backup mini flashlight',       'tools', 1, 2, 'Redundancy.'),
            ('Multi-tool',                   'tools', 1, 9, ''),
            ('Fixed-blade knife',            'tools', 1, 8, ''),
            ('Bic lighter',                  'fire',  2, 1, ''),
            ('Ferro rod',                    'fire',  1, 2, ''),
            ('Tinder',                       'fire',  1, 2, ''),
            ('First aid compact',            'medical', 1, 8, 'Tourniquet, gauze, tape, ibuprofen.'),
            ('Rain shell + pants',           'clothing', 1, 18, ''),
            ('Walking shoes / boots',        'clothing', 1, 28, ''),
            ('Spare socks (wool)',           'clothing', 2, 4, ''),
            ('Baseball cap or beanie',       'clothing', 1, 3, ''),
            ('Cash ($150 smalls)',           'documents', 1, 1, ''),
            ('Paper map of route',           'navigation', 1, 2, ''),
            ('Compass',                      'navigation', 1, 2, ''),
        ],
    },

    # ───────────────────────── I.N.C.H. ──────────────────────────────
    {
        'name': 'I.N.C.H. Bag (I\'m Never Coming Home)',
        'bag_type': 'inch',
        'season': 'all',
        'target_weight_lb': 45,
        'description':
            'Long-term survival loadout for permanent relocation scenarios. '
            'Heavy — expect to carry a shorter daily distance but sustain '
            'for weeks to months. Only makes sense for experienced hikers '
            'with proven aerobic conditioning.',
        'use_case':
            'Permanent evacuation with no return plan. Extended living '
            'in the field until other shelter or community is reached.',
        'items': [
            ('Water filter (gravity system, Sawyer Squeeze + 4 L bladder)', 'water', 1, 12, ''),
            ('Stainless steel nesting cookset', 'water', 1, 16, 'Boil + cook + eat.'),
            ('2-month seed supply (heirloom veg mix, vacuum-sealed)', 'food', 1, 12, 'Lettuce, bean, squash, tomato, carrot, etc.'),
            ('Fishing kit (hooks, line, lures)', 'food', 1, 8, 'Take + Fish kit.'),
            ('Snare wire (50 ft, 24 gauge)',  'food',  1, 4, ''),
            ('30 days freeze-dried meal core', 'food', 30, 4, '30 × 4 oz = 7.5 lb for 30 days.'),
            ('Tarp (10×12 silnylon)',        'shelter', 1, 18, ''),
            ('0°F sleeping bag',              'shelter', 1, 48, 'Quilts save weight.'),
            ('Sleeping pad (closed-cell foam)', 'shelter', 1, 16, ''),
            ('Hennessy hammock (backup)',    'shelter', 1, 32, 'Use as shelter above wet ground.'),
            ('Fire: ferro + Bic × 3 + storm matches', 'fire', 1, 4, ''),
            ('Emberlit folding stove',        'fire', 1, 12, 'Wood-burning — no fuel dependence.'),
            ('Comprehensive IFAK',            'medical', 1, 24, ''),
            ('Antibiotics (fish mox / cipro, 30-day)', 'medical', 1, 2, 'Know your contraindications.'),
            ('Dental emergency kit',         'medical', 1, 2, 'Temp filling material + floss.'),
            ('Amateur radio (Baofeng UV-5R + Nagoya antenna)', 'comms', 1, 12, ''),
            ('AM/FM/NOAA crank radio',       'comms', 1, 10, ''),
            ('Fixed-blade knife (heavy duty 6 in)', 'tools', 1, 14, 'Bravo 1, Mora Pathfinder.'),
            ('Folding saw',                  'tools',  1, 8, ''),
            ('Axe (1.5 lb hatchet)',         'tools',  1, 24, ''),
            ('Machete / kukri',              'tools',  1, 24, 'Region-dependent.'),
            ('Multi-tool (heavy-duty)',      'tools',  1, 10, ''),
            ('Sewing + repair kit (needles, thread, patches)', 'tools', 1, 4, ''),
            ('Rain shell + insulated layer', 'clothing', 1, 40, ''),
            ('Spare full change of clothes', 'clothing', 1, 32, ''),
            ('Gloves (leather + insulated)', 'clothing', 2, 8, ''),
            ('Hygiene pack (soap, razor, towel, floss, toothbrush)', 'hygiene', 1, 8, ''),
            ('Paracord (100 ft)',            'shelter', 1, 16, ''),
            ('Cash ($500) + precious metal (1 oz silver rounds × 5)', 'documents', 1, 8, 'Barter + anonymity.'),
            ('Waterproof document case (IDs, titles, copies)', 'documents', 1, 4, ''),
            ('Compass + USGS topos for target region', 'navigation', 1, 8, ''),
        ],
    },

    # ───────────────────────── Vehicle — Temperate ───────────────────
    {
        'name': 'Vehicle Emergency Kit — Temperate',
        'bag_type': 'vehicle',
        'season': 'all',
        'target_weight_lb': 20,
        'description':
            'Stays in trunk year-round for temperate climates. Mechanical '
            'roadside problems + minor emergency shelter.',
        'use_case':
            'Stuck on shoulder, dead battery, minor crash, running out of '
            'fuel in bad area, waiting for tow.',
        'items': [
            ('Jumper cables (12 ft, 4-gauge)', 'tools', 1, 32, ''),
            ('Tire inflator (12V compressor)', 'tools', 1, 48, ''),
            ('Tire repair plug kit',         'tools',  1, 8, ''),
            ('Tow strap (20 ft, 10k lb)',    'tools',  1, 32, ''),
            ('Basic tool roll (socket, wrench, screwdrivers, pliers)', 'tools', 1, 48, ''),
            ('Duct tape + electrical tape',  'tools',  1, 8, ''),
            ('Flashlight + spare D batteries', 'tools', 1, 24, 'Big for signaling.'),
            ('Road flares × 3 OR LED emergency beacon', 'comms', 1, 8, ''),
            ('Reflective triangle (2)',      'comms',  2, 16, ''),
            ('Safety vest',                  'clothing', 1, 4, ''),
            ('First aid kit (road trauma)',  'medical', 1, 20, ''),
            ('Water (3 × 1 qt sealed)',      'water',  3, 32, 'Bottled shelf-stable.'),
            ('Emergency food bars',          'food',   2, 8, ''),
            ('Mylar blankets × 2',           'shelter', 2, 2, ''),
            ('Hand-crank AM/FM/NOAA radio',  'comms',  1, 12, ''),
            ('Fire extinguisher (5 lb ABC)', 'tools',  1, 80, ''),
            ('Seatbelt cutter + window punch', 'tools', 1, 2, 'Keep in driver reach.'),
            ('Gas siphon hand pump',         'tools',  1, 4, ''),
            ('Toilet paper + ziplock (waste)', 'hygiene', 1, 2, ''),
            ('Cash ($60 smalls)',            'documents', 1, 1, ''),
            ('Insurance card + registration copy', 'documents', 1, 1, ''),
        ],
    },

    # ───────────────────────── Vehicle — Winter ──────────────────────
    {
        'name': 'Vehicle Emergency Kit — Winter',
        'bag_type': 'vehicle',
        'season': 'winter',
        'target_weight_lb': 30,
        'description':
            'Temperate kit plus winter-survival layer. Adds sleeping bag '
            'rated to coldest local night, cat-hole stove, hand warmers, '
            'shovel, and snow traction aids.',
        'use_case':
            'Winter road closure, stuck in drift, need to survive 24-48 hr '
            'in vehicle until plow reaches you.',
        'items': [
            ('Sleeping bag (0°F rated)',     'shelter', 1, 64, 'Sized to your coldest local night.'),
            ('Wool blanket',                 'shelter', 1, 48, 'Emergency layer or trade.'),
            ('Hand warmers (8 hr)',          'clothing', 10, 2, 'Chemical pack type.'),
            ('Toe warmers',                  'clothing', 6, 1, ''),
            ('Knit cap + insulated gloves',  'clothing', 1, 8, ''),
            ('Wool socks (pair)',            'clothing', 2, 4, ''),
            ('Small folding shovel',         'tools',   1, 32, 'Dig out + cat-hole.'),
            ('Traction mats (2) or tire chains', 'tools', 2, 80, ''),
            ('Ice scraper + snow brush',     'tools',   1, 8,  ''),
            ('Windshield de-icer spray',     'tools',   1, 16, ''),
            ('Kitty litter or sand (10 lb)', 'tools',   1, 160, 'Traction aid; weight over drive wheels.'),
            ('Candle in can + lighter',      'fire',    1, 8,   'Emergency vehicle heat. 1 candle keeps vehicle above freezing for hours.'),
            ('Water (3 qt shelf-stable)',    'water',   3, 32,  ''),
            ('High-calorie food bars',       'food',    6, 6,   ''),
            ('Thermos (fill before trip)',   'water',   1, 24,  ''),
            ('Cell phone car charger',       'tools',   1, 2,   ''),
            ('USB power bank (20k mAh)',     'tools',   1, 16,  ''),
            ('Hand-crank NOAA radio',        'comms',   1, 12,  ''),
            ('Whistle',                      'comms',   1, 1,   ''),
            ('First aid kit',                'medical', 1, 20,  ''),
            ('Emergency bivy / space blanket', 'shelter', 2, 3, ''),
            # include the temperate baseline
            ('Jumper cables',                'tools',   1, 32, ''),
            ('Tow strap',                    'tools',   1, 32, ''),
            ('Tire inflator',                'tools',   1, 48, ''),
            ('Small tool roll',              'tools',   1, 32, ''),
            ('Reflective triangles (2)',     'comms',   2, 16, ''),
        ],
    },

    # ───────────────────────── Vehicle — Desert / Hot ────────────────
    {
        'name': 'Vehicle Emergency Kit — Desert / Hot Climate',
        'bag_type': 'vehicle',
        'season': 'summer',
        'target_weight_lb': 25,
        'description':
            'Focus: MORE WATER + sun protection + heat rescue. Cellphones '
            'and batteries degrade fast in 120 °F cabins — plan for that.',
        'use_case':
            'Summer desert drive breakdown, stranded off-pavement, overheated '
            'radiator waiting for night cooling.',
        'items': [
            ('Water (5 gal bulk + 6 × 1 qt bottles)', 'water', 1, 680, 'Priority #1.'),
            ('Electrolyte tabs (Nuun / LMNT)', 'water', 20, 1, 'Replace salt lost sweating.'),
            ('Sunscreen SPF 50+',            'hygiene', 1, 6, ''),
            ('Wide-brim hat',                'clothing', 1, 4, ''),
            ('Lightweight long-sleeve shirt', 'clothing', 1, 8, 'UPF 50+.'),
            ('Bandana / shemagh (2)',        'clothing', 2, 4, 'Wet for neck cooling.'),
            ('Sunglasses (2 — redundant)',   'clothing', 2, 2, ''),
            ('White tarp / sun shade (8×10)', 'shelter', 1, 24, 'Reflective over vehicle.'),
            ('Radiator stop-leak',           'tools',   1, 8, ''),
            ('Extra quart motor oil',        'tools',   1, 32, ''),
            ('Gas can (metal, 1 gal, safety-approved)', 'tools', 1, 80, ''),
            ('Window reflective shade',      'tools',   1, 8, 'Lowers cabin temp 30 °F.'),
            ('Trauma first aid',             'medical', 1, 16, ''),
            ('Snake bite kit / EXTRACTOR pump', 'medical', 1, 2, 'Sucker NOT recommended by modern field med — keep for snake-bite pressure immobilization instead.'),
            ('Signal mirror',                'comms',   1, 2, ''),
            ('Flashlight',                   'tools',   1, 4, ''),
            ('Hand-crank radio',             'comms',   1, 12, ''),
            ('Jumper cables (heat-resistant insulation)', 'tools', 1, 32, ''),
            ('Tow strap',                    'tools',   1, 32, ''),
            ('Cash',                         'documents', 1, 1, ''),
        ],
    },

    # ───────────────────────── IFAK+ ─────────────────────────────────
    {
        'name': 'IFAK+ (Individual First Aid Kit, Plus)',
        'bag_type': 'medical',
        'season': 'all',
        'target_weight_lb': 4,
        'description':
            'Compact civilian med kit that adds dental + respiratory + GI '
            'meds on top of the trauma basics. Designed for a trained user '
            '— some items require practice.',
        'use_case':
            'Hunting accident, vehicle crash, active-shooter bystander '
            'response, wilderness injury 1+ hr from definitive care.',
        'items': [
            ('CAT Gen 7 tourniquet',         'medical', 2, 3, 'Two minimum — self + bystander.'),
            ('HyFin vent chest seals (pair)', 'medical', 1, 2, 'Sucking chest wound.'),
            ('Hemostatic gauze (QuikClot or Celox)', 'medical', 1, 2, 'Pack deep wounds.'),
            ('Compressed gauze (Z-fold, 4 yd)', 'medical', 2, 2, ''),
            ('Israeli bandage 6 in',         'medical', 1, 4, ''),
            ('Nasopharyngeal airway (28 Fr) + lube', 'medical', 1, 2, ''),
            ('Trauma shears',                'medical', 1, 3, ''),
            ('Nitrile gloves (4 pairs)',     'medical', 1, 2, ''),
            ('Permanent marker (black)',     'medical', 1, 1, 'Document tourniquet time on forehead.'),
            ('Space blanket',                'medical', 1, 2, 'Shock prevention.'),
            ('SAM splint 36 in',             'medical', 1, 4, ''),
            ('Antibiotic ointment (Neosporin 0.5 oz)', 'medical', 1, 1, ''),
            ('Betadine prep pads (10)',      'medical', 1, 1, ''),
            ('Adhesive bandages (20)',       'medical', 1, 1, ''),
            ('Wound-closure strips (Steri-Strips)', 'medical', 1, 1, ''),
            ('Medical tape (1 in × 10 yd)',  'medical', 1, 1, ''),
            ('Moleskin (10 pieces)',         'medical', 1, 1, 'Hot-spot blister prevention.'),
            ('Ibuprofen 200 mg (20)',        'medical', 1, 1, ''),
            ('Acetaminophen 500 mg (20)',    'medical', 1, 1, ''),
            ('Diphenhydramine 25 mg (12)',   'medical', 1, 1, ''),
            ('Loperamide 2 mg (12)',         'medical', 1, 1, 'Anti-diarrheal.'),
            ('ORS rehydration packets (6)',  'medical', 1, 1, ''),
            ('Aspirin 325 mg (chew-for-MI)', 'medical', 1, 1, 'Mark "CARDIAC ONLY".'),
            ('Epinephrine auto-injector (if prescribed)', 'medical', 1, 2, 'EpiPen.'),
            ('Dental emergency: temp filling material + clove oil', 'medical', 1, 1, ''),
            ('Burn gel dressing (4×4)',      'medical', 1, 2, ''),
            ('Eye wash saline (15 mL)',      'medical', 1, 1, ''),
            ('Bite-and-sting wipes',         'medical', 1, 1, ''),
        ],
    },

    # ───────────────────────── Canoe / Boat ──────────────────────────
    {
        'name': 'Canoe / Boat Bag',
        'bag_type': '72hour',
        'season': 'all',
        'target_weight_lb': 18,
        'description':
            'Water-specific BOB variant. Everything waterproof or in dry '
            'bag. Flotation + signaling + cold-water survival emphasis.',
        'use_case':
            'Canoe / kayak expedition capsize, coastal grounding, inland '
            'lake weather trap, sudden storm while fishing.',
        'items': [
            ('Waterproof dry bag (large, 30L)', 'other', 1, 16, 'Your pack itself.'),
            ('Water filter (gravity or pump)', 'water', 1, 12, 'Lake water not drinkable untreated.'),
            ('Collapsible water container (4 L)', 'water', 1, 4, ''),
            ('PFD (type III)',               'clothing', 1, 32, 'Worn, not stowed.'),
            ('Throw bag (75 ft)',            'shelter', 1, 16, 'Rescue + hauling.'),
            ('Wet suit top or drysuit',      'clothing', 1, 64, 'If water < 60 °F.'),
            ('Extra paddle',                 'tools',   1, 48, ''),
            ('Marine knife (fixed, with line-cutting groove)', 'tools', 1, 6, ''),
            ('Waterproof headlamp',          'tools',   1, 6, ''),
            ('Signal flares (orange smoke + red handheld)', 'comms', 2, 6, 'SOLAS if offshore.'),
            ('Whistle (pealess, loud)',      'comms',   1, 1, ''),
            ('Signal mirror',                'comms',   1, 2, ''),
            ('VHF marine radio (handheld waterproof)', 'comms', 1, 12, 'Ch 16 monitoring.'),
            ('Compass (boat mounted + backup)', 'navigation', 2, 8, ''),
            ('Waterproof chart (laminated)', 'navigation', 1, 2, ''),
            ('Spare clothing in dry bag',    'clothing', 1, 24, 'Full change — hypothermia prevention.'),
            ('Emergency bivy + mylar',       'shelter', 1, 6, ''),
            ('First aid (waterproof case)',  'medical', 1, 12, ''),
            ('Shelf-stable food (24 hr min)', 'food',    1, 16, ''),
            ('Fire kit (waterproof)',        'fire',    1, 4, ''),
            ('EPIRB / PLB',                  'comms',   1, 10, 'ACR ResQLink, Ocean Signal.'),
        ],
    },

    # ───────────────────────── Winter-Mountain ───────────────────────
    {
        'name': 'Winter Mountain 72-hr',
        'bag_type': '72hour',
        'season': 'winter',
        'target_weight_lb': 32,
        'description':
            'Cold-weather alpine focus. Adds 0°F bag, stove + fuel (you '
            'WILL need hot liquids), redundant shell layers, avalanche basics. '
            'Bivouac-capable.',
        'use_case':
            'Ski-touring, backcountry snowmobile trip, winter hunt. Must '
            'survive overnight at -20 °F with wind.',
        'items': [
            ('Sleeping bag (-20 °F rated)',  'shelter', 1, 80, ''),
            ('Sleeping pad (closed-cell foam + inflatable)', 'shelter', 2, 24, 'R-value 5+.'),
            ('Bivy sack (Gore-Tex)',         'shelter', 1, 24, ''),
            ('4-season tent OR snow saw (build snow cave)', 'shelter', 1, 48, ''),
            ('MSR Whisperlite stove + fuel bottle (20 oz)', 'fire', 1, 22, 'White gas works at -40 °F.'),
            ('Titanium pot (1 L)',           'water',   1, 6, ''),
            ('Lighter + storm matches + ferro rod', 'fire', 1, 3, ''),
            ('High-calorie food (6 days at 4000 cal/day)', 'food', 24, 6, 'Fat-dense: cheese, nuts, pemmican.'),
            ('Hot drinks (cocoa / tea / broth cubes)', 'food', 20, 1, 'Morale + hydration.'),
            ('Thermos (1 L stainless)',      'water',   1, 24, ''),
            ('Water bottle with insulated sleeve', 'water', 2, 20, 'Upside down to keep mouth from freezing.'),
            ('Water purification tabs',      'water',   1, 1, 'Filter freezes; tabs do not.'),
            ('Shovel (avalanche rescue + snow work)', 'tools', 1, 24, ''),
            ('Avalanche probe (240 cm)',     'tools',   1, 12, ''),
            ('Avalanche transceiver',        'tools',   1, 10, '457 kHz — worn on body, not in pack.'),
            ('Goggles + sunglasses',         'clothing', 2, 4, ''),
            ('Insulated mitts + liner gloves', 'clothing', 2, 8, ''),
            ('Wool beanie + balaclava',      'clothing', 2, 5, ''),
            ('Down puffy jacket (spare)',    'clothing', 1, 20, ''),
            ('Insulated pants shell',        'clothing', 1, 24, ''),
            ('Wool socks (3 pairs)',         'clothing', 3, 4, ''),
            ('Headlamp (300+ lumen, winter-rated batteries)', 'tools', 1, 4, ''),
            ('Chemical hand + toe warmers (24)', 'clothing', 24, 1, ''),
            ('Skin tape / moleskin (blister kit)', 'medical', 1, 1, ''),
            ('Comprehensive first aid',      'medical', 1, 16, 'Include frostbite + hypothermia treatment.'),
            ('Emergency beacon (PLB)',       'comms',   1, 10, ''),
            ('Compass + map',                'navigation', 1, 4, ''),
        ],
    },

    # ───────────────────────── Desert 72-hr ──────────────────────────
    {
        'name': 'Desert 72-hr',
        'bag_type': '72hour',
        'season': 'summer',
        'target_weight_lb': 28,
        'description':
            'Arid climate focus. Water is #1 — plan 1.5 gal/person/day '
            'minimum. Sun protection second, shade third. Night movement '
            'only during peak heat months.',
        'use_case':
            'SW desert hiking, overlanding Mojave / Sonoran / Chihuahuan, '
            'rural off-grid in low-latitude arid regions.',
        'items': [
            ('Water (4.5 gal = ~36 lb)',      'water', 1, 576,
             '3 days × 1.5 gal/person/day. Decant to ease carrying.'),
            ('Electrolyte tablets (80)',      'water', 1, 2, 'Sweat loss = sodium + potassium loss.'),
            ('Wide-brim hat (lightweight)',   'clothing', 1, 4, ''),
            ('UV-rated long-sleeve shirt',    'clothing', 1, 8, ''),
            ('Shemagh / bandana (4)',         'clothing', 4, 4, 'Dampen for neck cooling, dust filter, sun shield.'),
            ('Sunglasses (polarized)',        'clothing', 1, 2, ''),
            ('Sunscreen SPF 50+',             'hygiene', 1, 6, ''),
            ('White tarp (8×10, reflective)', 'shelter', 1, 16, 'Shade is life in desert.'),
            ('Bivy (breathable mesh, no insulation)', 'shelter', 1, 4, 'Night can drop 40 °F.'),
            ('Fleece midlayer',               'clothing', 1, 14, 'Nights are cold.'),
            ('Fire kit (lighter, tinder, ferro)', 'fire', 1, 3, ''),
            ('Signal mirror',                 'comms', 1, 2, 'Desert reflects forever.'),
            ('Whistle',                       'comms', 1, 1, ''),
            ('Baofeng UV-5R',                 'comms', 1, 10, ''),
            ('Headlamp + red-light filter',   'tools', 1, 4, 'Night movement only.'),
            ('Fixed-blade knife',             'tools', 1, 8, ''),
            ('Multi-tool',                    'tools', 1, 9, ''),
            ('GPS receiver + spare batteries', 'navigation', 1, 8, 'Desert terrain features deceive eye.'),
            ('Local topo + road atlas',       'navigation', 1, 4, ''),
            ('Compass',                       'navigation', 1, 2, ''),
            ('Shelf-stable calorie bars (3 days × 2200 cal)', 'food', 12, 6, 'Low-thirst foods.'),
            ('Trauma kit',                    'medical', 1, 12, 'Add snake-bite pressure bandage.'),
            ('Heat-illness thermometer',      'medical', 1, 2, 'Core temp check.'),
            ('Cash',                          'documents', 1, 1, ''),
        ],
    },

    # ───────────────────────── Backcountry 3-day ─────────────────────
    {
        'name': 'Backcountry 3-day',
        'bag_type': '72hour',
        'season': 'all',
        'target_weight_lb': 28,
        'description':
            'Planned 3-day multi-night wilderness trip. Not an emergency '
            'kit per se — a lightweight backpacking setup that doubles as '
            'bug-out if needed. Full "10 essentials" plus sleep + cook.',
        'use_case':
            'Weekend trekking, remote fishing, planned off-grid solitude '
            'that can extend to 7 days if necessary.',
        'items': [
            ('Backpacking pack (55 L)',      'other',   1, 48, ''),
            ('Tent (2-person, 3-season)',    'shelter', 1, 48, ''),
            ('Sleeping bag (30 °F)',         'shelter', 1, 32, ''),
            ('Sleeping pad (inflatable)',    'shelter', 1, 16, ''),
            ('Canister stove + 2 × 8oz fuel', 'fire',    1, 18, ''),
            ('Cookset (pot + spoon + lighter)', 'water', 1, 10, ''),
            ('Water filter (gravity) + 2 L bladder', 'water', 1, 10, ''),
            ('Freeze-dried meals (6 dinners + 3 lunches)', 'food', 9, 4, ''),
            ('Backpacking breakfasts (granola / oats × 3)', 'food', 3, 4, ''),
            ('Trail snacks / bars (12)',     'food',   12, 3, ''),
            ('Coffee + sugar',               'food',    1, 4, ''),
            ('Headlamp + spare batteries',   'tools',   1, 4, ''),
            ('Multi-tool / knife',           'tools',   1, 6, ''),
            ('First aid (basic)',            'medical', 1, 8, ''),
            ('Bear spray (if applicable)',   'tools',   1, 14, ''),
            ('Rain shell',                   'clothing', 1, 14, ''),
            ('Insulating midlayer',          'clothing', 1, 16, ''),
            ('Sun hat + sunglasses',         'clothing', 1, 5, ''),
            ('Hiking pants + shorts',        'clothing', 1, 16, ''),
            ('Camp shoes (Crocs / sandals)', 'clothing', 1, 10, ''),
            ('Hygiene kit (trowel, TP, tooth)', 'hygiene', 1, 4, ''),
            ('Map + compass',                'navigation', 1, 4, ''),
            ('GPS watch or phone in airplane mode', 'navigation', 1, 4, ''),
            ('Cash',                         'documents', 1, 1, ''),
        ],
    },

    # ───────────────────────── Urban / Apartment ─────────────────────
    {
        'name': 'Urban / Apartment 72-hr',
        'bag_type': '72hour',
        'season': 'all',
        'target_weight_lb': 18,
        'description':
            'Shelter-in-place variant for the city apartment or office. '
            'No yard + no grill = no outdoor cook options. Focus on '
            'no-cook food, filtered water from bathroom tub, '
            'stairwell-navigable weight.',
        'use_case':
            'Urban grid-down, boil-water advisory, wildfire smoke event, '
            'civil unrest lockdown. Primary location is home.',
        'items': [
            ('Water (3 gal case) OR WaterBOB tub liner', 'water', 1, 408, 'WaterBOB holds 100 gal in tub.'),
            ('Sawyer Squeeze filter',        'water',   1, 4, 'For tap water under boil advisory.'),
            ('Bleach (8 oz unscented)',      'water',   1, 8, 'Large-batch treatment.'),
            ('No-cook food (72 hr × 2500 cal)', 'food', 1, 96,
             'Peanut butter, trail mix, tuna pouches, crackers, canned fruit.'),
            ('Manual can opener',            'tools',   1, 2, ''),
            ('Mess kit (plate + utensils)',  'water',   1, 6, ''),
            ('Battery-operated lantern',     'tools',   1, 16, '200+ lumen. 20 hr runtime.'),
            ('Headlamp',                     'tools',   1, 3, ''),
            ('Candles + matches (emergency)', 'fire',   6, 4, 'Check building rules on open flame.'),
            ('First aid kit',                'medical', 1, 12, ''),
            ('Personal meds (2-week supply)', 'medical', 1, 4, ''),
            ('N95 masks (10)',               'medical', 10, 1, 'Smoke + dust event.'),
            ('Duct tape + plastic sheeting', 'shelter', 1, 16, 'Seal around vents for smoke/chem event.'),
            ('Hand-crank NOAA radio',        'comms',   1, 12, ''),
            ('Baofeng UV-5R (monitor-only)', 'comms',   1, 10, ''),
            ('Phone chargers + 20k mAh power bank', 'tools', 1, 16, ''),
            ('Toilet (5-gal bucket + bags + litter)', 'hygiene', 1, 80,
             'Luggable loo setup. Bathroom may not function if water/sewer out.'),
            ('Handwashing soap (bar) + sanitizer', 'hygiene', 1, 4, ''),
            ('Feminine hygiene (if applicable)', 'hygiene', 1, 4, ''),
            ('Baby supplies (if applicable)', 'hygiene', 1, 8, ''),
            ('Pet food + water (3 days)',    'other',   1, 48, 'If applicable — pet also counts as dependent.'),
            ('Documents (digital + paper copies)', 'documents', 1, 2, ''),
            ('Cash ($200 smalls + coin)',    'documents', 1, 2, ''),
            ('Fire extinguisher (home unit)', 'tools',   1, 80, 'Already in apartment; list here so it makes the checklist.'),
        ],
    },
]
