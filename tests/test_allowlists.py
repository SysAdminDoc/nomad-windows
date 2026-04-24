"""Module-level column allowlist tests (V8-14).

Guard against regression of the inline→module-level allowlist hoist by
pinning the exact field sets exposed by blueprints. If a schema column is
added or removed, these tests fail loudly so the allowlist stays in sync.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_emergency_allowlists_are_module_level():
    from web.blueprints import emergency

    assert isinstance(emergency.ALLOWED_EVAC_PLAN_FIELDS, frozenset)
    assert isinstance(emergency.ALLOWED_EVAC_RALLY_FIELDS, frozenset)
    assert isinstance(emergency.ALLOWED_EVAC_ASSIGNMENT_FIELDS, frozenset)

    assert emergency.ALLOWED_EVAC_PLAN_FIELDS == frozenset({
        'name', 'plan_type', 'is_active', 'destination', 'primary_route',
        'alternate_route', 'distance_miles', 'estimated_time_min',
        'trigger_conditions', 'notes',
    })
    assert emergency.ALLOWED_EVAC_RALLY_FIELDS == frozenset({
        'name', 'location', 'lat', 'lng', 'point_type', 'sequence_order',
        'notes',
    })
    assert emergency.ALLOWED_EVAC_ASSIGNMENT_FIELDS == frozenset({
        'person_name', 'role', 'vehicle', 'go_bag', 'notes',
    })


def test_maps_waypoint_allowlist_is_module_level():
    from web.blueprints import maps

    assert isinstance(maps.ALLOWED_WAYPOINT_FIELDS, frozenset)
    assert maps.ALLOWED_WAYPOINT_FIELDS == frozenset({
        'name', 'lat', 'lng', 'category', 'notes', 'elevation_m', 'icon',
    })


def test_media_allowlists_are_module_level():
    from web.blueprints import media

    assert isinstance(media.ALLOWED_MEDIA_META_FIELDS, frozenset)
    assert isinstance(media.ALLOWED_AUDIO_META_EXTRAS, frozenset)
    assert isinstance(media.ALLOWED_BOOK_META_EXTRAS, frozenset)

    base = {'title', 'category', 'notes', 'description'}
    assert media.ALLOWED_MEDIA_META_FIELDS == frozenset(base)
    assert media.ALLOWED_AUDIO_META_EXTRAS == frozenset({'artist', 'album'})
    assert media.ALLOWED_BOOK_META_EXTRAS == frozenset({'author', 'description'})


def test_media_effective_allowlist_per_type():
    from web.blueprints.media import _allowed_media_meta_fields

    base = {'title', 'category', 'notes', 'description'}
    assert _allowed_media_meta_fields('video') == frozenset(base)
    assert _allowed_media_meta_fields('audio') == frozenset(
        base | {'artist', 'album'}
    )
    assert _allowed_media_meta_fields('book') == frozenset(
        base | {'author', 'description'}
    )
    # Unknown types fall back to the safe base set, never a broader one.
    assert _allowed_media_meta_fields('unknown') == frozenset(base)


def test_allowlists_reject_injection_like_keys():
    """Allowlists must silently drop SQL-injection-flavored keys."""
    from web.blueprints import emergency, maps

    hostile = {
        'name': 'ok',
        'id; DROP TABLE evac_plans;--': 'x',
        'password': 'x',
        'lat = 1 OR 1=1': 'x',
    }
    kept_plan = {k: v for k, v in hostile.items()
                 if k in emergency.ALLOWED_EVAC_PLAN_FIELDS}
    assert kept_plan == {'name': 'ok'}

    kept_wp = {k: v for k, v in hostile.items()
               if k in maps.ALLOWED_WAYPOINT_FIELDS}
    assert kept_wp == {'name': 'ok'}
