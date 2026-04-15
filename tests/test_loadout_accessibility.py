from pathlib import Path


LOADOUT_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "web"
    / "templates"
    / "index_partials"
    / "_tab_loadout.html"
)


def _load_loadout_template():
    return LOADOUT_TEMPLATE.read_text(encoding="utf-8")


def test_loadout_bag_cards_support_keyboard_activation():
    template = _load_loadout_template()
    assert 'function handleBagCardActivate(event)' in template
    assert "bagGrid.addEventListener('keydown', handleBagCardActivate);" in template
    assert 'data-bag-id="${b.id}"' in template
    assert 'aria-controls="lo-detail"' in template
    assert "event.key !== 'Enter' && event.key !== ' '" in template


def test_loadout_detail_panel_and_item_actions_expose_accessible_state():
    template = _load_loadout_template()
    assert 'role="region" aria-label="Loadout bag details" aria-live="polite" tabindex="-1"' in template
    assert "window.matchMedia('(prefers-reduced-motion: reduce)').matches" in template
    assert 'aria-pressed="${packed ? \'true\' : \'false\'}"' in template
    assert 'aria-label="${packed ? \'Mark \' + escapeAttr(item.name) + \' unpacked\' : \'Mark \' + escapeAttr(item.name) + \' packed\'}"' in template
    assert 'aria-label="Edit ${escapeAttr(item.name)}"' in template
    assert 'aria-label="Delete ${escapeAttr(item.name)}"' in template
