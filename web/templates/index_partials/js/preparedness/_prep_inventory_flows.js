/* ─── Resource Calculators ─── */
function filterCalcs() {
  const q = (document.getElementById('calc-search').value || '').toLowerCase();
  document.querySelectorAll('.calc-card').forEach(card => {
    const text = card.textContent.toLowerCase();
    card.style.display = !q || text.includes(q) ? '' : 'none';
  });
}

function calcWater() {
  const people = parseInt(document.getElementById('calc-water-people').value) || 1;
  const days = parseInt(document.getElementById('calc-water-days').value) || 1;
  const climate = parseFloat(document.getElementById('calc-water-climate').value) || 1;
  const gal = people * days * climate;
  const liters = gal * 3.785;
  const containers = Math.ceil(gal / 5); // 5-gallon jugs
  document.getElementById('calc-water-result').innerHTML =
    `<strong>${gal.toFixed(1)} gallons</strong> (${liters.toFixed(0)} liters) needed<br>
     That's about <strong>${containers}</strong> five-gallon jugs<br>
     <span class="text-size-11 text-dim">Based on 1 gal/person/day (drinking + cooking + hygiene). Minimum 0.5 gal/day for drinking only.</span>`;
}

function calcFood() {
  const people = parseInt(document.getElementById('calc-food-people').value) || 1;
  const days = parseInt(document.getElementById('calc-food-days').value) || 1;
  const cal = parseInt(document.getElementById('calc-food-cal').value) || 2000;
  const totalCal = people * days * cal;
  const lbsDry = totalCal / 1800; // ~1800 cal per lb of dry staples
  const mres = Math.ceil(totalCal / 1250); // ~1250 cal per MRE
  document.getElementById('calc-food-result').innerHTML =
    `<strong>${totalCal.toLocaleString()} calories</strong> total needed<br>
     ~<strong>${lbsDry.toFixed(0)} lbs</strong> of dry staples (rice, beans, oats)<br>
     Or ~<strong>${mres}</strong> MREs<br>
     <span class="text-size-11 text-dim">Dry staples avg ~1,800 cal/lb. Store variety: grains, legumes, canned protein, comfort foods.</span>`;
}

function calcPower() {
  const watts = parseInt(document.getElementById('calc-power-watts').value) || 1;
  const hours = parseInt(document.getElementById('calc-power-hours').value) || 1;
  const days = parseInt(document.getElementById('calc-power-days').value) || 1;
  const sunHrs = parseInt(document.getElementById('calc-power-sun').value) || 5;
  const dailyWh = watts * hours;
  const totalWh = dailyWh * days;
  const batteryAh12v = Math.ceil(totalWh / 12 * 1.2); // 12V, 20% safety margin, per day
  const solarWatts = Math.ceil(dailyWh / sunHrs * 1.3); // 30% loss factor
  const batteryKwh = (totalWh / 1000).toFixed(1);
  document.getElementById('calc-power-result').innerHTML =
    `<strong>${dailyWh.toLocaleString()} Wh/day</strong> (${(dailyWh/1000).toFixed(1)} kWh/day)<br>
     Total for ${days} days: <strong>${batteryKwh} kWh</strong><br>
     Battery bank: <strong>${batteryAh12v} Ah</strong> @ 12V (per day, with 20% margin)<br>
     Solar panel: <strong>${solarWatts}W</strong> minimum (with ${sunHrs}h sun, 30% loss factor)<br>
     <span class="text-size-11 text-dim">For LiFePO4 batteries, use 80% depth of discharge. Lead-acid: 50% DOD max.</span>`;
}

/* ─── Inventory ─── */
let _cachedInvItems = [];
let _invSortCol = 'name';
let _invSortDir = 'asc';
try {
  const saved = JSON.parse(localStorage.getItem('nomad-inv-sort') || '{}');
  if (saved.col) _invSortCol = saved.col;
  if (saved.dir) _invSortDir = saved.dir;
} catch(_) {}

function setInvSort(col) {
  if (_invSortCol === col) _invSortDir = _invSortDir === 'asc' ? 'desc' : 'asc';
  else { _invSortCol = col; _invSortDir = 'asc'; }
  try { localStorage.setItem('nomad-inv-sort', JSON.stringify({col: _invSortCol, dir: _invSortDir})); } catch(_) {}
  loadInventory();
}

async function loadInventory() {
  const cat = document.getElementById('inv-cat-filter').value;
  const q = document.getElementById('inv-search').value.trim();
  let url = '/api/inventory?';
  if (cat) url += `category=${encodeURIComponent(cat)}&`;
  if (q) url += `q=${encodeURIComponent(q)}&`;
  if (_invSortCol) url += `sort_by=${encodeURIComponent(_invSortCol)}&sort_dir=${_invSortDir}&`;
  try {
    const items = await safeFetch(url, {}, []);
    if (!Array.isArray(items)) throw new Error('invalid inventory payload');
    _cachedInvItems = items;
    const tbody = document.getElementById('inv-tbody');
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="prep-table-empty"><div style="text-align:center;padding:24px 0"><div style="font-size:36px;margin-bottom:8px;opacity:0.5">&#128230;</div><strong>No items found</strong><p class="tone-muted" style="margin:8px 0">Start tracking your supplies, food, water, and gear.</p><button type="button" class="btn btn-sm btn-primary" data-prep-action="show-inv-form">Add First Item</button></div></td></tr>';
      document.getElementById('inv-tfoot').innerHTML = '';
    } else {
      const today = new Date().toISOString().slice(0,10);
      const soon = new Date(Date.now()+30*86400000).toISOString().slice(0,10);
      let totalValue = 0;
      tbody.innerHTML = items.map(i => {
        const lowStock = i.min_quantity > 0 && i.quantity <= i.min_quantity;
        const usageDays = i.daily_usage > 0 ? Math.round(i.quantity / i.daily_usage) : null;
        const expDays = i.expiration ? Math.round((new Date(i.expiration) - new Date(today)) / 86400000) : null;
        const daysLeft = usageDays !== null && expDays !== null ? Math.min(usageDays, expDays) : usageDays !== null ? usageDays : expDays;
        const expired = Boolean(i.expiration && i.expiration < today);
        const expiringSoon = Boolean(i.expiration && i.expiration <= soon && !expired);
        const itemToneClass = lowStock ? 'inventory-row-alert' : daysLeft !== null && daysLeft < 7 ? 'inventory-row-risk' : expiringSoon ? 'inventory-row-watch' : '';
        const expirationToneClass = expired ? 'inventory-pill-risk' : expiringSoon ? 'inventory-pill-watch' : 'inventory-pill-neutral';
        const daysToneClass = daysLeft === null ? 'inventory-pill-neutral' : daysLeft < 7 ? 'inventory-pill-risk' : daysLeft < 30 ? 'inventory-pill-watch' : 'inventory-pill-good';
        const itemCost = (i.cost || 0);
        const itemValue = itemCost * i.quantity;
        totalValue += itemValue;
        return `<tr class="${itemToneClass}">
          <td>
            <div class="inventory-item-stack">
              <span class="inventory-item-title">${escapeHtml(i.name)}</span>
              ${i.checked_out_to ? `<span class="inventory-checkout-chip">⇄ ${escapeHtml(i.checked_out_to)}</span>` : '<span class="inventory-item-meta">Available</span>'}
            </div>
          </td>
          <td><span class="check-cat inventory-cat-chip">${escapeHtml(i.category)}</span></td>
          <td>
            <div class="inventory-qty-stack">
              <button type="button" class="qty-adj" data-prep-action="adjust-inv-qty" data-inv-id="${i.id}" data-delta="-1" title="Decrease quantity" aria-label="Decrease quantity for ${escapeAttr(i.name)}">&#9660;</button>
              <span class="inventory-qty-value" data-inv-id="${i.id}" data-inv-qty="${i.quantity}" title="Double-click to edit">${i.quantity} ${escapeHtml(i.unit)}</span>
              <button type="button" class="qty-adj" data-prep-action="adjust-inv-qty" data-inv-id="${i.id}" data-delta="1" title="Increase quantity" aria-label="Increase quantity for ${escapeAttr(i.name)}">&#9650;</button>
            </div>
          </td>
          <td class="inventory-days-cell"><span class="inventory-status-pill ${daysToneClass}">${daysLeft !== null ? `${daysLeft}d` : '-'}</span></td>
          <td class="text-size-11 inventory-meta-text">${itemCost > 0 ? '$'+itemCost.toFixed(2) : '-'}</td>
          <td class="text-size-11 inventory-meta-text">${escapeHtml(i.location || '-')}</td>
          <td class="text-size-11 inventory-meta-text">${escapeHtml(i.lot_number || '-')}</td>
          <td class="inventory-expiration-cell"><span class="inventory-status-pill ${expirationToneClass}">${expired ? 'Expired' : expDays !== null && expDays <= 30 ? 'In ' + expDays + 'd' : i.expiration || '-'}</span></td>
          <td class="inventory-notes-cell"><span class="inventory-notes-copy">${escapeHtml(i.notes || '—')}</span></td>
          <td class="prep-row-actions inventory-actions"><button type="button" class="prep-action-link" data-prep-action="edit-inv-item" data-inv-id="${i.id}">edit</button><button type="button" class="prep-action-link prep-action-link-danger" data-prep-action="delete-inv-item" data-inv-id="${i.id}" aria-label="Delete ${escapeAttr(i.name)}">x</button></td>
        </tr>`;
      }).join('');
      document.getElementById('inv-tfoot').innerHTML = totalValue > 0 ? `<tr><td colspan="4" class="prep-table-total-label">Total Inventory Value:</td><td class="prep-table-total-value">$${totalValue.toFixed(2)}</td><td colspan="5"></td></tr>` : '';
    }
    // Load summary alerts
    const summary = await safeFetch('/api/inventory/summary', {}, {});
    const alerts = document.getElementById('inv-alerts');
    const alertCards = [];
    if (summary.expired > 0) alertCards.push({tone: 'danger', label: 'Expired now', value: summary.expired, note: 'Rotate or discard first.'});
    if (summary.expiring_soon > 0) alertCards.push({tone: 'warn', label: 'Expiring soon', value: summary.expiring_soon, note: 'Review before the next cycle.'});
    if (summary.low_stock > 0) alertCards.push({tone: 'warn', label: 'Low stock', value: summary.low_stock, note: 'Restock before demand spikes.'});
    if (summary.total > 0 && !summary.expired && !summary.expiring_soon && !summary.low_stock) {
      alertCards.push({tone: 'ok', label: 'Tracked items', value: summary.total, note: 'No urgent shortages or expiry pressure.'});
    }
    alerts.innerHTML = alertCards.length ? `<div class="inventory-alert-grid">${alertCards.map(card => `
      <div class="inventory-alert-card inventory-alert-card-${card.tone}">
        <span class="inventory-alert-label">${card.label}</span>
        <strong class="inventory-alert-value">${card.value}</strong>
        <span class="inventory-alert-note">${card.note}</span>
      </div>
    `).join('')}</div>` : '';
    // Populate category filter
    const sel = document.getElementById('inv-cat-filter');
    if (sel.options.length <= 1) {
      const cats = await safeFetch('/api/inventory/categories', {}, []);
      if (!Array.isArray(cats)) throw new Error('invalid inventory categories payload');
      cats.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; sel.appendChild(o); });
    }
  } catch(e) {
    document.getElementById('inv-tbody').innerHTML = '<tr><td colspan="10" class="prep-table-empty prep-error-state">Failed to load inventory</td></tr>';
  }
}

const _invFields = {name:'inv-name', category:'inv-category', qty:'inv-qty', unit:'inv-unit', min:'inv-min', daily:'inv-daily', location:'inv-location', exp:'inv-exp', barcode:'inv-barcode', lot:'inv-lot', cost:'inv-cost', notes:'inv-notes'};
let _invRecoveryAttached = false;
function showInvForm(item) {
  document.getElementById('inv-form').style.display = 'block';
  if (item) {
    document.getElementById('inv-edit-id').value = item.id;
    document.getElementById('inv-name').value = item.name;
    document.getElementById('inv-category').value = item.category;
    document.getElementById('inv-qty').value = item.quantity;
    document.getElementById('inv-unit').value = item.unit;
    document.getElementById('inv-min').value = item.min_quantity;
    document.getElementById('inv-daily').value = item.daily_usage || 0;
    document.getElementById('inv-location').value = item.location;
    document.getElementById('inv-exp').value = item.expiration;
    document.getElementById('inv-barcode').value = item.barcode || '';
    document.getElementById('inv-lot').value = item.lot_number || '';
    document.getElementById('inv-cost').value = item.cost || 0;
    document.getElementById('inv-notes').value = item.notes;
  } else {
    document.getElementById('inv-edit-id').value = '';
    ['inv-name','inv-location','inv-notes','inv-barcode','inv-lot'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('inv-qty').value = 1;
    document.getElementById('inv-unit').value = 'ea';
    document.getElementById('inv-min').value = 0;
    document.getElementById('inv-daily').value = 0;
    document.getElementById('inv-cost').value = 0;
    document.getElementById('inv-exp').value = '';
    // Restore unsaved form state if not editing an existing item
    if (FormStateRecovery.restore('inventory', _invFields)) {
      toast('Recovered unsaved inventory data', 'info');
    }
  }
  if (!_invRecoveryAttached) { FormStateRecovery.attach('inventory', _invFields); _invRecoveryAttached = true; }
  // Populate category dropdown
  const sel = document.getElementById('inv-category');
  if (sel.options.length === 0) {
    safeFetch('/api/inventory/categories', {}, []).then(cats => {
      if (!Array.isArray(cats)) return;
      cats.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; sel.appendChild(o); });
      if (item) sel.value = item.category;
    }).catch(()=>{});
  }
}
function hideInvForm() {
  const form = document.getElementById('inv-form');
  form.style.display = 'none';
  // Clear all inputs for next entry
  form.querySelectorAll('input[type="text"],input[type="number"],input[type="date"]').forEach(i => { i.value = ''; });
  form.querySelectorAll('select').forEach(s => { s.selectedIndex = 0; });
  FormStateRecovery.clear('inventory');
}

async function saveInvItem() {
  const editId = document.getElementById('inv-edit-id').value;
  const data = {
    name: document.getElementById('inv-name').value.trim(),
    category: document.getElementById('inv-category').value,
    quantity: parseFloat(document.getElementById('inv-qty').value) || 0,
    unit: document.getElementById('inv-unit').value.trim() || 'ea',
    min_quantity: parseFloat(document.getElementById('inv-min').value) || 0,
    daily_usage: parseFloat(document.getElementById('inv-daily').value) || 0,
    location: document.getElementById('inv-location').value.trim(),
    expiration: document.getElementById('inv-exp').value,
    barcode: document.getElementById('inv-barcode').value.trim(),
    lot_number: document.getElementById('inv-lot').value,
    cost: parseFloat(document.getElementById('inv-cost').value) || 0,
    notes: document.getElementById('inv-notes').value.trim(),
  };
  if (!data.name) { toast('Name is required', 'warning'); return; }
  const btn = document.querySelector('#inv-form .btn-primary, #inv-form [onclick*="saveInvItem"]');
  if (btn) btn.classList.add('is-loading');
  try {
    if (editId) {
      await apiPut(`/api/inventory/${editId}`, data);
      toast('Item updated', 'success');
    } else {
      await apiPost('/api/inventory', data);
      toast('Item added', 'success');
    }
  } catch(e) { toast(e.message || 'Failed to save item', 'error'); return;
  } finally { if (btn) btn.classList.remove('is-loading'); }
  FormStateRecovery.clear('inventory');
  hideInvForm();
  loadInventory();
}

function editInvItem(id) {
  const item = _cachedInvItems.find(i => i.id === id);
  if (item) showInvForm(item);
}

async function deleteInvItem(id) {
  try {
    await apiDelete(`/api/inventory/${id}`);
    toast('Item deleted', 'warning');
    loadInventory();
  } catch(e) { toast(e?.data?.error || e?.message || 'Failed to delete item', 'error'); }
}

async function adjustQty(id, delta) {
  const item = _cachedInvItems.find(i => i.id === id);
  if (!item) return;
  const newQty = Math.max(0, item.quantity + delta);
  try {
    await apiPut(`/api/inventory/${id}`, {quantity: newQty});
    item.quantity = newQty;
    loadInventory();
  } catch(e) { console.error(e); toast(e?.data?.error || e?.message || 'Failed to update quantity', 'error'); }
}

async function dailyConsume() {
  const items = _cachedInvItems?.filter(i => i.daily_usage > 0 && i.quantity > 0) || [];
  if (!items.length) { toast('No items have daily usage set', 'info'); return; }
  try {
    const r = await safeFetch('/api/inventory/batch-consume', {method:'POST', headers:{'Content-Type':'application/json'}}, null);
    if (r.items?.length) {
      toast(`Consumed daily usage for ${r.items.length} items`, 'success');
      loadInventory();
    } else {
      toast('No items to consume', 'info');
    }
  } catch(e) { toast('Failed to consume', 'error'); }
}

/* ─── Receipt Scanner ─── */
let _receiptScanResults = [];

function openReceiptScanner() {
  const body = `
    <div id="receipt-scanner-body" class="scan-modal scan-modal-receipt">
      <div id="receipt-drop-zone" class="scan-drop-zone"
           role="button" tabindex="0" aria-label="Choose a receipt image"
           data-click-target="receipt-file-input"
           ondragover="event.preventDefault();this.style.borderColor='var(--accent)'"
           ondrageleave="this.style.borderColor='var(--border)'"
           ondrop="event.preventDefault();this.style.borderColor='var(--border)';handleReceiptDrop(event)">
        <div class="scan-drop-icon">&#128424;</div>
        <div class="scan-drop-title">Drop a receipt image here or click to browse</div>
        <div class="scan-drop-note">Supports JPG, PNG, WEBP — also works with camera capture</div>
        <input type="file" id="receipt-file-input" accept="image/*" capture="environment" class="is-hidden" data-change-action="handle-receipt-file-select">
      </div>
      <div id="receipt-preview-wrap" class="scan-preview-wrap is-hidden">
        <img id="receipt-preview-img" class="scan-preview-image scan-preview-image-sm" alt="Receipt preview">
        <div class="scan-preview-actions">
          <button type="button" class="btn btn-sm btn-primary" id="receipt-scan-btn" data-prep-action="scan-receipt">Scan Receipt</button>
          <button type="button" class="btn btn-sm" data-prep-action="clear-receipt-preview">Clear</button>
        </div>
      </div>
      <div id="receipt-status" class="scan-status is-hidden"></div>
      <div id="receipt-results" class="scan-results is-hidden">
        <div class="scan-results-header">
          <span id="receipt-results-count" class="scan-results-count"></span>
          <span id="receipt-source-badge" class="scan-badge"></span>
        </div>
        <div class="scan-table-wrap">
          <table class="freq-table scan-results-table">
            <thead><tr><th class="scan-check-col"><input type="checkbox" id="receipt-check-all" data-change-action="toggle-receipt-items" checked aria-label="Select all scanned receipt items"></th><th>Item Name</th><th>Qty</th><th>Unit Price</th><th>Total</th></tr></thead>
            <tbody id="receipt-items-tbody"></tbody>
          </table>
        </div>
        <div class="scan-results-actions">
          <button type="button" class="btn btn-sm btn-primary" data-prep-action="import-receipt-items">Import Selected</button>
          <button type="button" class="btn btn-sm" data-shell-action="close-modal-overlay">Cancel</button>
        </div>
      </div>
    </div>
  `;
  showModal(body, {title: 'Receipt Scanner', size: 'lg'});
}

let _receiptFile = null;

function handleReceiptDrop(e) {
  const files = e.dataTransfer.files;
  if (files.length > 0 && files[0].type.startsWith('image/')) {
    loadReceiptPreview(files[0]);
  }
}

function handleReceiptFileSelect(input) {
  if (input.files.length > 0) {
    loadReceiptPreview(input.files[0]);
  }
}

function loadReceiptPreview(file) {
  if (file && !file.type.startsWith('image/')) return;
  _receiptFile = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    const previewImg = document.getElementById('receipt-preview-img');
    previewImg.src = e.target.result;
    previewImg.alt = file?.name ? `Receipt preview for ${file.name}` : 'Receipt preview';
    document.getElementById('receipt-preview-wrap').style.display = 'block';
    document.getElementById('receipt-drop-zone').style.display = 'none';
    document.getElementById('receipt-results').style.display = 'none';
    document.getElementById('receipt-status').style.display = 'none';
  };
  reader.readAsDataURL(file);
}

function clearReceiptPreview() {
  _receiptFile = null;
  _receiptScanResults = [];
  document.getElementById('receipt-preview-wrap').style.display = 'none';
  document.getElementById('receipt-drop-zone').style.display = 'block';
  document.getElementById('receipt-results').style.display = 'none';
  document.getElementById('receipt-status').style.display = 'none';
  document.getElementById('receipt-file-input').value = '';
}

async function scanReceipt() {
  if (!_receiptFile) { toast('No image selected', 'warning'); return; }

  const statusEl = document.getElementById('receipt-status');
  const scanBtn = document.getElementById('receipt-scan-btn');
  const resultsEl = document.getElementById('receipt-results');

  statusEl.style.display = 'block';
  statusEl.innerHTML = '<div class="scan-status-title">&#9203; Scanning receipt...</div><div class="scan-status-note">This may take a moment if using AI vision</div>';
  scanBtn.disabled = true;
  scanBtn.textContent = 'Scanning...';
  resultsEl.style.display = 'none';

  try {
    const formData = new FormData();
    formData.append('image', _receiptFile);
    const data = await apiUpload('/api/inventory/receipt-scan', formData);
    _receiptScanResults = Array.isArray(data?.items) ? data.items : [];
    if (_receiptScanResults.length === 0) {
      statusEl.innerHTML = '<div class="scan-status-warning">&#9888; No items found on this receipt. Try a clearer image or different angle.</div>';
      return;
    }

    // Show results
    statusEl.style.display = 'none';
    document.getElementById('receipt-results-count').textContent = `Found ${_receiptScanResults.length} item(s)`;
    document.getElementById('receipt-source-badge').textContent = data?.source === 'ollama' ? 'AI Vision' : 'Tesseract OCR';

    const tbody = document.getElementById('receipt-items-tbody');
    tbody.innerHTML = _receiptScanResults.map((item, i) => `
      <tr>
        <td><input type="checkbox" class="receipt-item-check" data-idx="${i}" checked aria-label="Select receipt item ${i + 1}"></td>
        <td><input type="text" value="${escapeAttr(item.name)}" class="receipt-edit-name scan-table-input scan-table-input-name" data-idx="${i}" aria-label="Receipt item name ${i + 1}"></td>
        <td><input type="number" value="${item.quantity}" min="0" step="1" class="receipt-edit-qty scan-table-input scan-table-input-qty" data-idx="${i}" aria-label="Receipt quantity ${i + 1}"></td>
        <td class="scan-cell-right">$${item.unit_price.toFixed(2)}</td>
        <td class="scan-cell-right scan-cell-strong">$${item.total_price.toFixed(2)}</td>
      </tr>
    `).join('');

    resultsEl.style.display = 'block';
  } catch(e) {
    statusEl.innerHTML = `<div class="scan-status-error">&#9888; ${escapeHtml(e?.data?.error || e.message || 'Network error')}</div>`;
  } finally {
    scanBtn.disabled = false;
    scanBtn.textContent = 'Scan Receipt';
  }
}

function toggleAllReceiptItems(checked) {
  document.querySelectorAll('.receipt-item-check').forEach(cb => cb.checked = checked);
}

async function importReceiptItems() {
  const checks = document.querySelectorAll('.receipt-item-check:checked');
  if (!checks.length) { toast('No items selected', 'warning'); return; }

  const items = [];
  checks.forEach(cb => {
    const idx = parseInt(cb.dataset.idx);
    const row = cb.closest('tr');
    const nameInput = row.querySelector('.receipt-edit-name');
    const qtyInput = row.querySelector('.receipt-edit-qty');
    const orig = _receiptScanResults[idx];
    items.push({
      name: nameInput ? nameInput.value.trim() : orig.name,
      quantity: qtyInput ? parseFloat(qtyInput.value) || 1 : orig.quantity,
      unit_price: orig.unit_price,
      total_price: orig.total_price,
    });
  });

  try {
    const data = await apiPost('/api/inventory/receipt-import', {items});

    toast(`Imported ${data.count} item(s) from receipt`, 'success');
    // Close the modal
    const overlay = document.querySelector('.modal-overlay');
    if (overlay) overlay.remove();
    // Refresh inventory
    loadInventory();
  } catch(e) {
    toast(`Import failed: ${e.message}`, 'error');
  }
}

/* ─── AI Vision Inventory Scanner ─── */
let _visionScanResults = [];
let _visionFile = null;

const VISION_CATEGORIES = ['Food','Water','Medical','Ammunition','Fuel','Equipment','Batteries','Hygiene','Clothing','Tools','Communication','Documents','Seeds','General'];
const VISION_CONDITIONS = ['New','Good','Fair','Poor'];

function openVisionScanner() {
  const catOpts = VISION_CATEGORIES.map(c => `<option value="${c}">${c}</option>`).join('');
  const condOpts = VISION_CONDITIONS.map(c => `<option value="${c}">${c}</option>`).join('');
  const body = `
    <div id="vision-scanner-body" class="scan-modal scan-modal-vision">
      <div id="vision-drop-zone" class="scan-drop-zone"
           role="button" tabindex="0" aria-label="Choose a supply image"
           data-click-target="vision-file-input"
           ondragover="event.preventDefault();this.style.borderColor='var(--accent)'"
           ondrageleave="this.style.borderColor='var(--border)'"
           ondrop="event.preventDefault();this.style.borderColor='var(--border)';handleVisionDrop(event)">
        <div class="scan-drop-icon">&#128247;</div>
        <div class="scan-drop-title">Drop a photo of your supplies here or click to browse</div>
        <div class="scan-drop-note">Supports JPG, PNG, WEBP — use camera to capture directly</div>
        <input type="file" id="vision-file-input" accept="image/*" capture="environment" class="is-hidden" data-change-action="handle-vision-file-select">
      </div>
      <div id="vision-preview-wrap" class="scan-preview-wrap is-hidden">
        <img id="vision-preview-img" class="scan-preview-image scan-preview-image-lg" alt="Supply image preview">
        <div class="scan-preview-actions">
          <button type="button" class="btn btn-sm btn-primary" id="vision-scan-btn" data-prep-action="scan-vision-image">&#128270; Analyze</button>
          <button type="button" class="btn btn-sm" data-prep-action="clear-vision-preview">Clear</button>
        </div>
      </div>
      <div id="vision-status" class="scan-status is-hidden"></div>
      <div id="vision-results" class="scan-results is-hidden">
        <div class="scan-results-header">
          <span id="vision-results-count" class="scan-results-count"></span>
          <span id="vision-model-badge" class="scan-badge"></span>
        </div>
        <div id="vision-items-grid" class="scan-item-grid"></div>
        <div class="scan-results-actions">
          <button type="button" class="btn btn-sm btn-primary" data-prep-action="import-vision-items">Import Selected</button>
          <button type="button" class="btn btn-sm" data-shell-action="close-modal-overlay">Cancel</button>
        </div>
      </div>
    </div>
  `;
  showModal(body, {title: 'AI Vision Scanner', size: 'lg'});
}

function handleVisionDrop(e) {
  const files = e.dataTransfer.files;
  if (files.length > 0 && files[0].type.startsWith('image/')) {
    loadVisionPreview(files[0]);
  }
}

function handleVisionFileSelect(input) {
  if (input.files.length > 0) {
    loadVisionPreview(input.files[0]);
  }
}

function loadVisionPreview(file) {
  if (file && !file.type.startsWith('image/')) return;
  _visionFile = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    const previewImg = document.getElementById('vision-preview-img');
    previewImg.src = e.target.result;
    previewImg.alt = file?.name ? `Supply image preview for ${file.name}` : 'Supply image preview';
    document.getElementById('vision-preview-wrap').style.display = 'block';
    document.getElementById('vision-drop-zone').style.display = 'none';
    document.getElementById('vision-results').style.display = 'none';
    document.getElementById('vision-status').style.display = 'none';
  };
  reader.readAsDataURL(file);
}

function clearVisionPreview() {
  _visionFile = null;
  _visionScanResults = [];
  document.getElementById('vision-preview-wrap').style.display = 'none';
  document.getElementById('vision-drop-zone').style.display = 'block';
  document.getElementById('vision-results').style.display = 'none';
  document.getElementById('vision-status').style.display = 'none';
  document.getElementById('vision-file-input').value = '';
}

function _resizeImageForVision(file) {
  return new Promise((resolve) => {
    const MAX_DIM = 1024;
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);
    const cleanup = () => {
      img.onload = null;
      img.onerror = null;
      img.removeAttribute('src');
      window.revokeObjectUrlSafe?.(objectUrl);
    };
    img.onload = () => {
      let w = img.width, h = img.height;
      if (!w || !h || (w <= MAX_DIM && h <= MAX_DIM)) {
        cleanup();
        resolve(file);
        return;
      }
      const scale = MAX_DIM / Math.max(w, h);
      w = Math.round(w * scale);
      h = Math.round(h * scale);
      const canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      const ctx = canvas.getContext('2d');
      if (!ctx || typeof canvas.toBlob !== 'function') {
        cleanup();
        resolve(file);
        return;
      }
      ctx.drawImage(img, 0, 0, w, h);
      canvas.toBlob((blob) => {
        cleanup();
        if (!(blob instanceof Blob)) {
          resolve(file);
          return;
        }
        try {
          resolve(new File([blob], file.name, {type: blob.type || file.type || 'image/jpeg'}));
        } catch (_) {
          resolve(file);
        }
      }, file.type || 'image/jpeg', 0.85);
    };
    img.onerror = () => {
      cleanup();
      resolve(file);
    };
    img.src = objectUrl;
  });
}

async function scanVisionImage() {
  if (!_visionFile) { toast('No image selected', 'warning'); return; }

  const statusEl = document.getElementById('vision-status');
  const scanBtn = document.getElementById('vision-scan-btn');
  const resultsEl = document.getElementById('vision-results');

  statusEl.style.display = 'block';
  statusEl.innerHTML = '<div class="scan-status-title">&#9203; Analyzing image with AI...</div><div class="scan-status-note">This may take 30\u201360 seconds depending on model and image complexity</div>';
  scanBtn.disabled = true;
  scanBtn.textContent = 'Analyzing...';
  resultsEl.style.display = 'none';

  try {
    const resized = await _resizeImageForVision(_visionFile);
    const formData = new FormData();
    formData.append('image', resized);
    const data = await apiUpload('/api/inventory/vision-scan', formData);
    _visionScanResults = Array.isArray(data?.items) ? data.items : [];
    if (_visionScanResults.length === 0) {
      statusEl.innerHTML = '<div class="scan-status-warning">&#9888; No items identified. Try a clearer image with items more visible.</div>';
      return;
    }

    // Show results
    statusEl.style.display = 'none';
    document.getElementById('vision-results-count').textContent = `Found ${_visionScanResults.length} item(s)`;
    document.getElementById('vision-model-badge').textContent = `Model: ${data?.model_used || 'unknown'} | ${data?.image_size || ''}`;

    const catOpts = VISION_CATEGORIES.map(c => `<option value="${c}">${c}</option>`).join('');
    const condOpts = VISION_CONDITIONS.map(c => `<option value="${c}">${c}</option>`).join('');

    const grid = document.getElementById('vision-items-grid');
    grid.innerHTML = _visionScanResults.map((item, i) => `
      <div class="vision-item-card" data-idx="${i}">
        <div class="vision-item-head">
          <input type="checkbox" class="vision-item-check" data-idx="${i}" checked aria-label="Select detected inventory item ${i + 1}">
          <input type="text" value="${escapeAttr(item.name)}" class="vision-edit-name vision-field-control vision-field-name" data-idx="${i}" aria-label="Detected item name ${i + 1}">
        </div>
        <div class="vision-item-grid">
          <div class="vision-field">
            <label class="vision-field-label">Quantity</label>
            <input type="number" value="${item.quantity}" min="1" step="1" class="vision-edit-qty vision-field-control" data-idx="${i}" aria-label="Detected item quantity ${i + 1}">
          </div>
          <div class="vision-field">
            <label class="vision-field-label">Category</label>
            <select class="vision-edit-cat vision-field-control" data-idx="${i}" aria-label="Detected item category ${i + 1}">
              ${catOpts.replace(`value="${escapeAttr(item.category)}"`, `value="${escapeAttr(item.category)}" selected`)}
            </select>
          </div>
        </div>
        <div class="vision-field">
          <label class="vision-field-label">Condition</label>
          <select class="vision-edit-cond vision-field-control" data-idx="${i}" aria-label="Detected item condition ${i + 1}">
            ${condOpts.replace(`value="${escapeAttr(item.condition)}"`, `value="${escapeAttr(item.condition)}" selected`)}
          </select>
        </div>
        ${item.notes ? `<div class="vision-item-note">${escapeHtml(item.notes)}</div>` : ''}
      </div>
    `).join('');

    resultsEl.style.display = 'block';
  } catch(e) {
    statusEl.innerHTML = `<div class="scan-status-error">&#9888; ${escapeHtml(e?.data?.error || e.message || 'Network error')}</div>`;
  } finally {
    scanBtn.disabled = false;
    scanBtn.innerHTML = '&#128270; Analyze';
  }
}

async function importVisionItems() {
  const checks = document.querySelectorAll('.vision-item-check:checked');
  if (!checks.length) { toast('No items selected', 'warning'); return; }

  const items = [];
  checks.forEach(cb => {
    const idx = parseInt(cb.dataset.idx);
    const card = cb.closest('.vision-item-card');
    const nameInput = card.querySelector('.vision-edit-name');
    const qtyInput = card.querySelector('.vision-edit-qty');
    const catSelect = card.querySelector('.vision-edit-cat');
    const condSelect = card.querySelector('.vision-edit-cond');
    const orig = _visionScanResults[idx];
    items.push({
      name: nameInput ? nameInput.value.trim() : orig.name,
      quantity: qtyInput ? parseInt(qtyInput.value) || 1 : orig.quantity,
      category: catSelect ? catSelect.value : orig.category,
      condition: condSelect ? condSelect.value : orig.condition,
      notes: orig.notes || '',
    });
  });

  try {
    const data = await apiPost('/api/inventory/vision-import', {items});

    toast(`Imported ${data.count} item(s) from AI vision scan`, 'success');
    const overlay = document.querySelector('.modal-overlay');
    if (overlay) overlay.remove();
    loadInventory();
  } catch(e) {
    toast(`Import failed: ${e.message}`, 'error');
  }
}

/* ─── Barcode / UPC Scanner ─── */
let _barcodeDetector = null;
let _inventoryBarcodeStream = null;
let _recentScans = [];
let _barcodeScanLoop = null;

function openBarcodeScanner() {
  const hasBarcodeAPI = 'BarcodeDetector' in window;
  const cameraSection = hasBarcodeAPI ? `
    <div id="barcode-camera-wrap" class="scan-camera-wrap">
      <video id="barcode-video" autoplay playsinline muted class="scan-camera-video"></video>
      <div id="barcode-camera-status" class="scan-camera-status">Starting camera...</div>
      <div class="scan-camera-actions">
        <button type="button" class="btn btn-sm" data-prep-action="stop-barcode-camera" id="barcode-stop-cam-btn">Stop Camera</button>
        <button type="button" class="btn btn-sm is-hidden" data-prep-action="start-barcode-camera" id="barcode-start-cam-btn">Start Camera</button>
      </div>
    </div>` : `
    <div class="scan-status-card">
      Camera barcode scanning requires Chrome 83+ or Edge 83+ with BarcodeDetector API.<br>Use manual entry below.
    </div>`;

  const body = `
    <div id="barcode-scanner-body" class="scan-modal scan-modal-barcode">
      ${cameraSection}
      <div class="scan-input-row">
        <input type="text" id="barcode-manual-input" inputmode="numeric" pattern="[0-9]*"
               placeholder="Enter UPC (8, 12, or 13 digits)…"
               class="scan-manual-input"
               data-enter-action="lookup-barcode">
        <button class="btn btn-sm btn-primary" type="button" data-shell-action="lookup-barcode">Look Up</button>
      </div>
      <div id="barcode-result" class="scan-result-shell is-hidden">
      </div>
      <div id="barcode-add-db-form" class="scan-form-shell is-hidden">
        <div class="scan-form-title">Add to UPC Database</div>
        <div class="scan-form-grid">
          <input type="text" id="barcode-new-name" placeholder="Item Name *" class="scan-form-control scan-form-control-span">
          <select id="barcode-new-category" class="scan-form-control">
            <option value="Food">Food</option><option value="Water">Water</option><option value="Medical">Medical</option>
            <option value="Batteries/Power">Batteries/Power</option><option value="Gear">Gear</option>
            <option value="Hygiene">Hygiene</option><option value="General">General</option>
          </select>
          <input type="text" id="barcode-new-brand" placeholder="Brand" class="scan-form-control">
          <input type="text" id="barcode-new-size" placeholder="Size (e.g. 15 oz)" class="scan-form-control">
          <select id="barcode-new-unit" class="scan-form-control">
            <option value="each">each</option><option value="can">can</option><option value="bottle">bottle</option>
            <option value="box">box</option><option value="bag">bag</option><option value="pack">pack</option>
            <option value="roll">roll</option><option value="jar">jar</option><option value="tube">tube</option>
          </select>
          <input type="number" id="barcode-new-shelf-life" placeholder="Shelf life (days)" min="0" class="scan-form-control">
        </div>
        <div class="scan-results-actions">
          <button type="button" class="btn btn-sm btn-primary" data-prep-action="add-upc-database">Save to Database &amp; Add to Inventory</button>
          <button type="button" class="btn btn-sm" data-prep-action="hide-barcode-db-form">Cancel</button>
        </div>
      </div>
      <div id="barcode-recent" class="scan-recent-shell${_recentScans.length ? '' : ' is-hidden'}">
        <div class="scan-recent-title">Recent Scans</div>
        <div id="barcode-recent-list" class="scan-recent-list">
          ${_recentScans.map(s => '<div class="scan-recent-item"><span>' + escapeHtml(s.name) + '</span><span class="scan-recent-code">' + escapeHtml(s.upc) + '</span></div>').join('')}
        </div>
      </div>
    </div>
  `;
  const overlay = showModal(body, {title: 'Barcode Scanner', size: 'lg', onClose: function() { stopBarcodeCamera(); }});
  if (hasBarcodeAPI) {
    startBarcodeCamera();
  }
}

async function startBarcodeCamera() {
  try {
    _inventoryBarcodeStream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment', width: {ideal: 1280}, height: {ideal: 720}}});
    const video = document.getElementById('barcode-video');
    if (!video) { stopBarcodeCamera(); return; }
    video.srcObject = _inventoryBarcodeStream;
    const statusEl = document.getElementById('barcode-camera-status');
    if (statusEl) statusEl.textContent = 'Scanning... point camera at barcode';
    const stopBtn = document.getElementById('barcode-stop-cam-btn');
    const startBtn = document.getElementById('barcode-start-cam-btn');
    if (stopBtn) stopBtn.style.display = '';
    if (startBtn) startBtn.style.display = 'none';

    _barcodeDetector = new BarcodeDetector({formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128']});

    function scanFrame() {
      if (!_inventoryBarcodeStream) return;
      if (_barcodeScanLoop) cancelAnimationFrame(_barcodeScanLoop);
      _barcodeDetector.detect(video).then(function(barcodes) {
        if (barcodes.length > 0) {
          var raw = barcodes[0].rawValue.replace(/[^0-9]/g, '');
          if (raw && (raw.length === 8 || raw.length === 12 || raw.length === 13)) {
            var input = document.getElementById('barcode-manual-input');
            if (input) input.value = raw;
            if (statusEl) statusEl.textContent = 'Detected: ' + raw;
            lookupBarcode(raw);
            setTimeout(function() { _barcodeScanLoop = requestAnimationFrame(scanFrame); }, 2000);
            return;
          }
        }
        _barcodeScanLoop = requestAnimationFrame(scanFrame);
      }).catch(function() {
        _barcodeScanLoop = requestAnimationFrame(scanFrame);
      });
    }
    _barcodeScanLoop = requestAnimationFrame(scanFrame);
  } catch(e) {
    var statusEl = document.getElementById('barcode-camera-status');
    if (statusEl) statusEl.textContent = 'Camera access denied or unavailable';
    console.warn('Barcode camera error:', e);
  }
}

function stopBarcodeCamera() {
  if (_barcodeScanLoop) { cancelAnimationFrame(_barcodeScanLoop); _barcodeScanLoop = null; }
  if (_inventoryBarcodeStream) {
    _inventoryBarcodeStream.getTracks().forEach(function(t) { t.stop(); });
    _inventoryBarcodeStream = null;
  }
  _barcodeDetector = null;
  var video = document.getElementById('barcode-video');
  if (video) video.srcObject = null;
  var statusEl = document.getElementById('barcode-camera-status');
  if (statusEl) statusEl.textContent = 'Camera stopped';
  var stopBtn = document.getElementById('barcode-stop-cam-btn');
  var startBtn = document.getElementById('barcode-start-cam-btn');
  if (stopBtn) stopBtn.style.display = 'none';
  if (startBtn) startBtn.style.display = '';
}

async function lookupBarcode(upc) {
  if (!upc) {
    var input = document.getElementById('barcode-manual-input');
    upc = input ? input.value.trim().replace(/[^0-9]/g, '') : '';
  }
  if (!upc || (upc.length !== 8 && upc.length !== 12 && upc.length !== 13)) {
    toast('Enter a valid UPC (8, 12, or 13 digits)', 'warning');
    return;
  }
  var resultEl = document.getElementById('barcode-result');
  var addDbForm = document.getElementById('barcode-add-db-form');
  resultEl.style.display = 'block';
  resultEl.innerHTML = '<div class="scan-status-title">Looking up...</div>';
  addDbForm.style.display = 'none';

  var data = await safeFetch('/api/barcode/lookup/' + upc, {}, null);
  if (!data) {
    resultEl.innerHTML = '<div class="scan-status-error">Failed to look up barcode</div>';
    return;
  }
  if (data.found) {
    var shelfStr = data.default_shelf_life_days ? Math.round(data.default_shelf_life_days / 365) + ' yr' : 'N/A';
    resultEl.innerHTML = '<div class="scan-result-title">' + escapeHtml(data.name) + '</div>'
      + '<div class="scan-detail-grid">'
      + '<span>Category: <b>' + escapeHtml(data.category) + '</b></span>'
      + '<span>Brand: <b>' + escapeHtml(data.brand || 'N/A') + '</b></span>'
      + '<span>Size: <b>' + escapeHtml(data.size || 'N/A') + '</b></span>'
      + '<span>Unit: <b>' + escapeHtml(data.unit) + '</b></span>'
      + '<span>Shelf Life: <b>' + shelfStr + '</b></span>'
      + '</div>'
      + '<div class="scan-input-row scan-input-row-inline">'
      + '<label class="scan-inline-label">Qty:</label>'
      + '<input type="number" id="barcode-add-qty" value="1" min="1" step="1" class="scan-qty-input">'
      + '<button type="button" class="btn btn-sm btn-primary" data-prep-action="add-barcode-to-inventory" data-upc="' + escapeAttr(upc) + '">Add to Inventory</button>'
      + '</div>';
  } else {
    resultEl.innerHTML = '<div class="scan-status-warning">UPC <span class="scan-inline-code">' + escapeHtml(upc) + '</span> not in database</div>'
      + '<button type="button" class="btn btn-sm" data-prep-action="show-barcode-db-form">Add to Database</button>';
    addDbForm.dataset.upc = upc;
  }
}

async function addBarcodeToInventory(upc, qty) {
  if (!qty) {
    var qtyInput = document.getElementById('barcode-add-qty');
    qty = qtyInput ? parseInt(qtyInput.value) || 1 : 1;
  }
  try {
    var data = await apiPost('/api/barcode/scan-to-inventory', {upc: upc, quantity: qty});
    _recentScans.unshift({name: data.item.name, upc: upc, qty: qty});
    if (_recentScans.length > 10) _recentScans.pop();
    _updateRecentScans();

    if (data.item) {
      toast('Added ' + data.item.name + ' x' + qty + ' to inventory', 'success');
    } else {
      toast('Item added to inventory', 'success');
    }
    loadInventory();

    var resultEl = document.getElementById('barcode-result');
    if (resultEl) resultEl.innerHTML = '<div class="scan-status-success">Added! Scan next item...</div>';
    var input = document.getElementById('barcode-manual-input');
    if (input) { input.value = ''; input.focus(); }
  } catch(e) {
    toast('Failed to add item: ' + (e?.data?.error || e.message), 'error');
  }
}

async function addToUpcDatabase() {
  var formEl = document.getElementById('barcode-add-db-form');
  var upc = formEl.dataset.upc;
  var name = document.getElementById('barcode-new-name').value.trim();
  if (!name) { toast('Item name is required', 'warning'); return; }

  var payload = {
    upc: upc,
    name: name,
    category: document.getElementById('barcode-new-category').value,
    brand: document.getElementById('barcode-new-brand').value.trim(),
    size: document.getElementById('barcode-new-size').value.trim(),
    unit: document.getElementById('barcode-new-unit').value,
    default_shelf_life_days: parseInt(document.getElementById('barcode-new-shelf-life').value) || 0,
  };

  try {
    await apiPost('/api/barcode/add', payload);
    toast('Saved ' + name + ' to UPC database', 'success');
    formEl.style.display = 'none';
    await addBarcodeToInventory(upc, 1);
  } catch(e) {
    toast('Failed to save: ' + (e?.data?.error || e.message), 'error');
  }
}

function _updateRecentScans() {
  var wrap = document.getElementById('barcode-recent');
  var list = document.getElementById('barcode-recent-list');
  if (!wrap || !list) return;
  wrap.style.display = _recentScans.length ? 'block' : 'none';
  list.innerHTML = _recentScans.map(function(s) {
    return '<div class="scan-recent-item"><span>' + escapeHtml(s.name) + '</span><span class="scan-recent-code">' + escapeHtml(s.upc) + '</span></div>';
  }).join('');
}

/* ─── Inline Quantity Edit (P1-08) ─── */
document.addEventListener('dblclick', function(e) {
  const span = e.target.closest('.inventory-qty-value[data-inv-id]');
  if (!span || span.querySelector('input')) return;
  const id = span.dataset.invId;
  const currentQty = span.dataset.invQty || '0';
  const origText = span.textContent;
  const input = document.createElement('input');
  input.type = 'number';
  input.value = currentQty;
  input.style.cssText = 'width:60px;text-align:center;font-size:inherit;padding:2px 4px';
  input.min = '0';
  span.textContent = '';
  span.appendChild(input);
  input.focus();
  input.select();

  function commit() {
    const newQty = parseInt(input.value, 10);
    if (isNaN(newQty) || newQty < 0) { span.textContent = origText; return; }
    if (String(newQty) === currentQty) { span.textContent = origText; return; }
    apiPut('/api/inventory/' + id, { quantity: newQty })
      .then(function() { loadInventory(); })
      .catch(function() { span.textContent = origText; toast('Failed to update quantity', 'error'); });
  }
  input.addEventListener('blur', commit);
  input.addEventListener('keydown', function(ev) {
    if (ev.key === 'Enter') { ev.preventDefault(); input.blur(); }
    if (ev.key === 'Escape') { span.textContent = origText; }
  });
});
