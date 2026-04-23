"""Weather action rule templates — CE-07 (v7.60).

Seeds ``weather_action_rules`` with 15 sensible defaults so the engine
emits real alerts on a fresh install rather than needing the user to hand-
author threshold math for every weather variable.

Schema (from db.py):
    (name, condition_type, threshold, comparison, action_type,
     action_data, enabled, cooldown_minutes)

condition_type values recognized by the evaluator (see weather.py):
    pressure_drop, pressure_below, temperature_below, temperature_above,
    wind_above, humidity_above, precipitation_above, aqi_above,
    lightning_distance_below

comparison values:
    lt (less than), gt (greater than), le, ge, eq
"""

import json

# (name, condition_type, threshold, comparison, action_type,
#  action_data_dict, enabled, cooldown_minutes)
RULES = [
    # ──── Pressure ────
    ('Storm Incoming (pressure drop ≥ 6 hPa / 3h)',
     'pressure_drop', 6.0, 'ge', 'alert',
     {'severity': 'warning',
      'message': 'Barometric pressure dropping fast. Storm within 6-12 hr likely. Secure outdoor gear, top off water, charge comms.'},
     1, 120),

    ('Severe Low Pressure (< 1000 hPa)',
     'pressure_below', 1000.0, 'lt', 'alert',
     {'severity': 'warning',
      'message': 'Pressure below 1000 hPa. Active low-pressure system overhead. Expect precipitation + wind.'},
     1, 180),

    # ──── Temperature ────
    ('Freeze Warning (< 32 °F / 0 °C)',
     'temperature_below', 32.0, 'lt', 'alert',
     {'severity': 'warning',
      'message': 'Subfreezing temps tonight. Protect pipes, bring in sensitive plants, check livestock water.'},
     1, 360),

    ('Hard Freeze — Pipe Risk (< 25 °F / -4 °C)',
     'temperature_below', 25.0, 'lt', 'alert',
     {'severity': 'critical',
      'message': 'Hard freeze. Open interior cabinet doors, drip faucets, shut off outdoor spigots, insulate meter.'},
     1, 360),

    ('Extreme Cold (< 0 °F / -18 °C)',
     'temperature_below', 0.0, 'lt', 'alert',
     {'severity': 'critical',
      'message': 'Extreme cold — frostbite in < 30 min exposed skin. Stay indoors, verify heat + CO alarm, extra blankets.'},
     1, 360),

    ('Heat Advisory (> 95 °F / 35 °C)',
     'temperature_above', 95.0, 'gt', 'alert',
     {'severity': 'warning',
      'message': 'Heat stress risk. Hydrate ≥ 1 L/hr outdoors, shift heavy labor to dawn/dusk, check on elderly + pets.'},
     1, 240),

    ('Extreme Heat (> 105 °F / 41 °C)',
     'temperature_above', 105.0, 'gt', 'alert',
     {'severity': 'critical',
      'message': 'Extreme heat — heatstroke probable for anyone outdoors > 1 hr. Cancel outdoor tasks, verify AC or cooling plan.'},
     1, 180),

    # ──── Wind ────
    ('High Wind — Secure Outdoors (> 25 mph / 40 kph sustained)',
     'wind_above', 25.0, 'gt', 'alert',
     {'severity': 'info',
      'message': 'Sustained wind over 25 mph — tie down light outdoor items + umbrellas.'},
     1, 180),

    ('Damaging Wind (> 40 mph / 64 kph)',
     'wind_above', 40.0, 'gt', 'alert',
     {'severity': 'warning',
      'message': 'Damaging wind. Stay away from large trees + power lines. Park vehicles clear of limbs. Charge devices before outage.'},
     1, 120),

    ('Severe Wind (> 58 mph — NWS severe threshold)',
     'wind_above', 58.0, 'gt', 'alert',
     {'severity': 'critical',
      'message': 'Severe-category wind. Take interior shelter now. Expect downed lines and widespread outages.'},
     1, 60),

    # ──── Humidity / precipitation ────
    ('Mold Risk — Sustained High RH (> 85 %)',
     'humidity_above', 85.0, 'gt', 'alert',
     {'severity': 'info',
      'message': 'Indoor RH > 85 % sustained. Run dehumidifier or ventilate. Inspect bathrooms, basements, gear bags for mold.'},
     1, 720),

    ('Heavy Rain — Flash Flood Watch (> 1 in/hr)',
     'precipitation_above', 1.0, 'gt', 'alert',
     {'severity': 'warning',
      'message': 'Heavy rain rate. Move vehicles off low ground. Never drive through flooded road — 6 in moving water floats a car.'},
     1, 60),

    # ──── Air quality ────
    ('Unhealthy Air (AQI > 150)',
     'aqi_above', 150.0, 'gt', 'alert',
     {'severity': 'warning',
      'message': 'AQI in Unhealthy range. N95/KN95 outdoors, windows closed, HVAC on recirculate with MERV 13+ filter if available.'},
     1, 240),

    ('Hazardous Air (AQI > 300)',
     'aqi_above', 300.0, 'gt', 'alert',
     {'severity': 'critical',
      'message': 'AQI Hazardous. Shelter in place, seal gaps, run air purifier, N95 even briefly outdoors. Consider evacuation if sustained.'},
     1, 180),

    # ──── Lightning ────
    ('Lightning Within 10 mi — Unplug Electronics',
     'lightning_distance_below', 10.0, 'lt', 'alert',
     {'severity': 'warning',
      'message': 'Lightning within 10 mi. Unplug sensitive electronics, stop outdoor work, 30/30 rule: stay inside 30 min after last thunder.'},
     1, 60),
]


def rules_for_insert():
    """Return rows ready for INSERT OR IGNORE (JSON-encodes action_data)."""
    return [
        (name, ct, thr, cmp_op, at, json.dumps(ad), en, cool)
        for (name, ct, thr, cmp_op, at, ad, en, cool) in RULES
    ]
