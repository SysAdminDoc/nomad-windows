"""Companion planting seed data — CE-02 (v7.60).

Seeds ``companion_plants`` with the canonical companion + antagonist pairs
used across most permaculture / biointensive references. Entries are
directed: plant_a is "the crop" and plant_b is its neighbor.

Schema (from db.py):
    (plant_a, plant_b, relationship, notes)

Relationship vocabulary:
    companion  — mutually beneficial (pest deterrent, pollinator lure,
                 nutrient exchange, shade/trellis, etc.)
    antagonist — known to stunt, stress, or cross-disease with plant_a
    trap_crop  — plant_b lures pests away from plant_a

Sources: Rodale Companion Planting, Cornell Cooperative Extension, Louise
Riotte's "Carrots Love Tomatoes", West Virginia University Extension
companion planting chart, Oregon State University IPM notes.
"""

# (plant_a, plant_b, relationship, notes)
COMPANION_PLANTS = [
    # ───────────────────────────── Tomato ─────────────────────────────
    ('Tomato', 'Basil', 'companion', 'Repels hornworms + whiteflies; improves tomato flavor.'),
    ('Tomato', 'Carrot', 'companion', 'Carrots loosen soil for deep tomato roots.'),
    ('Tomato', 'Marigold', 'companion', 'Repels root-knot nematodes + many soft-body pests.'),
    ('Tomato', 'Onion', 'companion', 'Deters aphids + spider mites.'),
    ('Tomato', 'Parsley', 'companion', 'Attracts hoverflies that predate aphids.'),
    ('Tomato', 'Chives', 'companion', 'Deters aphids; reputedly improves flavor.'),
    ('Tomato', 'Borage', 'companion', 'Attracts pollinators; reputedly deters tomato hornworm.'),
    ('Tomato', 'Brassicas', 'antagonist', 'Cabbage family stunts tomato growth (allelopathy + competition).'),
    ('Tomato', 'Potato', 'antagonist', 'Shares early/late blight (Phytophthora). Rotate and separate beds.'),
    ('Tomato', 'Fennel', 'antagonist', 'Fennel inhibits most garden plants; never interplant.'),
    ('Tomato', 'Corn', 'antagonist', 'Share corn earworm / tomato fruitworm (Helicoverpa zea).'),
    ('Tomato', 'Dill', 'antagonist', 'Mature dill stunts tomatoes; young dill is fine as trap.'),

    # ───────────────────────────── Three Sisters ──────────────────────
    ('Corn', 'Beans', 'companion', 'Beans fix N for hungry corn; corn stalks are bean trellis.'),
    ('Corn', 'Squash', 'companion', 'Squash vines shade soil (living mulch) + spines deter raccoons.'),
    ('Beans', 'Squash', 'companion', 'Complete "three sisters" polyculture.'),
    ('Corn', 'Cucumber', 'companion', 'Corn provides trellis; cucumber roots shade corn root zone.'),
    ('Corn', 'Dill', 'companion', 'Dill lures beneficial wasps that parasitize corn earworm.'),
    ('Corn', 'Tomato', 'antagonist', 'Shares fruitworm (see Tomato↔Corn).'),

    # ───────────────────────────── Brassicas (cabbage, broccoli, etc) ─
    ('Cabbage', 'Dill', 'companion', 'Dill lures parasitoid wasps of cabbage worm.'),
    ('Cabbage', 'Mint', 'companion', 'Repels cabbage white butterfly + flea beetles.'),
    ('Cabbage', 'Onion', 'companion', 'Deters cabbage loopers + maggots.'),
    ('Cabbage', 'Rosemary', 'companion', 'Strong scent masks brassicas from cabbage moth.'),
    ('Cabbage', 'Thyme', 'companion', 'Repels cabbage white butterfly.'),
    ('Cabbage', 'Nasturtium', 'trap_crop', 'Nasturtium pulls aphids + cabbage white off brassicas.'),
    ('Cabbage', 'Strawberry', 'antagonist', 'Cabbage retards strawberry; also Verticillium wilt risk.'),
    ('Cabbage', 'Tomato', 'antagonist', 'Cabbage stunts tomato (see Tomato↔Brassicas).'),
    ('Broccoli', 'Celery', 'companion', 'Celery deters cabbage white.'),
    ('Broccoli', 'Chamomile', 'companion', 'Attracts hoverflies; reputedly improves flavor.'),
    ('Broccoli', 'Strawberry', 'antagonist', 'Same Verticillium risk as cabbage↔strawberry.'),
    ('Kale', 'Onion', 'companion', 'Deters cabbage aphids.'),

    # ───────────────────────────── Carrot ─────────────────────────────
    ('Carrot', 'Onion', 'companion', 'Classic — onion deters carrot fly; carrot masks onion scent.'),
    ('Carrot', 'Leek', 'companion', 'Same mutual pest-masking as onion.'),
    ('Carrot', 'Chives', 'companion', 'Deters carrot fly; reputedly sweetens carrots.'),
    ('Carrot', 'Rosemary', 'companion', 'Deters carrot fly.'),
    ('Carrot', 'Sage', 'companion', 'Deters carrot fly.'),
    ('Carrot', 'Dill', 'antagonist', 'Mature dill reduces carrot yield.'),

    # ───────────────────────────── Cucumber / squash ──────────────────
    ('Cucumber', 'Nasturtium', 'companion', 'Repels cucumber beetle.'),
    ('Cucumber', 'Radish', 'companion', 'Radish lures flea beetle + repels cucumber beetle.'),
    ('Cucumber', 'Sunflower', 'companion', 'Trellis + partial shade; sunflower attracts pollinators.'),
    ('Cucumber', 'Marigold', 'companion', 'Repels cucumber beetle + nematodes.'),
    ('Cucumber', 'Sage', 'antagonist', 'Sage slows cucumber growth.'),
    ('Cucumber', 'Potato', 'antagonist', 'Potato encourages Phytophthora cucumber blight.'),
    ('Squash', 'Nasturtium', 'companion', 'Deters squash bugs + cucumber beetles.'),
    ('Squash', 'Borage', 'companion', 'Attracts squash pollinators.'),
    ('Squash', 'Marigold', 'companion', 'Repels squash vine borer.'),

    # ───────────────────────────── Potato ─────────────────────────────
    ('Potato', 'Horseradish', 'companion', 'Reputedly confers disease resistance; plant at corners.'),
    ('Potato', 'Beans', 'companion', 'Beans fix N + repel Colorado potato beetle.'),
    ('Potato', 'Marigold', 'companion', 'Repels potato beetle.'),
    ('Potato', 'Catnip', 'companion', 'Repels potato beetle.'),
    ('Potato', 'Tomato', 'antagonist', 'Share blight.'),
    ('Potato', 'Squash', 'antagonist', 'Potato stunts squash + shares blight.'),
    ('Potato', 'Sunflower', 'antagonist', 'Sunflower allelopathy stunts potato.'),
    ('Potato', 'Raspberry', 'antagonist', 'Share Verticillium wilt.'),
    ('Potato', 'Cucumber', 'antagonist', 'See Cucumber↔Potato.'),

    # ───────────────────────────── Bean / legume ──────────────────────
    ('Beans', 'Summer Savory', 'companion', 'Deters bean beetle; improves flavor.'),
    ('Beans', 'Rosemary', 'companion', 'Deters bean beetle.'),
    ('Beans', 'Marigold', 'companion', 'Repels Mexican bean beetle.'),
    ('Beans', 'Carrot', 'companion', 'Carrots benefit from N fixed by beans.'),
    ('Beans', 'Onion', 'antagonist', 'Alliums inhibit bean growth (canonical exclusion).'),
    ('Beans', 'Garlic', 'antagonist', 'Same allium antagonism.'),
    ('Beans', 'Leek', 'antagonist', 'Same allium antagonism.'),
    ('Beans', 'Fennel', 'antagonist', 'Universal inhibitor.'),

    # ───────────────────────────── Pepper ─────────────────────────────
    ('Pepper', 'Basil', 'companion', 'Repels aphids, spider mites, and thrips.'),
    ('Pepper', 'Carrot', 'companion', 'Carrots loosen soil for pepper roots.'),
    ('Pepper', 'Tomato', 'companion', 'Share similar culture but not disease (unlike tomato↔potato).'),
    ('Pepper', 'Onion', 'companion', 'Deters aphids + thrips.'),
    ('Pepper', 'Fennel', 'antagonist', 'Universal inhibitor.'),
    ('Pepper', 'Brassicas', 'antagonist', 'Cabbage family stunts peppers.'),

    # ───────────────────────────── Onion / garlic / allium ────────────
    ('Onion', 'Beet', 'companion', 'Mutually non-competing root depths.'),
    ('Onion', 'Lettuce', 'companion', 'Onions deter rabbits + slugs from lettuce.'),
    ('Onion', 'Strawberry', 'companion', 'Deters strawberry pests.'),
    ('Onion', 'Chamomile', 'companion', 'Reputedly improves onion flavor.'),
    ('Onion', 'Asparagus', 'antagonist', 'Onions stunt asparagus.'),
    ('Onion', 'Peas', 'antagonist', 'Allium inhibits legume.'),

    # ───────────────────────────── Lettuce / greens ───────────────────
    ('Lettuce', 'Carrot', 'companion', 'Complementary root depth + canopy shade.'),
    ('Lettuce', 'Radish', 'companion', 'Radish lures flea beetle off lettuce.'),
    ('Lettuce', 'Strawberry', 'companion', 'Lettuce shades strawberry roots in summer.'),
    ('Lettuce', 'Celery', 'antagonist', 'Celery stunts lettuce.'),
    ('Spinach', 'Strawberry', 'companion', 'Low-growing ground cover under strawberries.'),
    ('Spinach', 'Peas', 'companion', 'Peas fix N for heavy-feeding spinach.'),

    # ───────────────────────────── Strawberry ─────────────────────────
    ('Strawberry', 'Borage', 'companion', 'Attracts pollinators; reputedly increases yield.'),
    ('Strawberry', 'Thyme', 'companion', 'Ground-cover thyme repels worms.'),
    ('Strawberry', 'Brassicas', 'antagonist', 'Verticillium wilt shared risk (see above).'),

    # ───────────────────────────── Universal helpers ──────────────────
    ('Marigold', 'All', 'companion', 'French marigold (Tagetes patula) repels root-knot nematodes when interplanted.'),
    ('Nasturtium', 'All', 'companion', 'Universal trap crop for aphids, whitefly, cabbage white.'),
    ('Borage', 'All', 'companion', 'Pollinator magnet; high in potassium when chopped into compost.'),
    ('Dill', 'All', 'companion', 'Attracts parasitic wasps, hoverflies, lacewings.'),
    ('Yarrow', 'All', 'companion', 'Attracts predatory wasps, hoverflies, ladybugs.'),
    ('Chamomile', 'All', 'companion', '"Plant doctor" — reputedly improves vigor of neighbors.'),

    # ───────────────────────────── Universal antagonists ──────────────
    ('Fennel', 'All', 'antagonist', 'Allelopathic — inhibits nearly every garden crop. Isolate.'),
    ('Black Walnut', 'All', 'antagonist', 'Juglone toxicity kills tomato, potato, blueberry, apple + many others within drip line.'),
    ('Sunflower', 'Potato', 'antagonist', 'Allelopathic to potato + beans.'),
]
