"""Tests for core API routes — services, alerts, activity, version."""

from pathlib import Path
import re
import os


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_get_data_dir_falls_back_when_custom_path_is_unavailable(monkeypatch, tmp_path):
    import config
    import platform_utils

    unavailable_dir = r'G:\nomad-missing-drive'

    monkeypatch.setattr(platform_utils, 'is_portable_mode', lambda: False)
    monkeypatch.setattr(platform_utils, 'get_data_base', lambda: str(tmp_path))
    monkeypatch.setattr(config, 'load_config', lambda: {'data_dir': unavailable_dir})

    real_makedirs = os.makedirs

    def fake_makedirs(path, exist_ok=False):
        if os.path.normpath(path) == os.path.normpath(unavailable_dir):
            raise FileNotFoundError('missing drive')
        return real_makedirs(path, exist_ok=exist_ok)

    monkeypatch.setattr(config.os, 'makedirs', fake_makedirs)

    resolved = config.get_data_dir()

    assert resolved == str(tmp_path / config.APP_STORAGE_DIRNAME)
    assert Path(resolved).is_dir()


class TestServicesEndpoint:
    def test_services_list(self, client):
        resp = client.get('/api/services')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        # Should have the 7 managed services
        ids = [s['id'] for s in data]
        for svc in ['ollama', 'kiwix', 'cyberchef', 'kolibri', 'qdrant', 'stirling', 'flatnotes']:
            assert svc in ids, f'{svc} missing from services list'

    def test_service_fields(self, client):
        resp = client.get('/api/services')
        svc = resp.get_json()[0]
        assert 'id' in svc
        assert 'installed' in svc
        assert 'running' in svc
        assert 'port' in svc


class TestAlertsEndpoint:
    def test_alerts_list(self, client):
        resp = client.get('/api/alerts')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)


class TestActivityLog:
    def test_activity_log_empty(self, client):
        resp = client.get('/api/activity')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_activity_log_limit(self, client):
        resp = client.get('/api/activity?limit=5')
        assert resp.status_code == 200

    def test_activity_log_filter(self, client):
        resp = client.get('/api/activity?filter=inventory')
        assert resp.status_code == 200


class TestVersionEndpoint:
    def test_version(self, client):
        resp = client.get('/api/version')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'version' in data


class TestErrorHandler:
    def _html(self, client, path):
        resp = client.get(path)
        assert resp.status_code == 200
        return resp.get_data(as_text=True)

    def test_404_json_for_api(self, client):
        resp = client.get('/api/nonexistent-route-xyz')
        assert resp.status_code == 404
        data = resp.get_json()
        assert 'error' in data

    def test_index_page_loads(self, client):
        resp = client.get('/')
        assert resp.status_code == 200

    def test_index_page_shell_controls(self, client):
        html = self._html(client, '/')
        assert '<title>Home · NOMAD Field Desk v' in html
        assert 'src="/static/nomad-mark.svg"' in html
        assert 'alt="NOMAD logo"' in html
        assert 'class="sidebar-brand-kicker">Field Operations Desk<' in html
        assert 'class="sidebar-group-title">Briefing<' in html
        assert 'Orient, assess, decide.' in html
        assert 'class="sidebar-group-title">Operations<' in html
        assert 'Run fieldwork, act on risk, manage resources.' in html
        assert 'class="sidebar-group-title">Knowledge<' in html
        assert 'class="sidebar-group-title">Assistant<' in html
        assert 'Drafting, synthesis, and copiloting.' in html
        assert 'class="sidebar-group-title">System<' in html
        assert '>Diagnostics</span>' in html
        assert '>Copilot</span>' in html
        assert 'href="/"' in html
        assert 'window.NOMAD_ACTIVE_TAB = "services";' in html
        assert 'window.NOMAD_ALLOW_LAUNCH_RESTORE = true;' in html
        assert 'Welcome to NOMAD' in html
        assert 'Start Using NOMAD' in html
        assert 'data-tab-target="services"' in html
        assert 'name="unified_search"' in html
        assert 'aria-labelledby="shortcuts-title"' in html
        assert 'data-mode-select="command"' in html
        assert 'class="home-launch-deck"' in html
        assert 'class="home-launch-hero home-surface-panel"' in html
        assert 'COMMAND DESK' in html
        assert 'Search, switch lanes, or resume live work.' in html
        assert 'id="home-continue-panel" class="home-continue-panel home-surface-panel"' in html
        assert 'Pinned' in html
        assert 'Recent' in html
        assert 'id="command-palette-overlay" class="command-palette-overlay" role="dialog" aria-modal="true" aria-labelledby="command-palette-title" hidden' in html
        assert 'id="workspace-context-bar" class="workspace-context-bar" hidden' in html
        assert 'id="workspace-inspector"' not in html
        assert 'id="sidebar-context-hub"' in html
        assert 'Return' in html
        assert 'Keep pinned desks and your active context within reach.' in html
        assert 'id="mobile-bottom-nav"' not in html
        assert 'data-shell-action="open-mobile-drawer"' not in html
        assert 'class="sidebar-toggle"' not in html
        assert 'viewport-fit=cover' not in html
        assert 'Can my family use it from another computer on the network?' in html
        assert 'data-install-service="ollama"' in html
        assert 'data-shell-action="install-service"' in html
        assert 'data-shell-action="reload-services"' in html
        assert 'data-shell-action="dismiss-broadcast"' in html
        assert 'id="broadcast-banner" class="broadcast-banner is-hidden"' in html
        assert 'id="tab-services"' in html
        assert 'id="tab-preparedness"' not in html
        assert 'id="tab-situation-room"' not in html
        assert 'id="tab-maps"' not in html
        assert 'id="tab-settings"' not in html
        assert 'utility-fab' not in html

    def test_workspace_pages_are_segmented(self, client):
        pages = [
            ('/situation-room', 'Situation Room · NOMAD Field Desk', 'tab-situation-room', 'sr-map-command-brief', ['tab-services', 'tab-settings', 'tab-media']),
            ('/preparedness', 'Preparedness · NOMAD Field Desk', 'tab-preparedness', 'data-prep-category="coordinate"', ['tab-services', 'tab-situation-room', 'tab-settings']),
            ('/maps', 'Maps · NOMAD Field Desk', 'tab-maps', 'class="map-command-deck map-surface"', ['tab-preparedness', 'tab-media', 'tab-settings']),
            ('/library', 'Library · NOMAD Field Desk', 'tab-kiwix-library', 'class="library-command-deck workspace-panel"', ['tab-preparedness', 'tab-media', 'tab-settings']),
            ('/notes', 'Notes · NOMAD Field Desk', 'tab-notes', 'class="notes-command-deck"', ['tab-preparedness', 'tab-media', 'tab-settings']),
            ('/media', 'Media · NOMAD Field Desk', 'tab-media', 'class="media-command-deck"', ['tab-preparedness', 'tab-settings', 'tab-situation-room']),
            ('/copilot', 'Copilot · NOMAD Field Desk', 'tab-ai-chat', 'COPILOT WORKSPACE', ['tab-settings', 'tab-preparedness', 'tab-media']),
            ('/settings', 'Settings · NOMAD Field Desk', 'tab-settings', 'class="settings-command-deck workspace-panel"', ['tab-services', 'tab-situation-room', 'tab-media']),
            ('/diagnostics', 'Diagnostics · NOMAD Field Desk', 'tab-benchmark', 'class="benchmark-command-deck workspace-panel"', ['tab-settings', 'tab-preparedness', 'tab-media']),
            ('/viptrack-tab', 'VIPTrack · NOMAD Field Desk', 'tab-viptrack', 'id="viptrack-stage"', ['tab-services', 'tab-settings', 'tab-media']),
        ]
        for path, title, tab_id, unique_marker, absent_tabs in pages:
            html = self._html(client, path)
            assert title in html
            assert f'id="{tab_id}"' in html
            assert unique_marker in html
            if path == '/viptrack-tab':
                assert 'Live military and VIP air traffic' in html
                assert 'src="/viptrack/?embed=nomad"' in html
            for absent in absent_tabs:
                assert f'id="{absent}"' not in html

    def test_workspace_page_runtime_shell_blocks(self, client):
        home_html = self._html(client, '/')
        assert '"services": "/"' in home_html
        assert 'window.NOMAD_ALLOW_LAUNCH_RESTORE = true;' in home_html
        assert 'id="workspace-context-bar" class="workspace-context-bar" hidden' in home_html
        assert 'id="workspace-inspector"' not in home_html

        prep_html = self._html(client, '/preparedness')
        assert 'window.NOMAD_ACTIVE_TAB = "preparedness";' in prep_html
        assert 'window.NOMAD_ALLOW_LAUNCH_RESTORE = false;' in prep_html
        assert 'id="prep-recent-workspaces"' in prep_html
        assert 'id="prep-favorite-workspaces"' in prep_html
        assert 'data-prep-nav-action="resume-last"' in prep_html
        assert 'data-prep-nav-action="toggle-current-favorite"' in prep_html
        assert 'class="prep-guide-selector-grid"' in prep_html
        assert 'class="prep-guide-card"' in prep_html
        assert 'id="inv-viz" class="inventory-viz-shell"' in prep_html
        assert 'id="rad-result"' in prep_html

        sitroom_html = self._html(client, '/situation-room')
        assert 'window.NOMAD_ACTIVE_TAB = "situation-room";' in sitroom_html
        assert 'data-sitroom-view="topline"' in sitroom_html
        assert 'data-sitroom-view="news"' in sitroom_html
        assert 'id="sr-posture-bar"' in sitroom_html
        assert 'id="sr-analysis-panel" hidden' in sitroom_html
        assert 'NEWS WIRE' in sitroom_html
        assert 'LIVE BROADCASTS' in sitroom_html
        assert 'data-sitroom-action="copy-desk-snapshot"' in sitroom_html
        assert 'data-sitroom-action="save-desk-note"' in sitroom_html
        assert 'data-sitroom-action="send-desk-lan"' in sitroom_html
        assert 'id="sr-story-modal"' not in sitroom_html
        assert 'onclick="runSitroomDeduction()"' not in sitroom_html
        assert '<span class="sr-layer-dot" style=' not in sitroom_html

        settings_html = self._html(client, '/settings')
        assert 'window.NOMAD_ACTIVE_TAB = "settings";' in settings_html
        assert 'DESK MEMORY' in settings_html
        assert 'id="settings-pin-current-context-btn"' in settings_html
        assert 'data-workspace-memory-action="toggle-current-pin"' in settings_html
        assert 'id="settings-launch-current-context-btn"' in settings_html
        assert 'data-workspace-memory-action="set-launch-current"' in settings_html
        assert 'id="settings-memory-launch"' in settings_html
        assert 'id="settings-memory-pinned"' in settings_html

    def test_workspace_page_bootstraps_saved_language_before_runtime_init(self, client, db):
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('language', 'es')")
        db.commit()

        html = self._html(client, '/preparedness')

        assert '<html lang="es" dir="ltr">' in html
        assert 'const i18n = {' in html
        assert '"lang": "es"' in html
        assert 'window.__NOMAD_I18N_BOOTSTRAP = i18n;' in html
        assert 'data-i18n="nav.home">Inicio<' in html
        assert 'data-i18n="nav.readiness">Estado<' in html
        assert 'data-i18n="nav.preparedness">Preparación<' in html
        assert 'data-i18n="nav.library">Biblioteca<' in html
        assert 'data-i18n="nav.media">Medios<' in html
        assert 'data-i18n="nav.copilot">Copiloto<' in html
        assert 'data-i18n="nav.diagnostics">Diagnósticos<' in html

    def test_shared_css_avoids_transition_all(self):
        css_root = REPO_ROOT / 'web' / 'static' / 'css'
        css_files = [
            css_root / 'app.css',
            css_root / 'premium.css',
            REPO_ROOT / 'web' / 'nukemap' / 'css' / 'styles.css',
            *sorted((css_root / 'app').glob('*.css')),
            *sorted((css_root / 'premium').glob('*.css')),
        ]
        for css_file in css_files:
            contents = css_file.read_text(encoding='utf-8')
            assert 'transition: all' not in contents, f'transition: all found in {css_file.name}'

    def test_gitignore_covers_legacy_binaries_and_runtime_artifacts(self):
        contents = (REPO_ROOT / '.gitignore').read_text(encoding='utf-8')

        assert 'NOMAD-Setup.exe' in contents
        assert 'NOMADFieldDesk.exe' in contents
        assert 'ProjectNOMAD-Setup.exe' in contents
        assert 'ProjectNOMAD.exe' in contents
        assert '.pytest_tmp/' in contents
        assert 'test_runtime/' in contents
        assert 'test_runtime_probe/' in contents

    def test_runtime_js_uses_shared_micro_ui_classes_instead_of_old_fixed_inline_styles(self):
        js_root = REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js'
        js_files = sorted(js_root.rglob('*.js'))
        combined = '\n'.join(path.read_text(encoding='utf-8') for path in js_files)
        style_count = sum(text.count('style="') + text.count('style=\\"') for text in [combined])

        assert 'class="runtime-empty-note"' in combined
        assert 'class="runtime-table-head-compact"' in combined
        assert 'class="weather-rule-condition"' in combined
        assert 'class="network-status-inline' in combined
        assert 'class="tour-content-title"' in combined
        assert 'class="note-template-item-icon"' in combined
        assert 'class="runtime-status-installed"' in combined
        assert 'class="coords-result-block"' in combined
        assert 'class="activity-service-tag"' in combined
        assert 'class="alert-dismiss alert-dismiss-link"' in combined
        assert 'class="antenna-result-value"' in combined
        assert 'note-backlink-link' in combined

        assert 'style="font-size:15px;color:${muted};"' not in combined
        assert 'style="display:block;margin-bottom:6px;column-span:all;"' not in combined
        assert 'style="color:var(--text-dim);font-size:12px;">No waypoints saved.' not in combined
        assert 'style="font-family:var(--font-data,monospace);font-weight:600;"' not in combined
        assert 'style="font-size:15px;margin-bottom:6px;"' not in combined
        assert 'style="font-size:13px;color:var(--text-dim);line-height:1.6;"' not in combined
        assert style_count <= 100, f'JS runtime inline style count regressed to {style_count}'

    def test_index_template_uses_theme_tokens_without_inline_body_override(self):
        index_text = (REPO_ROOT / 'web' / 'templates' / 'index.html').read_text(encoding='utf-8')
        workspace_page_text = (REPO_ROOT / 'web' / 'templates' / 'workspace_page.html').read_text(encoding='utf-8')

        assert '<style>' not in index_text
        assert 'body{background:' not in index_text
        assert '<style>' not in workspace_page_text
        assert 'body{background:' not in workspace_page_text

    def test_css_focus_contract_does_not_regress_to_outline_none(self):
        css_root = REPO_ROOT / 'web' / 'static' / 'css'
        combined = '\n'.join(path.read_text(encoding='utf-8') for path in sorted(css_root.rglob('*.css')))

        assert 'outline: none' not in combined
        assert 'outline:none' not in combined
        assert ':focus-visible' in combined

    def test_embedded_tool_pages_keep_zoom_enabled_and_status_regions(self):
        viptrack_text = (REPO_ROOT / 'web' / 'viptrack' / 'index.html').read_text(encoding='utf-8')
        nukemap_text = (REPO_ROOT / 'web' / 'nukemap' / 'index.html').read_text(encoding='utf-8')
        nukemap_partial = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_nukemap.html').read_text(encoding='utf-8')

        assert 'maximum-scale=1.0' not in viptrack_text
        assert 'user-scalable=no' not in viptrack_text
        assert 'user-scalable=no' not in nukemap_text
        assert 'transition: all' not in viptrack_text
        assert 'aria-label="Clear search"' in viptrack_text
        assert 'role="tablist"' in viptrack_text
        assert 'aria-controls="bottomPanels"' in viptrack_text
        assert 'aria-controls="settingsPanel"' in viptrack_text
        assert 'role="status" aria-live="polite" aria-atomic="true"' in viptrack_text
        assert 'aria-controls="panel"' in nukemap_text
        assert 'aria-expanded="true"' in nukemap_text
        assert 'Select scenario…' in nukemap_text
        assert 'Select scenario...' not in nukemap_text
        assert 'role="status" aria-live="polite" aria-atomic="true"' in nukemap_text
        assert 'role="status" aria-live="polite" aria-atomic="true"' in nukemap_partial
        assert '@media (prefers-reduced-motion: reduce)' in viptrack_text
        assert '@media (prefers-reduced-motion: reduce)' in nukemap_partial
        assert viptrack_text.index('const searchSystem = {') < viptrack_text.index('searchSystem.init();')

    def test_app_css_is_split_into_ordered_import_manifest(self):
        manifest = REPO_ROOT / 'web' / 'static' / 'css' / 'app.css'
        app_dir = REPO_ROOT / 'web' / 'static' / 'css' / 'app'
        manifest_text = manifest.read_text(encoding='utf-8')
        manifest_lines = manifest_text.count('\n') + 1
        parts = sorted(app_dir.glob('*.css'))

        assert manifest_lines < 20, f'app.css manifest still too large: {manifest_lines} lines'
        assert len(parts) >= 6, f'expected app css parts, found {len(parts)}'
        assert '@import url("./app/00_theme_tokens.css");' in manifest_text
        assert '@import url("./app/70_cleanup_utilities.css");' in manifest_text

    def test_premium_css_is_split_into_ordered_import_manifest(self):
        manifest = REPO_ROOT / 'web' / 'static' / 'css' / 'premium.css'
        premium_dir = REPO_ROOT / 'web' / 'static' / 'css' / 'premium'
        manifest_text = manifest.read_text(encoding='utf-8')
        manifest_lines = manifest_text.count('\n') + 1
        parts = sorted(premium_dir.glob('*.css'))

        assert manifest_lines < 20, f'premium.css manifest still too large: {manifest_lines} lines'
        assert len(parts) >= 6, f'expected premium css parts, found {len(parts)}'
        assert '@import url("./premium/00_base.css");' in manifest_text
        assert '@import url("./premium/70_layout_hardening.css");' in manifest_text

    def test_partial_controls_have_names(self):
        partial_dir = REPO_ROOT / 'web' / 'templates' / 'index_partials'
        control_pattern = re.compile(r'<(input|select|textarea)\b([^>]*)>', re.I)
        missing = []

        for partial in sorted(partial_dir.rglob('*.html')):
            text = partial.read_text(encoding='utf-8')
            for match in control_pattern.finditer(text):
                attrs = match.group(2).lower()
                if ' type="hidden"' in attrs or " type='hidden'" in attrs:
                    continue
                if ' name=' not in attrs:
                    missing.append(f'{partial.name}:{match.group(0)[:120]}')

        assert not missing, f'controls missing name attributes: {missing[:10]}'

    def test_split_partials_avoid_legacy_inline_hidden_and_layout_styles(self):
        html_root = REPO_ROOT / 'web' / 'templates' / 'index_partials'
        js_root = html_root / 'js'
        forbidden = [
            'style="display:none;"',
            'style="width:0%"',
            'style="display:none;width:100%;margin-top:4px;"',
            'style="grid-column:1/-1;"',
            'style="margin-left:auto;"',
        ]
        offenders = []

        for path in sorted(html_root.rglob('*.html')):
            text = path.read_text(encoding='utf-8')
            for token in forbidden:
                if token in text:
                    offenders.append(f'{path.name}:{token}')

        for path in sorted(js_root.rglob('*.js')):
            text = path.read_text(encoding='utf-8')
            for token in forbidden:
                if token in text:
                    offenders.append(f'{path.name}:{token}')

        assert not offenders, f'legacy inline style tokens found: {offenders[:10]}'

    def test_preparedness_tab_is_split_into_domain_partials(self):
        parent = REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_preparedness.html'
        prep_dir = REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'preparedness'
        parent_text = parent.read_text(encoding='utf-8')
        parent_lines = parent_text.count('\n') + 1
        prep_partials = sorted(prep_dir.glob('*.html'))

        assert parent_lines < 40, f'preparedness parent partial still too large: {parent_lines} lines'
        assert len(prep_partials) >= 12, f'expected preparedness domain partials, found {len(prep_partials)}'
        assert '{% include "index_partials/preparedness/_overview.html" %}' in parent_text
        assert '{% include "index_partials/preparedness/_guides.html" %}' in parent_text
        assert '{% include "index_partials/preparedness/_analytics.html" %}' in parent_text

    def test_preparedness_runtime_is_split_into_domain_partials(self):
        parent = REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_preparedness_core.js'
        prep_dir = REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / 'preparedness'
        parent_text = parent.read_text(encoding='utf-8')
        parent_lines = parent_text.count('\n') + 1
        prep_partials = sorted(prep_dir.glob('*.js'))

        assert parent_lines < 20, f'preparedness runtime manifest still too large: {parent_lines} lines'
        assert len(prep_partials) >= 5, f'expected preparedness runtime partials, found {len(prep_partials)}'
        assert '{% include "index_partials/js/preparedness/_prep_nav_core.js" %}' in parent_text
        assert '{% include "index_partials/js/preparedness/_prep_inventory_flows.js" %}' in parent_text
        assert '{% include "index_partials/js/preparedness/_prep_calcs_misc.js" %}' in parent_text

    def test_workspace_memory_runtime_is_split_from_main_workspaces(self):
        manifest = REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_app_inline.js'
        workspaces = REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspaces.js'
        memory = REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspace_memory.js'

        manifest_text = manifest.read_text(encoding='utf-8')
        workspaces_lines = workspaces.read_text(encoding='utf-8').count('\n') + 1
        memory_lines = memory.read_text(encoding='utf-8').count('\n') + 1

        assert "{% include 'index_partials/js/_app_workspace_memory.js' %}" in manifest_text
        assert workspaces_lines < 2500, f'workspace runtime still too large: {workspaces_lines} lines'
        assert memory_lines > 500, f'workspace memory runtime looks unexpectedly small: {memory_lines} lines'

    def test_index_page_runtime_shell_blocks(self, client):
        home_html = self._html(client, '/')
        assert 'data-tab-target="preparedness" data-prep-sub="inventory"' in home_html
        assert 'data-tab-target="services"' in home_html
        assert 'data-stop-propagation' in home_html
        assert 'id="workspace-context-bar" class="workspace-context-bar" hidden' in home_html
        assert 'id="command-palette-overlay" class="command-palette-overlay"' in home_html

        notes_html = self._html(client, '/notes')
        assert 'data-note-action="create-note"' in notes_html
        assert 'data-note-action="select-note"' in notes_html
        assert 'data-note-action="apply-note-template"' in notes_html
        assert 'class="note-item-head"' in notes_html
        assert 'data-workspace-guide-target="notes"' not in notes_html

        media_html = self._html(client, '/media')
        assert 'data-media-sub-switch="channels"' in media_html
        assert 'data-media-action="download-url"' in media_html
        assert 'data-media-action="resume-media"' in media_html
        assert 'class="media-download-item"' in media_html
        assert 'data-workspace-guide-target="media"' not in media_html

        maps_html = self._html(client, '/maps')
        assert 'data-map-action="toggle-map-view"' in maps_html
        assert 'data-map-action="delete-map"' in maps_html
        assert 'data-input-action="geocode-search"' in maps_html
        assert 'map-zone-panel' in maps_html

        tools_html = self._html(client, '/tools')
        assert 'data-tool-action="start-compass"' in tools_html
        assert 'data-drill-type="72hour"' in tools_html
        assert 'class="tools-subsection-head"' in tools_html

        diagnostics_html = self._html(client, '/diagnostics')
        assert 'data-benchmark-mode="full"' in diagnostics_html
        assert 'class="benchmark-command-deck workspace-panel"' in diagnostics_html

    def test_manifest_uses_nomad_branding(self):
        manifest = (REPO_ROOT / 'web' / 'static' / 'manifest.json').read_text(encoding='utf-8')
        assert '"name": "NOMAD Field Desk"' in manifest
        assert '"short_name": "NOMAD"' in manifest
        assert '/static/nomad-mark.svg' in manifest

    def test_desktop_branding_assets_exist(self):
        assert (REPO_ROOT / 'icon.ico').is_file()
        assert (REPO_ROOT / 'nomad-mark.png').is_file()
        assert (REPO_ROOT / 'web' / 'static' / 'logo.png').is_file()

    def test_packaging_files_use_nomad_field_desk_branding(self):
        build_spec = (REPO_ROOT / 'build.spec').read_text(encoding='utf-8')
        installer = (REPO_ROOT / 'installer.iss').read_text(encoding='utf-8')
        workflow = (REPO_ROOT / '.github' / 'workflows' / 'build.yml').read_text(encoding='utf-8')
        readme = (REPO_ROOT / 'README.md').read_text(encoding='utf-8')
        package_json = (REPO_ROOT / 'package.json').read_text(encoding='utf-8')

        assert "name='NOMADFieldDesk'" in build_spec
        assert '#define MyAppName "NOMAD Field Desk"' in installer
        assert '#define MyAppExeName "NOMADFieldDesk.exe"' in installer
        assert 'OutputBaseFilename=NOMAD-Setup' in installer
        assert 'artifact: NOMADFieldDesk-Windows' in workflow
        assert 'release/NOMAD-Setup.exe' in workflow
        assert '# NOMAD Field Desk v1.0.0' in readme
        assert 'NOMADFieldDesk-Windows.exe' in readme
        assert 'NOMAD-Setup.exe' in readme
        assert '"name": "nomad-field-desk"' in package_json


class TestSettingsEndpoint:
    def test_get_settings(self, client):
        resp = client.get('/api/settings')
        assert resp.status_code == 200

    def test_save_setting(self, client):
        resp = client.put('/api/settings', json={
            'theme': 'dark',
        })
        assert resp.status_code == 200
