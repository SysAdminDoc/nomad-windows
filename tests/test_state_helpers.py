"""Regression tests for shared state helpers used across routes and threads."""

import web.state as state


def test_wizard_snapshot_returns_detached_collections():
    state.wizard_reset(status='running', completed=['ollama'], errors=['warn'])

    snapshot = state.wizard_snapshot()
    snapshot['completed'].append('kiwix')
    snapshot['errors'].append('later')

    fresh = state.wizard_snapshot()
    assert fresh['completed'] == ['ollama']
    assert fresh['errors'] == ['warn']


def test_wizard_append_list_item_recovers_from_corrupted_field():
    state.wizard_reset(errors='not-a-list')

    state.wizard_append_list_item('errors', 'fixed')

    assert state.wizard_snapshot()['errors'] == ['fixed']


def test_alert_check_flag_allows_only_one_runner_until_reset():
    state.set_alert_check_running(False)

    assert state.try_begin_alert_check() is True
    assert state.try_begin_alert_check() is False

    state.set_alert_check_running(False)
    assert state.try_begin_alert_check() is True
    state.set_alert_check_running(False)
