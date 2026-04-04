/**
 * Internationalization (i18n) for NOMAD Field Desk.
 * Handles language loading, translation, and RTL support.
 */

const NomadI18n = {
    _lang: 'en',
    _translations: {},
    _fallback: {},

    async init() {
        const bootstrap = window.__NOMAD_I18N_BOOTSTRAP;
        if (bootstrap && bootstrap.lang && bootstrap.translations) {
            this._lang = bootstrap.lang || 'en';
            this._translations = bootstrap.translations || {};
            this._fallback = bootstrap.fallback || (this._lang === 'en' ? this._translations : {});
        } else {
            try {
                const resp = await fetch('/api/i18n/language');
                const data = await resp.json();
                this._lang = data.language || 'en';
            } catch(e) {
                this._lang = 'en';
            }
            await this.loadTranslations(this._lang);
        }
        this.applyTranslations();
        loadLanguageSelector();
    },

    async loadTranslations(lang) {
        this._translations = {};
        this._fallback = {};
        try {
            const resp = await fetch(`/api/i18n/translations/${lang}`);
            if (resp.ok) {
                const data = await resp.json();
                this._translations = data.translations || {};
            }
            // Always load English as fallback
            if (lang !== 'en') {
                const fbResp = await fetch('/api/i18n/translations/en');
                if (fbResp.ok) {
                    const fbData = await fbResp.json();
                    this._fallback = fbData.translations || {};
                }
            } else {
                this._fallback = this._translations;
            }
        } catch(e) {
            console.error('[i18n] Failed to load translations:', e);
        }
    },

    t(key, params) {
        let str = this._translations[key] || this._fallback[key] || key;
        if (params) {
            Object.entries(params).forEach(([k, v]) => {
                str = str.split(`{${k}}`).join(String(v));
            });
        }
        return str;
    },

    async setLanguage(lang) {
        try {
            await fetch('/api/i18n/language', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({language: lang})
            });
        } catch(e) { console.warn('[i18n] Language save failed:', e.message); }
        this._lang = lang;
        await this.loadTranslations(lang);
        window.__NOMAD_I18N_BOOTSTRAP = {
            lang: this._lang,
            translations: this._translations,
            fallback: this._fallback
        };
        this.applyTranslations();
    },

    applyTranslations() {
        document.documentElement.lang = this._lang;
        const rtlLangs = new Set(['ar', 'he', 'fa', 'ur']);
        const dir = rtlLangs.has(this._lang) ? 'rtl' : 'ltr';
        document.documentElement.dir = dir;
        // Update all elements with data-i18n attribute
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translated = this.t(key);
            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                el.placeholder = translated;
            } else {
                el.textContent = translated;
            }
        });
        // Update data-i18n-title for title attributes
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            el.title = this.t(el.getAttribute('data-i18n-title'));
        });
        // Update data-i18n-aria for aria-label
        document.querySelectorAll('[data-i18n-aria]').forEach(el => {
            el.setAttribute('aria-label', this.t(el.getAttribute('data-i18n-aria')));
        });
    },

    get currentLang() { return this._lang; }
};

async function loadLanguageSelector() {
    try {
        const resp = await fetch('/api/i18n/languages');
        if (!resp.ok) return;
        const data = await resp.json();
        const sel = document.getElementById('language-selector');
        if (!sel) return;
        sel.innerHTML = '';
        Object.entries(data.languages).forEach(([code, name]) => {
            const opt = document.createElement('option');
            opt.value = code;
            opt.textContent = name;
            if (code === NomadI18n.currentLang) opt.selected = true;
            sel.appendChild(opt);
        });
    } catch(e) {}
}

// Attach to window for backward compatibility
window.NomadI18n = NomadI18n;
window.loadLanguageSelector = loadLanguageSelector;
