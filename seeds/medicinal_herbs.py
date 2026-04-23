"""Medicinal herbs expanded reference — CE-15 (v7.62).

Extends the 10 herbs originally hard-coded in ``medical_phase2.BUILTIN_HERBS``
to 50 entries covering most of the working temperate herbal pharmacopoeia.
Each entry follows the ``herbal_remedies`` table shape:

    (name, scientific_name, uses_json, preparation, dosing,
     contraindications_json, season, habitat)

``uses`` and ``contraindications`` are JSON-encoded lists so the DB column
stays as plain TEXT. Seeding merges with the existing inline list: rows
with names already present (Yarrow, Plantain, etc.) are skipped by the
``INSERT OR IGNORE`` logic, so the 10 existing entries stay authoritative
and only new names land.

Sources: King's American Dispensatory (Felter + Lloyd, 1898), Rosemary
Gladstar's "Medicinal Herbs: A Beginner's Guide" (2012), American Herbal
Products Association Botanical Safety Handbook (2nd ed), WHO Monographs on
Selected Medicinal Plants (vols 1-4), NIH NCCIH herb fact sheets.

**Safety disclaimer.** Herbal medicine is not a substitute for acute
emergency care. Contraindications listed here are non-exhaustive. Any
pregnant / nursing / pediatric / immune-compromised patient, or anyone on
prescription medication, should confer with a qualified clinician before
using any botanical preparation.
"""

import json


def _j(lst):
    """JSON-encode a python list for the TEXT column."""
    return json.dumps(lst)


# Every row is: (name, scientific_name, uses_json, preparation, dosing,
#                contraindications_json, season, habitat)
HERBS = [
    # ════ Existing in inline (BUILTIN_HERBS) — kept here for completeness.
    #      The _seed_* function uses INSERT OR IGNORE so these won't double.
    # ════════════════════════════════════════════════════════════════
    ('Yarrow', 'Achillea millefolium',
     _j(['wound healing', 'fever reduction', 'anti-inflammatory', 'hemostatic']),
     'Poultice for wounds; infusion for fever',
     'Tea: 1-2 tsp dried herb per cup, 3× daily. Fresh leaf poultice for cuts.',
     _j(['blood thinners', 'pregnancy', 'asteraceae allergy']),
     'summer', 'Fields, roadsides, disturbed soil — temperate zones worldwide'),

    ('Plantain', 'Plantago major',
     _j(['insect bites', 'bee stings', 'wound healing', 'anti-inflammatory', 'draws out splinters']),
     'Chew leaf and apply as poultice',
     'Apply fresh leaf directly to bite/wound. Replace every 1-2 hr.',
     _j([]),
     'all', 'Lawns, disturbed soil, sidewalks — globally invasive'),

    ('Elderberry', 'Sambucus nigra',
     _j(['immune support', 'cold/flu', 'antiviral', 'cough suppressant']),
     'Syrup from COOKED berries — raw berries are toxic',
     'Syrup 1 tbsp 4× daily during illness. Children: 1 tsp.',
     _j(['autoimmune conditions', 'raw berries toxic', 'stems + leaves cyanogenic']),
     'fall', 'Hedgerows, woodland edges, stream banks'),

    ('Echinacea', 'Echinacea purpurea',
     _j(['immune stimulant', 'wound healing', 'anti-inflammatory']),
     'Tincture or tea from root / flower',
     'Tincture 1-2 mL 3× daily; tea 1-2 tsp per cup.',
     _j(['autoimmune disorders', 'ragweed/asteraceae allergy', 'pregnancy']),
     'summer', 'Prairies, gardens — North American native'),

    ('Willow Bark', 'Salix alba',
     _j(['pain relief', 'fever reduction', 'anti-inflammatory', 'headache']),
     'Decoction of inner bark (salicin — precursor to aspirin)',
     '1-2 tsp bark per cup, simmer 10 min, 3× daily.',
     _j(['aspirin allergy', 'blood thinners', 'children < 16 (Reye syndrome)', 'pregnancy']),
     'spring', 'Near water — streambanks, wetlands'),

    ('Chamomile', 'Matricaria chamomilla',
     _j(['sleep aid', 'digestive', 'anti-anxiety', 'anti-inflammatory', 'teething']),
     'Tea from dried flowers',
     '1-2 tsp per cup, steep 5-10 min, up to 4× daily.',
     _j(['ragweed/asteraceae allergy']),
     'summer', 'Fields, gardens'),

    ('Calendula', 'Calendula officinalis',
     _j(['wound healing', 'antifungal', 'skin conditions', 'eczema']),
     'Salve or poultice from flowers',
     'Apply salve to affected skin 2-3× daily.',
     _j(['ragweed/asteraceae allergy', 'pregnancy']),
     'summer', 'Gardens'),

    ('Comfrey', 'Symphytum officinale',
     _j(['bone healing ("knit-bone")', 'sprains', 'bruises', 'tendon tears']),
     'Poultice from leaves — EXTERNAL USE ONLY',
     'Apply poultice to area, wrap, 2-3× daily. Never ingest.',
     _j(['NEVER INGEST — liver damage (pyrrolizidine alkaloids)',
         'do not apply to open wounds (risk of systemic absorption)', 'pregnancy']),
     'summer', 'Damp areas, gardens'),

    ('Garlic', 'Allium sativum',
     _j(['antibiotic', 'antiviral', 'blood pressure', 'immune support', 'cholesterol']),
     'Raw cloves, crushed + rested 10 min (allicin forms on crushing)',
     '2-3 raw cloves daily; poultice for skin infections.',
     _j(['blood thinners', 'surgery within 2 weeks', 'GI upset at high doses']),
     'all', 'Gardens'),

    ('Ginger', 'Zingiber officinale',
     _j(['nausea', 'digestive', 'anti-inflammatory', 'circulation', 'motion sickness']),
     'Tea from fresh root, candied, or standardized capsules',
     'Tea: 1 inch fresh root per cup; nausea: 250 mg capsule 4× daily.',
     _j(['blood thinners', 'gallstones', 'pregnancy > 1.5 g/day']),
     'all', 'Tropical; container gardens in temperate zones'),

    # ════ NEW (CE-15, v7.62) — 40 more ═════════════════════════════
    ('Peppermint', 'Mentha × piperita',
     _j(['digestive', 'headache (topical)', 'nausea', 'decongestant']),
     'Tea from leaves; essential oil diluted 1:10 for topical',
     'Tea 1 tsp/cup, steep 5 min; 3-5× daily. Essential oil: never internally.',
     _j(['GERD/hiatal hernia (worsens reflux)', 'infants (apnea risk from menthol)',
         'gallstones']),
     'summer', 'Moist soils, gardens'),

    ('Spearmint', 'Mentha spicata',
     _j(['digestive', 'nausea', 'breath freshener']),
     'Tea from leaves',
     'Tea 1 tsp/cup, 3× daily.',
     _j(['safer alternative to peppermint in pregnancy — still moderate in quantity']),
     'summer', 'Gardens'),

    ('Rosemary', 'Salvia rosmarinus',
     _j(['digestive', 'memory / cognitive', 'circulation', 'antifungal']),
     'Tea, culinary use, topical oil',
     'Tea 1 tsp/cup, up to 3× daily.',
     _j(['pregnancy (high dose)', 'seizure disorders']),
     'all', 'Mediterranean climate; perennial in zones 7+'),

    ('Sage', 'Salvia officinalis',
     _j(['sore throat', 'excessive sweating', 'memory', 'cough']),
     'Gargle (strong tea) for sore throat; culinary use',
     'Gargle: 1 tbsp/cup, steep 10 min; tea: 1 tsp/cup.',
     _j(['pregnancy / nursing (may reduce milk supply)', 'seizure disorders', 'high doses']),
     'all', 'Mediterranean; perennial in zones 4+'),

    ('Thyme', 'Thymus vulgaris',
     _j(['cough', 'antimicrobial', 'bronchitis', 'sore throat']),
     'Steam inhalation, tea, culinary',
     'Tea 1 tsp/cup, 3× daily. Steam: 1 tbsp in 2 cups boiling water.',
     _j(['pregnancy (high dose)', 'thyme allergy (rare)']),
     'all', 'Mediterranean; hardy to zone 5'),

    ('Oregano', 'Origanum vulgare',
     _j(['antimicrobial', 'upper respiratory', 'digestive']),
     'Tea, culinary, essential oil diluted 1:20 topical',
     'Tea 1 tsp/cup, 3× daily. Essential oil: dilute, never undiluted on skin.',
     _j(['pregnancy', 'iron absorption inhibitor (large doses)']),
     'all', 'Mediterranean; gardens'),

    ('Lavender', 'Lavandula angustifolia',
     _j(['sleep aid', 'anxiety', 'headache', 'burns (topical oil)']),
     'Tea, essential oil (topical), dried sachet',
     'Tea 1-2 tsp/cup. Topical oil neat on small burn only — otherwise 1:10 dilute.',
     _j(['pregnancy (internal use)', 'young boys (possible endocrine effect — controversial)']),
     'summer', 'Dry rocky gardens; perennial zones 5+'),

    ('Lemon Balm', 'Melissa officinalis',
     _j(['sleep aid', 'anxiety', 'cold sores (topical)', 'mild antiviral']),
     'Tea from fresh / dried leaves; topical salve for herpes simplex',
     'Tea 2 tsp/cup, 3-4× daily. Salve on cold sore at first tingle.',
     _j(['thyroid disorders (may suppress TSH)']),
     'all', 'Gardens; escapes readily'),

    ('Valerian', 'Valeriana officinalis',
     _j(['insomnia', 'anxiety', 'muscle relaxant']),
     'Tincture or tea from root',
     'Tincture 1-3 mL at bedtime; tea 1 tsp root, simmer 15 min.',
     _j(['pregnancy', 'CNS depressants (additive sedation)',
         'surgery within 1 week (discontinue)', 'driving / machinery']),
     'fall', 'Gardens; wild in damp meadows'),

    ('Passionflower', 'Passiflora incarnata',
     _j(['anxiety', 'insomnia', 'mild analgesic']),
     'Tincture or tea',
     'Tincture 1-4 mL 3× daily; tea 1-2 tsp/cup.',
     _j(['pregnancy (uterine stimulant)', 'MAOIs', 'CNS depressants']),
     'summer', 'South-central US; cultivated'),

    ('Skullcap', 'Scutellaria lateriflora',
     _j(['anxiety', 'nerve pain', 'muscle tension']),
     'Tincture or tea from aerial parts',
     'Tincture 1-2 mL 3× daily.',
     _j(['pregnancy', 'liver disease (rare hepatotoxicity reports)']),
     'summer', 'Meadows, marshes'),

    ('Hops', 'Humulus lupulus',
     _j(['insomnia', 'anxiety', 'appetite stimulant']),
     'Tea, pillow stuffing, tincture',
     'Tea 1 tsp/cup before bed. Tincture 1-2 mL at night.',
     _j(['depression (may worsen)', 'pregnancy', 'breast / hormone-sensitive conditions']),
     'fall', 'Rural cultivation; climbing vine'),

    ('Dandelion (root + leaf)', 'Taraxacum officinale',
     _j(['diuretic (leaf)', 'liver / gallbladder support (root)', 'digestive bitter', 'nutritive']),
     'Leaf as salad; root roasted as coffee substitute or decoction',
     'Root tea: 1 tsp dried/cup, simmer 10 min, 3× daily.',
     _j(['gallstones / bile duct obstruction', 'asteraceae allergy', 'K-sparing diuretics']),
     'spring', 'Lawns, meadows — invasive'),

    ('Burdock Root', 'Arctium lappa',
     _j(['blood purifier', 'skin conditions (eczema)', 'liver support']),
     'Decoction of root; edible (gobo)',
     '1 tsp dried root/cup, simmer 15 min, 3× daily.',
     _j(['pregnancy (uterine stimulant)', 'diabetes meds (blood sugar drop)']),
     'fall', 'Disturbed soil, roadsides'),

    ('Nettle (stinging)', 'Urtica dioica',
     _j(['allergy / hay fever', 'diuretic', 'joint pain', 'nutritive (high in iron + Ca + K)']),
     'Tea; young leaves steamed; tincture',
     'Tea 2 tsp dried/cup, 3× daily. Fresh leaves — cook before eating.',
     _j(['diuretics (additive)', 'K-sparing diuretics', 'fresh leaves sting']),
     'spring', 'Moist disturbed soil — globally invasive'),

    ('Mullein', 'Verbascum thapsus',
     _j(['cough', 'bronchitis', 'ear infection (oil topical)', 'respiratory']),
     'Tea from leaf; flower infused in olive oil for ear drops',
     'Tea 1 tsp dried leaf/cup, STRAIN TWICE (hairs irritate throat), 3× daily.',
     _j(['pregnancy (limited data)']),
     'summer', 'Disturbed soil, roadsides'),

    ('Horehound', 'Marrubium vulgare',
     _j(['cough', 'expectorant', 'bitter digestive']),
     'Tea, candied lozenges',
     'Tea 1-2 tsp/cup, 3× daily. Bitter — often candied.',
     _j(['pregnancy (uterine stimulant)', 'GI ulcers', 'diabetes meds']),
     'summer', 'Dry waste ground'),

    ('Goldenseal', 'Hydrastis canadensis',
     _j(['antimicrobial (topical + mucous membranes)', 'sore throat gargle', 'conjunctivitis']),
     'Decoction for gargle; tincture; root powder poultice',
     'Gargle: 1 tsp powder/cup hot water, gargle 3× daily. Tincture 1-2 mL 3× daily.',
     _j(['pregnancy', 'nursing', 'infants', 'hypertension', 'never use > 3 weeks straight',
         'at-risk species — use cultivated, not wild-harvested']),
     'summer', 'Hardwood forest understory (wild-harvesting imperils population)'),

    ('Goldenrod', 'Solidago canadensis',
     _j(['urinary tract infection', 'allergy (misunderstood — does NOT cause hay fever)',
         'diuretic']),
     'Tea from aerial parts',
     'Tea 2 tsp dried/cup, 3× daily. Drink plenty of water.',
     _j(['kidney failure (do not force diuresis)', 'asteraceae allergy']),
     'fall', 'Fields, roadsides — common in N. America'),

    ('Uva Ursi', 'Arctostaphylos uva-ursi',
     _j(['urinary antiseptic (short-term UTI)']),
     'Tea or tincture from leaves',
     'Tea 1 tsp/cup, up to 5 days. Never more than 5 days / not more than 5× per year.',
     _j(['pregnancy', 'children < 12', 'kidney disease', 'long-term use (hepatotoxic)']),
     'fall', 'Acidic soils, rocky woodlands'),

    ('Red Clover', 'Trifolium pratense',
     _j(['menopausal symptoms', 'bronchitis', 'skin conditions']),
     'Tea from flowers',
     'Tea 2 tsp dried flowers/cup, 3× daily.',
     _j(['blood thinners', 'hormone-sensitive conditions',
         'pregnancy', 'surgery within 2 wk']),
     'summer', 'Fields, meadows'),

    ('Raspberry Leaf', 'Rubus idaeus',
     _j(['uterine tonic (late pregnancy)', 'diarrhea', 'sore throat gargle']),
     'Tea from dried leaves',
     'Tea 1-2 tsp/cup, 2-3× daily. Late pregnancy: starting 3rd trimester only.',
     _j(['1st + 2nd trimester pregnancy — only take in 3rd trimester under midwife direction']),
     'summer', 'Bramble thickets'),

    ('Black Cohosh', 'Actaea racemosa',
     _j(['menopausal symptoms', 'menstrual cramps']),
     'Tincture or capsules from root',
     'Tincture 1-2 mL 2× daily; capsules per label.',
     _j(['pregnancy (except labor prep under midwife)', 'hormone-sensitive cancer',
         'hepatic disease (rare hepatotoxicity)']),
     'fall', 'Woodland understory, eastern N. America'),

    ('Blue Cohosh', 'Caulophyllum thalictroides',
     _j(['labor induction (traditional — risks known)', 'menstrual pain']),
     'Tincture or decoction of root',
     'Only under midwife supervision at term. Not for general use.',
     _j(['pregnancy EXCEPT labor prep under qualified midwife (cardiotoxic to fetus)',
         'hypertension', 'cardiac disease']),
     'fall', 'Rich woodland'),

    ('Shepherd\'s Purse', 'Capsella bursa-pastoris',
     _j(['postpartum hemorrhage', 'heavy menstruation', 'wound hemostatic (fresh)']),
     'Fresh tincture or strong tea',
     'Tincture 2-5 mL PRN bleeding. Fresh is stronger than dried.',
     _j(['hypertension', 'heart disease', 'pregnancy (uterine stimulant)']),
     'spring', 'Fields, lawns, disturbed soil — globally invasive'),

    ('Cramp Bark', 'Viburnum opulus',
     _j(['menstrual cramps', 'muscle spasm', 'threatened miscarriage (traditional)']),
     'Tincture or decoction of bark',
     'Tincture 2-4 mL 3× daily during cramps.',
     _j(['pregnancy (except threatened miscarriage under practitioner)',
         'kidney stones (contains oxalates)']),
     'fall', 'Moist woodland, streambanks'),

    ('Wild Lettuce', 'Lactuca virosa',
     _j(['mild analgesic', 'sedative', 'cough suppressant']),
     'Tincture or tea from dried aerial parts',
     'Tincture 1-2 mL at bedtime for sleep.',
     _j(['pregnancy', 'operating machinery', 'CNS depressants']),
     'summer', 'Disturbed soil'),

    ('Catnip', 'Nepeta cataria',
     _j(['colic (infants — very dilute)', 'anxiety', 'mild sedative']),
     'Tea from aerial parts',
     'Adult tea: 1 tsp/cup. Infant colic: very weak tea, 1 tsp given by dropper.',
     _j(['pregnancy (uterine stimulant)', 'heavy menstrual bleeding']),
     'summer', 'Gardens, roadsides'),

    ('Bee Balm', 'Monarda didyma',
     _j(['cold / flu', 'fever', 'sore throat gargle']),
     'Tea, gargle, compress',
     'Tea 1-2 tsp dried/cup, 3× daily.',
     _j(['pregnancy']),
     'summer', 'Gardens; wild in eastern woodlands'),

    ('Lemongrass', 'Cymbopogon citratus',
     _j(['fever', 'digestive', 'mild diuretic', 'insect repellent (citronella relative)']),
     'Tea from chopped stalk',
     'Tea 1 tbsp chopped/cup, 3× daily.',
     _j(['pregnancy (high dose)', 'lemongrass allergy']),
     'all', 'Tropical; container gardens temperate'),

    ('Mugwort', 'Artemisia vulgaris',
     _j(['digestive bitter', 'menstrual regulator', 'dream / lucid dreaming']),
     'Tea, tincture, moxa (moxibustion)',
     'Tea 1 tsp/cup; bitter — use sparingly.',
     _j(['pregnancy (uterine stimulant)', 'asteraceae allergy',
         'breastfeeding', 'seizure disorders (thujone)']),
     'summer', 'Disturbed soil, roadsides'),

    ('Wormwood', 'Artemisia absinthium',
     _j(['intestinal parasites', 'digestive bitter']),
     'Tincture only — short courses. Do not use > 4 weeks.',
     'Tincture 1 mL 3× daily, max 4 weeks.',
     _j(['pregnancy', 'nursing', 'seizure disorders (thujone neurotoxic)', 'renal impairment']),
     'summer', 'Dry waste ground'),

    ('Cayenne', 'Capsicum annuum',
     _j(['circulation', 'topical pain (capsaicin)', 'hemorrhage (traditional)']),
     'Tincture, powder, capsules, topical cream',
     '0.5 mL tincture 3× daily; topical cream per label.',
     _j(['active GI ulcers', 'hemorrhoids (topical worsens)', 'eyes / mucous membranes']),
     'all', 'Gardens (zones 5+ annual)'),

    ('Astragalus', 'Astragalus membranaceus',
     _j(['immune support (chronic / tonic)', 'anti-fatigue', 'adaptogen']),
     'Decoction of root; tincture; capsules',
     '1 tbsp dried root/cup, simmer 20 min, 3× daily. Not for acute infection.',
     _j(['acute infection (can worsen)', 'immunosuppressant drugs',
         'autoimmune disease']),
     'fall', 'TCM cultivation; US availability commercial'),

    ('Ashwagandha', 'Withania somnifera',
     _j(['adaptogen', 'stress / cortisol regulation', 'thyroid support']),
     'Root capsules; decoction',
     '300-600 mg standardized root extract daily.',
     _j(['pregnancy', 'thyroid meds (may raise T4)', 'nightshade allergy',
         'hyperthyroidism']),
     'all', 'Cultivated; Indian origin'),

    ('Holy Basil (Tulsi)', 'Ocimum tenuiflorum',
     _j(['adaptogen', 'stress', 'anti-inflammatory', 'blood sugar regulation']),
     'Tea from leaves; capsules',
     'Tea 1 tbsp dried leaves/cup, 3× daily.',
     _j(['pregnancy', 'blood thinners (mild antiplatelet)', 'hypothyroidism']),
     'summer', 'Gardens; perennial in tropics'),

    ('Turmeric', 'Curcuma longa',
     _j(['anti-inflammatory', 'joint pain', 'liver support', 'digestive']),
     'Culinary powder; capsules (curcumin standardized)',
     '500-1000 mg standardized curcumin 2-3× daily with black pepper / fat.',
     _j(['gallstones', 'blood thinners', 'surgery within 2 wk', 'pregnancy (high dose)']),
     'all', 'Tropical cultivation'),

    ('Slippery Elm', 'Ulmus rubra',
     _j(['sore throat', 'GERD / gastric ulcer', 'diarrhea', 'demulcent / mucilage']),
     'Powdered inner bark; lozenges; gruel',
     '1-2 tsp powder in warm water, 3× daily. Take 2 hr away from other meds.',
     _j(['may interfere with absorption of other meds',
         'pregnancy (inner bark OK; outer bark traditionally abortifacient)',
         'at-risk tree — use cultivated source']),
     'spring', 'Eastern N. America hardwood'),

    ('Marshmallow Root', 'Althaea officinalis',
     _j(['sore throat', 'gastric ulcer', 'urinary irritation', 'demulcent']),
     'Cold infusion (not hot — preserves mucilage)',
     '1 tbsp root in 1 cup cold water overnight; drink next day, 3× daily.',
     _j(['diabetes meds (lowers blood sugar)', 'may delay absorption of other meds']),
     'all', 'Moist meadow; gardens'),

    ('Mallow', 'Malva sylvestris',
     _j(['cough', 'skin inflammation', 'digestive demulcent']),
     'Cold infusion from leaves or flowers',
     '1 tbsp/cup cold water overnight; 3× daily.',
     _j([]),
     'summer', 'Disturbed soil, gardens'),

    ('Violet (Sweet)', 'Viola odorata',
     _j(['cough', 'lymphatic', 'skin inflammation', 'edible flower']),
     'Infused oil (topical); syrup; leaf tea',
     'Leaf tea 1 tbsp dried/cup, 3× daily.',
     _j(['seed + rhizome emetic — use leaves + flowers only']),
     'spring', 'Woodland edges; gardens'),

    ('Chickweed', 'Stellaria media',
     _j(['skin inflammation', 'itch', 'nutritive salad green']),
     'Fresh poultice; infused oil; raw in salad',
     'Fresh leaves + stems raw. Infused oil for skin.',
     _j(['pregnancy (large quantities)']),
     'spring', 'Gardens, disturbed soil — winter annual'),

    ('Cleavers (Bedstraw)', 'Galium aparine',
     _j(['lymphatic', 'mild diuretic', 'skin inflammation']),
     'Fresh juice; tincture; cold infusion',
     'Fresh juice 10 mL 3× daily (blend + strain); tincture 2-4 mL.',
     _j(['diabetes meds (may lower BG)']),
     'spring', 'Hedgerows, disturbed soil'),

    ('Yellow Dock', 'Rumex crispus',
     _j(['iron-deficiency anemia', 'constipation', 'skin conditions']),
     'Root tincture or decoction; syrup',
     'Tincture 2-3 mL 3× daily; syrup 1 tbsp daily.',
     _j(['kidney stones (oxalates)', 'pregnancy', 'iron overload conditions']),
     'fall', 'Pasture, roadsides'),

    ('Oregon Grape Root', 'Mahonia aquifolium',
     _j(['antimicrobial', 'digestive', 'skin (psoriasis, eczema topical)']),
     'Tincture; cream from bark alkaloids',
     'Tincture 2-3 mL 3× daily.',
     _j(['pregnancy', 'nursing', 'liver disease']),
     'fall', 'Woodland understory, Pacific NW'),

    ('Usnea', 'Usnea spp.',
     _j(['antimicrobial (strep, MRSA in vitro)', 'sore throat', 'skin infection (topical)']),
     'Tincture from lichen',
     'Tincture 2-3 mL 3× daily; topical diluted 1:3 for wound.',
     _j(['liver disease (rare hepatotoxicity with large doses)',
         'do not harvest without verified ID — many similar lichens are different species']),
     'all', 'Old-growth conifer forests'),

    ('St. John\'s Wort', 'Hypericum perforatum',
     _j(['mild to moderate depression', 'nerve pain (topical)', 'wound healing (topical oil)']),
     'Tincture, capsules, infused oil (red)',
     'Capsules: 300 mg standardized 3× daily, 4-6 wk minimum trial.',
     _j(['MANY DRUG INTERACTIONS — induces CYP enzymes and will reduce effect of oral contraceptives, warfarin, digoxin, SSRI (serotonin syndrome), tamoxifen, immunosuppressants. Check interactions before ANY other med.',
         'bipolar disorder (mania risk)', 'pregnancy', 'photosensitivity']),
     'summer', 'Dry pastures'),

    ('Kava', 'Piper methysticum',
     _j(['anxiety', 'muscle tension', 'insomnia (short-term)']),
     'Traditional water extract from root; standardized capsules',
     'Traditional: 1-3 cups kava drink; capsules 150-300 mg kavalactones.',
     _j(['liver disease', 'alcohol', 'driving', 'pregnancy',
         'long-term use (> 1 month — hepatotoxicity risk with ethanolic extracts)']),
     'all', 'South Pacific cultivation'),

    ('Ginkgo', 'Ginkgo biloba',
     _j(['cerebral circulation', 'tinnitus', 'cognitive support', 'peripheral circulation']),
     'Standardized 24/6 extract (capsule)',
     '120-240 mg standardized extract daily.',
     _j(['blood thinners (major bleeding risk)',
         'surgery within 2 wk', 'seizure disorders', 'raw seeds neurotoxic']),
     'fall', 'Cultivated ornamental'),

    ('Ginseng (American)', 'Panax quinquefolius',
     _j(['adaptogen', 'diabetes (mild blood sugar)', 'immune tonic']),
     'Root tincture, capsules, tea',
     'Tincture 2-4 mL 1-2× daily; capsules 200-400 mg.',
     _j(['MAOIs', 'blood thinners', 'diabetes meds (hypoglycemia)',
         'hormone-sensitive conditions', 'pregnancy', 'at-risk species in wild']),
     'fall', 'Eastern hardwood forest; cultivated'),

    ('Meadowsweet', 'Filipendula ulmaria',
     _j(['fever', 'pain (salicin)', 'GERD / gastric ulcer',
         'anti-inflammatory (gentler than willow)']),
     'Tea from aerial parts',
     'Tea 1 tsp dried/cup, 3× daily.',
     _j(['aspirin allergy', 'children < 16 (Reye syndrome)', 'blood thinners']),
     'summer', 'Wet meadows, streambanks'),
]
