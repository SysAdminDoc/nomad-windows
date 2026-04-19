"""Remaining reference data and SOPs — bulk roadmap items.

Covers: Medical Depth II, Water Quality, Community Health, Biosecurity,
Digital Asset Sovereignty, SOHO Business Continuity, Hardware Catalogs,
Environmental Monitoring, Foraging references.
"""

import json
import logging

from flask import Blueprint, request, jsonify
from db import db_session

remaining_refs_bp = Blueprint('remaining_refs', __name__)
_log = logging.getLogger('nomad.remaining_refs')


# ═══════════════════════════════════════════════════════════════════
# Medical Depth II — AA references
# ═══════════════════════════════════════════════════════════════════

@remaining_refs_bp.route('/api/reference/soap-note-template')
def api_soap_note():
    """AA2: SOAP note format template."""
    return jsonify({
        'format': {
            'S': {'label': 'Subjective', 'description': 'Patient\'s own words — chief complaint, history, symptoms',
                  'prompts': ['What happened?', 'Where does it hurt?', 'When did it start?', 'What makes it better/worse?', 'Pain scale 0-10?', 'Allergies?', 'Medications?']},
            'O': {'label': 'Objective', 'description': 'Measurable findings — vitals, physical exam, observations',
                  'prompts': ['Vitals: BP, HR, RR, SpO2, Temp', 'Mental status (AVPU or GCS)', 'Skin: color, moisture, turgor',
                              'Pupils: PERRL?', 'Breath sounds', 'Abdomen: soft/rigid, tenderness location', 'Extremities: pulses, sensation, motor']},
            'A': {'label': 'Assessment', 'description': 'Working diagnosis or problem list',
                  'prompts': ['Primary problem', 'Differential diagnoses', 'Severity (stable/unstable/critical)', 'Trend (improving/worsening/unchanged)']},
            'P': {'label': 'Plan', 'description': 'Treatment plan and follow-up',
                  'prompts': ['Interventions performed', 'Medications given (drug, dose, route, time)', 'Monitoring plan', 'Evacuation criteria', 'Follow-up timing']},
        },
    })


@remaining_refs_bp.route('/api/reference/improvised-splints')
def api_improvised_splints():
    """AA4: Improvised splint reference."""
    return jsonify({
        'principles': ['Splint in position found (don\'t straighten deformities in the field)',
                       'Immobilize joint above AND below fracture', 'Pad all bony prominences',
                       'Check circulation BEFORE and AFTER splinting (CSM: circulation, sensation, motor)',
                       'Elevate if possible', 'Apply cold if available (never directly on skin)'],
        'materials': {
            'rigid': ['SAM splint (moldable aluminum)', 'Sticks/branches (padded)', 'Cardboard', 'Magazines/newspapers (rolled)',
                      'Sleeping pad (folded)', 'Tent poles', 'Ski poles', 'Umbrella'],
            'soft': ['Pillow splint (tape pillow around injury)', 'Blanket roll', 'Clothing (stuffed jacket sleeve)',
                     'Sleeping bag', 'Sling and swathe (upper extremity)'],
            'buddy_splint': 'Tape injured finger to adjacent finger, or injured leg to uninjured leg',
            'traction': 'Improvised traction splint for femur: ski pole or branch + cravats. Pull to length of uninjured leg.',
        },
        'by_location': {
            'forearm': 'Rigid splint both sides, sling, swathe to chest',
            'upper_arm': 'Sling + swathe. If mid-shaft humerus, padded board medial and lateral',
            'lower_leg': 'Rigid splint both sides, pad ankle prominences, elevate',
            'femur': 'TRACTION SPLINT if mid-shaft. Do NOT use traction for hip/knee/ankle injuries',
            'ankle': 'Pillow splint or SAM splint. Figure-8 wrap with elastic bandage',
            'wrist': 'Volar (palm-side) splint to mid-forearm, hand in position of function',
            'finger': 'Buddy tape to adjacent finger with padding between',
            'clavicle': 'Sling + swathe. No figure-8 harness (outdated, increases pain)',
        },
    })


@remaining_refs_bp.route('/api/reference/ppe-doffing')
def api_ppe_doffing():
    """AA6: PPE doffing SOP — contamination prevention."""
    return jsonify({
        'sequence': [
            {'step': 1, 'action': 'Remove GLOVES first', 'method': 'Pinch outside of one glove, peel off. Hold in gloved hand. Slide finger under second glove, peel off enclosing first glove. Discard.',
             'why': 'Gloves are most contaminated — remove first to prevent hand contamination'},
            {'step': 2, 'action': 'Remove GOWN/COVERALL', 'method': 'Unfasten ties. Pull away from body, turning inside out as you remove. Roll into a bundle. Discard.',
             'why': 'Inside-out roll contains contamination on the inside'},
            {'step': 3, 'action': 'HAND HYGIENE', 'method': 'Wash hands or use alcohol-based sanitizer (60%+ alcohol)',
             'why': 'Critical barrier between contaminated and clean phases'},
            {'step': 4, 'action': 'Remove FACE SHIELD/GOGGLES', 'method': 'Lift from behind head (grab straps/arms, not front). Place in designated receptacle.',
             'why': 'Front surface contaminated — handle from back only'},
            {'step': 5, 'action': 'Remove MASK/RESPIRATOR', 'method': 'Grab bottom strap first, lift over head. Then top strap. Pull mask away from face. Discard.',
             'why': 'Bottom strap first prevents mask from snapping into face'},
            {'step': 6, 'action': 'FINAL HAND HYGIENE', 'method': 'Wash hands again',
             'why': 'Last defense against any contamination transferred during doffing'},
        ],
        'critical_errors': [
            'Touching the front of the mask with bare hands',
            'Pulling gown over head (should open/unfasten and roll down)',
            'Skipping hand hygiene between steps',
            'Touching face/eyes during doffing',
            'Rushing — slow and deliberate prevents errors',
        ],
        'buddy_system': 'Have a trained observer watch doffing and call out errors. This is standard in HAZMAT/infectious disease.',
    })


@remaining_refs_bp.route('/api/reference/decontamination')
def api_decontamination():
    """AA8: Decontamination product matrix."""
    return jsonify({
        'products': {
            'bleach_sodium_hypochlorite': {
                'concentration': '0.5% (1:10 dilution of household 5.25%)',
                'contact_time': '10 minutes',
                'effective_against': ['Bacteria', 'Viruses (incl. norovirus, COVID)', 'Fungi', 'Some spores'],
                'not_effective': ['Prions', 'Some chemical agents'],
                'notes': 'Most versatile. Degrades in sunlight — mix fresh daily. Corrosive to metals.',
            },
            'alcohol_70pct': {
                'concentration': '70% isopropyl or ethanol',
                'contact_time': '30 seconds',
                'effective_against': ['Most bacteria', 'Most viruses (enveloped)', 'TB'],
                'not_effective': ['Spores', 'Norovirus', 'Some non-enveloped viruses'],
                'notes': 'Fast-acting. Flammable. Evaporates — limited residual activity.',
            },
            'hydrogen_peroxide_3pct': {
                'concentration': '3% (pharmacy grade)',
                'contact_time': '10 minutes',
                'effective_against': ['Bacteria', 'Viruses', 'Fungi', 'Spores (extended contact)'],
                'notes': 'Gentle on surfaces. Decomposes to water + oxygen. Light-sensitive storage.',
            },
            'quaternary_ammonium': {
                'concentration': 'Per label (varies)',
                'contact_time': '10 minutes',
                'effective_against': ['Bacteria', 'Enveloped viruses', 'Fungi'],
                'not_effective': ['Non-enveloped viruses', 'Spores', 'TB'],
                'notes': 'Found in many household cleaners. Low toxicity. Residual activity on surfaces.',
            },
            'soap_and_water': {
                'concentration': 'Any soap',
                'contact_time': '20 seconds scrubbing',
                'effective_against': ['Physical removal of most pathogens', 'Disrupts viral envelopes'],
                'notes': 'ALWAYS the first step before chemical disinfection. Removes organic material that inactivates disinfectants.',
            },
        },
        'order_of_operations': [
            '1. Remove gross contamination (brush off, rinse with water)',
            '2. Wash with soap and water',
            '3. Apply appropriate disinfectant at correct concentration',
            '4. Maintain wet contact time (don\'t wipe off early)',
            '5. Allow to air dry or rinse after contact time',
        ],
    })


# ═══════════════════════════════════════════════════════════════════
# Water Quality — AC references
# ═══════════════════════════════════════════════════════════════════

@remaining_refs_bp.route('/api/reference/water-testing')
def api_water_testing():
    """AC1-AC6: Water quality testing and treatment reference."""
    return jsonify({
        'test_strip_workflow': {
            'parameters': ['pH (6.5-8.5)', 'Chlorine residual (0.2-2.0 ppm)', 'Hardness', 'Nitrate (<10 ppm)',
                           'Nitrite (<1 ppm)', 'Iron (<0.3 ppm)', 'Coliform (absent)'],
            'procedure': ['Collect sample in clean container', 'Dip strip, hold 15-30 sec',
                          'Compare to color chart in good light', 'Record results with date/source',
                          'Test at least quarterly for private wells'],
        },
        'well_yield_test': {
            'method': 'Pump test — run pump at max rate, measure gallons and time until well draws down',
            'formula': 'Yield (GPM) = gallons pumped / minutes to drawdown',
            'minimum_acceptable': '3-5 GPM for household use',
            'notes': 'Test during dry season for worst-case capacity. Re-test annually.',
        },
        'legionella_prevention': {
            'risk_factors': ['Water temperature 77-113°F (25-45°C)', 'Stagnant water in unused pipes',
                             'Biofilm buildup', 'Low disinfectant residual'],
            'prevention': ['Maintain hot water heater at 140°F (60°C) minimum',
                           'Flush unused taps weekly (2 min)', 'Clean and disinfect showerheads quarterly',
                           'Drain and clean water heater annually', 'If water has been stagnant >1 week, flush entire system before use'],
        },
        'cistern_maintenance': {
            'first_flush_sizing': 'Diverter volume = 1 gallon per 100 sqft of collection area',
            'cleaning_schedule': 'Inspect annually, clean every 2-3 years or when sediment exceeds 1 inch',
            'procedure': ['Drain cistern', 'Scrub walls with brush + bleach solution (1 cup per 5 gal)',
                          'Rinse thoroughly', 'Refill and add 1/4 tsp bleach per gallon for initial disinfection',
                          'Test pH and chlorine before use'],
        },
    })


# ═══════════════════════════════════════════════════════════════════
# Biosecurity — AR references
# ═══════════════════════════════════════════════════════════════════

@remaining_refs_bp.route('/api/reference/biosecurity')
def api_biosecurity():
    """AR1-AR7: Farm biosecurity reference."""
    return jsonify({
        'avian_flu_sop': {
            'signs': ['Sudden high mortality (>5% in 24h)', 'Swollen heads/combs', 'Purple discoloration', 'Drop in egg production',
                      'Respiratory distress', 'Watery diarrhea'],
            'immediate_actions': ['Isolate affected birds IMMEDIATELY', 'Report to state veterinarian (required by law)',
                                  'Restrict all farm access', 'Change clothes/boots between coops', 'Do NOT move birds off property'],
            'disinfection': 'Virkon S or 3% bleach on all surfaces, boots, equipment. Virus survives weeks in manure.',
        },
        'biosecurity_zones': {
            'clean': 'Office, house, vehicle parking — no animal contact',
            'transition': 'Boot wash, coverall change, hand wash station — MANDATORY between zones',
            'production': 'Animal housing, pasture, feed storage — restricted access',
            'isolation': 'New animals 21-day quarantine before joining flock/herd — separate water/feed systems',
        },
        'quarantine_protocol': {
            'duration': '21 days minimum for new livestock',
            'requirements': ['Separate housing ≥30 feet from existing animals', 'Separate waterers and feeders',
                             'Dedicated boots/coveralls for quarantine area', 'Feed quarantine animals LAST (don\'t carry pathogens back)',
                             'Daily health observation + temperature log', 'Fecal testing before release'],
        },
        'vaccination_calendar': {
            'poultry': {'mareks': 'Day 1 (hatchery)', 'newcastle': '14 days, boost 6 weeks', 'fowl_pox': '8-12 weeks'},
            'goats': {'cdt': '4 weeks before kidding (does), kids at 6-8 weeks + boost 4 weeks later', 'rabies': 'Annually'},
            'cattle': {'blackleg_cdt': '2-4 months, boost 4 weeks, annual', 'brucellosis': 'Heifers 4-12 months (state program)'},
            'dogs': {'rabies': '12-16 weeks, boost 1 year, then every 3 years', 'dhpp': '6-8 weeks, q3-4 weeks to 16 weeks, annual'},
        },
    })


# ═══════════════════════════════════════════════════════════════════
# Digital Asset Sovereignty — AP references
# ═══════════════════════════════════════════════════════════════════

@remaining_refs_bp.route('/api/reference/digital-assets')
def api_digital_assets():
    """AP1-AP7: Digital asset sovereignty reference."""
    return jsonify({
        'seed_vault_guide': {
            'bip39': 'Standard 12-24 word recovery phrase for Bitcoin/Ethereum wallets',
            'slip39': 'Shamir backup — split seed into M-of-N shares (use NOMAD\'s Shamir vault)',
            'storage': ['Stamp/engrave on titanium/steel plate (fire/water proof)', 'Store in fireproof safe',
                        'Geographic distribution: keep shares in different locations', 'NEVER photograph or type into a computer'],
        },
        'hardware_wallet_ledger': {
            'fields': ['Device model', 'Serial number', 'Firmware version', 'Accounts/chains supported',
                       'Location stored', 'PIN backup location', 'Recovery phrase location'],
            'best_practices': ['Update firmware on air-gapped computer', 'Verify receive addresses on device screen',
                               'Test recovery procedure with small amount before storing large value'],
        },
        'crypto_estate_plan': {
            'steps': ['Document all wallets, exchanges, and accounts', 'Create dead-man\'s switch for heir notification (use NOMAD\'s warrant canary)',
                      'Shamir-split master recovery phrases (3-of-5 recommended)', 'Distribute shares to trusted parties with sealed instructions',
                      'Include step-by-step recovery instructions for non-technical heirs',
                      'Update annually or after any wallet/exchange change'],
        },
        'two_factor_reset_kit': {
            'backup_codes': 'Print and store backup codes for every 2FA-protected account',
            'authenticator_backup': 'Export authenticator seeds (Aegis, Authy) to encrypted backup',
            'hardware_keys': 'Register at least 2 FIDO2 keys per account — keep backup key in separate location',
            'recovery_emails': 'Use a dedicated recovery email that is NOT your daily driver',
        },
    })


# ═══════════════════════════════════════════════════════════════════
# SOHO Business Continuity — AQ references
# ═══════════════════════════════════════════════════════════════════

@remaining_refs_bp.route('/api/reference/business-continuity')
def api_business_continuity():
    """AQ1-AQ6: SOHO business continuity reference."""
    return jsonify({
        'client_notification_cascade': {
            'template': 'Due to [event], our operations are [status]. Expected return: [date]. For urgent matters: [contact].',
            'channels': ['Email blast (pre-drafted, ready to send)', 'Voicemail/auto-attendant update',
                         'Website banner', 'Social media post', 'Key client personal calls'],
            'timing': 'Within 4 hours of decision to activate. Update every 24 hours until resolved.',
        },
        'revenue_buffer': {
            'formula': 'Monthly expenses × target months = buffer needed',
            'tiers': {'survival': 1, 'basic': 3, 'standard': 6, 'resilient': 12},
            'note': 'Include: rent/mortgage, utilities, insurance, payroll, loan payments, taxes',
        },
        'workstation_redundancy': {
            'tier1_essential': ['Laptop with all software', 'Phone with hotspot', 'Cloud backup access', 'VPN credentials'],
            'tier2_productive': ['External monitor', 'Printer/scanner', 'UPS/battery backup', 'Separate internet connection'],
            'tier3_full_capability': ['Duplicate of primary workstation at secondary location', 'NAS/server backup',
                                      'Dedicated phone line', 'Full office supplies'],
        },
        'coop_plan_template': {
            'sections': ['Essential functions list', 'Delegation of authority chain',
                         'Order of succession (who takes over what)', 'Alternate operating locations',
                         'Vital records and databases (location + backup)', 'Communication plan (internal + external)',
                         'Reconstitution plan (return to normal operations)'],
        },
        'offline_invoice_archive': {
            'what_to_archive': ['Last 7 years of invoices (IRS requirement)', 'All contracts and agreements',
                                'Tax returns', 'Bank statements', 'Insurance policies'],
            'format': 'PDF on encrypted USB drive, updated quarterly',
            'storage': 'Fireproof safe + offsite copy (safety deposit box or trusted party)',
        },
    })


# ═══════════════════════════════════════════════════════════════════
# Hardware Reference Catalogs — U1-U7
# ═══════════════════════════════════════════════════════════════════

@remaining_refs_bp.route('/api/reference/hardware-catalogs')
def api_hardware_catalogs():
    """U1-U7: Hardware reference catalogs for off-grid equipment."""
    return jsonify({
        'generators': {
            'types': {
                'portable_gas': {'power_w': '1000-12000', 'fuel': 'Gasoline', 'runtime_h': '4-12', 'noise_db': '60-80', 'use': 'Emergency backup, camping'},
                'portable_dual': {'power_w': '3000-12000', 'fuel': 'Gas + propane', 'runtime_h': '6-18', 'noise_db': '55-75', 'use': 'Flexible fuel supply'},
                'inverter': {'power_w': '1000-7000', 'fuel': 'Gasoline', 'runtime_h': '4-18', 'noise_db': '48-65', 'use': 'Clean power for electronics'},
                'standby': {'power_w': '7000-150000', 'fuel': 'Natural gas / propane', 'runtime_h': 'Unlimited (piped)', 'noise_db': '55-70', 'use': 'Whole-house automatic'},
                'diesel': {'power_w': '5000-50000', 'fuel': 'Diesel', 'runtime_h': '24-72', 'noise_db': '65-85', 'use': 'Long-duration, heavy loads'},
            },
            'sizing': 'Add up critical load watts × 1.25 safety margin. Motor loads (fridge, pump) need 3× starting watts.',
        },
        'water_pumps': {
            'types': {
                'hand_pump': {'depth_ft': '0-200', 'gpm': '2-5', 'power': 'Manual', 'use': 'Shallow-medium wells, grid-down'},
                'solar_dc': {'depth_ft': '0-600', 'gpm': '1-10', 'power': '100-1500W solar', 'use': 'Off-grid wells'},
                'jet_pump': {'depth_ft': '0-25', 'gpm': '5-25', 'power': '120/240V AC', 'use': 'Shallow wells/springs'},
                'submersible': {'depth_ft': '25-1000', 'gpm': '5-50', 'power': '240V AC', 'use': 'Deep wells'},
                'ram_pump': {'depth_ft': 'Gravity-fed', 'gpm': '0.5-5', 'power': 'None (hydraulic)', 'use': 'Stream/spring with fall'},
            },
        },
        'inverters': {
            'types': {
                'modified_sine': {'efficiency': '85-90%', 'cost': 'Low', 'compatible': 'Lights, tools, heaters', 'not_compatible': 'Sensitive electronics, motors with capacitors'},
                'pure_sine': {'efficiency': '90-95%', 'cost': 'Medium', 'compatible': 'Everything', 'not_compatible': 'N/A — universal'},
                'hybrid_inverter': {'efficiency': '93-97%', 'cost': 'High', 'compatible': 'Grid-tie + battery + solar', 'not_compatible': 'N/A'},
            },
            'sizing': 'Continuous watts ≥ total load. Surge watts ≥ largest motor starting load × 3.',
        },
    })


# ═══════════════════════════════════════════════════════════════════
# Environmental Monitoring — Z references
# ═══════════════════════════════════════════════════════════════════

@remaining_refs_bp.route('/api/reference/environmental-monitoring')
def api_environmental_monitoring():
    """Z1-Z6: Environmental monitoring reference."""
    return jsonify({
        'indoor_air': {
            'parameters': {
                'co2_ppm': {'good': '<1000', 'moderate': '1000-2000', 'poor': '>2000', 'action': 'Open windows, improve ventilation'},
                'pm25': {'good': '<12 µg/m³', 'moderate': '12-35', 'unhealthy': '>35', 'action': 'Run HEPA filter, seal gaps from outdoor smoke'},
                'co_ppm': {'safe': '<9', 'warning': '9-35', 'danger': '>35', 'action': 'EVACUATE, ventilate, identify source'},
                'humidity_pct': {'low': '<30%', 'ideal': '30-50%', 'high': '>60%', 'action': 'Dehumidify to prevent mold'},
                'radon': {'safe': '<2 pCi/L', 'action_level': '4 pCi/L', 'action': 'Install mitigation system, seal basement cracks'},
            },
        },
        'mold_risk': {
            'dew_point_formula': 'Mold risk HIGH when surface temperature drops below dew point (condensation forms)',
            'risk_zones': ['Behind furniture against exterior walls', 'Window sills and frames', 'Bathroom ceiling',
                           'Under sinks', 'Crawl spaces', 'Around HVAC ducts in unconditioned spaces'],
            'prevention': ['Keep humidity below 60% (ideally 30-50%)', 'Fix leaks within 24 hours',
                           'Exhaust fans in bathrooms and kitchen', 'Don\'t carpet basements'],
        },
        'heritage_hazards': {
            'lead_paint': {'homes_at_risk': 'Built before 1978', 'testing': 'EPA-certified lead test kits ($10-30)',
                           'action': 'Don\'t sand/scrape — wet methods only. Encapsulate or professional abatement.'},
            'asbestos': {'common_locations': 'Pipe insulation, floor tiles (9x9"), popcorn ceiling, vermiculite insulation',
                         'action': 'Do NOT disturb. If intact, leave in place and monitor. Professional removal if damaged.'},
            'well_water_lead': {'risk': 'Lead solder in pipes (pre-1986), brass fixtures',
                                'testing': 'First-draw sample after 6+ hours stagnation', 'action_level': '15 ppb'},
        },
    })


# ═══════════════════════════════════════════════════════════════════
# Community Health — AD references
# ═══════════════════════════════════════════════════════════════════

@remaining_refs_bp.route('/api/reference/community-health')
def api_community_health():
    """AD1-AD9: Community health surveillance reference."""
    return jsonify({
        'pod_health_pulse': {
            'description': 'Daily 2-minute health check-in per household in your pod',
            'questions': ['Anyone sick today? (Y/N)', 'New symptoms in last 24h? (Y/N)',
                          'Medication supply adequate? (Y/N)', 'Morale (1-5 scale)', 'Any safety concerns?'],
            'aggregation': 'Compile responses — watch for clusters (3+ sick in same area/timeframe)',
        },
        'phq2_screening': {
            'description': 'Patient Health Questionnaire-2 — ultra-brief depression screen',
            'questions': [
                'Over the last 2 weeks, how often have you been bothered by: little interest or pleasure in doing things?',
                'Over the last 2 weeks, how often have you been bothered by: feeling down, depressed, or hopeless?',
            ],
            'scoring': {'0': 'Not at all', '1': 'Several days', '2': 'More than half the days', '3': 'Nearly every day'},
            'interpretation': 'Score ≥3 = positive screen → follow up with PHQ-9 or clinical assessment',
            'note': 'Screening tool only — not a diagnosis. Use for community wellness monitoring.',
        },
        'k6_screening': {
            'description': 'Kessler K6 — 6-item psychological distress scale',
            'questions': [
                'During the past 30 days, how often did you feel: nervous?',
                'hopeless?', 'restless or fidgety?', 'so depressed nothing could cheer you up?',
                'that everything was an effort?', 'worthless?',
            ],
            'scoring': {'0': 'None', '1': 'A little', '2': 'Some', '3': 'Most', '4': 'All of the time'},
            'interpretation': 'Score ≥13 (of 24) = serious psychological distress → refer for support',
        },
    })
