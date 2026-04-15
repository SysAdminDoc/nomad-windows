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
