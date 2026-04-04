/**
 * IndexedDB offline data sync for NOMAD Field Desk.
 * Caches critical data tables for offline access.
 */

const OfflineSync = {
  DB_NAME: 'nomad-offline',
  DB_VERSION: 1,
  STORES: ['inventory', 'contacts', 'patients', 'waypoints', 'checklists', 'freq_database'],
  _db: null,
  _syncInterval: null,

  async init() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(this.DB_NAME, this.DB_VERSION);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        this.STORES.forEach(store => {
          if (!db.objectStoreNames.contains(store)) {
            db.createObjectStore(store, { keyPath: 'id' });
          }
        });
        if (!db.objectStoreNames.contains('_meta')) {
          db.createObjectStore('_meta', { keyPath: 'key' });
        }
      };
      req.onsuccess = (e) => { this._db = e.target.result; resolve(this._db); };
      req.onerror = (e) => { console.warn('IndexedDB init failed:', e); reject(e.target?.error || e); };
    });
  },

  async fullSync() {
    if (!this._db) await this.init();
    try {
      const resp = await fetch('/api/offline/snapshot');
      if (!resp.ok) throw new Error('Snapshot fetch failed');
      const data = await resp.json();
      for (const store of this.STORES) {
        if (!data[store]) continue;
        await new Promise((resolve, reject) => {
          const tx = this._db.transaction(store, 'readwrite');
          const os = tx.objectStore(store);
          os.clear();
          data[store].forEach(row => os.put(row));
          tx.oncomplete = resolve;
          tx.onerror = () => reject(tx.error);
        });
      }
      // Save sync metadata
      await new Promise((resolve, reject) => {
        const metaTx = this._db.transaction('_meta', 'readwrite');
        metaTx.objectStore('_meta').put({ key: 'lastSync', value: data._timestamp || new Date().toISOString(), fullSync: true });
        metaTx.oncomplete = resolve;
        metaTx.onerror = () => reject(metaTx.error);
      });
      this._updateSyncBadge('synced');
      return { tables: this.STORES.length, timestamp: data._timestamp };
    } catch (e) {
      console.warn('Offline full sync failed:', e);
      this._updateSyncBadge('error');
      return null;
    }
  },

  async incrementalSync() {
    if (!this._db) await this.init();
    try {
      const metaTx = this._db.transaction('_meta', 'readonly');
      const meta = await new Promise(resolve => {
        const req = metaTx.objectStore('_meta').get('lastSync');
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => resolve(null);
      });
      const since = meta ? meta.value : '2000-01-01T00:00:00';
      const resp = await fetch(`/api/offline/changes-since?since=${encodeURIComponent(since)}`);
      if (!resp.ok) throw new Error('Changes fetch failed');
      const data = await resp.json();
      let totalChanges = 0;
      const ts = data._timestamp || new Date().toISOString();
      for (const [table, rows] of Object.entries(data)) {
        if (table.startsWith('_') || !this.STORES.includes(table)) continue;
        if (!rows.length) continue;
        await new Promise((resolve, reject) => {
          const tx = this._db.transaction(table, 'readwrite');
          const os = tx.objectStore(table);
          rows.forEach(row => { os.put(row); totalChanges++; });
          tx.oncomplete = resolve;
          tx.onerror = () => reject(tx.error);
        });
      }
      await new Promise((resolve, reject) => {
        const metaTx2 = this._db.transaction('_meta', 'readwrite');
        metaTx2.objectStore('_meta').put({ key: 'lastSync', value: ts, fullSync: false, changes: totalChanges });
        metaTx2.oncomplete = resolve;
        metaTx2.onerror = () => reject(metaTx2.error);
      });
      this._updateSyncBadge('synced');
      return { changes: totalChanges, timestamp: ts };
    } catch (e) {
      console.warn('Offline incremental sync failed:', e);
      this._updateSyncBadge('error');
      return null;
    }
  },

  async getOfflineData(store) {
    if (!this._db) await this.init();
    return new Promise((resolve, reject) => {
      const tx = this._db.transaction(store, 'readonly');
      const req = tx.objectStore(store).getAll();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  },

  async getSyncStatus() {
    if (!this._db) await this.init();
    return new Promise(resolve => {
      const tx = this._db.transaction('_meta', 'readonly');
      const req = tx.objectStore('_meta').get('lastSync');
      req.onsuccess = () => resolve(req.result || { key: 'lastSync', value: null });
      req.onerror = () => resolve({ key: 'lastSync', value: null });
    });
  },

  startAutoSync(intervalMs, skipInitialSync) {
    if (this._syncInterval) clearInterval(this._syncInterval);
    this._syncInterval = setInterval(() => this.incrementalSync(), intervalMs || 300000); // 5 min default
    // Do initial full sync unless called from battery throttle
    if (!skipInitialSync) this.fullSync().catch(err => console.warn('[Offline] Initial sync failed:', err));
  },

  stopAutoSync() {
    if (this._syncInterval) { clearInterval(this._syncInterval); this._syncInterval = null; }
  },

  _updateSyncBadge(status) {
    const badge = document.getElementById('offline-sync-badge');
    if (!badge) return;
    if (status === 'synced') {
      badge.style.background = 'var(--green)';
      badge.title = 'Offline data synced';
    } else if (status === 'error') {
      badge.style.background = 'var(--orange)';
      badge.title = 'Offline sync error';
    } else {
      badge.style.background = 'var(--text-muted)';
      badge.title = 'Offline sync pending';
    }
  }
};

// Attach to window for backward compatibility
window.OfflineSync = OfflineSync;
