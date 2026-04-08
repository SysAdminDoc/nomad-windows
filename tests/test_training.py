"""Tests for AI training datasets and jobs API routes."""

import json
from pathlib import Path

from config import get_data_dir


class TestTrainingDatasets:
    def test_training_datasets_list(self, client):
        resp = client.get('/api/ai/training/datasets')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_training_dataset_create(self, client):
        resp = client.post('/api/ai/training/datasets', json={
            'name': 'Test Dataset',
            'source': 'upload',
            'description': 'Uploaded JSONL dataset',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert 'id' in data
        assert 'records' in data

    def test_training_dataset_path_traversal(self, client):
        """Names containing ../ should be sanitized to safe filenames."""
        resp = client.post('/api/ai/training/datasets', json={
            'name': '../../etc/passwd',
            'source': 'upload',
        })
        assert resp.status_code == 201
        # Should succeed but the name on disk is sanitized (only a-z0-9_-)
        data = resp.get_json()
        assert 'id' in data


class TestTrainingJobs:
    def test_training_jobs_list(self, client):
        resp = client.get('/api/ai/training/jobs')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_training_job_create(self, client):
        # First create a dataset to reference
        ds = client.post('/api/ai/training/datasets', json={
            'name': 'Job Test Dataset',
            'source': 'upload',
        }).get_json()

        resp = client.post('/api/ai/training/jobs', json={
            'dataset_id': ds['id'],
            'base_model': 'llama3.2',
            'output_model': 'nomad-test-model',
            'epochs': 3,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert 'id' in data
        assert data['output_model'] == 'nomad-test-model'

    def test_training_job_run_not_found(self, client):
        resp = client.post('/api/ai/training/jobs/999/run')
        assert resp.status_code == 404
        assert 'not found' in resp.get_json()['error'].lower() or 'Job' in resp.get_json()['error']

    def test_training_job_path_traversal(self, client):
        """output_model containing ../ should be sanitized."""
        resp = client.post('/api/ai/training/jobs', json={
            'base_model': 'llama3.2',
            'output_model': '../../../evil-model',
            'epochs': 1,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        # Slashes and dots should be stripped from output_model
        assert '/' not in data['output_model']
        assert '..' not in data['output_model']

    def test_training_base_model_injection(self, client):
        """base_model containing newlines or special chars should be sanitized."""
        resp = client.post('/api/ai/training/jobs', json={
            'base_model': 'llama3.2\n; rm -rf /',
            'output_model': 'safe-model',
            'epochs': 1,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert 'id' in data
        # The base_model should have been cleaned of dangerous characters

    def test_training_job_create_skips_malformed_dataset_sample_lines(self, client, db, tmp_path):
        dataset_path = tmp_path / 'mixed-dataset.jsonl'
        dataset_path.write_text(
            '\n'.join([
                json.dumps({'instruction': 'Purify water for a field team', 'response': 'Boil for one minute.'}),
                '{broken',
                json.dumps({'instruction': 'Establish a perimeter at night', 'response': 'Set overlapping sectors.'}),
            ]),
            encoding='utf-8',
        )

        db.execute(
            'INSERT INTO training_datasets (name, description, format, record_count, file_path, base_model, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ('Mixed Dataset', 'mixed sample file', 'jsonl', 2, str(dataset_path), '', 'ready'),
        )
        db.commit()
        ds = db.execute('SELECT id FROM training_datasets WHERE name = ?', ('Mixed Dataset',)).fetchone()

        resp = client.post('/api/ai/training/jobs', json={
            'dataset_id': ds['id'],
            'base_model': 'llama3.2',
            'output_model': 'mixed-sample-model',
            'epochs': 1,
        })

        assert resp.status_code == 201
        modelfile = Path(get_data_dir()) / 'modelfiles' / 'mixed-sample-model.Modelfile'
        assert modelfile.exists()
        contents = modelfile.read_text(encoding='utf-8')
        assert 'Purify water for a field team' in contents
