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
        assert 'src="/static/logo.png"' in html
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
        assert 'window.NOMAD_FIRST_RUN_COMPLETE = false;' in html
        assert 'window.NOMAD_WIZARD_SHOULD_LAUNCH = true;' in html
        assert 'Stand up the desk before the network becomes the problem.' in html
        assert 'Start Guided Setup' in html
        assert 'data-tab-target="services"' in html
        assert 'id="gs-resume-setup-btn"' in html
        assert 'id="gs-onboarding-note"' in html
        assert 'id="wiz-mini-banner"' in html
        assert 'data-shell-action="restore-wizard"' in html
        assert 'name="unified_search"' in html
        assert 'aria-labelledby="shortcuts-title"' in html
        assert 'data-mode-select="command"' in html
        assert 'class="home-launch-deck"' in html
        assert 'class="home-launch-hero home-surface-panel"' in html
        assert 'COMMAND DESK' in html
        assert 'Find the desk you need and reopen work with context intact.' in html
        assert 'id="home-continue-panel" class="home-continue-panel home-surface-panel"' in html
        assert 'Pinned' in html
        assert 'Recent' in html
        assert 'id="command-palette-overlay" class="command-palette-overlay" role="dialog" aria-modal="true" aria-labelledby="command-palette-title" aria-hidden="true" hidden' in html
        assert 'id="workspace-context-bar" class="workspace-context-bar" hidden' in html
        assert 'id="workspace-inspector"' not in html
        assert 'id="sidebar-context-hub"' in html
        assert 'Return' in html
        assert 'Keep your pinned desks and live context one click away.' in html
        assert 'Suggested actions' in html
        assert 'Stay in the flow with the next step that fits the desk you already have open.' in html
        assert 'id="mobile-bottom-nav"' not in html
        assert 'data-shell-action="open-mobile-drawer"' not in html
        assert 'class="sidebar-toggle"' not in html
        assert 'viewport-fit=cover' in html
        assert 'data-install-service="ollama"' in html
        assert 'data-shell-action="dismiss-broadcast"' in html
        assert 'id="broadcast-banner" class="broadcast-banner is-hidden"' in html
        assert 'id="tab-services"' in html
        assert 'id="tab-preparedness"' not in html
        assert 'id="tab-situation-room"' not in html
        assert 'id="tab-maps"' not in html
        assert 'id="tab-settings"' not in html
        runtime_js = self._html(client, '/app-runtime.js?v=test')
        assert 'Can my family use it from another computer on the network?' in runtime_js
        assert 'data-shell-action="install-service"' in runtime_js
        assert 'data-shell-action="reload-services"' in runtime_js
        assert 'utility-fab' not in html

    def test_workspace_pages_are_segmented(self, client):
        pages = [
            ('/situation-room', 'Situation Room · NOMAD Field Desk', 'tab-situation-room', 'sr-map-command-brief', ['tab-services', 'tab-settings', 'tab-media']),
            ('/preparedness', 'Preparedness · NOMAD Field Desk', 'tab-preparedness', 'data-prep-category="coordinate"', ['tab-services', 'tab-situation-room', 'tab-settings']),
            ('/maps', 'Maps · NOMAD Field Desk', 'tab-maps', 'class="map-command-deck map-surface"', ['tab-preparedness', 'tab-media', 'tab-settings']),
            ('/loadout', 'Loadout · NOMAD Field Desk', 'tab-loadout', 'class="loadout-command-deck"', ['tab-preparedness', 'tab-media', 'tab-settings']),
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
                assert 'data-src="/viptrack/?embed=nomad"' in html
                assert 'loading="lazy"' in html
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

        loadout_html = self._html(client, '/loadout')
        assert 'window.NOMAD_ACTIVE_TAB = "loadout";' in loadout_html
        assert '"loadout": "/loadout"' in loadout_html
        assert 'id="lo-bags-grid"' in loadout_html
        assert 'Loadout Manager' in loadout_html
        assert 'window.loadLoadout = loadLoadout;' in loadout_html
        assert 'id="tab-services"' not in loadout_html
        assert 'id="tab-settings"' not in loadout_html

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

    def test_shared_premium_polish_contract_for_shell_home_and_settings(self):
        premium_text = (REPO_ROOT / 'web' / 'static' / 'css' / 'premium' / '90_theme_consistency.css').read_text(encoding='utf-8')
        shell_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_shell.html').read_text(encoding='utf-8')
        services_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_services.html').read_text(encoding='utf-8')
        settings_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_settings.html').read_text(encoding='utf-8')

        assert '.workspace-context-bar {' in premium_text
        assert '.settings-command-pill {' in premium_text
        assert '.daily-brief-empty' in premium_text
        assert '.benchmark-empty-state' in premium_text
        assert 'Quick Return' in shell_text
        assert 'Suggested actions' in shell_text
        assert 'Find the desk you need and reopen work with context intact.' in services_text
        assert 'Pinned desks, startup desks, and recent return points stay staged here for quick re-entry.' in services_text
        assert 'Building your live dashboard...' in services_text
        assert 'Collecting live system metrics...' in settings_text
        assert 'No AI models are installed yet. Choose a recommended model below or download the full set.' in settings_text

    def test_specialty_workspaces_gain_premium_command_decks_and_calmer_empty_states(self):
        benchmark_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_benchmark.html').read_text(encoding='utf-8')
        benchmark_css = (REPO_ROOT / 'web' / 'static' / 'css' / 'premium' / '60_benchmark_tools.css').read_text(encoding='utf-8')
        interop_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_interoperability.html').read_text(encoding='utf-8')
        training_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_training_knowledge.html').read_text(encoding='utf-8')

        assert 'See how this machine will feel under live NOMAD workloads.' in benchmark_text
        assert 'Run a full benchmark to generate a NOMAD score, a local-model recommendation, and a baseline for future comparisons.' in benchmark_text
        assert '.benchmark-command-pill {' in benchmark_css
        assert 'text-transform: none;' in benchmark_css

        assert 'class="io-command-deck workspace-panel"' in interop_text
        assert 'Move records in and out without losing structure or audit history.' in interop_text
        assert 'data-io-panel-target="history"' in interop_text
        assert 'function ioActivatePanel(panelName, focusPanel)' in interop_text
        assert 'No exports yet. Generated files and print runs will appear here.' in interop_text
        assert "Couldn\\'t load export history right now." in interop_text

        assert 'class="tk-command-deck workspace-panel"' in training_text
        assert 'Build skills, rehearse workflows, and keep operational knowledge current.' in training_text
        assert 'data-tk-panel-target="flashcards"' in training_text
        assert 'function tkActivatePanel(panelName, focusPanel = false)' in training_text
        assert 'No skills are recorded yet. Start with the first person and capability above.' in training_text
        assert 'No flashcard decks yet. Add your first card above to create one.' in training_text

    def test_agriculture_and_daily_living_gain_premium_command_decks_and_accessible_panel_switching(self):
        agriculture_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_agriculture.html').read_text(encoding='utf-8')
        daily_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_daily_living.html').read_text(encoding='utf-8')

        assert 'class="ag-command-deck workspace-panel"' in agriculture_text
        assert 'Plan resilient food systems, soil recovery, and closed-loop support from one field-ready workspace.' in agriculture_text
        assert 'data-ag-panel-target="recycling"' in agriculture_text
        assert 'role="tablist" aria-label="Agriculture sections"' in agriculture_text
        assert 'function agActivatePanel(panelName, focusPanel = false)' in agriculture_text
        assert 'No guilds yet. Start with the first planting guild above to anchor the layout.' in agriculture_text
        assert 'Add recycling systems to reveal how nutrients, water, and materials loop together.' in agriculture_text

        assert 'class="dl-command-deck workspace-panel"' in daily_text
        assert 'Keep routines, morale, and grid-down quality of life stable when conditions change.' in daily_text
        assert 'data-dl-panel-target="recipes"' in daily_text
        assert 'role="tablist" aria-label="Daily living sections"' in daily_text
        assert 'function dlActivatePanel(panelName, focusPanel = false)' in daily_text
        assert '&#128197;' not in daily_text
        assert 'No morale check-ins yet. Start logging how the household is holding up.' in daily_text
        assert 'Not enough sleep data yet. Log a few more nights to build a reliable watch rotation.' in daily_text

    def test_group_ops_and_disaster_modules_gain_premium_command_decks_and_accessible_panel_switching(self):
        group_ops_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_group_ops.html').read_text(encoding='utf-8')
        disaster_modules_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_disaster_modules.html').read_text(encoding='utf-8')

        assert 'class="go-command-deck workspace-panel"' in group_ops_text
        assert 'Coordinate pods, governance, and community response from one calm operations desk.' in group_ops_text
        assert 'data-go-panel-target="civil-defense"' in group_ops_text
        assert 'role="tablist" aria-label="Group operations sections"' in group_ops_text
        assert 'function goActivatePanel(panelName, focusPanel = false)' in group_ops_text
        assert 'id="go-tab-civil-defense">Civil Defense</button>' in group_ops_text
        assert 'No pods yet. Create the first team above to anchor staffing, governance, and duty coverage.' in group_ops_text
        assert 'No community warnings yet. Published alerts and advisories will appear here.' in group_ops_text

        assert 'class="dm-command-deck workspace-panel"' in disaster_modules_text
        assert 'Stage disaster plans, hardening projects, and backup systems from one readiness workspace.' in disaster_modules_text
        assert 'data-dm-panel-target="checklists"' in disaster_modules_text
        assert 'role="tablist" aria-label="Disaster modules sections"' in disaster_modules_text
        assert 'function dmActivatePanel(panelName, focusPanel = false)' in disaster_modules_text
        assert 'No plans yet. Build the first scenario above to anchor the rest of the workspace.' in disaster_modules_text
        assert 'No fortifications yet. Add the first barrier, shelter, or hardened position above.' in disaster_modules_text
        assert 'No checklist items match the current filters.' in disaster_modules_text

    def test_medical_phase2_and_movement_ops_gain_premium_command_decks_and_accessible_panel_switching(self):
        medical_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_medical_phase2.html').read_text(encoding='utf-8')
        movement_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_movement_ops.html').read_text(encoding='utf-8')

        assert 'class="mp-command-deck workspace-panel"' in medical_text
        assert 'Track maternal care, chronic conditions, wellness, and veterinary support from one continuity desk.' in medical_text
        assert 'data-mp-panel-target="calculators"' in medical_text
        assert 'role="tablist" aria-label="Medical phase 2 sections"' in medical_text
        assert 'function mpActivatePanel(panelName, focusPanel = false)' in medical_text
        assert 'id="mp-tab-vet">Veterinary</button>' in medical_text
        assert 'No maternal care records yet. Add the first patient above to track due dates and care context.' in medical_text
        assert 'No wellness check-ins yet. Log the first mental health entry above.' in medical_text

        assert 'class="mo-command-deck workspace-panel"' in movement_text
        assert 'Plan routes, alternate transport, and departure criteria from one movement workspace.' in movement_text
        assert 'data-mo-panel-target="go-nogo"' in movement_text
        assert 'role="tablist" aria-label="Movement operations sections"' in movement_text
        assert 'function moActivatePanel(panelName, focusPanel = false)' in movement_text
        assert 'No movement plans yet. Capture the first route above to anchor timing, distance, and movement method.' in movement_text
        assert 'No alternate transport assets are registered yet. Add the first bike, animal, or watercraft above.' in movement_text
        assert 'No go/no-go criteria are defined yet. Add the first departure gate above.' in movement_text

    def test_security_opsec_and_tactical_comms_gain_premium_command_decks_and_accessible_panel_switching(self):
        security_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_security_opsec.html').read_text(encoding='utf-8')
        comms_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_tactical_comms.html').read_text(encoding='utf-8')

        assert 'class="so-command-deck workspace-panel"' in security_text
        assert 'Protect access, track threats, and coordinate contamination response from one security desk.' in security_text
        assert 'data-so-panel-target="cbrn-emp"' in security_text
        assert 'role="tablist" aria-label="Security and OPSEC sections"' in security_text
        assert 'function soActivatePanel(panelName, focusPanel = false)' in security_text
        assert 'id="so-tab-cbrn-emp">CBRN & EMP</button>' in security_text
        assert 'No compartments yet. Create the first compartment above to define access boundaries and member lists.' in security_text
        assert 'No EMP inventory yet. Add the first critical item above to assess protection gaps.' in security_text

        assert 'class="tc-command-deck workspace-panel"' in comms_text
        assert 'Keep radio plans, authentication, and field weather tools in one comms desk.' in comms_text
        assert 'data-tc-panel-target="weather"' in comms_text
        assert 'role="tablist" aria-label="Tactical communications sections"' in comms_text
        assert 'function tcActivatePanel(panelName, focusPanel = false)' in comms_text
        assert 'id="tc-tab-auth">Auth Sets</button>' in comms_text
        assert 'No radios are logged yet. Add the first handheld, base station, or repeater above.' in comms_text
        assert 'No net schedules yet. Add the first check-in window above to publish frequency and control station.' in comms_text
        assert 'No message templates yet. Seed the built-in formats or add your own reporting standard above.' in comms_text

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

    def test_workspace_page_bootstraps_onboarding_state(self, client, db):
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('first_run_complete', '1')")
        db.commit()

        settings_html = self._html(client, '/settings')
        home_html = self._html(client, '/')

        assert 'window.NOMAD_FIRST_RUN_COMPLETE = true;' in settings_html
        assert 'window.NOMAD_WIZARD_SHOULD_LAUNCH = false;' in settings_html
        assert 'window.NOMAD_FIRST_RUN_COMPLETE = true;' in home_html
        assert 'window.NOMAD_WIZARD_SHOULD_LAUNCH = false;' in home_html

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

        inline_partials = sorted((REPO_ROOT / 'web' / 'templates' / 'index_partials').glob('_tab_*.html'))
        for partial in inline_partials:
            contents = partial.read_text(encoding='utf-8')
            assert 'transition:all' not in contents, f'transition:all found in {partial.name}'
            assert 'transition: all' not in contents, f'transition: all found in {partial.name}'

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
        inline_partials = sorted((REPO_ROOT / 'web' / 'templates' / 'index_partials').glob('_tab_*.html'))
        partial_text = '\n'.join(path.read_text(encoding='utf-8') for path in inline_partials)

        assert 'outline: none' not in combined
        assert 'outline:none' not in combined
        assert 'outline: none' not in partial_text
        assert 'outline:none' not in partial_text
        assert ':focus-visible' in combined

    def test_embedded_tool_pages_keep_zoom_enabled_and_status_regions(self):
        viptrack_text = (REPO_ROOT / 'web' / 'viptrack' / 'index.html').read_text(encoding='utf-8')
        nukemap_text = (REPO_ROOT / 'web' / 'nukemap' / 'index.html').read_text(encoding='utf-8')
        nukemap_styles_text = (REPO_ROOT / 'web' / 'nukemap' / 'css' / 'styles.css').read_text(encoding='utf-8')
        nukemap_app_text = (REPO_ROOT / 'web' / 'nukemap' / 'js' / 'app.js').read_text(encoding='utf-8')
        nukemap_extras_text = (REPO_ROOT / 'web' / 'nukemap' / 'js' / 'extras.js').read_text(encoding='utf-8')
        offline_atlas_text = (REPO_ROOT / 'web' / 'nukemap' / 'data' / 'offline_atlas.json').read_text(encoding='utf-8')
        nukemap_partial = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_nukemap.html').read_text(encoding='utf-8')
        viptrack_partial = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_viptrack.html').read_text(encoding='utf-8')
        viptrack_leaflet_js = REPO_ROOT / 'web' / 'viptrack' / 'lib' / 'leaflet.js'
        viptrack_leaflet_css = REPO_ROOT / 'web' / 'viptrack' / 'lib' / 'leaflet.css'
        viptrack_pako = REPO_ROOT / 'web' / 'viptrack' / 'lib' / 'pako.min.js'

        assert 'maximum-scale=1.0' not in viptrack_text
        assert 'user-scalable=no' not in viptrack_text
        assert 'user-scalable=no' not in nukemap_text
        assert 'transition: all' not in viptrack_text
        assert 'outline: none' not in viptrack_text
        assert 'outline:none' not in viptrack_text
        assert 'outline: none' not in nukemap_styles_text
        assert 'outline:none' not in nukemap_styles_text
        assert 'outline: none' not in nukemap_partial
        assert 'outline:none' not in nukemap_partial
        assert 'aria-label="Clear search"' in viptrack_text
        assert 'role="switch"' in viptrack_text
        assert 'id="toggleTrailArrows" type="button" role="switch"' in viptrack_text
        assert 'id="toggleAlerts" type="button" role="switch"' in viptrack_text
        assert 'id="toggleNotifications" type="button" role="switch"' in viptrack_text
        assert 'aria-label="Trail color mode"' in viptrack_text
        assert 'aria-label="Military alert radius"' in viptrack_text
        assert 'aria-label="Sort aircraft list"' in viptrack_text
        assert '.toggle:focus-visible' in viptrack_text
        assert 'role="tablist"' in viptrack_text
        assert 'aria-controls="bottomPanels"' in viptrack_text
        assert 'aria-controls="settingsPanel"' in viptrack_text
        assert 'role="status" aria-live="polite" aria-atomic="true"' in viptrack_text
        assert '.search-box:focus-visible' in viptrack_text
        assert "function syncToggleSwitchState(id, checked)" in viptrack_text
        assert 'trailRenderer.init();' in viptrack_text
        assert "syncToggleSwitchState('toggleTrailArrows', this.options.showDirection);" in viptrack_text
        assert "document.getElementById('bookmarkNameInput').addEventListener('keydown'" in viptrack_text
        assert 'aria-label="Filter warheads"' in nukemap_text
        assert 'aria-label="Select warhead"' in nukemap_text
        assert 'aria-label="Yield slider"' in nukemap_text
        assert 'aria-label="Yield unit"' in nukemap_text
        assert 'aria-label="Wind speed in kilometers per hour"' in nukemap_text
        assert 'aria-controls="panel"' in nukemap_text
        assert 'aria-expanded="true"' in nukemap_text
        assert 'Select scenario…' in nukemap_text
        assert 'Select scenario...' not in nukemap_text
        assert 'role="status" aria-live="polite" aria-atomic="true"' in nukemap_text
        assert 'role="status" aria-live="polite" aria-atomic="true"' in nukemap_partial
        assert 'aria-label="Filter warheads"' in nukemap_partial
        assert 'aria-label="Select warhead"' in nukemap_partial
        assert 'aria-label="Yield slider"' in nukemap_partial
        assert 'aria-label="Yield unit"' in nukemap_partial
        assert 'aria-label="Wind speed in kilometers per hour"' in nukemap_partial
        assert '#yield-slider:focus-visible' in nukemap_styles_text
        assert '#tab-nukemap #yield-slider:focus-visible' in nukemap_partial
        assert '.toggle-row input{display:none}' not in nukemap_styles_text
        assert '#tab-nukemap .toggle-row input{display:none}' not in nukemap_partial
        assert '.toggle-row:focus-visible .tg-slider' in nukemap_styles_text
        assert '.toggle-row input:focus-visible+.tg-slider' in nukemap_styles_text
        assert '#tab-nukemap .toggle-row:focus-visible .tg-slider' in nukemap_partial
        assert '#tab-nukemap .toggle-row input:focus-visible+.tg-slider' in nukemap_partial
        assert '.toggle-row input{position:absolute;inset:0;margin:0;opacity:0;cursor:pointer}' in nukemap_styles_text
        assert '#tab-nukemap .toggle-row input{position:absolute;inset:0;margin:0;opacity:0;cursor:pointer}' in nukemap_partial
        assert 'NM.enhanceToggleRows = function()' in nukemap_app_text
        assert "toggleRow.setAttribute('role', 'switch');" in nukemap_app_text
        assert "if (input.id) toggleRow.dataset.toggleInput = input.id;" in nukemap_app_text
        assert '@media (prefers-reduced-motion: reduce)' in viptrack_text
        assert '@media (prefers-reduced-motion: reduce)' in nukemap_partial
        assert '/viptrack/lib/leaflet.css' in viptrack_text
        assert '/viptrack/lib/leaflet.js' in viptrack_text
        assert '/viptrack/lib/pako.min.js' in viptrack_text
        assert viptrack_leaflet_js.exists()
        assert viptrack_leaflet_css.exists()
        assert viptrack_pako.exists()
        assert viptrack_text.index('const searchSystem = {') < viptrack_text.index('searchSystem.init();')
        assert 'body.day-mode .aircraft-marker.vip .sprite-icon' in viptrack_text
        assert 'refreshAircraftMarkerTheme()' in viptrack_text
        assert '_clearPausableInterval' in viptrack_text
        assert "_setPausableInterval(() => this.checkConnection(), 30000, 'offlineConnection')" in viptrack_text
        assert 'pauseWorkspaceActivity()' in viptrack_text
        assert 'onHidden()' in viptrack_text
        assert 'const preserveSettingsOpen = !!(' in viptrack_text
        assert 'const preserveBottomPanelsOpen = !!(' in viptrack_text
        assert 'setSettingsPanelOpen(preserveSettingsOpen);' in viptrack_text
        assert 'setBottomPanelsOpen(preserveBottomPanelsOpen);' in viptrack_text
        assert "const OFFLINE_ATLAS_STORAGE_KEY = 'nomad-offline-atlas-cache';" in viptrack_text
        assert "const OFFLINE_ATLAS_URL = '/nukemap/data/offline_atlas.json';" in viptrack_text
        assert 'onboardAtlasStatus' in viptrack_text
        assert 'offlineAtlasStatus' in viptrack_text
        assert 'installOfflineAtlasBtn' in viptrack_text
        assert 'Enhanced offline basemap ready. VIPTrack now has real coastlines, country borders, state and province outlines, lakes, rivers, and place labels offline.' in viptrack_text
        assert 'offlineAtlasReady: !!offlineAtlasData' in viptrack_text
        assert 'window.NomadEmbeddedWorkspaceState?.save?.(tabId, snapshot);' in viptrack_partial
        assert "persistFrameSnapshot('tab-hidden')" in viptrack_partial
        assert 'NM.getHostSnapshot = function()' in nukemap_app_text
        assert 'nomad-offline-atlas-cache' in nukemap_app_text
        assert 'NM.installOfflineAtlas = function()' in nukemap_app_text
        assert 'NM.buildOfflineAtlasLayer = function(theme)' in nukemap_app_text
        assert 'data-src="/viptrack/?embed=nomad"' in viptrack_partial
        assert 'loading="lazy"' in viptrack_partial
        assert 'aria-busy="true"' in viptrack_partial
        assert 'ensureFrameLoaded()' in viptrack_partial
        assert '_nomadTabLeaveCallbacks[tabId]' in viptrack_partial
        assert 'NM.ensureZipcodesLoaded = function()' in nukemap_app_text
        assert 'NM.syncAmbientUi = function(options = {})' in nukemap_app_text
        assert 'offlineAtlas: NM.buildOfflineAtlasLayer?.(' in nukemap_extras_text
        assert 'refreshOfflineAtlasLayer()' in nukemap_extras_text
        assert "document.querySelector('script[data-nukemap-zipcodes=\"true\"]')" in nukemap_app_text
        assert 'welcome-atlas-status' in nukemap_text
        assert 'welcome-atlas-status' in nukemap_partial
        assert 'data-layer="offlineAtlas"' in nukemap_text
        assert 'data-layer="offlineAtlas"' in nukemap_partial
        assert '"version":"2026-04-02.3"' in offline_atlas_text
        assert '"dataset":"Natural Earth 1:50m"' in offline_atlas_text
        assert '"countryBorders":[' in offline_atlas_text
        assert '"admin1Borders":[' in offline_atlas_text
        assert '"lakes":[' in offline_atlas_text
        assert '"rivers":[' in offline_atlas_text
        assert '"places":[' in offline_atlas_text
        assert "window.NomadEmbeddedWorkspaceState?.save?.('nukemap', snapshot);" in nukemap_partial
        assert '_nomadTabLeaveCallbacks.nukemap' in nukemap_partial

    def test_runtime_generated_import_training_and_scan_controls_keep_semantics(self):
        interop_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_interoperability.html').read_text(encoding='utf-8')
        training_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_training_knowledge.html').read_text(encoding='utf-8')
        prep_inventory_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / 'preparedness' / '_prep_inventory_flows.js').read_text(encoding='utf-8')
        init_runtime_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_init_runtime.js').read_text(encoding='utf-8')

        assert 'role="button" tabindex="0" aria-label="Choose an import file" data-click-target="io-import-file-input"' in interop_text
        assert '.io-drop-zone:focus-visible' in interop_text
        assert "onclick=\"document.getElementById('io-import-file-input').click()\"" not in interop_text

        assert '<button type="button" class="tk-card tk-card-button"' in training_text
        assert 'aria-label="Review ' in training_text
        assert '.tk-card-button:focus-visible' in training_text
        assert '.tk-btn:focus-visible' in training_text
        assert '<div class="tk-card" style="cursor:pointer" onclick="tkStartReview(' not in training_text

        assert 'alt="Receipt preview"' in prep_inventory_text
        assert 'alt="Supply image preview"' in prep_inventory_text
        assert 'aria-label="Select all scanned receipt items"' in prep_inventory_text
        assert 'aria-label="Select receipt item ${i + 1}"' in prep_inventory_text
        assert 'aria-label="Receipt item name ${i + 1}"' in prep_inventory_text
        assert 'aria-label="Receipt quantity ${i + 1}"' in prep_inventory_text
        assert 'aria-label="Select detected inventory item ${i + 1}"' in prep_inventory_text
        assert 'aria-label="Detected item name ${i + 1}"' in prep_inventory_text
        assert 'aria-label="Detected item quantity ${i + 1}"' in prep_inventory_text
        assert 'aria-label="Detected item category ${i + 1}"' in prep_inventory_text
        assert 'aria-label="Detected item condition ${i + 1}"' in prep_inventory_text

        assert 'aria-label="Map CSV column ${escapeAttr(h)}"' in init_runtime_text

    def test_interoperability_and_training_sub_tab_semantics(self):
        interop_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_interoperability.html').read_text(encoding='utf-8')
        training_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_training_knowledge.html').read_text(encoding='utf-8')

        # IO: tablist container
        assert 'role="tablist"' in interop_text
        assert 'aria-label="Data exchange sections"' in interop_text
        # IO: each tab button has role, aria-selected, aria-controls, and type
        assert 'role="tab" aria-selected="true" aria-controls="io-panel-export" id="io-tab-export"' in interop_text
        assert 'role="tab" aria-selected="false" aria-controls="io-panel-import" id="io-tab-import"' in interop_text
        assert 'role="tab" aria-selected="false" aria-controls="io-panel-batch" id="io-tab-batch"' in interop_text
        assert 'role="tab" aria-selected="false" aria-controls="io-panel-history" id="io-tab-history"' in interop_text
        # IO: panels have role=tabpanel, tabindex, aria-labelledby
        assert 'role="tabpanel" tabindex="-1" aria-labelledby="io-tab-export"' in interop_text
        assert 'role="tabpanel" tabindex="-1" aria-labelledby="io-tab-import"' in interop_text
        assert 'role="tabpanel" tabindex="-1" aria-labelledby="io-tab-batch"' in interop_text
        assert 'role="tabpanel" tabindex="-1" aria-labelledby="io-tab-history"' in interop_text
        # IO: history tables have accessible names
        assert 'aria-label="Recent exports"' in interop_text
        assert 'aria-label="Recent imports"' in interop_text
        # IO: focus-visible on sub-tab and btn
        assert '.io-sub-tab:focus-visible' in interop_text
        assert '.io-btn:focus-visible' in interop_text
        assert 'data-io-panel-target="export"' in interop_text
        # IO: JS switches aria-selected on tab change
        assert "b.setAttribute('aria-selected', 'false')" in interop_text
        assert "btn.setAttribute('aria-selected', 'true')" in interop_text

        # TK: tablist container
        assert 'role="tablist"' in training_text
        assert 'aria-label="Training and knowledge sections"' in training_text
        # TK: each tab button has role, aria-selected, aria-controls, and type
        assert 'role="tab" aria-selected="true" aria-controls="tk-panel-skills" id="tk-tab-skills"' in training_text
        assert 'role="tab" aria-selected="false" aria-controls="tk-panel-courses" id="tk-tab-courses"' in training_text
        assert 'role="tab" aria-selected="false" aria-controls="tk-panel-flashcards" id="tk-tab-flashcards"' in training_text
        # TK: panels have role=tabpanel, tabindex, aria-labelledby
        assert 'role="tabpanel" tabindex="-1" aria-labelledby="tk-tab-skills"' in training_text
        assert 'role="tabpanel" tabindex="-1" aria-labelledby="tk-tab-courses"' in training_text
        assert 'role="tabpanel" tabindex="-1" aria-labelledby="tk-tab-drills"' in training_text
        assert 'role="tabpanel" tabindex="-1" aria-labelledby="tk-tab-knowledge"' in training_text
        assert 'data-tk-panel-target="skills"' in training_text
        # TK: JS switches aria-selected on tab change
        assert "b.setAttribute('aria-selected', 'false')" in training_text
        assert "btn.setAttribute('aria-selected', 'true')" in training_text
        # TK: cross-training matrix modal has dialog semantics
        assert 'role="dialog" aria-modal="true" aria-labelledby="tk-matrix-title"' in training_text
        assert 'id="tk-matrix-title"' in training_text
        assert 'id="tk-matrix-close"' in training_text
        assert 'aria-label="Close cross-training matrix"' in training_text
        assert "type=\"button\"" in training_text
        # TK: tkShowMatrix focuses close button on open
        assert "closeBtn.focus()" in training_text

    def test_runtime_generated_media_and_preview_images_keep_alt_and_intrinsic_sizing(self):
        media_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_media_maps_sync.js').read_text(encoding='utf-8')
        services_ai_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_services_ai.js').read_text(encoding='utf-8')
        workspaces_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspaces.js').read_text(encoding='utf-8')
        secondary_css_text = (REPO_ROOT / 'web' / 'static' / 'css' / 'app' / '30_secondary_workspaces.css').read_text(encoding='utf-8')
        viptrack_text = (REPO_ROOT / 'web' / 'viptrack' / 'index.html').read_text(encoding='utf-8')

        assert 'class="media-card-thumb-img" loading="lazy" width="160" height="90" alt="Thumbnail for ${escapeAttr(v.title)}"' in media_text
        assert 'class="media-list-thumb" loading="lazy" width="48" height="27" alt="Thumbnail for ${escapeAttr(v.title)}"' in media_text
        assert 'class="media-browser-thumb-img" loading="lazy" width="160" height="90" alt="Thumbnail for ${escapeAttr(v.title)}"' in media_text
        assert 'alt="Operational map snapshot" width="${printWidth}" height="${printHeight}"' in media_text
        assert 'alt="Preview of ' in services_ai_text
        assert 'class="chat-image-preview-thumb" alt="Preview of ' in services_ai_text
        assert 'width="40" height="40"' in services_ai_text
        assert '.chat-image-preview-thumb {' in secondary_css_text
        assert 'width: 40px;' in secondary_css_text
        assert 'object-fit: cover;' in secondary_css_text
        assert 'alt="Map export preview" width="' in workspaces_text
        assert '<div class="airline-banner" id="airlineBanner" style="display:none;"><img src="" alt="" width="160" height="32"></div>' in viptrack_text

    def test_blob_downloads_and_viptrack_pwa_use_static_assets_and_safe_cleanup(self):
        init_runtime_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_init_runtime.js').read_text(encoding='utf-8')
        media_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_media_maps_sync.js').read_text(encoding='utf-8')
        services_ai_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_services_ai.js').read_text(encoding='utf-8')
        sitroom_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_situation_room.js').read_text(encoding='utf-8')
        prep_inventory_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / 'preparedness' / '_prep_inventory_flows.js').read_text(encoding='utf-8')
        viptrack_text = (REPO_ROOT / 'web' / 'viptrack' / 'index.html').read_text(encoding='utf-8')
        viptrack_manifest_text = (REPO_ROOT / 'web' / 'viptrack' / 'manifest.webmanifest').read_text(encoding='utf-8')
        viptrack_sw_text = (REPO_ROOT / 'web' / 'viptrack' / 'sw.js').read_text(encoding='utf-8')

        assert 'function revokeObjectUrlSafe(url)' in init_runtime_text
        assert 'function downloadBlobFile(blob, filename)' in init_runtime_text
        assert "window.downloadBlobFile = downloadBlobFile;" in init_runtime_text
        assert 'link.click();' in init_runtime_text
        assert 'window.setTimeout(() => {' in init_runtime_text
        assert 'a.click(); URL.revokeObjectURL(url);' not in init_runtime_text

        assert "window.downloadBlobFile(blob, filename || 'nomad-document.pdf');" in media_text
        assert 'const blobUrl = URL.createObjectURL(blob);' not in media_text
        assert 'a.click(); URL.revokeObjectURL(url);' not in media_text

        assert 'window._chatImagePreviewUrl = null;' in services_ai_text
        assert "preview.innerHTML = '';" in services_ai_text
        assert 'const objectUrl = URL.createObjectURL(file);' in prep_inventory_text
        assert "window.revokeObjectUrlSafe?.(objectUrl);" in prep_inventory_text
        assert 'window.downloadBlobFile(blob, `sitroom-desk-snapshot-${Date.now()}.txt`);' in sitroom_text
        assert 'const workerUrl = URL.createObjectURL(blob);' in sitroom_text
        assert "window.setTimeout(() => window.revokeObjectUrlSafe?.(workerUrl), 0);" in sitroom_text

        assert 'document.write(' not in viptrack_text
        assert "manifestLink.href = '/viptrack/manifest.webmanifest';" in viptrack_text
        assert "const viptrackServiceWorkerUrl = new URL('/viptrack/sw.js', window.location.origin).href;" in viptrack_text
        assert "navigator.serviceWorker.register(viptrackServiceWorkerUrl, { scope: '/viptrack/' })" in viptrack_text
        assert 'const manifestBlob = new Blob' not in viptrack_text
        assert 'const swBlob = new Blob' not in viptrack_text
        assert 'for (const r of regs) await r.unregister();' not in viptrack_text

        assert '"scope": "/viptrack/"' in viptrack_manifest_text
        assert '"start_url": "/viptrack/"' in viptrack_manifest_text
        assert "const CACHE_NAME = 'viptrack-v4.15';" in viptrack_sw_text
        assert "'/viptrack/manifest.webmanifest'," in viptrack_sw_text
        assert 'function isStaticAssetRequest(url, requestUrl) {' in viptrack_sw_text

    def test_print_popup_flows_open_windows_synchronously_and_render_status_shells(self):
        init_runtime_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_init_runtime.js').read_text(encoding='utf-8')
        media_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_media_maps_sync.js').read_text(encoding='utf-8')
        workspaces_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspaces.js').read_text(encoding='utf-8')

        assert 'function renderPopupStatus(popup, title, message, tone = \'info\') {' in init_runtime_text
        assert 'function replacePopupHtml(popup, html) {' in init_runtime_text
        assert 'function openPendingPopup(title, loadingMessage = \'Preparing document…\') {' in init_runtime_text
        assert "window.openPendingPopup = openPendingPopup;" in init_runtime_text
        assert "window.replacePopupHtml = replacePopupHtml;" in init_runtime_text
        assert "const w = window.openPendingPopup?.('ICS-213', 'Preparing the printable ICS-213 form…');" in init_runtime_text
        assert "const w = window.openPendingPopup?.('ICS-309', 'Preparing the printable ICS-309 log…');" in init_runtime_text
        assert "const w = window.openPendingPopup?.('ICS-214', 'Preparing the printable ICS-214 activity log…');" in init_runtime_text
        assert 'w.document.write(`<!DOCTYPE html><html><head><title>ICS-213</title>' not in init_runtime_text
        assert "const w = window.openPendingPopup?.('Generating Map Atlas', 'Building the printable atlas packet. This can take a moment for larger grids.');" in media_text
        assert "window.renderPopupStatus?.(w, 'Map Atlas Unavailable'" in media_text
        assert "if (!window.replacePopupHtml?.(w, html)) {" in media_text
        assert "const win = window.openPendingPopup?.('NOMAD Map Print', 'Preparing the printable map capture…');" in workspaces_text
        assert "toast('Pop-up blocked -- please allow pop-ups', 'warning');" in workspaces_text
        assert "window.replacePopupHtml?.(win, '<html><head><title>NOMAD Map Print</title>" in workspaces_text

    def test_iframe_render_and_hidden_print_flows_use_shared_runtime_helpers(self):
        init_runtime_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_init_runtime.js').read_text(encoding='utf-8')
        workspaces_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspaces.js').read_text(encoding='utf-8')
        dashboards_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / 'preparedness' / '_prep_dashboards.js').read_text(encoding='utf-8')

        assert "let _iframeHtmlWriteNonce = 0;" in init_runtime_text
        assert "function writeIframeHtml(iframe, html, options = {}) {" in init_runtime_text
        assert "iframe.dataset.nomadFrameRenderToken = renderToken;" in init_runtime_text
        assert "iframe.addEventListener('load', handleBlankLoad, { once: true });" in init_runtime_text
        assert "function printHtmlInHiddenFrame(html, title = 'Document') {" in init_runtime_text
        assert "win.addEventListener('afterprint', cleanup, { once: true });" in init_runtime_text
        assert "window.writeIframeHtml = writeIframeHtml;" in init_runtime_text
        assert "window.printHtmlInHiddenFrame = printHtmlInHiddenFrame;" in init_runtime_text

        assert "function resetAppFrameSurface(iframe) {" in workspaces_text
        assert "resetAppFrameSurface(iframe);" in workspaces_text
        assert "if (window.writeIframeHtml?.(iframe, html, { scrollTo })) return;" in workspaces_text
        assert "toast('Could not load this view in the application frame', 'error');" in workspaces_text
        assert "if (!iframe || !frameWin || !frameDoc?.body || !frameDoc.body.childNodes.length) {" in workspaces_text
        assert "toast('Nothing is loaded in the application frame yet', 'warning');" in workspaces_text
        assert "frameWin.focus();" in workspaces_text

        assert "window.printHtmlInHiddenFrame?.(html, 'Emergency Wallet Card')" in dashboards_text
        assert "frame.contentDocument.write(html);" not in dashboards_text
        assert "setTimeout(() => { frame.contentWindow.print();" not in dashboards_text

    def test_long_running_workspace_polls_use_shared_runtime_guards(self):
        services_ai_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_services_ai.js').read_text(encoding='utf-8')
        media_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_media_maps_sync.js').read_text(encoding='utf-8')
        ops_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_ops_support.js').read_text(encoding='utf-8')
        workspaces_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspaces.js').read_text(encoding='utf-8')
        memory_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspace_memory.js').read_text(encoding='utf-8')

        assert "NomadShellRuntime?.stopInterval('services.install-progress')" in services_ai_text
        assert "NomadShellRuntime.startInterval('services.install-progress'" in services_ai_text
        assert "NomadShellRuntime.startInterval('ai-chat.model-ready'" in services_ai_text
        assert "NomadShellRuntime.startInterval('ai-chat.pull-progress'" in services_ai_text
        assert "NomadShellRuntime.startInterval('library.zim-downloads'" in services_ai_text
        assert "if (!bar || !fillEl || !detailEl || !pctEl) { stopPullProgressPolling(); return; }" in services_ai_text
        assert "if (!el) return;" in services_ai_text
        assert "const modelSelect = document.getElementById('model-select');" in services_ai_text
        assert "if (!input || !modelSelect || !sendBtn || !stopBtn) return;" in services_ai_text
        assert "const statsEl = document.getElementById('chat-stats');" in services_ai_text
        assert "if (statsEl) statsEl.textContent =" in services_ai_text
        assert "const regenBtn = document.getElementById('regen-btn');" in services_ai_text

        assert "NomadShellRuntime.startInterval('media.ytdlp-install'" in media_text
        assert "NomadShellRuntime.startInterval('media.download-progress'" in media_text
        assert 'startMediaDownloadPolling(watchId);' in media_text
        assert "NomadShellRuntime?.stopInterval('media.download-progress')" in media_text
        assert "NomadShellRuntime.startInterval('preparedness.motion-status'" in ops_text
        assert "NomadShellRuntime.startInterval('preparedness.camera-snapshots'" in ops_text
        assert 'startCameraSnapshotRefresh(cameras);' in ops_text
        assert "cameras.filter(c => c.stream_type === 'snapshot').forEach(c => {" not in ops_text
        assert "NomadShellRuntime.startInterval('shell.auto-backup'" in ops_text

        assert "NomadShellRuntime.startInterval('wizard.progress'" in workspaces_text
        assert "NomadShellRuntime.startInterval('ai-chat.kb-embed'" in workspaces_text
        assert "NomadShellRuntime.startInterval(`ai-chat.kb-analyze.${id}`" in workspaces_text
        assert "NomadShellRuntime?.stopInterval('wizard.progress')" in workspaces_text
        assert "NomadShellRuntime.startInterval('settings.update-download'" in memory_text
        assert "NomadShellRuntime?.stopInterval('settings.update-download')" in memory_text

    def test_media_workspace_uses_visibility_helper_for_hidden_panels(self):
        media_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_media_maps_sync.js').read_text(encoding='utf-8')

        assert "function setMediaVisibility(target, visible, displayValue = '') {" in media_text
        assert "function isMediaVisible(target) {" in media_text
        assert "setMediaVisibility(channelBrowser, true, 'flex');" in media_text
        assert "setMediaVisibility(results, true);" in media_text
        assert "setMediaVisibility('yt-video-results', false);" in media_text
        assert "setMediaVisibility('channel-list', true);" in media_text
        assert "setMediaVisibility('media-catalog-panel', _mediaCatalogVisible);" in media_text

    def test_onboarding_runtime_uses_real_first_run_state_and_shell_visibility_helpers(self):
        services_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_tab_services.html').read_text(encoding='utf-8')
        overlays_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_utility_overlays.html').read_text(encoding='utf-8')
        readiness_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_dashboard_readiness.js').read_text(encoding='utf-8')
        services_ai_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_services_ai.js').read_text(encoding='utf-8')
        workspaces_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspaces.js').read_text(encoding='utf-8')

        assert 'id="gs-resume-setup-btn"' in services_text
        assert 'id="gs-onboarding-note"' in services_text
        assert 'id="wiz-mini-banner"' in overlays_text
        assert "window.NOMAD_FIRST_RUN_COMPLETE === false" in readiness_text
        assert "window.NOMAD_FIRST_RUN_COMPLETE === false" in services_ai_text
        assert 'setWizardSectionVisibility(' in workspaces_text
        assert 'persistOnboardingComplete()' in workspaces_text
        assert 'clearWizardUrlFlag()' in workspaces_text
        assert "apiPost('/api/settings/wizard-complete')" in workspaces_text
        assert "setShellVisibility(document.getElementById('wiz-mini-banner'), true);" in workspaces_text
        assert "setShellVisibility(document.getElementById('wiz-mini-banner'), false);" in workspaces_text
        assert "const TOUR_SESSION_KEY = 'nomad-guided-tour-state';" in workspaces_text
        assert "const TOUR_FOCUS_KEY = 'nomad-guided-tour-focus';" in workspaces_text
        assert "_writeTourSession(_tourStep);" in workspaces_text
        assert "const activeTab = window.NOMAD_ACTIVE_TAB || getWorkspacePageTab();" in workspaces_text
        assert "openWorkspaceRouteAware(step.tab)" in workspaces_text
        assert "_queueTourFocusRestore('services');" in workspaces_text
        assert 'function restoreGuidedTourIfNeeded() {' in workspaces_text
        assert "fetch('/api/settings', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tour_complete:'1'})});" not in workspaces_text

    def test_shared_shell_runtime_skips_route_specific_ui_when_missing(self):
        ops_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_ops_support.js').read_text(encoding='utf-8')
        memory_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspace_memory.js').read_text(encoding='utf-8')

        assert "if (!banner) return;" in ops_text
        assert "if (!badge && !bar && !items && !count) return;" in ops_text
        assert "if (!preparednessBadge && !mapsBadge && !mediaBadge && !aiBadge) return;" in ops_text
        assert "if (typeof _lastServicesData !== 'undefined' && Array.isArray(_lastServicesData) && _lastServicesData.length)" in ops_text
        assert "if (!banner && !dlBtn && !statusEl) return;" in memory_text

    def test_visual_regression_harness_uses_an_isolated_nomad_server(self):
        config_text = (REPO_ROOT / 'playwright.config.mjs').read_text(encoding='utf-8')

        assert "const PLAYWRIGHT_PORT = process.env.NOMAD_PLAYWRIGHT_PORT || '4317';" in config_text
        assert "const PLAYWRIGHT_BASE_URL = process.env.NOMAD_PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${PLAYWRIGHT_PORT}`;" in config_text
        assert "baseURL: PLAYWRIGHT_BASE_URL" in config_text
        assert "command: `py -3 -m flask --app web.app run --host 127.0.0.1 --port ${PLAYWRIGHT_PORT} --no-debugger --no-reload`" in config_text
        assert "url: PLAYWRIGHT_BASE_URL" in config_text
        assert "reuseExistingServer: false" in config_text

    def test_shared_runtime_read_flows_use_safe_fetch_for_release_critical_panels(self):
        init_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_init_runtime.js').read_text(encoding='utf-8')
        ops_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_ops_support.js').read_text(encoding='utf-8')

        assert "const routes = await safeFetch('/api/maps/routes', {}, []);" in init_text
        assert "const results = await safeFetch(`/api/geocode/search?q=${encodeURIComponent(query)}`, {}, []);" in init_text
        assert "const tasks = await safeFetch('/api/tasks', {}, null);" in init_text
        assert "const schedules = await safeFetch('/api/watch-schedules', {}, null);" in init_text
        assert "const templates = await safeFetch('/api/templates/inventory', {}, []);" in init_text
        assert "const d = await safeFetch('/api/system/health', {}, null);" in init_text
        assert "const ports = await safeFetch('/api/serial/ports', {}, null);" in init_text

        assert "const b = await safeFetch('/api/broadcast', {}, null);" in ops_text
        assert "const r = await safeFetch('/api/planner/calculate'" in ops_text
        assert "const cls = await safeFetch('/api/dashboard/checklists', {}, []);" in ops_text
        assert "const entries = await safeFetch('/api/journal', {}, null);" in ops_text
        assert "const d = await safeFetch('/api/security/dashboard', {}, null);" in ops_text
        assert "const cameras = await safeFetch('/api/security/cameras', {}, null);" in ops_text
        assert "const logs = await safeFetch('/api/security/access-log', {}, null);" in ops_text
        assert "const alerts = await safeFetch('/api/alerts', {}, null);" in ops_text

    def test_dashboard_and_workspace_memory_use_safe_fetch_for_shared_shell_panels(self):
        readiness_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_dashboard_readiness.js').read_text(encoding='utf-8')
        memory_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspace_memory.js').read_text(encoding='utf-8')

        assert "const data = await apiPost('/api/ai/quick-query', {question});" in readiness_text
        assert "const data = await safeFetch('/api/dashboard/widgets', {}, null);" in readiness_text
        assert "safeFetch('/api/dashboard/overview', {}, null)" in readiness_text
        assert "safeFetch('/api/dashboard/critical', {}, {critical_burn:[], expiring_items:[]})" in readiness_text
        assert "const d = await safeFetch('/api/readiness-score', {}, null);" in readiness_text
        assert "const entries = await safeFetch('/api/vault', {}, null);" in readiness_text
        assert "const trend = await safeFetch('/api/weather/trend', {}, null);" in readiness_text
        assert "const history = await safeFetch('/api/weather?limit=20', {}, []);" in readiness_text
        assert "const rules = await safeFetch('/api/weather/action-rules', {}, null);" in readiness_text
        assert "await Promise.all(_wxRuleDefaults.map(def => apiPost('/api/weather/action-rules', def)));" in readiness_text
        assert "await apiPost(`/api/weather/action-rules/${id}/toggle`);" in readiness_text
        assert "await apiPut(`/api/garden/plots/${_gardenPlotEditId}`, {boundary_geojson: geojson, lng: center[0], lat: center[1]});" in readiness_text
        assert "const r = await apiUpload('/api/inventory/import-csv', formData);" in readiness_text
        assert "const r = await apiUpload('/api/contacts/import-csv', formData);" in readiness_text
        assert "if (!progressTextEl || !el) return;" in readiness_text
        assert "if (!passwordInput || !lockedEl || !unlockedEl) return;" in readiness_text
        assert "if (!el) return;" in readiness_text
        assert "if (!form || !titleInput || !contentInput || !editIdInput) return;" in readiness_text
        assert "if (!titleInput || !contentInput || !editIdInput) return;" in readiness_text
        assert "if (!pressureInput || !tempInput || !windDirInput || !windSpeedInput || !cloudsInput || !precipInput || !notesInput) return;" in readiness_text
        assert "if (!histEl) return;" in readiness_text
        assert "if (!nameInput || !severityInput || !titleInput || !messageInput || !taskNameInput || !taskCategoryInput || !conditionInput || !comparisonInput || !thresholdInput || !actionInput || !cooldownInput || !form) return;" in readiness_text
        assert "if (!freqInput || !timeInput || !intervalInput || !purposeInput) return;" in readiness_text
        assert "if (!input || !input.files.length) return;" in readiness_text
        assert "const statusEl = document.getElementById('mesh-status');" in readiness_text
        assert "if (!statusEl || !messageInput || !sendBtn) return;" in readiness_text
        assert "if (!messageInput) return;" in readiness_text
        assert "if (!video || !resultEl) return;" in readiness_text
        assert "if (!barcodeInput) return;" in readiness_text

        assert "await apiPut('/api/settings', {[WORKSPACE_RESUME_SETTINGS_KEY]: JSON.stringify(state)});" in memory_text
        assert "const settings = await safeFetch('/api/settings', {}, null);" in memory_text
        assert "return await safeFetch(`/api/search/all?q=${encodeURIComponent(q)}`, {}, null);" in memory_text
        assert "const s = await safeFetch('/api/content-summary', {}, null);" in memory_text
        assert "const items = await safeFetch('/api/activity?limit=' + parseInt(lines), {}, null);" in memory_text
        assert "const d = await safeFetch('/api/data-summary', {}, null);" in memory_text
        assert "safeFetch('/api/system', {}, null)," in memory_text
        assert "safeFetch('/api/content-summary', {}, null)," in memory_text
        assert ": await safeFetch('/api/services', {}, []);" in memory_text
        assert "const u = await safeFetch('/api/update-check', {}, null);" in memory_text
        assert "const s = await safeFetch('/api/update-download/status', {}, null);" in memory_text
        assert "const downloads = await safeFetch('/api/downloads/active', {}, []);" in memory_text
        assert "const data = await safeFetch('/api/services/' + svc + '/logs?tail=200', {}, null);" in memory_text
        assert "const updates = await safeFetch('/api/kiwix/check-updates', {}, null);" in memory_text
        assert "safeFetch('/api/kiwix/wikipedia-options', {}, [])," in memory_text
        assert "safeFetch('/api/kiwix/zims', {}, [])," in memory_text
        assert "const d = await apiPost('/api/backups/restore', {filename});" in memory_text
        assert "if (r.ok)" not in memory_text

    def test_init_runtime_uses_shared_api_helpers_for_remaining_shared_mutations(self):
        init_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_init_runtime.js').read_text(encoding='utf-8')

        assert "const d = await safeFetch('/api/update-check', {}, null);" in init_text
        assert "if (id) await apiPut(`/api/skills/${id}`, body);" in init_text
        assert "else await apiPost('/api/skills', body);" in init_text
        assert "if (!nameInput || !categoryInput || !proficiencyInput || !practicedInput || !notesInput || !editIdInput || !form) return;" in init_text
        assert "if (!editIdInput || !form) return;" in init_text
        assert "if (!editIdInput || !nameInput || !categoryInput || !proficiencyInput || !practicedInput || !notesInput) return;" in init_text
        assert "if (id) await apiPut(`/api/ammo/${id}`, body);" in init_text
        assert "else await apiPost('/api/ammo', body);" in init_text
        assert "if (!caliberInput || !brandInput || !weightInput || !typeInput || !qtyInput || !locationInput || !notesInput || !editIdInput || !form) return;" in init_text
        assert "if (!editIdInput || !caliberInput || !brandInput || !weightInput || !typeInput || !qtyInput || !locationInput || !notesInput) return;" in init_text
        assert "const data = await safeFetch('/api/community', {}, []);" in init_text
        assert "if (id) await apiPut(`/api/community/${id}`, body);" in init_text
        assert "else await apiPost('/api/community', body);" in init_text
        assert "if (!nameInput || !distanceInput || !trustInput || !contactInput || !skillsInput || !equipmentInput || !notesInput || !editIdInput || !form) return;" in init_text
        assert "if (!editIdInput || !nameInput || !distanceInput || !trustInput || !contactInput || !skillsInput || !equipmentInput || !notesInput) return;" in init_text
        assert "const d = await safeFetch('/api/radiation', {}, null);" in init_text
        assert "if (!rateInput || !locationInput || !notesInput) return;" in init_text
        assert "if (!panel || !tabBtn) return;" in init_text
        assert "if (!toInput || !fromInput || !subjectInput || !dtInput || !incidentInput || !priorityInput || !messageInput || !replyByInput || !replyInput) return;" in init_text
        assert "if (fields.some(field => !field)) return;" in init_text
        assert "if (!timeInput || !fromInput || !toInput || !msgInput) return;" in init_text
        assert "if (!incidentInput || !operatorInput || !stationInput) return;" in init_text
        assert "if (!timeInput || !activityInput) return;" in init_text
        assert "if (!incidentInput || !unitInput || !leaderInput || !periodInput) return;" in init_text
        assert "await apiDelete(`/api/comms/frequencies/${id}`);" in init_text
        assert "const data = await safeFetch('/api/inventory?category=Medical', {}, null);" in init_text
        assert "if (id) await apiPut(url, body);" in init_text
        assert "else await apiPost(url, body);" in init_text
        assert "await apiDelete(`/api/fuel/${id}`);" in init_text
        assert "await apiPut(`/api/equipment/${id}`, { ...r, last_service: today, status: 'operational' });" in init_text
        assert "await apiDelete(`/api/equipment/${id}`);" in init_text
        assert "await apiPost(`/api/tasks/${id}/complete`, {});" in init_text
        assert "await apiDelete(`/api/tasks/${id}`);" in init_text
        assert "await apiDelete(`/api/watch-schedules/${id}`);" in init_text
        assert "const preds = await safeFetch('/api/alerts/predictive', {}, []);" in init_text
        assert "await apiDelete(`/api/ai/memory/${id}`);" in init_text
        assert "await apiPut(`/api/medical/triage/${patientId}`, {triage_category: category});" in init_text
        assert "safeFetch('/api/system/portable-mode', {}, null).then" in init_text
        assert "const hasNodes = ids => ids.every(id => document.getElementById(id));" in init_text
        assert "const calculatorInitializers = [" in init_text
        assert "{ label: 'Dead reckoning', fn: calcDeadReckoning, required: ['dr-lat', 'dr-lon', 'dr-result'] }" in init_text
        assert "{ label: 'Vitals', fn: calcVitals, required: ['vs-hr', 'vs-sbp', 'vs-dbp', 'vs-rr', 'vs-temp', 'vs-spo2', 'vs-age', 'vs-result'] }" in init_text
        assert "calculatorInitializers.forEach(safeInit);" in init_text
        assert "if (!caliberSelect || !zeroInput || !windInput || !resultEl) return;" in init_text
        assert "if (!brownsInput || !greensInput || !volumeInput || !resultEl) return;" in init_text
        assert "if (!acresInput || !auInput || !paddocksInput || !seasonInput || !resultEl) return;" in init_text
        assert "if (!methodInput || !lengthInput || !heightInput || !thicknessInput || !resultEl) return;" in init_text
        assert "if (!rateInput || !shelterInput || !hoursInput || !resultEl) return;" in init_text
        assert "if (!foodSelect || !poundsInput || !jarInput || !altitudeInput || !resultEl) return;" in init_text
        assert "if (!languageSelect || !el) return;" in init_text

    def test_media_maps_runtime_uses_shared_api_helpers_for_interactive_actions(self):
        media_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_media_maps_sync.js').read_text(encoding='utf-8')

        assert "return apiFetch(url, opts);" in media_text
        assert "const videos = await _fetchJson(`/api/youtube/search?q=${encodeURIComponent(q)}&limit=${_ytSearchLimit}`);" in media_text
        assert "apiPost('/api/channels/validate', {url: channelUrl}).catch(() => {});" in media_text
        assert "apiFetch(`/api/books/${id}`, {method:'PATCH', body:JSON.stringify({last_position:loc.start?.cfi||''})}).catch(() => {});" in media_text
        assert "await apiFetch(`${apiMap[type]}/${id}`, {method:'PATCH', body:JSON.stringify({folder:name})});" in media_text
        assert "const d = await apiPost(endpoint, {url, category:cat, folder:_mediaFolder});" in media_text
        assert "return apiUpload(uploadMap[_mediaSub], formData)" in media_text
        assert "const d = await apiPost(`/api/node/conflicts/${id}/resolve`, body);" in media_text
        assert "await apiPost(`/api/group-exercises/${exerciseId}/update-state`, {decision, event: `Phase advanced with decision: ${decision}`," in media_text
        assert "await apiPost(`/api/group-exercises/${exerciseId}/update-state`, {status: 'completed', event: 'Exercise completed'});" in media_text
        assert "await apiPost(`/api/ai/training/jobs/${jid}/run`, {});" in media_text
        assert "apiPost('/api/drills/history', {drill_type: _currentDrillType || '', title, duration_sec: elapsed, tasks_total: total, tasks_completed: checked})" in media_text
        assert "await apiUpload('/api/library/upload-pdf', formData);" in media_text
        assert "await apiPut(`/api/checklists/${_currentChecklistId}`, {items: _currentChecklistItems});" in media_text

    def test_ops_support_and_workspaces_use_guarded_helpers_for_shared_actions(self):
        ops_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_ops_support.js').read_text(encoding='utf-8')
        workspaces_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspaces.js').read_text(encoding='utf-8')
        profiles_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspace_profiles.js').read_text(encoding='utf-8')
        inline_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_app_inline.js').read_text(encoding='utf-8')

        assert "await apiPost(`/api/notes/${currentNoteId}/pin`, {pinned:newPinned});" in ops_text
        assert "const pinBtn = document.getElementById('note-pin-btn');" in ops_text
        assert "if (!pinBtn) return;" in ops_text
        assert "await apiDelete(`/api/journal/${id}`);" in ops_text
        assert "await apiDelete(`/api/security/cameras/${id}`);" in ops_text
        assert "await apiDelete(`/api/power/devices/${id}`);" in ops_text
        assert "await apiPost(`/api/livestock/${id}/health`, {event: event_text});" in ops_text
        assert "const comp = await apiPost(`/api/scenarios/${_scenarioDbId || 0}/complication`, {" in ops_text
        assert "const aar = await apiPost(`/api/scenarios/${_scenarioDbId || 0}/aar`, {" in ops_text
        assert "await apiPost(`/api/patients/${_activePatientId}/vitals`, data);" in ops_text
        assert "const data = await safeFetch(`/api/patients/${pid}/wounds/${wid}/photos`, {}, null);" in ops_text
        assert "_guideContext = await safeFetch('/api/guides/context', {}, null);" in ops_text
        assert "await apiPost(`/api/alerts/${id}/dismiss`, {});" in ops_text
        assert "const resp = await apiFetch('/api/export-config');" in ops_text
        assert "if (!peopleInput || !daysInput || !activityInput || !resultEl) return;" in ops_text
        assert "if (!peopleInput || !monthsInput || !resultEl) return;" in ops_text
        assert "if (!wattsInput || !fuelInput || !hoursInput || !daysInput || !loadInput || !resultEl) return;" in ops_text
        assert "if (!areaInput || !rainInput || !efficiencyInput || !peopleInput || !resultEl) return;" in ops_text
        assert "if (!typeInput || !terrainInput || !heightInput || !resultEl) return;" in ops_text
        assert "if (!weightInput || !unitInput || !ageInput || !resultEl) return;" in ops_text
        assert "if (!dailyWhInput || !sunHoursInput || !batteryTypeInput || !autonomyInput || !resultEl) return;" in ops_text
        assert "if (!bodyWeightInput || !resultEl) return;" in ops_text
        assert "if (!enabledInput || !intervalInput || !keepInput || !encryptInput || !passwordInput) return;" in ops_text
        assert "if (!input || !input.files || !input.files.length) return;" in ops_text
        assert "if (!entryInput || !moodInput || !tagsInput) return;" in ops_text
        assert "if (!nameInput || !urlInput || !typeInput || !locationInput) return;" in ops_text
        assert "if (!form || !nameInput || !ageInput || !weightInput || !sexInput || !bloodInput || !allergiesInput || !medsInput || !conditionsInput || !notesInput || !editIdInput || !interactionResults) return;" in ops_text
        assert "if (!nameInput || !ageInput || !weightInput || !sexInput || !bloodInput || !allergiesInput || !medsInput || !conditionsInput || !notesInput || !editIdInput) return;" in ops_text
        assert "if (!el || !medsInput) return;" in ops_text
        assert "if (!sel) return;" in ops_text
        assert "if (!pSel || !ageInput || !weightInput) return;" in ops_text
        assert "if (!drugSelect || !patientSelect || !ageInput || !weightInput || !el) return;" in ops_text
        assert "if (!panel || !woundForm || !titleEl || !banner) return;" in ops_text
        assert "if (!systolicInput || !diastolicInput || !pulseInput || !respInput || !tempInput || !spo2Input || !painInput || !gcsInput || !notesInput) return;" in ops_text
        assert "if (!tbody) return;" in ops_text
        assert "if (!locationInput || !typeInput || !severityInput || !descriptionInput || !treatmentInput || !photoInput) return;" in ops_text
        assert "if (!intervalInput) return;" in ops_text
        assert "if (!chatInput) return;" in ops_text
        assert "if (!tagsInput) return;" in ops_text
        assert "if (!messageInput || !severityInput) return;" in ops_text
        assert "if (!thresholdInput || !intervalInput || !cooldownInput) return;" in ops_text
        assert "if (!personInput || !directionInput || !locationInput || !methodInput || !notesInput) return;" in ops_text
        assert "if (!typeInput || !nameInput) return;" in ops_text
        assert "if (!voltageInput || !socInput || !solarInput || !solarWhInput || !loadInput || !loadWhInput || !generatorInput) return;" in ops_text
        assert "if (!latInput || !lngInput) return;" in ops_text
        assert "if (!latInput || !lngInput || !wattsInput || !countInput || !efficiencyInput || !el || !cloudIndicator) return;" in ops_text
        assert "if (!cropInput || !methodInput || !qtyInput || !unitInput || !dateInput || !shelfInput) return;" in ops_text
        assert "if (!el || !sel) return;" in ops_text
        assert "if (!nameInput || !widthInput || !lengthInput || !sunInput) return;" in ops_text
        assert "if (!speciesInput || !varietyInput || !quantityInput || !yearInput || !maturityInput || !seasonInput) return;" in ops_text
        assert "if (!cropInput || !quantityInput || !unitInput || !plotInput) return;" in ops_text
        assert "if (!speciesInput || !nameInput || !sexInput || !dobInput || !weightInput) return;" in ops_text
        assert "const panel = document.getElementById(`security-${t}-panel`);" in ops_text
        assert "const panel = document.getElementById(`power-${t}-panel`);" in ops_text
        assert "const tabBtn = document.getElementById(`sec-tab-${t}`);" in ops_text
        assert "const tabBtn = document.getElementById(`pwr-tab-${t}`);" in ops_text
        assert "if (!panel || !tabBtn) return;" in ops_text

        assert "await _workspaceFetchOk('/api/maps/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({filename})}, 'Failed to delete map');" in workspaces_text
        assert "await _workspaceFetchJson('/api/maps/download-region', {" in workspaces_text
        assert "await _workspaceFetchJson('/api/maps/download-url', {" in workspaces_text
        assert "const data = await _workspaceFetchJson('/api/maps/import-file', {" in workspaces_text
        assert "const notes = await _workspaceFetchJsonSafe('/api/notes', {}, allNotes || [], 'Failed to load notes');" in workspaces_text
        assert "await _workspaceFetchOk(`/api/notes/${currentNoteId}`, {method:'DELETE'}, 'Failed to delete note');" in workspaces_text
        assert "await _workspaceFetchOk(`/api/notes/${currentNoteId}`, {method:'PUT', headers:{'Content-Type':'application/json'}," in workspaces_text
        assert "const d = await _workspaceFetchJson(`/api/kb/documents/${docId}/import-entities`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({})}, 'Import failed');" in workspaces_text
        assert "signal: AbortSignal.timeout(8000)," in workspaces_text
        assert "else { toast('Geocoding returned an invalid response', 'error'); }" in workspaces_text
        assert "if (!panel) return;" in workspaces_text
        assert "if (!list) return;" in workspaces_text
        assert "if (!el || !recommendedEl) return;" in workspaces_text
        assert "recommendedEl.innerHTML = rec.map(r => `" in workspaces_text
        assert "if (!input) return;" in workspaces_text
        assert "if (!toggle || !docsEl) return;" in workspaces_text
        assert "if (!regionGrid || !filesEl) return;" in workspaces_text
        assert "if (!titleInput || !contentInput || !tagsInput || !pinBtn) return;" in workspaces_text
        assert "if (!dd || !list) return;" in workspaces_text
        assert "if (!dropdown) return;" in workspaces_text
        assert "if (!searchInput || !list) return;" in workspaces_text
        assert "if (!runBtn || !progressEl || !resultsEl) return;" in workspaces_text
        assert "if (!fillEl || !stageEl || !pctEl) return;" in workspaces_text
        assert "if (!resultsEl) return;" in workspaces_text
        assert "if (!aiNameInput) return;" in workspaces_text
        assert "if (!gaugesEl || !systemInfoEl || !dataDirEl || !diskDevicesEl) return;" in workspaces_text
        assert "if (!viewerEl || !managementEl || !toggleBtn) return;" in workspaces_text
        assert "if (!measureBtn) return;" in workspaces_text
        assert "if (!searchInput) return;" in workspaces_text
        assert "if (!previewEl || !previewBtn) return;" in profiles_text
        assert "if (!contentInput || !previewEl) return;" in profiles_text
        assert "if (!builderTagInput) return;" in profiles_text
        assert "if (!systemPresetSelect) return;" in profiles_text
        assert "if (!customPromptInput || !systemPresetSelect) return;" in profiles_text
        assert "_app_workspace_profiles.js" in inline_text
        assert "if (!input || !input.files.length) return;" in workspaces_text
        assert "if (!titleEl || !iframe || !overlay) return;" in workspaces_text
        assert "if (!iframe || !titleEl || !overlay) return;" in workspaces_text
        assert "if (!overlay || !iframe) return;" in workspaces_text
        assert "if (!overallFillEl || !overallPctEl || !currentItemEl || !itemFillEl || !itemPctEl || !miniPctEl || !miniFillEl || !miniItemEl || !phaseLabelEl || !completedListEl) return;" in workspaces_text
        assert "if (!lanUrlEl || !summaryEl || !errorSummaryEl) return;" in workspaces_text
        assert "if (!tourOverlay) return;" in workspaces_text
        assert "if (!contentEl || !stepNumEl || !nextBtn || !card) return;" in workspaces_text

    def test_services_ai_uses_shared_api_fetch_for_streaming_chat_paths(self):
        services_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_services_ai.js').read_text(encoding='utf-8')

        assert "const payload = await apiFetch(url, opts);" in services_text
        assert "const resp = await apiFetch('/api/ai/chat', {" in services_text
        assert "if (!(resp instanceof Response) || !resp.body) throw new Error('Warmup failed: invalid stream response');" in services_text
        assert "if (!(resp instanceof Response) || !resp.body) throw new Error('AI service returned an invalid stream response');" in services_text

    def test_preparedness_and_sitroom_runtime_use_shared_api_helpers_for_remaining_actions(self):
        core_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_core_shell.js').read_text(encoding='utf-8')
        sitroom_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_situation_room.js').read_text(encoding='utf-8')
        calcs_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / 'preparedness' / '_prep_calcs_misc.js').read_text(encoding='utf-8')
        family_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / 'preparedness' / '_prep_family_field.js').read_text(encoding='utf-8')
        inventory_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / 'preparedness' / '_prep_inventory_flows.js').read_text(encoding='utf-8')
        nav_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / 'preparedness' / '_prep_nav_core.js').read_text(encoding='utf-8')
        mapping_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / 'preparedness' / '_prep_ops_mapping.js').read_text(encoding='utf-8')
        people_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / 'preparedness' / '_prep_people_comms.js').read_text(encoding='utf-8')

        assert "apiPut('/api/settings', {[key]: value})" in core_text
        assert "signal: AbortSignal.timeout(8000)," in sitroom_text
        assert "apiPost('/api/sitroom/monitors', {keyword: keyword.trim()})" in sitroom_text

        assert "apiPut('/api/settings', {pace_plan: JSON.stringify(pace)}).catch(() => {});" in calcs_text
        assert "apiPut('/api/settings', {vehicles: JSON.stringify(_vehicles)}).catch(() => {});" in family_text

        assert "await apiDelete(`/api/inventory/${id}`);" in inventory_text
        assert "await apiPut(`/api/inventory/${id}`, {quantity: newQty});" in inventory_text
        assert "const data = await apiUpload('/api/inventory/receipt-scan', formData);" in inventory_text
        assert "const data = await apiPost('/api/inventory/receipt-import', {items});" in inventory_text
        assert "const data = await apiUpload('/api/inventory/vision-scan', formData);" in inventory_text
        assert "const data = await apiPost('/api/inventory/vision-import', {items});" in inventory_text
        assert "var data = await apiPost('/api/barcode/scan-to-inventory', {upc: upc, quantity: qty});" in inventory_text
        assert "await apiPost('/api/barcode/add', payload);" in inventory_text

        assert "await apiPut(`/api/checklists/${_currentChecklistId}`, {items: _currentChecklistItems});" in nav_text
        assert "await apiDelete(`/api/checklists/${id}`);" in nav_text

        assert "const timers = await apiFetch('/api/timers');" in mapping_text
        assert "const timerList = Array.isArray(timers) ? timers : [];" in mapping_text
        assert "apiPut('/api/settings', {threat_matrix: JSON.stringify(saved)}).catch(() => {});" in mapping_text

        assert "const results = await Promise.allSettled(numbers.map(c => apiPost('/api/contacts', c)));" in people_text
        assert "await apiDelete(`/api/contacts/${id}`);" in people_text

    def test_runtime_uses_shared_json_safety_helpers_for_saved_state_and_payloads(self):
        core_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_core_shell.js').read_text(encoding='utf-8')
        readiness_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_dashboard_readiness.js').read_text(encoding='utf-8')
        init_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_init_runtime.js').read_text(encoding='utf-8')
        media_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_media_maps_sync.js').read_text(encoding='utf-8')
        family_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / 'preparedness' / '_prep_family_field.js').read_text(encoding='utf-8')
        mapping_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / 'preparedness' / '_prep_ops_mapping.js').read_text(encoding='utf-8')
        services_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_services_ai.js').read_text(encoding='utf-8')
        sitroom_text = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_situation_room.js').read_text(encoding='utf-8')
        ai_text = (REPO_ROOT / 'web' / 'blueprints' / 'ai.py').read_text(encoding='utf-8')
        app_text = (REPO_ROOT / 'web' / 'app.py').read_text(encoding='utf-8')
        medical_text = (REPO_ROOT / 'web' / 'blueprints' / 'medical.py').read_text(encoding='utf-8')
        maps_text = (REPO_ROOT / 'web' / 'blueprints' / 'maps.py').read_text(encoding='utf-8')
        security_text = (REPO_ROOT / 'web' / 'blueprints' / 'security.py').read_text(encoding='utf-8')
        power_text = (REPO_ROOT / 'web' / 'blueprints' / 'power.py').read_text(encoding='utf-8')
        kb_text = (REPO_ROOT / 'web' / 'blueprints' / 'kb.py').read_text(encoding='utf-8')
        media_blueprint_text = (REPO_ROOT / 'web' / 'blueprints' / 'media.py').read_text(encoding='utf-8')
        services_blueprint_text = (REPO_ROOT / 'web' / 'blueprints' / 'services.py').read_text(encoding='utf-8')
        system_blueprint_text = (REPO_ROOT / 'web' / 'blueprints' / 'system.py').read_text(encoding='utf-8')
        comms_text = (REPO_ROOT / 'web' / 'blueprints' / 'comms.py').read_text(encoding='utf-8')
        garden_text = (REPO_ROOT / 'web' / 'blueprints' / 'garden.py').read_text(encoding='utf-8')
        weather_text = (REPO_ROOT / 'web' / 'blueprints' / 'weather.py').read_text(encoding='utf-8')
        federation_text = (REPO_ROOT / 'web' / 'blueprints' / 'federation.py').read_text(encoding='utf-8')
        inventory_text = (REPO_ROOT / 'web' / 'blueprints' / 'inventory.py').read_text(encoding='utf-8')
        sitroom_blueprint_text = (REPO_ROOT / 'web' / 'blueprints' / 'situation_room.py').read_text(encoding='utf-8')
        exercises_text = (REPO_ROOT / 'web' / 'blueprints' / 'exercises.py').read_text(encoding='utf-8')
        preparedness_text = (REPO_ROOT / 'web' / 'blueprints' / 'preparedness.py').read_text(encoding='utf-8')
        tasks_text = (REPO_ROOT / 'web' / 'blueprints' / 'tasks.py').read_text(encoding='utf-8')
        benchmark_text = (REPO_ROOT / 'web' / 'blueprints' / 'benchmark.py').read_text(encoding='utf-8')
        checklists_text = (REPO_ROOT / 'web' / 'blueprints' / 'checklists.py').read_text(encoding='utf-8')
        ollama_text = (REPO_ROOT / 'services' / 'ollama.py').read_text(encoding='utf-8')
        cyberchef_text = (REPO_ROOT / 'services' / 'cyberchef.py').read_text(encoding='utf-8')
        qdrant_text = (REPO_ROOT / 'services' / 'qdrant.py').read_text(encoding='utf-8')
        stirling_text = (REPO_ROOT / 'services' / 'stirling.py').read_text(encoding='utf-8')

        assert 'function safeJsonParse(value, fallback = null, options = {}) {' in core_text
        assert 'function readJsonStorage(storage, key, fallback = null, options = {}) {' in core_text
        assert "const data = readJsonStorage(localStorage, this._prefix + formId, null);" in core_text

        assert "readJsonStorage(localStorage, 'nomad-signal-schedule', []);" in readiness_text
        assert 'const offers = safeJsonParse(p.offers, []);' in readiness_text
        assert 'const items = safeJsonParse(p.matched_items, []);' in readiness_text

        assert "let _ics309Entries = readJsonStorage(localStorage, 'nomad_ics309', []);" in init_text
        assert "chatMessages = safeJsonParse(c.messages, []);" in services_text
        assert "chatMessages = safeJsonParse(r.messages, []);" in services_text
        assert "readJsonStorage(localStorage, 'nomad-map-zones', []);" in media_text
        assert "readJsonStorage(localStorage, 'nomad-map-bookmarks', []);" in media_text
        assert "readJsonStorage(localStorage, 'nomad-fep', {});" in family_text
        assert "readJsonStorage(localStorage, 'nomad-threats', {});" in mapping_text
        assert 'function _parseSitroomDetailJson(value) {' in sitroom_text
        assert "return readJsonStorage(localStorage, key, fallback);" in sitroom_text
        assert "const det = _parseSitroomDetailJson(q.detail_json);" in sitroom_text
        assert "const sizes = _readSitroomStorageObject('sitroom-card-sizes', {});" in sitroom_text

        assert 'def _safe_message_list(val, default=None):' in ai_text
        assert "messages = _safe_message_list(data.get('messages', []))" in ai_text
        assert "memories = _safe_memory_entries(mem_row['value'])" in ai_text
        assert "update_data['messages'] = json.dumps(_safe_message_list(data['messages']))" in ai_text
        assert 'def _load_jsonl_samples(path, limit=5):' in ai_text
        assert "samples = _load_jsonl_samples(ds['file_path'], limit=5)" in ai_text

        utils_text = (REPO_ROOT / 'web' / 'utils.py').read_text(encoding='utf-8')
        assert 'def safe_json_value(value, fallback=None):' in utils_text
        assert 'def safe_json_list(value, fallback=None):' in utils_text
        assert 'def safe_json_object(value, fallback=None):' in utils_text
        assert 'def safe_id_list(value):' in utils_text
        assert 'def esc(s):' in utils_text

        assert 'from web.utils import' in app_text
        print_text = (REPO_ROOT / 'web' / 'blueprints' / 'print_routes.py').read_text(encoding='utf-8')
        assert "report['situation'] = _safe_json_value(sit_row['value'] if sit_row else None, {})" in print_text
        assert "memories = _safe_json_value(mem_row['value'], [])" in print_text
        assert 'def _join_safe_list(value, empty=\'\'):' in print_text
        assert "items = _safe_json_list(c['items'], [])" in print_text
        assert "allergies = _safe_json_list(record.get('allergies'), [])" in print_text
        assert "allergies = _join_safe_list(p.get('allergies'))" in print_text
        assert "channels = _safe_json_list(prof.get('channels'), [])" in print_text

        assert 'from web.utils import' in maps_text
        assert 'def _load_json_response_bytes(raw, fallback=None):' in maps_text
        assert "wp_ids = _safe_id_list(route['waypoint_ids'])" in maps_text
        assert "geojson = _safe_track_geojson(trk['geojson'])" in maps_text
        assert "item['properties'] = _safe_json_object(item.get('properties'), {})" in maps_text
        assert "release = _load_json_response_bytes(resp.read(), {})" in maps_text

        assert 'from web.utils import' in security_text
        assert "sit = _safe_json_object(sit_raw['value'], {})" in security_text
        assert "entry['camera_ids'] = _safe_id_list(entry.get('camera_ids'))" in security_text
        assert "camera_ids = _safe_id_list(z['camera_ids'])" in security_text

        assert 'def _resolve_map_center(value):' in power_text
        assert "specs = _safe_json_object(d['specs'], {})" in power_text
        assert "center_lat, center_lng = _resolve_map_center(mc['value'])" in power_text
        assert "specs = _safe_json_object(d_dict.get('specs'), {})" in power_text

        assert 'def _parse_json_list(value):' in medical_text
        assert 'def _safe_response_json(response):' in medical_text
        assert "json.dumps(_parse_json_list(data.get('allergies')))" in medical_text
        assert "photos = _parse_json_list(existing['photo_path'])" in medical_text
        assert "photos = _parse_json_list(row['photo_path'])" in medical_text
        assert "allergies = _parse_json_list(patient['allergies'])" in medical_text
        assert "current_meds = _parse_json_list(patient['medications'])" in medical_text
        assert "ref_json = _safe_response_json(ref_resp)" in medical_text

        assert 'from web.utils import' in kb_text
        assert 'def _safe_response_payload(response, fallback=None):' in kb_text
        assert 'def _normalize_extracted_entities(value):' in kb_text
        assert "payload = _safe_response_payload(resp, {})" in kb_text
        assert "embeddings = payload.get('embeddings', [])" in kb_text
        assert "entities = _normalize_extracted_entities(entity_payload.get('response', []))" in kb_text
        assert "d['entities'] = _normalize_extracted_entities(d.get('entities'))" in kb_text
        assert "d['linked_records'] = _safe_json_list(d.get('linked_records'), [])" in kb_text
        assert "entities = _normalize_extracted_entities(doc['entities'])" in kb_text
        assert "selected = _safe_index_list(data.get('entities'))" in kb_text

        assert 'def _safe_response_payload(response, fallback=None):' in ai_text
        assert "info = _safe_response_payload(r, {})" in ai_text
        assert "data = _safe_response_payload(resp, {})" in ai_text

        assert 'def _safe_string_list(value):' in media_blueprint_text
        assert 'def _safe_response_json(response, fallback=None):' in media_blueprint_text
        assert "dead_urls = set(_safe_string_list(dead_row['value'] if dead_row else None))" in media_blueprint_text
        assert "dead = _safe_string_list(row['value'] if row else None)" in media_blueprint_text
        assert 'd = _load_json_line(line, {})' in media_blueprint_text
        assert "found = _load_json_line(search_result.stdout.strip().split('\\n')[0], {})" in media_blueprint_text
        assert "release = _safe_response_json(resp, {})" in media_blueprint_text

        assert 'def _safe_response_json(response, fallback=None):' in services_blueprint_text
        assert "data = _safe_response_json(resp, {})" in services_blueprint_text

        assert 'def _safe_response_json(response, fallback=None):' in system_blueprint_text
        assert "data = _safe_response_json(resp, {})" in system_blueprint_text

        assert 'def _normalize_radio_channels(value):' in comms_text
        assert "entry['channels'] = _normalize_radio_channels(entry.get('channels'))" in comms_text
        assert "json.dumps(_normalize_radio_channels(data.get('channels', [])))" in comms_text
        assert "channels = _normalize_radio_channels(r['channels'])" in comms_text

        assert 'def _normalize_boundary_geojson(value):' in garden_text
        assert "_normalize_boundary_geojson(data.get('boundary_geojson'))" in garden_text
        assert "geometry = _safe_plot_geometry(d.get('boundary_geojson'), d['lng'], d['lat'])" in garden_text

        assert 'from web.utils import' in weather_text
        assert "action_data = _safe_json_object(rule['action_data'], {})" in weather_text
        assert "d['action_data'] = _safe_json_object(d.get('action_data'), {})" in weather_text
        assert "action_data = _safe_json_object(data.get('action_data'), {})" in weather_text

        assert 'def _safe_clock(value):' in federation_text
        assert 'def _safe_response_payload(response, fallback=None):' in federation_text
        assert "clock = _safe_clock(existing['clock'] if existing else None)" in federation_text
        assert "result = _safe_response_payload(r, {})" in federation_text
        assert "payload['vector_clocks'][r['table_name']][r['row_hash']] = _safe_clock(r['clock'])" in federation_text
        assert "local_clock = _safe_clock(local_vc_row['clock'] if local_vc_row else None)" in federation_text
        assert "entry['conflict_details'] = _safe_conflict_list(entry.get('conflict_details'))" in federation_text
        assert "conflicts = _safe_conflict_list(row['conflict_details'])" in federation_text
        assert "manifest = _safe_json_object(z.read('manifest.json'), {})" in federation_text
        assert "json.dumps(_safe_json_list(data.get('our_commitments'), []))" in federation_text
        assert "sit = _safe_json_object(row['situation'], {})" in federation_text
        assert "sit = _safe_json_object(peer['situation'], {})" in federation_text
        assert "shared_contacts = _safe_json_list(sit.get('contacts', sit.get('shared_contacts', [])), [])" in federation_text

        assert 'from web.utils import' in inventory_text
        assert 'def _extract_json_array(raw_text):' in inventory_text
        assert "result = _safe_json_value(resp.read(), {})" in inventory_text
        assert "for item in _extract_json_array(raw_text):" in inventory_text
        assert "for item in _extract_json_array(raw_response):" in inventory_text

        assert "prices = _safe_json_value(m.get('outcomePrices', '[]'), [])" in sitroom_blueprint_text
        assert "sw = _safe_json_object(sw_row['value_json'], {})" in sitroom_blueprint_text
        assert 'def _safe_response_json(response, fallback=None):' in sitroom_blueprint_text
        assert "data = _safe_response_json(resp, {})" in sitroom_blueprint_text
        assert "markets = _safe_response_json(resp, [])" in sitroom_blueprint_text
        assert "kp_data = _safe_response_json(resp, [])" in sitroom_blueprint_text
        assert "alerts = _safe_response_json(resp, [])" in sitroom_blueprint_text
        assert "rows = payload.get('response', {}).get('data', []) if isinstance(payload, dict) else []" in sitroom_blueprint_text
        assert "data = _safe_response_json(resp, []) if resp.text.strip() else []" in sitroom_blueprint_text

        assert 'safe_json_object as _safe_json_object' in exercises_text
        assert "entry['shared_state'] = _safe_json_object(entry.get('shared_state'), {})" in exercises_text
        assert "shared_state = _safe_json_object(row['shared_state'], {})" in exercises_text
        assert "shared_state = _safe_json_object(data.get('shared_state'), {})" in exercises_text
        assert "decisions_log = _safe_json_list(data.get('decisions_log'), [])" in exercises_text

        assert "log_entries = _safe_json_list(animal['health_log'], [])" in preparedness_text
        assert 'def _safe_response_json(response, fallback=None):' in preparedness_text
        assert "result = _safe_response_json(resp, {})" in preparedness_text
        assert "decisions = _safe_json_list(data.get('decisions', []), [])" in preparedness_text
        assert "complications = _safe_json_list(data.get('complications', []), [])" in preparedness_text
        assert "complication = _safe_json_value(result, {})" in preparedness_text
        assert "decisions = _safe_json_list(scenario['decisions'], [])" in preparedness_text
        assert "complications = _safe_json_list(scenario['complications'], [])" in preparedness_text

        assert "from web.utils import esc as _esc, safe_json_list as _safe_json_list" in tasks_text
        assert 'def _normalize_watch_personnel(value):' in tasks_text
        assert 'def _normalize_watch_schedule(value):' in tasks_text
        assert "'personnel': _normalize_watch_personnel(r['personnel'])" in tasks_text
        assert "'schedule_json': _normalize_watch_schedule(r['schedule_json'])" in tasks_text
        assert "schedule = _safe_json_list(sched['schedule_json'], [])" in tasks_text
        assert "personnel = _safe_json_list(sched['personnel'], [])" in tasks_text

        assert 'from web.utils import safe_json_value as _safe_json_value' in benchmark_text
        assert 'def _load_stream_json_line(line):' in benchmark_text
        assert 'resp.raise_for_status()' in benchmark_text
        assert 'd = _load_stream_json_line(line)' in benchmark_text

        assert 'def _load_stream_json_line(line):' in ollama_text
        assert 'def _safe_response_payload(response, fallback=None):' in ollama_text
        assert 'data = _load_stream_json_line(line)' in ollama_text
        assert 'return _safe_response_payload(resp, {})' in ollama_text
        assert 'AI service returned unreadable pull progress data.' in ollama_text

        assert 'def _safe_response_payload(response, fallback=None):' in cyberchef_text
        assert 'release = _safe_response_payload(_api_resp, {})' in cyberchef_text

        assert 'def _safe_response_payload(response, fallback=None):' in qdrant_text
        assert 'release = _safe_response_payload(resp, {})' in qdrant_text
        assert "payload = _safe_response_payload(r, {})" in qdrant_text

        assert 'def _safe_response_payload(response, fallback=None):' in stirling_text
        assert 'release = _safe_response_payload(resp, {})' in stirling_text

        assert "items = json.dumps(_safe_json_list(data.get('items', []), []))" in checklists_text
        assert "update_data['items'] = json.dumps(_safe_json_list(data['items'], []))" in checklists_text
        assert "items = _safe_json_list(data.get('items', []), [])" in checklists_text
        assert "msg = _safe_json_value(data, {})" in app_text
        assert "data, error = _require_json_body(request)" in app_text
        assert "items = _safe_json_list(cl['items'], [])" in app_text

    def test_backend_blueprints_use_shared_json_body_guard_for_bulk_and_settings_routes(self):
        contacts_text = (REPO_ROOT / 'web' / 'blueprints' / 'contacts.py').read_text(encoding='utf-8')
        preparedness_text = (REPO_ROOT / 'web' / 'blueprints' / 'preparedness.py').read_text(encoding='utf-8')
        supplies_text = (REPO_ROOT / 'web' / 'blueprints' / 'supplies.py').read_text(encoding='utf-8')
        system_text = (REPO_ROOT / 'web' / 'blueprints' / 'system.py').read_text(encoding='utf-8')
        utils_text = (REPO_ROOT / 'web' / 'utils.py').read_text(encoding='utf-8')

        assert "def require_json_body(req):" in utils_text
        assert "data, error = _require_json_body(request)" in contacts_text
        assert "data, error = _require_json_body(request)" in preparedness_text
        assert "data, error = _require_json_body(request)" in supplies_text
        assert "data, error = _require_json_body(request)" in system_text

    def test_customize_panel_layers_above_overlay_and_updates_accessibility_state(self):
        shell_html = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_shell.html').read_text(encoding='utf-8')
        support_js = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_ops_support.js').read_text(encoding='utf-8')
        customize_css = (REPO_ROOT / 'web' / 'static' / 'css' / 'app' / '50_home_customize.css').read_text(encoding='utf-8')

        assert 'id="customize-panel"' in shell_html
        assert 'aria-hidden="true"' in shell_html
        assert "z-index: 9600;" in customize_css
        assert "z-index: 9601;" in customize_css
        assert "pointer-events: none;" in customize_css
        assert "overlay.setAttribute('aria-hidden', 'false');" in support_js
        assert "overlay.setAttribute('aria-hidden', 'true');" in support_js
        assert "panel.setAttribute('aria-hidden', 'false');" in support_js
        assert "panel.setAttribute('aria-hidden', 'true');" in support_js

    def test_shell_dialog_surfaces_share_hidden_state_and_focus_safe_visibility(self):
        shell_html = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_shell.html').read_text(encoding='utf-8')
        overlays_html = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_utility_overlays.html').read_text(encoding='utf-8')
        shortcuts_html = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_shortcuts_overlay.html').read_text(encoding='utf-8')
        core_shell_js = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_core_shell.js').read_text(encoding='utf-8')
        workspaces_js = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspaces.js').read_text(encoding='utf-8')
        support_js = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_ops_support.js').read_text(encoding='utf-8')
        memory_js = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_workspace_memory.js').read_text(encoding='utf-8')

        assert 'id="wizard"' in overlays_html and 'aria-hidden="true"' in overlays_html
        assert 'id="tour-overlay"' in overlays_html and 'aria-hidden="true"' in overlays_html
        assert 'id="command-palette-overlay"' in shortcuts_html and 'aria-hidden="true"' in shortcuts_html
        assert 'id="shortcuts-overlay"' in shortcuts_html and 'aria-hidden="true"' in shortcuts_html
        assert 'id="shell-health-overlay"' in shell_html and 'aria-hidden="true"' in shell_html
        assert 'class="sidebar-brand-mark" width="52" height="52"' in shell_html
        assert 'class="wizard-logo" width="100" height="100"' in overlays_html
        assert 'id="lan-encrypt-toggle"' in overlays_html and 'aria-label="Encrypt LAN messages"' in overlays_html
        assert 'id="lan-chat-messages" class="utility-panel-body utility-message-list" role="log" aria-live="polite" aria-relevant="additions text" aria-label="LAN chat messages"' in overlays_html
        assert "el.setAttribute('aria-hidden', visible ? 'false' : 'true');" in core_shell_js
        assert "setShellVisibility(overlay, true);" in core_shell_js
        assert "setShellVisibility(overlay, false);" in core_shell_js
        assert "overlay.querySelector('.shell-health-close')?.focus()" in core_shell_js
        assert "setShellVisibility(el, true);" in support_js
        assert "setShellVisibility(el, false);" in support_js
        assert "el.querySelector('.shortcuts-close')?.focus()" in support_js
        assert "toggleShortcutsHelp(false)" in memory_js
        assert "document.getElementById('tour-next-btn')?.focus()" in workspaces_js

    def test_shell_escape_closer_targets_visible_surfaces_and_force_closes_live_panels(self):
        overlays_html = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_utility_overlays.html').read_text(encoding='utf-8')
        core_shell_js = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_core_shell.js').read_text(encoding='utf-8')
        init_runtime_js = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_init_runtime.js').read_text(encoding='utf-8')

        assert 'id="wizard" role="dialog" aria-modal="true" aria-label="Setup Wizard" aria-hidden="true" hidden' in overlays_html
        assert 'id="tour-overlay" class="tour-overlay-shell is-hidden" data-shell-action="tour-next" role="dialog" aria-modal="true" aria-label="Guided Tour" aria-hidden="true" hidden' in overlays_html
        assert 'id="lan-chat-panel" class="utility-panel utility-panel-shell utility-panel-shell-wide utility-panel-shell-lan is-hidden" hidden' in overlays_html
        assert 'id="quick-actions-menu" class="floating-action-menu utility-actions-menu is-hidden" hidden' in overlays_html
        assert 'id="timer-panel" class="utility-panel utility-panel-shell is-hidden" hidden' in overlays_html
        assert "function closeTopVisibleShellSurface()" in core_shell_js
        assert "const modal = document.querySelector('.modal-overlay:not(.hidden), .modal-overlay[style*=\"flex\"], .wizard-overlay:not(.hidden)');" not in core_shell_js
        assert "if (closeTopVisibleShellSurface()) {" in core_shell_js
        assert "if (typeof skipWizard === 'function')" in core_shell_js
        assert "if (typeof stopLanMessagePolling === 'function') stopLanMessagePolling();" in core_shell_js
        assert "if (typeof stopTimerPolling === 'function') stopTimerPolling();" in core_shell_js
        assert "if (e.target === shortcutsOverlay) toggleShortcutsHelp(false);" in init_runtime_js

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
        assert 'data-workspace-guide-target="notes"' not in notes_html
        assert 'src="/app-runtime.js?v=' in notes_html

        runtime_js = self._html(client, '/app-runtime.js?v=test')
        assert 'data-note-action="select-note"' in runtime_js
        assert 'data-note-action="apply-note-template"' in runtime_js
        assert 'class="note-item-head"' in runtime_js

        media_html = self._html(client, '/media')
        assert 'data-media-sub-switch="channels"' in media_html
        assert 'data-media-action="download-url"' in media_html
        assert 'data-workspace-guide-target="media"' not in media_html
        assert 'data-media-action="resume-media"' in runtime_js
        assert 'class="media-download-item"' in runtime_js

        maps_html = self._html(client, '/maps')
        assert 'data-map-action="toggle-map-view"' in maps_html
        assert 'data-input-action="geocode-search"' in maps_html
        assert 'data-map-action="delete-map"' in runtime_js
        assert 'map-zone-panel' in runtime_js

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
        assert '/static/logo-192.png' in manifest

    def test_desktop_branding_assets_exist(self):
        assert (REPO_ROOT / 'icon.ico').is_file()
        assert (REPO_ROOT / 'logo.png').is_file()
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
        # Version-agnostic: match any v<major>.<minor>.<patch> so test survives bumps.
        import re as _re
        assert _re.search(r'# NOMAD Field Desk v\d+\.\d+\.\d+', readme), 'README missing NOMAD Field Desk version header'
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


class TestWatchScheduleUpdate404:
    def test_update_nonexistent_returns_404(self, client):
        resp = client.put('/api/watch-schedules/99999', json={
            'name': 'Does Not Exist',
        })
        assert resp.status_code == 404
