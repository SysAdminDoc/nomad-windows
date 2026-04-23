"""Blueprint registry — import and register all blueprints with the Flask app.

Call ``register_blueprints(app)`` from ``create_app()`` after all middleware
is in place. Import side effects (alert engine, scheduler) are also handled here.
"""

import logging
import os

log = logging.getLogger('nomad.web')


def register_blueprints(app):
    """Import and register every blueprint, then start dependent services."""

    # ─── Core v1 ─────────────────────────────────────────────────────────────
    from web.blueprints.benchmark import benchmark_bp
    from web.blueprints.garden import garden_bp
    from web.blueprints.notes import notes_bp
    from web.blueprints.weather import weather_bp
    from web.blueprints.medical import medical_bp
    from web.blueprints.power import power_bp
    from web.blueprints.federation import federation_bp
    from web.blueprints.kb import kb_bp
    from web.blueprints.security import security_bp
    from web.blueprints.supplies import supplies_bp
    app.register_blueprint(benchmark_bp)
    app.register_blueprint(garden_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(weather_bp)
    app.register_blueprint(medical_bp)
    app.register_blueprint(power_bp)
    app.register_blueprint(federation_bp)
    app.register_blueprint(kb_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(supplies_bp)

    # ─── Phase 2 Batch 3 ─────────────────────────────────────────────────────
    from web.blueprints.services import services_bp
    from web.blueprints.ai import ai_bp
    from web.blueprints.inventory import inventory_bp
    from web.blueprints.comms import comms_bp
    from web.blueprints.media import media_bp
    from web.blueprints.maps import maps_bp
    from web.blueprints.system import system_bp
    from web.blueprints.situation_room import situation_room_bp
    app.register_blueprint(services_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(comms_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(maps_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(situation_room_bp)

    # ─── Phase 3 ─────────────────────────────────────────────────────────────
    from web.blueprints.checklists import checklists_bp
    from web.blueprints.tasks import tasks_bp
    from web.blueprints.contacts import contacts_bp
    from web.blueprints.exercises import exercises_bp
    from web.blueprints.print_routes import print_routes_bp
    from web.blueprints.kiwix import kiwix_bp
    app.register_blueprint(checklists_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(exercises_bp)
    app.register_blueprint(print_routes_bp)
    app.register_blueprint(kiwix_bp)

    # ─── Undo ────────────────────────────────────────────────────────────────
    from web.blueprints.undo import undo_bp
    app.register_blueprint(undo_bp)

    # ─── Kit Builder (v7.3.0) ─────────────────────────────────────────────
    from web.blueprints.kit_builder import kit_builder_bp
    app.register_blueprint(kit_builder_bp)

    # ─── Emergency Mode (v7.5.0) ─────────────────────────────────────────
    from web.blueprints.emergency import emergency_bp
    app.register_blueprint(emergency_bp)

    # ─── Family Check-in (v7.6.0) ─────────────────────────────────────────
    from web.blueprints.family import family_bp
    app.register_blueprint(family_bp)

    # ─── Daily Operations Brief (v7.7.0) ─────────────────────────────────
    from web.blueprints.brief import brief_bp
    app.register_blueprint(brief_bp)

    # ─── v7.8.0 — Critical Path Modules ──────────────────────────────────
    from web.blueprints.water_mgmt import water_mgmt_bp
    from web.blueprints.financial import financial_bp
    from web.blueprints.vehicles import vehicles_bp
    from web.blueprints.loadout import loadout_bp
    app.register_blueprint(water_mgmt_bp)
    app.register_blueprint(financial_bp)
    app.register_blueprint(vehicles_bp)
    app.register_blueprint(loadout_bp)

    # ─── v7.10.0 — High Value Modules ─────────────────────────────────────
    from web.blueprints.readiness_goals import readiness_goals_bp
    from web.blueprints.alert_rules import alert_rules_bp
    from web.blueprints.timeline import timeline_bp
    from web.blueprints.threat_intel import threat_intel_bp
    from web.blueprints.evac_drills import evac_drills_bp
    app.register_blueprint(readiness_goals_bp)
    app.register_blueprint(alert_rules_bp)
    app.register_blueprint(timeline_bp)
    app.register_blueprint(threat_intel_bp)
    app.register_blueprint(evac_drills_bp)

    # ─── v7.11.0 — Data Foundation & Localization ─────────────────────────
    from web.blueprints.data_packs import data_packs_bp
    from web.blueprints.regional_profile import regional_profile_bp
    from web.blueprints.nutrition import nutrition_bp
    from web.blueprints.pack_importers import pack_importers_bp
    from web.blueprints.scheduled_reports import scheduled_reports_bp
    from web.blueprints.shamir_vault import shamir_vault_bp
    from web.blueprints.field_tools import field_tools_bp
    from web.blueprints.field_ops import field_ops_bp
    from web.blueprints.specialized_threats import specialized_threats_bp
    from web.blueprints.homestead import homestead_bp
    from web.blueprints.health_family import health_family_bp
    from web.blueprints.tier8_tools import tier8_bp
    from web.blueprints.remaining_calcs import remaining_calcs_bp
    from web.blueprints.remaining_refs import remaining_refs_bp
    from web.blueprints.remaining_features import remaining_features_bp
    app.register_blueprint(data_packs_bp)
    app.register_blueprint(regional_profile_bp)
    app.register_blueprint(nutrition_bp)
    app.register_blueprint(pack_importers_bp)
    app.register_blueprint(scheduled_reports_bp)
    app.register_blueprint(shamir_vault_bp)
    app.register_blueprint(field_tools_bp)
    app.register_blueprint(field_ops_bp)
    app.register_blueprint(specialized_threats_bp)
    app.register_blueprint(homestead_bp)
    app.register_blueprint(health_family_bp)
    app.register_blueprint(tier8_bp)
    app.register_blueprint(remaining_calcs_bp)
    app.register_blueprint(remaining_refs_bp)
    app.register_blueprint(remaining_features_bp)

    # ─── v7.12.0 — Nutritional Intelligence & Water Expansion ─────────────
    from web.blueprints.consumption import consumption_bp
    app.register_blueprint(consumption_bp)

    # ─── v7.13.0 — Advanced Inventory & Consumption Modeling ──────────────
    from web.blueprints.meal_planning import meal_planning_bp
    app.register_blueprint(meal_planning_bp)

    # ─── v7.14.0 — Movement & Route Planning ──────────────────────────────
    from web.blueprints.movement_ops import movement_ops_bp
    app.register_blueprint(movement_ops_bp)

    # ─── v7.14.0 — Tactical Communications ────────────────────────────────
    from web.blueprints.tactical_comms import tactical_comms_bp
    app.register_blueprint(tactical_comms_bp)

    # ─── v7.15.0 — Land Assessment & Property ─────────────────────────────
    from web.blueprints.land_assessment import land_assessment_bp
    app.register_blueprint(land_assessment_bp)

    # ─── v7.15.0 — Medical Phase 2 ────────────────────────────────────────
    from web.blueprints.medical_phase2 import medical_phase2_bp
    app.register_blueprint(medical_phase2_bp)

    # ─── v7.16.0 — Training & Knowledge ───────────────────────────────────
    from web.blueprints.training_knowledge import training_knowledge_bp
    app.register_blueprint(training_knowledge_bp)

    # ─── v7.17.0 — Group Operations & Governance ──────────────────────────
    from web.blueprints.group_ops import group_ops_bp
    app.register_blueprint(group_ops_bp)

    # ─── v7.18.0 — Security, OPSEC & Night Ops ────────────────────────────
    from web.blueprints.security_opsec import security_opsec_bp
    app.register_blueprint(security_opsec_bp)

    # ─── v7.19.0 — Agriculture & Permaculture ─────────────────────────────
    from web.blueprints.agriculture import agriculture_bp
    app.register_blueprint(agriculture_bp)

    # ─── v7.20.0 — Disaster-Specific Modules ──────────────────────────────
    from web.blueprints.disaster_modules import disaster_modules_bp
    app.register_blueprint(disaster_modules_bp)

    # ─── v7.21.0 — Daily Living & Quality of Life ─────────────────────────
    from web.blueprints.daily_living import daily_living_bp
    app.register_blueprint(daily_living_bp)

    # ─── v7.22.0 — Interoperability & Data Exchange ───────────────────────
    from web.blueprints.interoperability import interoperability_bp
    app.register_blueprint(interoperability_bp)

    # ─── v7.23.0 — Hunting, Foraging & Wild Food ──────────────────────────
    from web.blueprints.hunting_foraging import hunting_foraging_bp
    app.register_blueprint(hunting_foraging_bp)

    # ─── v7.24.0 — Hardware, Sensors & Mesh ──────────────────────────────
    from web.blueprints.hardware_sensors import hardware_sensors_bp
    app.register_blueprint(hardware_sensors_bp)

    # ─── Platform Security ────────────────────────────────────────────────
    from web.blueprints.platform_security import platform_security_bp
    app.register_blueprint(platform_security_bp)

    # ─── Specialized Modules ──────────────────────────────────────────────
    from web.blueprints.specialized_modules import specialized_modules_bp
    app.register_blueprint(specialized_modules_bp)

    # ─── Roadmap Features (v7.47.0+) ──────────────────────────────────────
    from web.blueprints.roadmap_features import roadmap_bp
    app.register_blueprint(roadmap_bp)

    # ─── Preparedness (registered after alert engine start) ───────────────
    # Under pytest the alert engine races with per-test ``init_db()`` in
    # conftest and causes intermittent ``database table is locked:
    # sqlite_master`` errors when ``ALTER TABLE`` runs while the daemon
    # thread is opening a connection against the new test DB. Skip the
    # background thread entirely during tests — blueprints + routes still
    # register, just without the long-running loop.
    from web.blueprints.preparedness import start_alert_engine, preparedness_bp
    if not app.config.get('TESTING') and 'PYTEST_CURRENT_TEST' not in os.environ:
        start_alert_engine()
    app.register_blueprint(preparedness_bp)

    # ─── Scheduled reports ───────────────────────────────────────────────
    from web.blueprints.scheduled_reports import _ensure_scheduler
    if not app.config.get('TESTING') and 'PYTEST_CURRENT_TEST' not in os.environ:
        _ensure_scheduler()

    # ─── User Plugins ─────────────────────────────────────────────────────
    from web.plugins import load_plugins
    load_plugins(app)

    log.debug('All blueprints registered (%d total)', len(app.blueprints))
