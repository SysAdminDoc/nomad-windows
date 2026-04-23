"""Seed data packages for NOMAD reference tables.

Each module exports a list/tuple named ``DATA`` (or specific well-known
names, e.g. ``FREQUENCIES``, ``RULES``) plus, where helpful, a short
docstring describing the schema each row maps to.

These modules hold reference DATA only — the ``INSERT OR IGNORE`` logic
lives in ``db.py`` next to the existing ``_seed_*`` functions. Keeping
data out of ``db.py`` prevents that file from ballooning past 7,000 lines
every time a new table gets seeded.

When adding a new seed table:

1. Add a module here exporting the rows as a list of tuples.
2. Add a matching ``_seed_<table>(conn)`` function in ``db.py`` that
   imports the module and does ``INSERT OR IGNORE`` on each row.
3. Call the new seeder from ``_init_db_inner`` alongside the others.
4. Flip the corresponding ``CE-*`` row in ``ROADMAP.md`` from Open to
   Done with the release tag.
"""
