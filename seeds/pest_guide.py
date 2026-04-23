"""Garden pest + disease guide seed data — CE-16 (v7.60).

Seeds ``pest_guide`` with the most common temperate / subtropical vegetable
garden pests and diseases. Treatment favors IPM (Integrated Pest
Management) — biological/cultural controls first, low-toxicity second,
synthetic pesticides as a last resort.

Schema (from db.py):
    (name, pest_type, affects, symptoms, treatment, prevention, image_url)

Sources: UC IPM Pest Notes, Cornell Cooperative Extension, OSU Extension
vegetable IPM, Utah State University pest fact sheets.
"""

# (name, pest_type, affects, symptoms, treatment, prevention, image_url)
PESTS = [
    # ─────────────────────────── Insects ──────────────────────────────
    ('Aphid', 'insect',
     'Nearly all soft tissue — tomato, pepper, brassicas, lettuce, fruit trees',
     'Clusters on stems + leaf undersides; honeydew + sooty mold; curled, yellowing leaves; stunted new growth.',
     'Strong water spray dislodges; release ladybugs / lacewings; insecticidal soap on heavy infestations; neem oil as last resort.',
     'Reflective mulch confuses winged forms; interplant chives, garlic, catnip; avoid over-fertilizing with N.',
     ''),

    ('Whitefly', 'insect',
     'Tomato, pepper, cucumber, squash, beans, sweet potato',
     'Tiny white moths lift off when plant disturbed; sticky honeydew + sooty mold on leaves; yellowing lower leaves.',
     'Yellow sticky traps; vacuum + blast with water early morning when torpid; insecticidal soap + neem; parasitic wasp Encarsia formosa in greenhouse.',
     'Reflective mulch; remove heavily infested lower leaves; keep weeds down around plot.',
     ''),

    ('Cabbage White Butterfly / Cabbage Worm', 'insect',
     'Cabbage, broccoli, kale, Brussels sprouts, collards, cauliflower',
     'White butterfly with black wing tips; velvety green caterpillars bore into heads; frass (green droppings) on leaves.',
     'Handpick caterpillars daily; Bt (Bacillus thuringiensis) spray; row cover until plants mature; spinosad on heavy pressure.',
     'Row cover from transplant; interplant dill / thyme / rosemary; plant nasturtium as trap crop.',
     ''),

    ('Cabbage Looper', 'insect',
     'Brassicas, lettuce, spinach, tomato, potato',
     'Light green caterpillar that loops its back when it walks; chews large irregular holes in leaves.',
     'Same as cabbage white: Bt, handpicking, spinosad.',
     'Row cover; encourage trichogramma wasps with dill / fennel flowers.',
     ''),

    ('Colorado Potato Beetle', 'insect',
     'Potato, tomato, eggplant, pepper',
     'Yellow + black striped adults; orange soft-body larvae underside of leaves; orange egg clusters; skeletonized leaves.',
     'Handpick + drop in soapy water daily; spinosad or Bt var. tenebrionis; rotate crops far from last year\'s potatoes.',
     '3-year rotation away from nightshades; trench-trap barriers; catnip / horseradish / tansy borders.',
     ''),

    ('Tomato Hornworm', 'insect',
     'Tomato, pepper, eggplant, potato',
     'Large (3-4 in) green caterpillar with white V-stripes + horn; defoliates branches overnight; black-green droppings.',
     'Handpick (size makes easy); leave hornworms bearing white rice-grain parasitoid wasp cocoons (Cotesia) in place.',
     'Till in fall to destroy overwintering pupae; interplant basil + borage; encourage braconid wasps with dill / parsley flowers.',
     ''),

    ('Squash Vine Borer', 'insect',
     'Summer + winter squash, pumpkin, zucchini, gourd',
     'Clear-wing orange moth lays eggs at base of vine; larvae burrow inside stem; sudden wilt with frass piles at stem base.',
     'Slit stem lengthwise at frass site, extract + crush larva, bury stem for adventitious roots; inject Bt with syringe into stem early.',
     'Row cover until female flowers open; wrap stems with foil collar; plant butternut / tromboncino (resistant); trap with yellow bowls of water.',
     ''),

    ('Squash Bug', 'insect',
     'Squash, pumpkin, gourd, cucumber, melon',
     'Gray-brown shield-shape adults; copper egg clusters on leaf undersides; gray stinky nymphs; leaves yellow then collapse.',
     'Crush eggs daily; vacuum adults at dawn; place board at night + destroy congregated bugs in morning; neem oil on nymphs only.',
     'Resistant butternut squash; companion plant nasturtium + marigold; remove all vine debris at end of season.',
     ''),

    ('Cucumber Beetle (striped + spotted)', 'insect',
     'Cucumber, squash, melon, pumpkin, beans, corn',
     'Yellow + black striped OR spotted beetles chew leaves + flowers; transmit bacterial wilt + mosaic virus.',
     'Row cover until female flowers open; yellow sticky traps; pyrethrin for severe infestation; kaolin clay spray.',
     'Delayed planting; interplant radish + nasturtium; resistant varieties (\'County Fair\', \'Saladin\').',
     ''),

    ('Mexican Bean Beetle', 'insect',
     'Bush + pole beans, cowpea, soybean',
     'Coppery-orange ladybug lookalike with 16 black spots; yellow spined larvae skeletonize leaves.',
     'Handpick adults + crush eggs; release Pediobius wasp (commercial); row cover; spinosad.',
     'Plant early before emergence; interplant marigold + summer savory; rotate yearly.',
     ''),

    ('Flea Beetle', 'insect',
     'Brassicas, eggplant, potato, tomato, beet, radish',
     'Tiny black beetles jump like fleas when disturbed; shotgun-hole pattern of pinholes in leaves.',
     'Row cover until plants are established; yellow sticky cards; kaolin clay spray; diatomaceous earth around stems.',
     'Radish as trap crop; till fall debris to destroy overwintering adults; plant late after peak emergence.',
     ''),

    ('Thrips', 'insect',
     'Onion, garlic, bean, pepper, tomato',
     'Tiny slender yellow-brown insects in blossoms + under leaves; silvery streaks + black frass specks; distorted growth; vector of tomato spotted wilt.',
     'Blue sticky traps (thrips prefer blue over yellow); insecticidal soap; spinosad; release Orius minute pirate bug.',
     'Avoid over-fertilizing; reflective mulch; remove weed hosts.',
     ''),

    ('Spider Mite', 'insect',
     'Tomato, bean, strawberry, raspberry, most fruit trees',
     'Fine webbing on leaf undersides; stippled yellow speckles on upper leaves; leaves dry out + drop; worst in hot dry weather.',
     'Strong water spray under leaves every 3 days; insecticidal soap; release predatory mite Phytoseiulus persimilis.',
     'Overhead irrigation (mites hate humidity); avoid dusty conditions; don\'t over-fertilize N.',
     ''),

    ('Japanese Beetle', 'insect',
     'Roses, beans, grapes, raspberry, basil, many fruit trees',
     'Metallic green-copper beetles cluster on leaves + flowers; skeletonized lacy leaves; grubs (larvae) damage turf roots.',
     'Handpick into soapy water early morning when torpid; milky spore bacteria on lawn for grubs; kaolin clay on foliage.',
     'Avoid pheromone traps (they attract more than they kill); beneficial nematodes for grubs; resistant plants (lilac, forsythia, dogwood).',
     ''),

    ('Corn Earworm / Tomato Fruitworm', 'insect',
     'Corn, tomato, pepper, bean',
     'Moth lays single eggs on silk / fruit; green-pink caterpillar bores into corn tip or tomato fruit near stem.',
     'Mineral oil drop on silk 4-6 days after silk emergence; Bt spray on silk; pick affected fruits early.',
     'Tight-husked varieties (\'Silver Queen\', \'Country Gentleman\'); trichogramma wasp release; plant dill / fennel for parasitoids.',
     ''),

    ('Slug / Snail', 'mollusk',
     'Lettuce, hosta, strawberry, seedlings, cabbage',
     'Silvery slime trails; ragged holes with smooth edges on leaves; fresh damage overnight.',
     'Beer trap (sink container flush with soil); copper tape perimeter; iron phosphate bait (Sluggo, pet-safe); handpick after dark.',
     'Remove boards / pots / debris (daytime hides); rough mulch like crushed egg shell or diatomaceous earth; ducks + chickens.',
     ''),

    ('Leafminer', 'insect',
     'Spinach, chard, beet, pepper, tomato',
     'Serpentine white/tan tunnels between leaf surfaces; damage cosmetic unless heavy.',
     'Remove + destroy affected leaves; encourage parasitic wasps (Diglyphus) with dill / yarrow flowers.',
     'Row cover; rotate brassicas + chenopods.',
     ''),

    ('Earwig', 'insect',
     'Seedlings, corn silk, dahlia, soft fruit',
     'Pincers on rear; chew ragged holes in petals + seedlings at night; hide by day in crevices.',
     'Roll of damp newspaper as trap (destroy each morning); oil + soy sauce jar trap; tangle foot around stems.',
     'Remove garden debris + untidy mulch; thin plantings; sluggo plus bait.',
     ''),

    ('Root-Knot Nematode', 'nematode',
     'Tomato, carrot, okra, cucumber, pepper, beans',
     'Stunted, wilting, yellowing above ground; galls / swellings on roots when plant pulled.',
     'No rescue once established in a season; solarize soil (clear plastic 6 wk mid-summer); rotate to non-hosts.',
     'French marigold cover crop 2-3 months; add compost; plant resistant varieties (label \'N\' or \'VFN\').',
     ''),

    # ─────────────────────────── Diseases ─────────────────────────────
    ('Early Blight (Alternaria)', 'disease',
     'Tomato, potato',
     'Brown concentric-ring spots on lower older leaves first; yellowing + leaf drop; stem lesions near soil line.',
     'Remove affected leaves immediately; copper fungicide for persistent infection; avoid overhead watering.',
     '3-year rotation; mulch to prevent soil splash; resistant varieties (\'Iron Lady\', \'Mountain Magic\'); stake + prune for airflow.',
     ''),

    ('Late Blight (Phytophthora)', 'disease',
     'Tomato, potato',
     'Water-soaked gray-green patches spread rapidly in cool wet weather; white fuzz on underside; fruit develops greasy brown patches.',
     'Remove + destroy affected plants (bag, do NOT compost); copper fungicide preventive only; harvest remaining green fruit.',
     'Resistant varieties (\'Mountain Magic\', \'Defiant\', \'Jasper\'); don\'t plant near potato; avoid overhead watering; mulch.',
     ''),

    ('Powdery Mildew', 'disease',
     'Squash, cucumber, melon, pumpkin, rose, grape, zinnia',
     'White flour-like coating on leaves (upper first); yellowing + premature leaf drop; stunted new growth.',
     'Milk spray (1:9 milk:water) weekly; potassium bicarbonate; neem oil; sulfur (not in hot weather).',
     'Resistant varieties; space for airflow; morning overhead water (splashing knocks spores off); avoid over-fertilizing N.',
     ''),

    ('Downy Mildew', 'disease',
     'Cucumber, basil, lettuce, squash, onion',
     'Yellow angular patches bounded by leaf veins on upper surface; gray-purple fuzz on leaf underside; rapid defoliation.',
     'Copper fungicide preventively; remove infected leaves; rogue severely affected plants.',
     'Resistant varieties; avoid wet leaves at night; prune for airflow; 2-year rotation.',
     ''),

    ('Fusarium Wilt', 'disease',
     'Tomato, cucumber, watermelon, banana, cotton',
     'One side of plant wilts during heat of day; lower leaves yellow then brown; vascular tissue stains brown when stem cut.',
     'No cure; pull + destroy plant; do not compost; soil remains infected for years.',
     'Resistant (VFN-labeled) varieties; solarize beds; avoid root damage during cultivation; rotate 4+ years.',
     ''),

    ('Verticillium Wilt', 'disease',
     'Tomato, potato, strawberry, cucumber, raspberry, maple',
     'V-shape yellow wedges on lower leaves; wilt + recovery + eventual collapse; brown vascular streaks; slow decline vs Fusarium\'s rapid.',
     'Remove + destroy affected plants; soil remains infected decades; switch bed to resistant species.',
     'Resistant varieties (VFN label); soil solarization; don\'t plant potato near strawberry / brassicas.',
     ''),

    ('Blossom-End Rot', 'disease',
     'Tomato, pepper, squash, watermelon',
     'Dark sunken leathery patch at blossom end of fruit; not a pest — calcium deficiency + uneven water.',
     'Not reversible on affected fruit — pick + discard. Mulch + even water for next fruit set.',
     'Even moisture (drip + mulch); avoid over-fertilizing N or K (competes with Ca uptake); soil test for Ca + pH (want 6.5 for Ca availability).',
     ''),

    ('Bacterial Wilt (cucurbits)', 'disease',
     'Cucumber, muskmelon, squash (not watermelon)',
     'Sudden wilt despite moist soil; cut stem oozes milky white strings when pulled apart slowly. Spread by cucumber beetle.',
     'No cure — pull + destroy. Vector control is everything.',
     'Control cucumber beetle aggressively (see Cucumber Beetle row); resistant varieties; row cover until female bloom.',
     ''),

    ('Tomato Spotted Wilt Virus (TSWV)', 'disease',
     'Tomato, pepper, lettuce, beans, many ornamentals',
     'Bronze / purple stippling on leaves; dark ring spots on fruit; stunted + distorted growth. Vectored by thrips.',
     'No cure — rogue + destroy infected plants. Control thrips (see Thrips row).',
     'Resistant varieties (\'Tasti-Lee\', \'Crista\', \'Fletcher\'); blue sticky traps; reflective mulch.',
     ''),

    ('Septoria Leaf Spot', 'disease',
     'Tomato',
     'Small circular tan spots with dark margins + tiny black pimple (pycnidia) in center; lower leaves first; defoliation progresses up.',
     'Copper fungicide; remove affected leaves; harvest + clear at end of season.',
     '3-year rotation; mulch; avoid overhead water; prune lower branches.',
     ''),

    ('Cedar-Apple Rust', 'disease',
     'Apple, crabapple, juniper / Eastern red cedar',
     'Bright yellow-orange spots on apple leaves + fruit in spring; gelatinous orange galls on juniper after spring rain.',
     'Remove cedar galls before spring rain if possible; fungicide (myclobutanil or sulfur) on apple at pink bud.',
     'Plant resistant apple varieties (\'Liberty\', \'Enterprise\', \'Williams Pride\'); remove junipers within 1 mile if feasible.',
     ''),

    ('Fire Blight', 'disease',
     'Apple, pear, quince, cotoneaster, hawthorn',
     'Branch tips blackened / burned appearance; shepherd\'s crook bend at tip; oozing bacterial cankers on bark.',
     'Prune 12+ in below visible damage; sterilize pruners between cuts (10% bleach or 70% isopropyl); destroy all cuttings.',
     'Avoid excess N fertilizer; resistant varieties (\'Liberty\', \'Enterprise\'); copper spray at budbreak.',
     ''),

    ('Club Root', 'disease',
     'Brassicas (cabbage, broccoli, turnip, radish)',
     'Stunted wilting plants; when pulled, roots are swollen, distorted clubs.',
     'No cure; pull + destroy plants (bag, don\'t compost); lime soil to raise pH above 7.2.',
     '7-year rotation away from brassicas; resistant varieties; raise soil pH with lime; good drainage.',
     ''),

    # ─────────────────────────── Vertebrate pests ─────────────────────
    ('Deer', 'vertebrate',
     'Almost everything — beans, lettuce, brassicas, fruit trees, rose',
     'Ragged torn edges on browsed plants (no lower teeth); cloven hoof prints; droppings; worst at dawn/dusk.',
     'Physical fencing 8 ft tall or 6 ft with outward lean; repellent sprays (putrescent egg / coyote urine) rotated weekly; motion-activated sprinkler.',
     'Plant unpalatable border (lavender, rosemary, yarrow, daffodil, foxglove); avoid roses + hosta near wood edges.',
     ''),

    ('Rabbit', 'vertebrate',
     'Lettuce, beans, brassicas, carrot tops, strawberry',
     'Clean 45° cut on stems (sharp teeth); pellet droppings; low-growing damage.',
     'Hardware cloth 24 in tall, buried 6 in; motion-activated sprinkler; blood meal spread at perimeter.',
     'Fencing is the only reliable control; remove brush piles (cover); avoid dense groundcover near garden.',
     ''),

    ('Vole / Field Mouse', 'vertebrate',
     'Root crops, bulbs, bark of young fruit trees in winter',
     'Runways 1-2 in wide in grass; girdling of trees under snow; gnawed tuber vegetables in storage.',
     'Trap with mousetraps baited with peanut butter; hardware cloth tree wraps; keep mulch 6 in from trunk.',
     'Mow meadow edges; remove mulch in late fall near young trees; encourage raptors (owl box).',
     ''),

    ('Groundhog', 'vertebrate',
     'Bean, pea, lettuce, broccoli, melon, apple',
     'Large bites taking entire plants; burrow 10-12 in diameter; flattened runway to garden.',
     'Trap + relocate (where legal); fence 3 ft above + 1 ft buried + outward L at bottom; ammonia or used kitty litter in burrow.',
     'Fence before damage starts; fill abandoned burrows; encourage foxes (apex predator).',
     ''),

    # ─────────────────────────── Physiological disorders ──────────────
    ('Sunscald', 'disorder',
     'Tomato, pepper, squash',
     'Whitish papery leathery patch on sun-exposed side of fruit; later colonized by black mold.',
     'Affected fruit generally not salvageable. Leave enough leaf cover on subsequent fruit.',
     'Don\'t over-prune foliage; plant cultivars with vigorous canopy; use 30-50% shade cloth in extreme heat zones.',
     ''),

    ('Cracking (tomato)', 'disorder',
     'Tomato, cherry, stone fruits',
     'Concentric or radial cracks at stem end, widen after sudden heavy rain following drought.',
     'Pick + use cracked fruit before decay sets in.',
     'Even moisture (drip + thick mulch); resistant varieties (\'Juliet\', \'Sun Gold\', \'Jet Star\').',
     ''),
]
