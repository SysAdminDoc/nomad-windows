/**
 * Battery-aware auto-throttling for NOMAD Field Desk.
 * Reduces polling and animations when battery is low.
 */

const BatteryManager = {
  _battery: null,
  _normalIntervals: {},
  _throttled: false,
  LOW_THRESHOLD: 0.20,
  CRITICAL_THRESHOLD: 0.10,

  async init() {
    if (!navigator.getBattery) return;
    try {
      this._battery = await navigator.getBattery();
      this._battery.addEventListener('levelchange', () => this._evaluate());
      this._battery.addEventListener('chargingchange', () => this._evaluate());
      this._evaluate();
    } catch(e) { console.warn('Battery API unavailable:', e); }
  },

  _evaluate() {
    if (!this._battery) return;
    const level = this._battery.level;
    const charging = this._battery.charging;
    const badge = document.getElementById('battery-indicator');

    if (charging) {
      this._unthrottle();
      if (badge) { badge.textContent = '\u26A1 ' + Math.round(level * 100) + '%'; badge.style.color = 'var(--green)'; badge.style.display = ''; }
      return;
    }

    if (badge) {
      badge.textContent = '\uD83D\uDD0B ' + Math.round(level * 100) + '%';
      badge.style.display = '';
      badge.style.color = level <= this.CRITICAL_THRESHOLD ? 'var(--red)' : level <= this.LOW_THRESHOLD ? 'var(--orange)' : 'var(--text-dim)';
    }

    if (level <= this.CRITICAL_THRESHOLD) {
      if (this._throttled !== 'critical') {
        toast('Critical battery \u2014 heavy polling disabled, animations off', 'warning');
      }
      this._throttle('critical');
    } else if (level <= this.LOW_THRESHOLD) {
      this._throttle('low');
    } else {
      this._unthrottle();
    }
  },

  _throttle(severity) {
    if (this._throttled === severity) return;
    this._throttled = severity;
    document.documentElement.classList.add('battery-saver');
    if (severity === 'critical') {
      document.documentElement.classList.add('battery-critical');
    }
    // Reduce OfflineSync interval if available
    if (typeof OfflineSync !== 'undefined' && OfflineSync._syncInterval) {
      try { OfflineSync.stopAutoSync(); } catch(e) { console.debug('[Battery] stopAutoSync error:', e); }
      OfflineSync.startAutoSync(severity === 'critical' ? 1800000 : 900000, true);
    }
  },

  _unthrottle() {
    if (!this._throttled) return;
    this._throttled = false;
    document.documentElement.classList.remove('battery-saver', 'battery-critical');
    if (typeof OfflineSync !== 'undefined') {
      try { OfflineSync.stopAutoSync(); } catch(e) { console.debug('[Battery] stopAutoSync error:', e); }
      OfflineSync.startAutoSync(300000, true);
    }
  },

  getStatus() {
    if (!this._battery) return { supported: false };
    return {
      supported: true,
      level: Math.round(this._battery.level * 100),
      charging: this._battery.charging,
      throttled: this._throttled
    };
  }
};

// Attach to window for backward compatibility
window.BatteryManager = BatteryManager;
