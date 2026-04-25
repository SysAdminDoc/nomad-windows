// ─── Phase A3: RAG scope manager ─────────────────────────────────────
// Lets the operator pick which DB tables get fed to the LLM as context,
// with per-table enabled/weight/max-rows and a preview button that shows
// exactly what the model will see.
//
// This file is intentionally self-contained — it only touches its own
// DOM node ids (#rag-scope-*) and exposes helpers on window without
// colliding with existing globals.

(function () {
    const BODY = () => document.getElementById('rag-scope-body');
    const STATUS = () => document.getElementById('rag-scope-status');
    const PREVIEW = () => document.getElementById('rag-scope-preview');

    const esc = (s) => String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

    function setStatus(msg, tone) {
        const el = STATUS();
        if (!el) return;
        el.textContent = msg || '';
        el.dataset.tone = tone || 'neutral';
    }

    async function loadScope() {
        const body = BODY();
        if (!body) return;
        body.innerHTML = '<div class="tone-muted">Loading RAG scope…</div>';
        try {
            const resp = await window.apiFetch('/api/ai/rag/scope');
            const data = resp && resp.data ? resp.data : resp;
            const rows = (data && data.scope) || [];
            if (rows.length === 0) {
                body.innerHTML = '<div class="tone-muted">No scope entries found. Run the seeder or reset defaults.</div>';
                return;
            }
            body.innerHTML = rows.map(renderRow).join('');
            wireRowEvents();
            setStatus(`${rows.length} table${rows.length === 1 ? '' : 's'} loaded`, 'neutral');
        } catch (e) {
            body.innerHTML = `<div class="tone-danger">Failed to load scope: ${esc(e && e.message)}</div>`;
        }
    }

    function renderRow(row) {
        const checked = row.enabled ? 'checked' : '';
        const customPill = row.source === 'custom'
            ? '<span class="ss-pill tone-info">custom</span>'
            : '';
        const formatterPill = row.formatter === 'builtin'
            ? '<span class="ss-pill tone-success">builtin</span>'
            : '<span class="ss-pill tone-muted">generic</span>';
        const colsPreview = row.columns_json
            ? `<div class="rag-scope-row-cols tone-muted">cols: ${esc(row.columns_json)}</div>`
            : '';
        return `
<div class="rag-scope-row" data-table="${esc(row.table_name)}">
  <div class="rag-scope-row-head">
    <label class="rag-scope-row-toggle">
      <input type="checkbox" data-field="enabled" ${checked} aria-label="Enable ${esc(row.table_name)} in RAG context">
      <strong>${esc(row.label)}</strong>
      <code class="tone-muted">${esc(row.table_name)}</code>
    </label>
    <span class="rag-scope-row-pills">${formatterPill}${customPill}</span>
  </div>
  <div class="rag-scope-row-controls">
    <label>Weight
      <input type="number" data-field="weight" value="${Number(row.weight)}" min="0" max="1000" step="1">
    </label>
    <label>Max rows
      <input type="number" data-field="max_rows" value="${Number(row.max_rows)}" min="1" max="500" step="1">
    </label>
    <button type="button" class="btn btn-sm" data-rag-action="save">Save</button>
    ${row.source === 'custom'
        ? `<button type="button" class="btn btn-sm btn-ghost" data-rag-action="delete">Remove</button>`
        : ''}
  </div>
  ${colsPreview}
</div>`;
    }

    function wireRowEvents() {
        const body = BODY();
        if (!body) return;
        body.querySelectorAll('[data-rag-action="save"]').forEach((btn) => {
            btn.addEventListener('click', onSaveRow);
        });
        body.querySelectorAll('[data-rag-action="delete"]').forEach((btn) => {
            btn.addEventListener('click', onDeleteRow);
        });
        body.querySelectorAll('input[data-field="enabled"]').forEach((cb) => {
            cb.addEventListener('change', onToggleEnabled);
        });
    }

    function rowPayload(rowEl) {
        return {
            table_name: rowEl.dataset.table,
            weight:   Number(rowEl.querySelector('[data-field="weight"]').value || 0),
            max_rows: Number(rowEl.querySelector('[data-field="max_rows"]').value || 10),
            enabled:  rowEl.querySelector('[data-field="enabled"]').checked,
        };
    }

    async function onSaveRow(ev) {
        const row = ev.currentTarget.closest('.rag-scope-row');
        if (!row) return;
        try {
            await window.apiPost('/api/ai/rag/scope', rowPayload(row));
            setStatus(`Saved ${row.dataset.table}`, 'success');
        } catch (e) {
            setStatus(`Save failed: ${(e && e.message) || 'unknown error'}`, 'danger');
        }
    }

    async function onDeleteRow(ev) {
        const row = ev.currentTarget.closest('.rag-scope-row');
        if (!row) return;
        const confirmed = await window.confirmChoice(`Remove custom RAG entry "${row.dataset.table}".`, {
            title: 'Remove RAG scope entry?',
            detail: 'The table will no longer contribute custom retrieval context until it is added again.',
            confirmLabel: 'Remove Entry',
            tone: 'danger',
        });
        if (!confirmed) return;
        try {
            await window.apiDelete(`/api/ai/rag/scope/${encodeURIComponent(row.dataset.table)}`);
            setStatus(`Removed ${row.dataset.table}`, 'success');
            loadScope();
        } catch (e) {
            setStatus(`Delete failed: ${(e && e.message) || 'unknown error'}`, 'danger');
        }
    }

    async function onToggleEnabled(ev) {
        const row = ev.currentTarget.closest('.rag-scope-row');
        if (!row) return;
        try {
            await window.apiPost('/api/ai/rag/scope', {
                table_name: row.dataset.table,
                enabled: ev.currentTarget.checked,
            });
            setStatus(`${ev.currentTarget.checked ? 'Enabled' : 'Disabled'} ${row.dataset.table}`, 'success');
        } catch (e) {
            ev.currentTarget.checked = !ev.currentTarget.checked; // revert
            setStatus(`Toggle failed: ${(e && e.message) || 'unknown error'}`, 'danger');
        }
    }

    async function onReset() {
        const confirmed = await window.confirmChoice('Reset all builtin RAG scope entries to defaults.', {
            title: 'Reset RAG defaults?',
            detail: 'Custom entries are preserved, but builtin table weights and enabled states will be restored.',
            confirmLabel: 'Reset Defaults',
            tone: 'warning',
        });
        if (!confirmed) return;
        try {
            await window.apiPost('/api/ai/rag/scope/reset', {});
            setStatus('Defaults restored', 'success');
            loadScope();
        } catch (e) {
            setStatus(`Reset failed: ${(e && e.message) || 'unknown error'}`, 'danger');
        }
    }

    async function onPreview() {
        const box = PREVIEW();
        if (!box) return;
        box.textContent = 'Generating preview…';
        try {
            const resp = await window.apiFetch('/api/ai/rag/preview?detail_level=full');
            const data = resp && resp.data ? resp.data : resp;
            const sections = (data && data.sections) || [];
            box.textContent = sections.length === 0
                ? '(empty — no enabled tables have data)'
                : `${data.section_count} sections · ${data.char_count} chars\n\n${data.payload}`;
        } catch (e) {
            box.textContent = `Preview failed: ${(e && e.message) || 'unknown error'}`;
        }
    }

    function init() {
        const panel = document.getElementById('rag-scope-panel');
        if (!panel) return; // panel not in DOM yet; settings tab not loaded
        const reset = document.getElementById('rag-scope-reset-btn');
        const preview = document.getElementById('rag-scope-preview-btn');
        const refresh = document.getElementById('rag-scope-refresh-btn');
        if (reset) reset.addEventListener('click', onReset);
        if (preview) preview.addEventListener('click', onPreview);
        if (refresh) refresh.addEventListener('click', loadScope);
        loadScope();
    }

    window.ragScopeReload = loadScope;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
