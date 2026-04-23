"""Radio frequency directory seed data — CE-05 (v7.60).

Seeds ``freq_database`` with the canonical public-safety / amateur / field
frequencies that any US-based operator is likely to want on day one.

Schema (from db.py):
    (frequency, mode, bandwidth, service, description, region,
     license_required, priority, notes)

Priorities:
    10 = life-safety / emergency-only (never key up casually)
     8 = shared-use critical (marine ch 16, NOAA WX, FRS/GMRS emergency)
     6 = routine coordination (FRS/GMRS/MURS channels, simplex calling)
     4 = band plan reference / calling frequencies
     2 = hobbyist / experimental

Sources: FCC Part 95, ARRL 2m/70cm band plans, USCG, NOAA, NIFOG.
"""

# (frequency_MHz, mode, bandwidth, service, description, region,
#  license_required, priority, notes)
FREQUENCIES = [
    # ───────────────────────────────── Emergency / Life-Safety ────────
    (121.500, 'AM', '6 kHz', 'Emergency', 'International Air Distress (Guard)', 'World', 0, 10,
     'Aviation emergency. Monitored by ATC, SAR, and most commercial aircraft. ELT beacons transmit here.'),
    (243.000, 'AM', '6 kHz', 'Emergency', 'Military Air Distress (UHF Guard)', 'World', 0, 10,
     'Military aviation emergency. Harmonic of 121.5 MHz.'),
    (156.800, 'FM', '16 kHz', 'Marine', 'VHF Marine Ch 16 — Distress/Calling', 'World', 1, 10,
     'International marine distress + calling. Monitored 24/7 by Coast Guard. License: SLM or MMSI.'),
    (156.450, 'FM', '16 kHz', 'Marine', 'VHF Marine Ch 9 — Secondary Hailing', 'World', 1, 8,
     'Alternate calling channel — use to offload Ch 16 for non-distress hailing.'),
    (156.300, 'FM', '16 kHz', 'Marine', 'VHF Marine Ch 6 — Intership Safety', 'World', 1, 8,
     'Mandatory intership safety. Used for bridge-to-bridge safety coordination.'),
    (156.650, 'FM', '16 kHz', 'Marine', 'VHF Marine Ch 13 — Bridge to Bridge', 'World', 1, 8,
     'Navigation safety between vessels. Required monitoring in US waters.'),
    (462.675, 'FM', '12.5 kHz', 'GMRS', 'GMRS Emergency / REACT Ch 20 (Travel)', 'US', 1, 10,
     'Monitored by REACT teams + many caravan/travel groups for emergencies.'),

    # ───────────────────────────────── NOAA Weather Radio ─────────────
    (162.400, 'FM', '25 kHz', 'NOAA', 'NOAA Weather Radio WX2', 'US', 0, 8, 'Listen-only.'),
    (162.425, 'FM', '25 kHz', 'NOAA', 'NOAA Weather Radio WX4', 'US', 0, 8, 'Listen-only.'),
    (162.450, 'FM', '25 kHz', 'NOAA', 'NOAA Weather Radio WX5', 'US', 0, 8, 'Listen-only.'),
    (162.475, 'FM', '25 kHz', 'NOAA', 'NOAA Weather Radio WX3', 'US', 0, 8, 'Listen-only.'),
    (162.500, 'FM', '25 kHz', 'NOAA', 'NOAA Weather Radio WX6', 'US', 0, 8, 'Listen-only.'),
    (162.525, 'FM', '25 kHz', 'NOAA', 'NOAA Weather Radio WX7', 'US', 0, 8, 'Listen-only.'),
    (162.550, 'FM', '25 kHz', 'NOAA', 'NOAA Weather Radio WX1', 'US', 0, 8, 'Listen-only.'),

    # ───────────────────────────────── FRS (Part 95B, no license) ─────
    # FRS 1-7 share with GMRS but FRS is limited to 2 W on 1-7 and 0.5 W on 8-14.
    (462.5625, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 1 (shared with GMRS)', 'US', 0, 6, 'No license. 2 W max.'),
    (462.5875, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 2 (shared with GMRS)', 'US', 0, 6, 'No license. 2 W max.'),
    (462.6125, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 3 (shared with GMRS)', 'US', 0, 6, 'No license. 2 W max.'),
    (462.6375, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 4 (shared with GMRS)', 'US', 0, 6, 'No license. 2 W max.'),
    (462.6625, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 5 (shared with GMRS)', 'US', 0, 6, 'No license. 2 W max.'),
    (462.6875, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 6 (shared with GMRS)', 'US', 0, 6, 'No license. 2 W max.'),
    (462.7125, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 7 (shared with GMRS)', 'US', 0, 6, 'No license. 2 W max.'),
    (467.5625, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 8', 'US', 0, 6, 'No license. 0.5 W max. FRS-only.'),
    (467.5875, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 9', 'US', 0, 6, 'No license. 0.5 W max. FRS-only.'),
    (467.6125, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 10', 'US', 0, 6, 'No license. 0.5 W max. FRS-only.'),
    (467.6375, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 11', 'US', 0, 6, 'No license. 0.5 W max. FRS-only.'),
    (467.6625, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 12', 'US', 0, 6, 'No license. 0.5 W max. FRS-only.'),
    (467.6875, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 13', 'US', 0, 6, 'No license. 0.5 W max. FRS-only.'),
    (467.7125, 'FM', '12.5 kHz', 'FRS', 'FRS Ch 14', 'US', 0, 6, 'No license. 0.5 W max. FRS-only.'),
    (462.5500, 'FM', '20 kHz', 'FRS', 'FRS Ch 15 (shared with GMRS 550)', 'US', 0, 6, '2 W FRS, 50 W GMRS.'),
    (462.5750, 'FM', '20 kHz', 'FRS', 'FRS Ch 16 (shared with GMRS 575)', 'US', 0, 6, '2 W FRS, 50 W GMRS.'),
    (462.6000, 'FM', '20 kHz', 'FRS', 'FRS Ch 17 (shared with GMRS 600)', 'US', 0, 6, '2 W FRS, 50 W GMRS.'),
    (462.6250, 'FM', '20 kHz', 'FRS', 'FRS Ch 18 (shared with GMRS 625)', 'US', 0, 6, '2 W FRS, 50 W GMRS.'),
    (462.6500, 'FM', '20 kHz', 'FRS', 'FRS Ch 19 (shared with GMRS 650)', 'US', 0, 6, '2 W FRS, 50 W GMRS.'),
    (462.7000, 'FM', '20 kHz', 'FRS', 'FRS Ch 21 (shared with GMRS 700)', 'US', 0, 6, '2 W FRS, 50 W GMRS.'),
    (462.7250, 'FM', '20 kHz', 'FRS', 'FRS Ch 22 (shared with GMRS 725)', 'US', 0, 6, '2 W FRS, 50 W GMRS.'),

    # ───────────────────────────────── GMRS Repeater Inputs (467 MHz) ─
    # GMRS repeaters: RX on the 462 main channel, TX input on the +5 MHz pair.
    (467.5500, 'FM', '20 kHz', 'GMRS', 'GMRS Repeater Input 550 (+5 MHz offset)', 'US', 1, 4, 'License required. Repeater use.'),
    (467.5750, 'FM', '20 kHz', 'GMRS', 'GMRS Repeater Input 575 (+5 MHz offset)', 'US', 1, 4, 'License required. Repeater use.'),
    (467.6000, 'FM', '20 kHz', 'GMRS', 'GMRS Repeater Input 600 (+5 MHz offset)', 'US', 1, 4, 'License required. Repeater use.'),
    (467.6250, 'FM', '20 kHz', 'GMRS', 'GMRS Repeater Input 625 (+5 MHz offset)', 'US', 1, 4, 'License required. Repeater use.'),
    (467.6500, 'FM', '20 kHz', 'GMRS', 'GMRS Repeater Input 650 (+5 MHz offset)', 'US', 1, 4, 'License required. Repeater use.'),
    (467.6750, 'FM', '20 kHz', 'GMRS', 'GMRS Repeater Input 675 (+5 MHz offset)', 'US', 1, 4, 'License required. Repeater use.'),
    (467.7000, 'FM', '20 kHz', 'GMRS', 'GMRS Repeater Input 700 (+5 MHz offset)', 'US', 1, 4, 'License required. Repeater use.'),
    (467.7250, 'FM', '20 kHz', 'GMRS', 'GMRS Repeater Input 725 (+5 MHz offset)', 'US', 1, 4, 'License required. Repeater use.'),

    # ───────────────────────────────── MURS (Part 95J, no license) ────
    (151.820, 'FM', '11.25 kHz', 'MURS', 'MURS Ch 1', 'US', 0, 6, 'No license. 2 W max.'),
    (151.880, 'FM', '11.25 kHz', 'MURS', 'MURS Ch 2', 'US', 0, 6, 'No license. 2 W max.'),
    (151.940, 'FM', '11.25 kHz', 'MURS', 'MURS Ch 3', 'US', 0, 6, 'No license. 2 W max.'),
    (154.570, 'FM', '20 kHz', 'MURS', 'MURS Ch 4 (Blue Dot)', 'US', 0, 6, 'No license. 2 W max. Common retail/business freq.'),
    (154.600, 'FM', '20 kHz', 'MURS', 'MURS Ch 5 (Green Dot)', 'US', 0, 6, 'No license. 2 W max. Common retail/business freq.'),

    # ───────────────────────────────── 2m Amateur (144-148 MHz) ───────
    (146.520, 'FM', '16 kHz', 'Ham 2m', '2m National Simplex Calling Frequency', 'US', 1, 8,
     'Primary simplex calling. Listen before use.'),
    (144.200, 'USB', '3 kHz', 'Ham 2m', '2m SSB Calling Frequency', 'US', 1, 4, 'Weak-signal / DX.'),
    (145.000, 'FM', '16 kHz', 'Ham 2m', '2m Repeater Subband Start', 'US', 1, 2, 'Range: 145.000-145.500 MHz repeater outputs.'),
    (146.400, 'FM', '16 kHz', 'Ham 2m', '2m Simplex Subband Start', 'US', 1, 2, 'Range: 146.400-146.595 MHz simplex.'),
    (146.580, 'FM', '16 kHz', 'Ham 2m', '2m Simplex Coordination Frequency', 'US', 1, 4, 'Common secondary simplex.'),
    (147.420, 'FM', '16 kHz', 'Ham 2m', '2m Simplex — common SAR/field freq', 'US', 1, 4, 'De facto SAR coordination simplex in many regions.'),

    # ───────────────────────────────── 70cm Amateur (420-450 MHz) ─────
    (446.000, 'FM', '16 kHz', 'Ham 70cm', '70cm National Simplex Calling', 'US', 1, 8,
     'Primary 70cm simplex calling. Listen before use.'),
    (432.100, 'USB', '3 kHz', 'Ham 70cm', '70cm SSB Calling Frequency', 'US', 1, 4, 'Weak-signal.'),

    # ───────────────────────────────── HF Emergency / Net Coordination ─
    (3.873, 'LSB', '3 kHz', 'Ham HF', '75m ARES/RACES Regional Emergency Net', 'US', 1, 8,
     '75m (LSB). SATERN and regional ARES nets often here. Check ARRL section listings for exact time.'),
    (7.268, 'LSB', '3 kHz', 'Ham HF', '40m Emergency Coordination', 'US', 1, 8,
     'Popular 40m emergency/traffic net frequency.'),
    (14.300, 'USB', '3 kHz', 'Ham HF', '20m Maritime Mobile Service Net', 'World', 1, 8,
     'Maritime Mobile Service Net — daily at 1600 UTC. 24/7 emergency monitoring.'),
    (14.265, 'USB', '3 kHz', 'Ham HF', '20m SATERN Intl Emergency Net', 'World', 1, 8,
     'Salvation Army Team Emergency Radio Network.'),
    (7.040, 'CW', '0.5 kHz', 'Ham HF', '40m QRP CW Calling', 'World', 1, 2, 'Low-power CW.'),
    (7.074, 'USB', '3 kHz', 'Ham HF', '40m FT8 Digital Mode', 'World', 1, 4, 'WSJT-X FT8.'),
    (14.074, 'USB', '3 kHz', 'Ham HF', '20m FT8 Digital Mode', 'World', 1, 4, 'WSJT-X FT8.'),
    (14.230, 'USB', '3 kHz', 'Ham HF', '20m SSTV Calling', 'World', 1, 2, 'Slow-scan TV.'),
    (10.138, 'USB', '3 kHz', 'Ham HF', '30m WSPR / Winlink', 'World', 1, 4, 'Winlink HF gateway freq.'),

    # ───────────────────────────────── Data / APRS ────────────────────
    (144.390, 'FM', '16 kHz', 'Ham 2m', 'APRS North America', 'NA', 1, 6,
     'Automatic Packet Reporting System — beacon / tracker / messaging.'),
    (144.800, 'FM', '16 kHz', 'Ham 2m', 'APRS Europe', 'EU', 1, 6, 'APRS in IARU Region 1.'),

    # ───────────────────────────────── CB (11m, Part 95C) ─────────────
    (26.965, 'AM', '8 kHz', 'CB', 'CB Channel 1', 'US', 0, 2, 'No license. 4 W AM / 12 W SSB.'),
    (27.065, 'AM', '8 kHz', 'CB', 'CB Channel 9 — Emergency / Motorist Assistance', 'US', 0, 10,
     'REACT emergency monitoring + motorist assistance. Only use for emergencies.'),
    (27.185, 'AM', '8 kHz', 'CB', 'CB Channel 19 — Trucker / Highway', 'US', 0, 6,
     'Standard OTR trucker channel. Road conditions + hazard alerts.'),
    (27.385, 'USB', '3 kHz', 'CB', 'CB Channel 38 LSB — DX Calling', 'US', 0, 2, 'Long-distance SSB calling.'),

    # ───────────────────────────────── FEMA / Interop (monitor only) ──
    (155.340, 'FM', '20 kHz', 'Public Safety', 'HEAR — Hospital Emergency Admin Radio', 'US', 1, 4,
     'Monitored by many hospitals for mass-casualty coordination.'),
    (155.160, 'FM', '20 kHz', 'Public Safety', 'Search & Rescue (SAR) Intersystem', 'US', 1, 4,
     'Common SAR coordination frequency.'),
    (155.475, 'FM', '20 kHz', 'Public Safety', 'NLEEC — National Law Enforcement Emergency', 'US', 1, 4,
     'Interagency LE emergency. Monitor-only for civilians.'),
    (154.280, 'FM', '20 kHz', 'Public Safety', 'VFIRE21 — Fire Mutual Aid', 'US', 1, 4, 'Fire mutual aid.'),

    # ───────────────────────────────── Meshtastic (LoRa ISM) ──────────
    (906.875, 'LoRa', '250 kHz', 'ISM 902-928', 'Meshtastic LongFast (US default)', 'US', 0, 6,
     'LoRa PHY. Meshtastic default channel (LongFast). FCC Part 15 ISM — license-free.'),
    (869.525, 'LoRa', '250 kHz', 'ISM 863-870', 'Meshtastic EU 868 default', 'EU', 0, 6,
     'EU ISM band. Meshtastic default for Region 1.'),
]
