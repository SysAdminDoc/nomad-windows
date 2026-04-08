"""DEPRECATED — routes have been distributed to proper blueprints.

- AI routes (sitrep, execute-action, memory) -> web/blueprints/ai.py
- Print routes (operations-binder, wallet-cards, soi, medical-flipbook) -> web/blueprints/print_routes.py
- System routes (db-check, db-vacuum) -> web/blueprints/system.py
- Federation routes (community-readiness, skill-search, relay-alert) -> web/blueprints/federation.py
- Undo system (undo, redo) -> web/blueprints/undo.py

The self-test route from this file was already present in system.py and was not duplicated.
"""
