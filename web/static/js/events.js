/**
 * Server-Sent Events (SSE) client for real-time updates in NOMAD Field Desk.
 * Handles connection, reconnection, and event dispatching.
 */

const NomadEvents = {
    _source: null,
    _handlers: {},
    _reconnectDelay: 1000,
    _maxReconnectDelay: 30000,

    connect() {
        if (this._source) this._source.close();
        this._source = new EventSource('/api/events/stream');

        this._source.onopen = () => {
            this._reconnectDelay = 1000;
            console.log('[SSE] Connected');
            const dot = document.getElementById('sse-dot');
            const wrap = document.getElementById('sse-status');
            if (dot) dot.style.background = 'var(--green)';
            if (wrap) wrap.title = 'Real-time updates: connected';
        };

        this._source.onerror = () => {
            const dot = document.getElementById('sse-dot');
            const wrap = document.getElementById('sse-status');
            if (dot) dot.style.background = 'var(--red)';
            if (wrap) wrap.title = 'Real-time updates: disconnected \u2014 reconnecting...';
            this._source.close();
            this._source = null;
            const jitter = Math.random() * this._reconnectDelay * 0.3;
            setTimeout(() => this.connect(), this._reconnectDelay + jitter);
            this._reconnectDelay = Math.min(this._reconnectDelay * 2, this._maxReconnectDelay);
        };

        // Register event types
        ['inventory_update', 'weather_update', 'alert', 'alert_check', 'task_update',
         'sync_update', 'backup_complete', 'power_update'].forEach(type => {
            this._source.addEventListener(type, (e) => {
                let data;
                try { data = JSON.parse(e.data); } catch(err) { console.warn('[SSE] Bad JSON:', err); return; }
                this._dispatch(type, data);
            });
        });
    },

    on(event, handler) {
        if (!this._handlers[event]) this._handlers[event] = [];
        this._handlers[event].push(handler);
    },

    off(event, handler) {
        if (!this._handlers[event]) return;
        this._handlers[event] = this._handlers[event].filter(h => h !== handler);
    },

    _dispatch(event, data) {
        (this._handlers[event] || []).forEach(h => {
            try { h(data); } catch(e) { console.error('[SSE] Handler error:', e); }
        });
    },

    disconnect() {
        if (this._source) { this._source.close(); this._source = null; }
        const dot = document.getElementById('sse-dot');
        const wrap = document.getElementById('sse-status');
        if (dot) dot.style.background = 'var(--red)';
        if (wrap) wrap.title = 'Real-time updates: disconnected';
    }
};

// Wire up real-time handlers
NomadEvents.on('inventory_update', () => {
    if (typeof loadInventory === 'function') loadInventory();
});
NomadEvents.on('weather_update', (data) => {
    if (typeof updateWeatherDisplay === 'function') updateWeatherDisplay(data);
});
NomadEvents.on('alert', (data) => {
    if (typeof showToast === 'function') showToast(data.message || 'New alert', data.level || 'info');
});
NomadEvents.on('alert_check', (data) => {
    if (!document.hidden && typeof loadAlerts === 'function') loadAlerts();
    // Push notification when page is hidden/backgrounded
    if (document.hidden && typeof _notifsEnabled !== 'undefined' && _notifsEnabled) {
        try {
            if (data.title) {
                if (navigator.serviceWorker && navigator.serviceWorker.controller) {
                    navigator.serviceWorker.controller.postMessage({type: 'push-alert', title: data.title, body: data.message || ''});
                } else if (typeof sendNotification === 'function') {
                    sendNotification(data.title, data.message || 'New alert');
                }
            } else if (data.event === 'new_alerts') {
                if (typeof sendNotification === 'function') sendNotification('NOMAD Alert', 'New situation alert received');
            }
        } catch(e) { if (typeof sendNotification === 'function') sendNotification('NOMAD Alert', 'New alert received'); }
    }
});
NomadEvents.on('task_update', () => {
    if (typeof loadTasks === 'function') loadTasks();
});
NomadEvents.on('sync_update', (data) => {
    if (typeof showToast === 'function') showToast('Sync received from ' + (data.source || 'peer'), 'info');
});
NomadEvents.on('backup_complete', (data) => {
    if (typeof showToast === 'function') showToast('Backup complete: ' + (data.filename || ''), 'success');
});

// Auto-connect when page loads
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => NomadEvents.connect());
    window.addEventListener('beforeunload', () => NomadEvents.disconnect());
}

// Attach to window for backward compatibility
window.NomadEvents = NomadEvents;
