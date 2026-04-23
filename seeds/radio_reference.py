"""Radio quick-reference tables — CE-14 (v7.61).

Phonetic alphabets (NATO + civilian LAPD), International Morse (letters +
digits + prosigns), US voice procedure prowords, RST signal reporting
reference, and a digital-mode comparison card. All of this is static
reference data — no DB writes, no user editing. The ``tactical_comms``
blueprint imports these dicts and exposes them read-only via the API.

Sources: ITU-R M.1677 (Morse), ACP 125(F) (prowords), NIFOG, ARRL
Operating Manual, ITU-R SM.1138 (emission designators).
"""

# ──────────────────────────────────────────────────────────────────
# Phonetic Alphabet — NATO / ICAO standard (IATA-equivalent).
# ──────────────────────────────────────────────────────────────────
NATO_PHONETIC = {
    'A': 'Alfa',    'B': 'Bravo',   'C': 'Charlie', 'D': 'Delta',
    'E': 'Echo',    'F': 'Foxtrot', 'G': 'Golf',    'H': 'Hotel',
    'I': 'India',   'J': 'Juliett', 'K': 'Kilo',    'L': 'Lima',
    'M': 'Mike',    'N': 'November','O': 'Oscar',   'P': 'Papa',
    'Q': 'Quebec',  'R': 'Romeo',   'S': 'Sierra',  'T': 'Tango',
    'U': 'Uniform', 'V': 'Victor',  'W': 'Whiskey', 'X': 'X-ray',
    'Y': 'Yankee',  'Z': 'Zulu',
    '0': 'Zero',    '1': 'One',     '2': 'Two',     '3': 'Three',
    '4': 'Four',    '5': 'Five',    '6': 'Six',     '7': 'Seven',
    '8': 'Eight',   '9': 'Nine',
}

# LAPD / civilian phonetic — still widely used by US public-safety radio.
LAPD_PHONETIC = {
    'A': 'Adam',  'B': 'Boy',    'C': 'Charles', 'D': 'David',
    'E': 'Edward','F': 'Frank',  'G': 'George',  'H': 'Henry',
    'I': 'Ida',   'J': 'John',   'K': 'King',    'L': 'Lincoln',
    'M': 'Mary',  'N': 'Nora',   'O': 'Ocean',   'P': 'Paul',
    'Q': 'Queen', 'R': 'Robert', 'S': 'Sam',     'T': 'Tom',
    'U': 'Union', 'V': 'Victor', 'W': 'William', 'X': 'X-ray',
    'Y': 'Young', 'Z': 'Zebra',
}


# ──────────────────────────────────────────────────────────────────
# International Morse (ITU-R M.1677). "-" = dash, "." = dot.
# ──────────────────────────────────────────────────────────────────
MORSE_CODE = {
    'A': '.-',    'B': '-...',  'C': '-.-.',  'D': '-..',
    'E': '.',     'F': '..-.',  'G': '--.',   'H': '....',
    'I': '..',    'J': '.---',  'K': '-.-',   'L': '.-..',
    'M': '--',    'N': '-.',    'O': '---',   'P': '.--.',
    'Q': '--.-',  'R': '.-.',   'S': '...',   'T': '-',
    'U': '..-',   'V': '...-',  'W': '.--',   'X': '-..-',
    'Y': '-.--',  'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...',
    '8': '---..', '9': '----.',
    '.': '.-.-.-', ',': '--..--', '?': '..--..', "'": '.----.',
    '!': '-.-.--', '/': '-..-.',  '(': '-.--.',  ')': '-.--.-',
    '&': '.-...',  ':': '---...', ';': '-.-.-.', '=': '-...-',
    '+': '.-.-.',  '-': '-....-', '_': '..--.-', '"': '.-..-.',
    '@': '.--.-.',
}

# Morse prosigns (run-together signals — the space between tokens is omitted).
# Conventionally overlined; we render with `<>` as the wire format.
MORSE_PROSIGNS = [
    # (prosign, morse, meaning)
    ('<CT>', '-.-.-',   'Attention / commencing transmission (pre-message)'),
    ('<AR>', '.-.-.',   'End of message'),
    ('<K>',  '-.-',     'Invitation for any station to transmit ("go ahead")'),
    ('<KN>', '-.--.',   'Invitation for a specific station to transmit'),
    ('<BT>', '-...-',   'Break / new paragraph / section separator'),
    ('<SK>', '...-.-',  'End of contact / end of work'),
    ('<SOS>','...---...','International distress signal'),
    ('<AS>', '.-...',   'Wait / stand by (30 s implied)'),
    ('<HH>', '........','Error — ignore preceding'),
    ('<VA>', '...-.-',  'End of work (EU synonym for SK)'),
]


# ──────────────────────────────────────────────────────────────────
# US voice procedure prowords (ACP 125(F) / NIFOG).
# ──────────────────────────────────────────────────────────────────
PROWORDS = [
    # (proword, meaning, usage_example)
    ('ROGER',         'I have received your last transmission satisfactorily.',
     'Station A: "Move to RP Bravo, time now 1400, over." Station B: "Roger, out."'),
    ('WILCO',         'Will comply. Implies ROGER; never say "ROGER WILCO".',
     'Station A: "RTB, over." Station B: "Wilco, out."'),
    ('OVER',          'My transmission is complete; I expect a response. Never use with OUT.',
     '"Base, this is Patrol 1, sitrep follows, over."'),
    ('OUT',           'This transmission is complete; no response expected. Ends the exchange.',
     '"Base, out."'),
    ('COPY',          'I received and understood (informal ROGER). Common in US LE/fire.',
     'Dispatch: "10-4, copy."'),
    ('BREAK',         'Pause that separates text portions of a long transmission.',
     '"... inventory short on water BREAK medical supplies adequate BREAK..."'),
    ('BREAK BREAK',   'Priority interruption on an active net — yields for emergency traffic.',
     '"Break break — emergency traffic — fire at ..."'),
    ('SAY AGAIN',     'Repeat your last (all / from word X to word Y / after word X / before word X).',
     '"Say again from word Charlie."'),
    ('I SAY AGAIN',   'I am repeating my transmission (usually after SAY AGAIN request).',
     '"I say again, move to RP Bravo."'),
    ('CORRECTION',    'An error was made — disregard my previous and use what follows.',
     '"RP is Bravo, correction, RP is Delta."'),
    ('WAIT',          'Short pause — 5 sec or less. Followed by OUT or continuation.',
     '"Wait — checking the map. Over."'),
    ('WAIT OUT',      'I must pause more than 5 sec; I will call you back.',
     '"Wait out, 10 minutes."'),
    ('THIS IS',       'Identifies the calling station. First call always starts with the recipient.',
     '"Dispatch, this is Team Lead, over."'),
    ('AFFIRMATIVE',   'Yes. Prefer over AFFIRM or YES (clearer under noise).',
     '"Are you at the rally point? Over." "Affirmative. Over."'),
    ('NEGATIVE',      'No. Prefer over NEG or NO (clearer under noise).',
     '"Negative, taking alternate route. Over."'),
    ('FIGURES',       'Numbers will follow (disambiguates from a spoken word).',
     '"Figures six four, figures three seven, over."'),
    ('SPELL',         'I will now spell a word phonetically.',
     '"Last name spell: Sierra-Mike-India-Tango-Hotel."'),
    ('READ BACK',     'Repeat this entire transmission back to me verbatim for verification.',
     '"Coordinates follow, read back: figures 38 decimal 95, figures -77 decimal 04."'),
    ('VERIFY',        'Confirm the accuracy of what you just sent — I am not sure.',
     '"Verify grid reference, over."'),
    ('ACKNOWLEDGE',   'Let me know you received and understood this message.',
     '"Route change, acknowledge. Over."'),
    ('AUTHENTICATE',  'The station whose call follows must authenticate.',
     '"Team Lead, this is Base, authenticate Kilo-Delta, over."'),
    ('I AUTHENTICATE','Response to AUTHENTICATE — the authentication follows.',
     '"I authenticate November-Charlie."'),
    ('RELAY TO',      'Pass this message to the named station.',
     '"Relay to Patrol 2: RTB by 1800."'),
    ('UNKNOWN STATION', 'I cannot identify who I am hearing.',
     '"Unknown station calling Base, say again your call sign, over."'),
    ('DISREGARD',     'Ignore my previous transmission.',
     '"Disregard last, stand by."'),
    ('PRIORITY',      'This traffic takes precedence over ROUTINE.',
     '"Priority — minor injury, need medic at RP Bravo."'),
    ('IMMEDIATE',     'Mass casualty / imminent life safety — highest civilian priority.',
     '"Immediate — multiple casualties, need all units."'),
    ('FLASH',         'Presidential-level / extreme emergency. Reserved.',
     '(Not used in civilian nets.)'),
    ('EXECUTE',       'Carry out the order I just sent NOW.',
     '"Execute plan Alpha. Out."'),
    ('MAYDAY',        'Distress — life-threatening emergency. Repeat 3x.',
     '"Mayday, mayday, mayday — this is ..."'),
    ('PAN-PAN',       'Urgency — serious but not life-threatening. Repeat 3x.',
     '"Pan-pan, pan-pan, pan-pan — engine failure, position ..."'),
    ('SECURITE',      '(Say: say-cure-it-ay) Safety advisory — navigation or meteorological hazard. Repeat 3x.',
     '"Securite, securite, securite — debris in channel at ..."'),
]


# ──────────────────────────────────────────────────────────────────
# RST signal-report reference (Readability, Strength, Tone).
# Tone (T) is used only for CW / digital modes, not voice.
# ──────────────────────────────────────────────────────────────────
RST_READABILITY = [
    (1, 'Unreadable.'),
    (2, 'Barely readable, occasional words distinguishable.'),
    (3, 'Readable with considerable difficulty.'),
    (4, 'Readable with practically no difficulty.'),
    (5, 'Perfectly readable.'),
]

RST_STRENGTH = [
    (1, 'Faint signals, barely perceptible.'),
    (2, 'Very weak signals.'),
    (3, 'Weak signals.'),
    (4, 'Fair signals.'),
    (5, 'Fairly good signals.'),
    (6, 'Good signals.'),
    (7, 'Moderately strong signals.'),
    (8, 'Strong signals.'),
    (9, 'Extremely strong signals.'),
]

RST_TONE = [
    (1, 'Sixty-cycle AC or less, very rough and broad.'),
    (2, 'Very rough AC, very harsh and broad.'),
    (3, 'Rough AC tone, rectified but not filtered.'),
    (4, 'Rough note, some trace of filtering.'),
    (5, 'Filtered rectified AC but strongly ripple-modulated.'),
    (6, 'Filtered tone, definite trace of ripple modulation.'),
    (7, 'Near-pure tone, trace of ripple modulation.'),
    (8, 'Near-perfect tone, slight trace of modulation.'),
    (9, 'Perfect tone, no trace of ripple or modulation.'),
]


# ──────────────────────────────────────────────────────────────────
# Q-codes most useful to a field/ham operator.
# ──────────────────────────────────────────────────────────────────
Q_CODES = [
    ('QRM', 'Man-made interference on frequency.'),
    ('QRN', 'Natural / atmospheric noise (static).'),
    ('QRP', 'Low power — typically ≤ 5 W.'),
    ('QRO', 'High power — above 100 W.'),
    ('QRS', 'Send more slowly.'),
    ('QRQ', 'Send faster.'),
    ('QRT', 'Stop sending / close down station.'),
    ('QRU', 'I have nothing more for you ("no more traffic").'),
    ('QRV', 'I am ready to receive / ready to work.'),
    ('QRX', 'Wait / I will call again at (time).'),
    ('QRZ', 'Who is calling me?'),
    ('QSB', 'Signal is fading.'),
    ('QSL', 'Confirmed / I acknowledge receipt.'),
    ('QSO', 'A two-way contact / conversation.'),
    ('QSY', 'Change frequency to ...'),
    ('QTH', 'My location is ...'),
    ('QRA', 'My station name / operator name is ...'),
    ('CQ',  'General call — any station please respond.'),
    ('DE',  'Used between call signs to mean "from" ("N0CALL DE K1ABC").'),
    ('73',  'Best regards / end of contact cordial close.'),
    ('88',  'Love and kisses (affectionate close — use with care).'),
]


# ──────────────────────────────────────────────────────────────────
# Digital-mode comparison card — "what mode should I use when?"
# ──────────────────────────────────────────────────────────────────
DIGITAL_MODES = [
    # (name, category, typical_bandwidth, typical_freq, throughput,
    #  best_for, notes)
    ('CW (Morse)', 'Keying', '~150 Hz', 'All ham bands',
     '~20 WPM human; 60+ WPM automated',
     'Weakest-signal voice comms; minimal equipment; trained operator.',
     'License-class-restricted sub-bands. Strong under interference.'),

    ('FT8', 'Weak-signal', '50 Hz (3 kHz RX window)', '7.074 / 14.074 MHz',
     '6-byte message per 15 s',
     'DX on noisy bands with trace signals.',
     'Near-100% of HF DX contacts today. WSJT-X software.'),

    ('FT4', 'Weak-signal', '83 Hz', '7.0475 / 14.080 MHz',
     '6-byte message per 7.5 s',
     'Contests + fast weak-signal. 2x FT8 rate.',
     'Same software as FT8.'),

    ('JS8Call', 'Weak-signal', '50 Hz', '40m / 20m as custom',
     '~20-30 WPM text',
     'Keyboard-to-keyboard chat + store-and-forward relay.',
     'Built on FT8 framing. Good off-grid messaging.'),

    ('PSK31', 'Narrow-band', '31 Hz', '14.070 / 7.070 MHz',
     '~30 WPM text',
     'Keyboard-to-keyboard chat.',
     'Mostly superseded by FT8/JS8 in practice.'),

    ('RTTY', 'Teleprinter', '~270 Hz', '14.080 / 7.080 MHz',
     '45 baud (~60 WPM)',
     'Contests, traditional ham digital.',
     'Older but still active.'),

    ('VARA HF', 'Data', '500/1000/2000 Hz selectable', 'Winlink gateway freqs',
     '1-20 kbps adaptive',
     'Winlink email, file transfer over HF.',
     'Proprietary codec. Huge improvement over Pactor at similar cost.'),

    ('Pactor', 'Data', '500 Hz', 'Winlink gateway freqs',
     '~200-3200 bps',
     'Commercial Winlink email (older standard).',
     'Expensive modem; being replaced by VARA.'),

    ('APRS (AX.25)', 'Data / tracking', '12-15 kHz FM', '144.39 MHz NA / 144.80 EU',
     '1200 baud packet',
     'Position beacons, short messages, WX telemetry.',
     'TNC or phone app (APRSdroid, Pocket Packet). 1-min beacon typical.'),

    ('Winlink', 'Data / email', 'varies', 'Gateway-dependent',
     'email rate',
     'Email over radio (HF + VHF).',
     'Runs on top of VARA / Pactor / Packet. Free-to-use radio email network.'),

    ('DMR', 'Digital voice', '12.5 kHz', 'VHF / UHF',
     'voice + text data',
     'Wide repeater network (BrandMeister, TGIF).',
     'Vocoder AMBE+2. Needs code plug setup.'),

    ('D-STAR', 'Digital voice', '6.25 kHz', 'UHF mostly',
     'voice + low-rate data',
     'Icom-dominant ecosystem; integrated callsign routing.',
     'Proprietary AMBE vocoder.'),

    ('C4FM (Fusion)', 'Digital voice', '12.5 kHz', 'VHF / UHF',
     'voice + data',
     'Yaesu System Fusion. Mixes analog + digital repeater modes.',
     'Wires-X network.'),

    ('P25 Phase 1', 'Public safety', '12.5 kHz', 'Gov/PS bands',
     'voice + data',
     'US public-safety standard — monitor only for civilians.',
     'Trunked P25 systems require scanner with trunking.'),

    ('SSTV', 'Imagery', '3 kHz', '14.230 / 7.171 / 21.340 MHz',
     'picture every 8-110 s',
     'Slow-scan TV — single-image transmission.',
     'MMSSTV software. Worth tuning 14.230 MHz for ISS SSTV events.'),

    ('Meshtastic (LoRa)', 'Mesh data', '125/250/500 kHz', '906.875 US / 869.525 EU',
     '~12 kbps max (LongFast ~2 kbps)',
     'Off-grid text mesh — multi-hop, GPS, mobile app pairing.',
     'ISM band, license-free. Range ~miles with good antenna.'),
]


# ──────────────────────────────────────────────────────────────────
# HF band plans for US General-class license (summary)
# ──────────────────────────────────────────────────────────────────
HF_BAND_PLAN_US_GEN = [
    # (band, freq_range_mhz, modes, notes)
    ('160 m',  '1.800 - 2.000',  'CW / SSB / digital',
     'Winter DX; nighttime propagation.'),
    ('80 m',   '3.525 - 3.600 CW / 3.800 - 4.000 phone',
     'CW / SSB / digital',
     'Nighttime regional — ARES / RACES nets here.'),
    ('60 m',   '5.330 - 5.405 (5 discrete channels)',
     'USB only, 2.8 kHz max',
     'US secondary allocation — 5 fixed channels, 100 W PEP max.'),
    ('40 m',   '7.025 - 7.125 CW / 7.175 - 7.300 phone',
     'CW / SSB / digital',
     'Day regional, night DX. Heavy SWBC QRM at night.'),
    ('30 m',   '10.100 - 10.150',  'CW / digital only (no phone)',
     '200 W max in US. Winlink, FT8, WSPR here.'),
    ('20 m',   '14.025 - 14.150 CW / 14.225 - 14.350 phone',
     'CW / SSB / digital',
     'Best daytime DX band. Maritime Mobile net at 14.300.'),
    ('17 m',   '18.068 - 18.168', 'CW / SSB / digital', 'DX-friendly, less crowded.'),
    ('15 m',   '21.025 - 21.200 CW / 21.275 - 21.450 phone',
     'CW / SSB / digital', 'Daytime DX when solar high.'),
    ('12 m',   '24.890 - 24.990', 'CW / SSB / digital',
     'Opens with high solar flux.'),
    ('10 m',   '28.000 - 28.300 CW/dig / 28.300 - 29.700 phone',
     'CW / SSB / FM / digital',
     'Sporadic-E spring/summer; DX at solar peak; FM simplex 29.600.'),
]
