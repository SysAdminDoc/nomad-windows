"""Extended tests for media blueprint — playlists, subscriptions, downloads."""


class TestPlaylists:
    def test_list_empty(self, client):
        resp = client.get('/api/playlists')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_playlist(self, client):
        resp = client.post('/api/playlists', json={
            'name': 'Test Playlist', 'media_type': 'audio', 'items': []
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('id')

    def test_update_playlist(self, client):
        # Create first
        create = client.post('/api/playlists', json={
            'name': 'Update Me', 'media_type': 'audio', 'items': []
        })
        pid = create.get_json()['id']
        resp = client.put(f'/api/playlists/{pid}', json={
            'name': 'Updated Name'
        })
        assert resp.status_code == 200

    def test_update_nonexistent_playlist(self, client):
        resp = client.put('/api/playlists/999999', json={'name': 'X'})
        assert resp.status_code == 404

    def test_delete_nonexistent_playlist(self, client):
        resp = client.delete('/api/playlists/999999')
        assert resp.status_code == 404

    def test_delete_playlist(self, client):
        create = client.post('/api/playlists', json={
            'name': 'Delete Me', 'media_type': 'video', 'items': []
        })
        pid = create.get_json()['id']
        resp = client.delete(f'/api/playlists/{pid}')
        assert resp.status_code == 200


class TestMediaProgress:
    def test_get_progress_default(self, client):
        resp = client.get('/api/media/progress/video/1')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['position_sec'] == 0

    def test_update_progress(self, client):
        resp = client.put('/api/media/progress/video/1', json={
            'position_sec': 120, 'duration_sec': 600
        })
        assert resp.status_code == 200

    def test_invalid_media_type(self, client):
        resp = client.get('/api/media/progress/invalid/1')
        assert resp.status_code == 400


class TestDownloadsActive:
    def test_active_downloads(self, client):
        resp = client.get('/api/downloads/active')
        assert resp.status_code == 200


class TestYtdlpStatus:
    def test_ytdlp_status(self, client):
        resp = client.get('/api/ytdlp/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'installed' in data
        assert 'source' in data

    def test_ytdlp_check_update(self, client):
        # Should not crash even if yt-dlp not installed
        resp = client.get('/api/ytdlp/check-update')
        # Could be 200 or 500 depending on network/install state
        assert resp.status_code in (200, 500)


class TestVideos:
    def test_videos_list(self, client):
        resp = client.get('/api/videos')
        assert resp.status_code == 200

    def test_audio_list(self, client):
        resp = client.get('/api/audio')
        assert resp.status_code == 200

    def test_books_list(self, client):
        resp = client.get('/api/books')
        assert resp.status_code == 200


class TestMediaBatch:
    def test_batch_delete_no_ids(self, client):
        resp = client.post('/api/media/batch-delete', json={
            'type': 'videos', 'ids': []
        })
        # Should handle empty IDs gracefully
        assert resp.status_code in (200, 400)

    def test_batch_move_invalid_type(self, client):
        resp = client.post('/api/media/batch-move', json={
            'type': 'invalid', 'ids': [1], 'folder': 'test'
        })
        assert resp.status_code in (200, 400)
