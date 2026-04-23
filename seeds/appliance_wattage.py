"""Appliance + load-wattage reference table — CE-06 (v7.60).

Used by the power / autonomy / solar-sizing calculators to let the user
pick a load from a realistic list instead of guessing wattages. These are
*typical* values; nameplate on the actual device always wins.

This data is stored in Python (not a DB table) because it's a static
reference lookup — no user edits, no search, no joins. The power blueprint
imports ``APPLIANCE_WATTAGE`` directly.

Columns:
    name           — human-readable device
    category       — grouping for the UI
    running_watts  — sustained draw under typical use
    surge_watts    — inrush / start-up draw (mostly motors + compressors)
                      None when no meaningful surge
    typical_hours  — rough hours/day an always-installed household item
                      tends to be "on". 0 = user picks.
    notes          — caveats, efficiency tips, safety flags

Sources: US DOE ENERGY STAR appliance benchmarks, manufacturer spec sheets
(Kenmore, Whirlpool, Frigidaire, ResMed, Philips), NEC motor tables.
"""

APPLIANCE_WATTAGE = [
    # ─────────── Refrigeration / cooking ───────────
    ('Refrigerator (20 cu ft, Energy Star)', 'Refrigeration', 150, 800, 8,
     'Compressor cycles; 24h avg ~1.5 kWh. Well-sealed box + full fridge runs less.'),
    ('Chest freezer (15 cu ft)', 'Refrigeration', 90, 500, 6,
     'Very efficient compared to upright freezer. Full freezer holds cold longer during outages.'),
    ('Upright freezer (20 cu ft)', 'Refrigeration', 250, 1000, 8, 'Less efficient than chest.'),
    ('Mini-fridge / dorm fridge', 'Refrigeration', 90, 300, 8, 'Good pharmacy-only option during grid-down.'),
    ('Microwave (1100 W nameplate)', 'Refrigeration', 1100, None, 0.25,
     'Nameplate = cooking power. Input draw 30-40 % higher. Short duration helps.'),
    ('Electric oven', 'Refrigeration', 2400, None, 1, 'Heating element can draw 4500 W peak; derate generator accordingly.'),
    ('Electric cooktop burner (large)', 'Refrigeration', 2000, None, 0.5, 'Cycling on/off during cook.'),
    ('Induction cooktop burner', 'Refrigeration', 1800, None, 0.5,
     '~85 % thermal efficient (vs ~40 % gas), so faster cook = lower energy per meal.'),
    ('Coffee maker (drip)', 'Refrigeration', 1000, None, 0.2, 'Only during brew; warming plate ~60 W.'),
    ('Electric kettle', 'Refrigeration', 1500, None, 0.1, '3-4 min per boil.'),
    ('Toaster oven', 'Refrigeration', 1200, None, 0.25, 'Good grid-down substitute for oven for small meals.'),
    ('Instant Pot (6 qt)', 'Refrigeration', 1000, None, 0.5,
     'Pressure cook phase only; pre-heat + low-pressure cruise far lower.'),
    ('Crock-pot / slow cooker', 'Refrigeration', 200, None, 6, 'Low-heat mode ~150 W.'),
    ('Dishwasher (Energy Star)', 'Refrigeration', 1200, None, 1, 'Heating element drives most load.'),

    # ─────────── Laundry / water heating ───────────
    ('Washing machine (agitator, cold)', 'Laundry', 500, 800, 0.5, 'Spin cycle ~500 W; wash motor ~250 W.'),
    ('Washing machine (HE front-load, cold)', 'Laundry', 350, 600, 0.5, 'Cold water cuts ~80 % of cycle energy.'),
    ('Clothes dryer (electric)', 'Laundry', 3000, None, 1, 'Monster load. Gas dryer only draws ~300 W for motor.'),
    ('Clothes dryer (gas)', 'Laundry', 300, None, 1, 'Just the drum motor + electronics.'),
    ('Electric water heater (tank, 50 gal)', 'Laundry', 4500, None, 3, 'Element cycles. Heat-pump version ~800 W avg.'),
    ('Tankless electric water heater', 'Laundry', 18000, None, 0.5,
     'Huge instantaneous load — rarely fits an off-grid inverter. Gas tankless: 120 W for the electronics + igniter.'),

    # ─────────── HVAC ───────────
    ('Window AC 5,000 BTU', 'HVAC', 500, 1200, 6, 'EER 10+ preferred. Cooling a single room.'),
    ('Window AC 10,000 BTU', 'HVAC', 1050, 2500, 6, ''),
    ('Window AC 18,000 BTU (220 V)', 'HVAC', 1800, 4000, 6, 'Two-stage compressors start gentler.'),
    ('Central AC 3-ton', 'HVAC', 3500, 10000, 6,
     'Hard-start kit can cut surge by 50 %. Still a grid-only load for most inverter systems.'),
    ('Mini-split heat pump (9k BTU)', 'HVAC', 700, 1500, 8,
     'Inverter-drive — tiny surge. 24k BTU unit: ~2200 W. Great for off-grid.'),
    ('Space heater (electric, 1500 W)', 'HVAC', 1500, None, 2, 'No free lunch: 5120 BTU/hr regardless of brand.'),
    ('Ceiling fan', 'HVAC', 60, None, 8, 'DC fans: 15 W. Massive cooling lift per watt.'),
    ('Box fan / pedestal fan', 'HVAC', 60, None, 8, ''),
    ('Electric blanket', 'HVAC', 100, None, 8, ''),
    ('Gas furnace (blower only)', 'HVAC', 600, 1500, 8,
     'Gas burner itself doesn\'t need electricity; the circulation fan does.'),
    ('Dehumidifier (50 pint)', 'HVAC', 550, 1100, 12, 'Runs in cycles.'),
    ('Humidifier (cool mist)', 'HVAC', 30, None, 8, 'Ultrasonic humidifier ~30 W.'),
    ('Humidifier (warm mist / evaporative)', 'HVAC', 300, None, 8, ''),

    # ─────────── Well + sump ───────────
    ('Well pump (1/2 HP submersible)', 'Well / Plumbing', 800, 2500, 1, '1 HP: 1100 W run / 3500 W surge.'),
    ('Well pump (1 HP submersible)', 'Well / Plumbing', 1100, 3500, 1, 'Soft-start helps sizing.'),
    ('Sump pump (1/3 HP)', 'Well / Plumbing', 400, 1200, 2, 'Critical load during flood scenarios.'),
    ('Sump pump (1/2 HP)', 'Well / Plumbing', 600, 1800, 2, ''),
    ('Septic grinder pump', 'Well / Plumbing', 900, 2500, 0.5, 'Sized per install. Check nameplate.'),
    ('Pressure tank bladder pump', 'Well / Plumbing', 300, 900, 0.5, ''),

    # ─────────── Medical ───────────
    ('CPAP (no humidifier / no heat)', 'Medical', 30, None, 8, 'ResMed AirSense 10: ~30 W peak, 15 W avg.'),
    ('CPAP with heated humidifier', 'Medical', 90, None, 8,
     'Disable heat to preserve battery during outages.'),
    ('BiPAP', 'Medical', 60, None, 8, ''),
    ('Oxygen concentrator (5 LPM home unit)', 'Medical', 350, 650, 24,
     'Critical-load prioritization: usually belongs on the same dedicated circuit as CPAP.'),
    ('Portable oxygen concentrator (POC)', 'Medical', 120, None, 12, 'Inogen One G5: 120 W on AC.'),
    ('Insulin pump', 'Medical', 1, None, 24, 'Battery-operated; AC draw is trivial.'),
    ('Electric wheelchair charger', 'Medical', 400, None, 4, 'Higher during bulk charge phase.'),
    ('Nebulizer', 'Medical', 100, None, 0.5, 'Short-duration treatment device.'),
    ('Dialysis machine (home HD)', 'Medical', 2000, 3500, 4,
     'Very grid-dependent; most home units require water heater too. Discuss backup strategy with clinician.'),

    # ─────────── Comms / IT ───────────
    ('Laptop', 'Comms / IT', 60, None, 6, 'Gaming laptop: 180-300 W.'),
    ('Desktop PC', 'Comms / IT', 200, None, 6, 'Workstation w/ GPU: 400-800 W.'),
    ('Gaming desktop + monitor', 'Comms / IT', 500, None, 3, 'RTX 4080-class rig can hit 700 W peak.'),
    ('LCD monitor 27 in', 'Comms / IT', 30, None, 6, 'Older plasma TVs: 200-400 W.'),
    ('OLED TV 55 in', 'Comms / IT', 120, None, 4, 'Scales ~2x per 10 in diagonal.'),
    ('LED TV 55 in', 'Comms / IT', 80, None, 4, ''),
    ('Router / modem / switch', 'Comms / IT', 15, None, 24, 'Always-on. Budget 30-40 W for full network stack.'),
    ('Mesh WiFi node', 'Comms / IT', 15, None, 24, ''),
    ('Starlink dishy + router', 'Comms / IT', 50, None, 24, 'Peak 100 W when de-icing.'),
    ('VoIP phone base / DECT', 'Comms / IT', 5, None, 24, ''),
    ('Printer (laser, idle)', 'Comms / IT', 10, 800, 0.5, 'Print burst draws full 800 W for seconds.'),

    # ─────────── Lighting ───────────
    ('LED bulb 60 W equivalent', 'Lighting', 10, None, 5, 'LED has no warm-up draw.'),
    ('LED bulb 100 W equivalent', 'Lighting', 15, None, 4, ''),
    ('CFL bulb 60 W equivalent', 'Lighting', 14, None, 5, 'Takes 30 s to reach full brightness.'),
    ('Incandescent bulb 60 W', 'Lighting', 60, None, 5, 'Obsolete but still found in utility fixtures.'),
    ('Workshop fluorescent fixture (4 ft, 2-bulb)', 'Lighting', 80, None, 2, ''),
    ('String / rope lighting (LED, 10 ft)', 'Lighting', 5, None, 4, ''),

    # ─────────── Power tools (intermittent) ───────────
    ('Drill (20 V cordless charger)', 'Power tools', 80, None, 1, 'Short bursts — size for surge, not hours.'),
    ('Circular saw (15 A corded)', 'Power tools', 1400, 2300, 0.25, ''),
    ('Table saw (15 A, 1.75 HP)', 'Power tools', 1800, 4500, 0.25, 'Very high startup surge; use soft-start or derate generator.'),
    ('Angle grinder (10 A)', 'Power tools', 1000, 2000, 0.25, ''),
    ('Air compressor (2 HP pancake)', 'Power tools', 1500, 4000, 0.5, 'Cycling — plan for surge when pressure switch trips.'),
    ('Miter saw (15 A)', 'Power tools', 1600, 3200, 0.25, ''),
    ('Shop vac (wet/dry, 6 HP peak)', 'Power tools', 900, 1600, 0.5, ''),
    ('Chest-style tool charger station', 'Power tools', 150, None, 2, 'Several battery packs bulk-charging.'),

    # ─────────── Yard / shop ───────────
    ('Electric lawnmower (corded)', 'Yard', 1500, 2000, 0.5, ''),
    ('Electric lawnmower (cordless charger)', 'Yard', 200, None, 1, 'Bulk charge cycle for 40-80V mower battery.'),
    ('Electric chainsaw', 'Yard', 2000, 2500, 0.5, ''),
    ('Electric leaf blower', 'Yard', 1200, 1800, 0.25, ''),
    ('Pool pump (1 HP)', 'Yard', 1500, 2500, 8, 'Variable-speed pumps cut this ~75 %.'),

    # ─────────── Small misc ───────────
    ('Electric toothbrush charger', 'Small misc', 1, None, 8, ''),
    ('Phone charger (USB-C, 20 W block)', 'Small misc', 10, None, 2, 'Full-charge phone = ~10 Wh.'),
    ('Tablet charger', 'Small misc', 20, None, 2, ''),
    ('Power bank charger (100 W)', 'Small misc', 100, None, 3, 'Bulk charge phase — tapers toward end.'),
    ('Garage door opener', 'Small misc', 350, 900, 0.1, 'Seconds of use per day.'),
    ('Deep-cycle battery charger (10 A)', 'Small misc', 150, None, 4, ''),
]
