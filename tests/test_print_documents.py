"""Regression checks for framed print/export HTML documents."""


class TestPrintDocuments:
    def test_preparedness_print_document(self, client):
        resp = client.get('/api/preparedness/print')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Emergency Card' in html
        assert 'Situation Status' in html
        assert 'Key Frequencies' in html

    def test_preparedness_print_document_recovers_from_corrupted_situation_json(self, client, db):
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sit_board', ?)", ('{broken',))
        db.commit()

        resp = client.get('/api/preparedness/print')

        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Emergency Card' in html
        assert 'Situation board is not configured yet.' in html

    def test_preparedness_print_document_recovers_from_corrupted_ai_memory(self, client, db):
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ai_memory', ?)", ('{broken',))
        db.commit()

        resp = client.get('/api/preparedness/print')

        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Emergency Card' in html
        assert 'Operator Notes' not in html

    def test_frequency_card_document(self, client):
        resp = client.get('/api/print/freq-card')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Frequency Reference Card' in html
        assert 'Recent Traffic' in html
        assert 'Radio Notes' in html

    def test_bugout_checklist_document(self, client):
        resp = client.get('/api/print/bug-out-checklist')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Bug-Out Checklist' in html
        assert 'Load Checklist' in html
        assert 'Rally Points' in html

    def test_medical_cards_document(self, client):
        client.post('/api/patients', json={'name': 'Jordan', 'blood_type': 'O+', 'allergies': ['Penicillin']})
        resp = client.get('/api/print/medical-cards')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Medical Cards' in html
        assert 'Patient Medical Cards' in html
        assert 'Jordan' in html

    def test_contacts_directory_document(self, client):
        client.post('/api/contacts', json={'name': 'Alex Base', 'phone': '555-0101', 'rally_point': 'Safehouse Alpha'})
        resp = client.get('/api/contacts/print')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Contact Directory' in html
        assert 'Known Rally Points' in html
        assert 'Alex Base' in html

    def test_inventory_report_document(self, client):
        client.post('/api/inventory', json={'name': 'Water Can', 'category': 'water', 'quantity': 4, 'unit': 'gal', 'min_quantity': 6, 'daily_usage': 1})
        resp = client.get('/api/inventory/print')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Inventory Report' in html
        assert 'Category Breakdown' in html
        assert 'Water Can' in html

    def test_emergency_sheet_document(self, client):
        client.post('/api/contacts', json={'name': 'Morgan', 'phone': '555-0102'})
        client.post('/api/patients', json={'name': 'Casey'})
        resp = client.get('/api/emergency-sheet')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Emergency Reference Sheet' in html
        assert 'Quick Reference' in html
        assert 'Morgan' in html

    def test_emergency_sheet_recovers_from_corrupted_patient_lists(self, client, db):
        client.post('/api/patients', json={'name': 'Casey Corrupt'})
        db.execute(
            'UPDATE patients SET allergies = ?, medications = ?, conditions = ? WHERE name = ?',
            ('{broken', '{broken', '{broken', 'Casey Corrupt'),
        )
        db.commit()

        resp = client.get('/api/emergency-sheet')

        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Casey Corrupt' in html
        assert '{broken' not in html

    def test_wallet_reference_cards_document(self, client):
        client.post('/api/patients', json={'name': 'Riley', 'blood_type': 'A-', 'allergies': ['Latex']})
        resp = client.get('/api/print/wallet-cards')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Wallet Reference Cards' in html
        assert 'ICE Card' in html
        assert 'Riley' in html

    def test_soi_document(self, client):
        resp = client.get('/api/print/soi')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'signal operating instructions' in html.lower()
        assert 'Section 1 - Frequency Assignments' in html
        assert 'Section 5 - Authentication &amp; Procedures' in html

    def test_medical_flipbook_document(self, client):
        resp = client.get('/api/print/medical-flipbook')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Medical Reference Flipbook' in html
        assert 'Field Medical Quick Reference' in html
        assert 'Page 1 of 8' in html

    def test_operations_binder_document(self, client):
        client.post('/api/contacts', json={'name': 'Harper Lane', 'phone': '555-0133', 'role': 'Medic'})
        client.post('/api/patients', json={'name': 'Sage', 'blood_type': 'AB+'})
        client.post('/api/inventory', json={'name': 'Trauma Kit', 'category': 'medical', 'quantity': 2, 'unit': 'kits'})
        resp = client.get('/api/print/operations-binder')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Operations Binder' in html
        assert 'Operations Binder Overview' in html
        assert 'Harper Lane' in html
        assert 'Trauma Kit' in html

    def test_operations_binder_recovers_from_corrupted_patient_lists_and_checklists(self, client, db):
        client.post('/api/patients', json={'name': 'Sage Corrupt', 'blood_type': 'AB+'})
        db.execute(
            'UPDATE patients SET allergies = ?, medications = ?, conditions = ? WHERE name = ?',
            ('{broken', '{broken', '{broken', 'Sage Corrupt'),
        )
        db.execute('INSERT INTO checklists (name, items) VALUES (?, ?)', ('Broken Checklist', '{broken'))
        db.commit()

        resp = client.get('/api/print/operations-binder')

        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Operations Binder' in html
        assert 'Sage Corrupt' in html
        assert 'Broken Checklist' in html
        assert '{broken' not in html

    def test_map_atlas_document(self, client):
        client.post('/api/waypoints', json={'name': 'Checkpoint Cedar', 'lat': 39.7392, 'lng': -104.9903, 'category': 'checkpoint'})
        resp = client.post('/api/maps/atlas', json={
            'title': 'Front Range Atlas',
            'lat': 39.7392,
            'lng': -104.9903,
            'zoom_levels': [10],
            'grid_size': 1,
        })
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Front Range Atlas' in html
        assert 'Atlas Contents' in html
        assert 'Checkpoint Cedar' in html

    def test_map_atlas_document_escapes_untrusted_title_and_waypoint_labels(self, client):
        client.post('/api/waypoints', json={'name': '<b>Checkpoint Cedar</b>', 'lat': 39.7392, 'lng': -104.9903, 'category': '<script>alert(1)</script>'})
        resp = client.post('/api/maps/atlas', json={
            'title': '<script>alert(1)</script>',
            'lat': 39.7392,
            'lng': -104.9903,
            'zoom_levels': [10],
            'grid_size': 1,
        })
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '<script>alert(1)</script>' not in html
        assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
        assert '&lt;b&gt;Checkpoint Cedar&lt;/b&gt;' in html
        assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html

    def test_watch_schedule_document(self, client):
        create = client.post('/api/watch-schedules', json={
            'name': 'Night Watch',
            'start_date': '2026-01-10',
            'end_date': '2026-01-11',
            'shift_duration_hours': 6,
            'personnel': ['Alex', 'Riley', 'Sage'],
            'notes': 'Rotate radios and perimeter notes at each handoff.',
        })
        assert create.status_code == 201
        sid = create.get_json()['id']
        resp = client.get(f'/api/watch-schedules/{sid}/print')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Watch Schedule - Night Watch' in html
        assert 'Shift Assignments' in html
        assert 'Rotate radios and perimeter notes at each handoff.' in html


class TestICS309:
    """Phase C1: ICS-309 Communications Log — HTML, JSON, and PDF.

    Verifies the default 24h window, multi-source merge of comms_log +
    lan_messages + mesh_messages, operator filter (which correctly
    excludes LAN/mesh traffic because operators filter only radio),
    explicit date window, direction-based from/to mapping, and the
    PDF endpoint's graceful fallback when reportlab is missing."""

    def test_ics309_html_renders_with_no_traffic(self, client):
        resp = client.get('/api/print/ics-309')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'ICS-309' in html
        assert 'Chronological Log' in html
        assert 'No comms traffic recorded' in html

    def test_ics309_json_shape(self, client):
        resp = client.get('/api/print/ics-309?format=json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['entry_count'] == 0
        assert data['entries'] == []
        assert 'operational_period' in data
        assert 'from' in data['operational_period']
        assert 'to' in data['operational_period']

    def test_ics309_merges_all_three_sources(self, client, db):
        db.execute(
            "INSERT INTO comms_log (freq, callsign, direction, message, created_at) "
            "VALUES ('146.520', 'W1AW', 'rx', 'Net check-in', datetime('now', '-1 hour'))"
        )
        db.execute(
            "INSERT INTO lan_messages (sender, content, created_at) "
            "VALUES ('Alice', 'Moving to rally point', datetime('now', '-30 minutes'))"
        )
        db.execute(
            "INSERT INTO mesh_messages (from_node, to_node, message, channel, timestamp) "
            "VALUES ('NODE1', 'BROADCAST', 'Mesh hello', 'primary', datetime('now', '-15 minutes'))"
        )
        db.commit()
        resp = client.get('/api/print/ics-309?format=json')
        data = resp.get_json()
        assert data['entry_count'] == 3
        sources = {e['source'] for e in data['entries']}
        assert sources == {'radio', 'lan', 'mesh'}
        times = [e['time'] for e in data['entries']]
        assert times == sorted(times)

    def test_ics309_operator_filter_restricts_to_comms_log(self, client, db):
        db.execute(
            "INSERT INTO comms_log (freq, callsign, direction, message, created_at) "
            "VALUES ('146.520', 'W1AW', 'rx', 'hello', datetime('now', '-1 hour'))"
        )
        db.execute(
            "INSERT INTO comms_log (freq, callsign, direction, message, created_at) "
            "VALUES ('146.520', 'K7XYZ', 'rx', 'hello too', datetime('now', '-30 minutes'))"
        )
        db.execute(
            "INSERT INTO lan_messages (sender, content, created_at) "
            "VALUES ('Alice', 'LAN msg', datetime('now', '-1 hour'))"
        )
        db.commit()
        resp = client.get('/api/print/ics-309?format=json&operator=W1AW')
        data = resp.get_json()
        assert data['entry_count'] == 1
        assert data['entries'][0]['from_station'] == 'W1AW'
        assert data['entries'][0]['source'] == 'radio'

    def test_ics309_window_excludes_old_traffic(self, client, db):
        db.execute(
            "INSERT INTO comms_log (freq, callsign, direction, message, created_at) "
            "VALUES ('146.520', 'OLD', 'rx', 'ancient', datetime('now', '-48 hours'))"
        )
        db.execute(
            "INSERT INTO comms_log (freq, callsign, direction, message, created_at) "
            "VALUES ('146.520', 'NEW', 'rx', 'recent', datetime('now', '-2 hours'))"
        )
        db.commit()
        resp = client.get('/api/print/ics-309?format=json')
        data = resp.get_json()
        callsigns = {e['from_station'] for e in data['entries']}
        assert 'NEW' in callsigns
        assert 'OLD' not in callsigns

    def test_ics309_incident_and_station_rendered(self, client):
        resp = client.get(
            '/api/print/ics-309?incident=Hurricane%20Alpha&station=K7NOMAD&operator=W1AW'
        )
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Hurricane Alpha' in html
        assert 'K7NOMAD' in html
        assert 'W1AW' in html

    def test_ics309_direction_flips_from_to(self, client, db):
        db.execute(
            "INSERT INTO comms_log (freq, callsign, direction, message, created_at) "
            "VALUES ('146.520', 'W1AW', 'tx', 'go ahead', datetime('now', '-1 hour'))"
        )
        db.execute(
            "INSERT INTO comms_log (freq, callsign, direction, message, created_at) "
            "VALUES ('146.520', 'K7XYZ', 'rx', 'copy that', datetime('now', '-30 minutes'))"
        )
        db.commit()
        resp = client.get('/api/print/ics-309?format=json')
        entries = resp.get_json()['entries']
        tx_row = next(e for e in entries if 'go ahead' in e['message'])
        rx_row = next(e for e in entries if 'copy that' in e['message'])
        assert tx_row['from_station'] == 'SELF'
        assert tx_row['to_station'] == 'W1AW'
        assert rx_row['from_station'] == 'K7XYZ'
        assert rx_row['to_station'] == 'SELF'

    def test_ics309_explicit_window(self, client, db):
        db.execute(
            "INSERT INTO comms_log (freq, callsign, direction, message, created_at) "
            "VALUES ('146.520', 'W1AW', 'rx', 'in range', '2025-01-02 12:00:00')"
        )
        db.execute(
            "INSERT INTO comms_log (freq, callsign, direction, message, created_at) "
            "VALUES ('146.520', 'K7XYZ', 'rx', 'out of range', '2025-02-15 09:00:00')"
        )
        db.commit()
        resp = client.get(
            '/api/print/ics-309?format=json&from=2025-01-01&to=2025-01-03'
        )
        data = resp.get_json()
        callsigns = {e['from_station'] for e in data['entries']}
        assert 'W1AW' in callsigns
        assert 'K7XYZ' not in callsigns

    def test_ics309_pdf_returns_200_or_graceful_500(self, client):
        resp = client.get('/api/print/pdf/ics-309')
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.headers.get('Content-Type', '').startswith('application/pdf')
            body = resp.get_data()
            assert body.startswith(b'%PDF-')
        else:
            err = resp.get_json()
            assert 'reportlab' in err.get('error', '').lower()
