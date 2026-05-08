/**
 * LedgerLense — Frontend Application
 * Handles PDF upload, transaction grid display, inline editing, and corrections.
 */

const API_BASE = '/api/v1';

// ─── State ───────────────────────────────────────────────────────────────────

const state = {
    documentId: null,
    transactions: [],
    originalTransactions: [],
    deletedRows: new Set(),
    modifiedCells: new Map(), // "rowIdx:field" → true
    selectedRow: null,
};

// ─── DOM References ──────────────────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const els = {
    uploadZone: $('#upload-zone'),
    fileInput: $('#file-input'),
    passwordSection: $('#password-section'),
    passwordInput: $('#password-input'),
    progressBar: $('#progress-bar'),
    progressFill: $('#progress-fill'),
    progressText: $('#progress-text'),
    docInfo: $('#doc-info'),
    toolbar: $('#toolbar'),
    gridContainer: $('#grid-container'),
    txnTableBody: $('#txn-table-body'),
    btnConfirm: $('#btn-confirm'),
    btnAddRow: $('#btn-add-row'),
    btnReset: $('#btn-reset'),
    txnCount: $('#txn-count'),
    toastContainer: $('#toast-container'),
    passwordToggle: $('#password-toggle'),
};

// ─── Upload ──────────────────────────────────────────────────────────────────

function initUpload() {
    const zone = els.uploadZone;
    const input = els.fileInput;

    zone.addEventListener('click', () => input.click());

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].name.toLowerCase().endsWith('.pdf')) {
            handleFile(files[0]);
        } else {
            showToast('Please drop a PDF file', 'error');
        }
    });

    input.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // Password toggle
    if (els.passwordToggle) {
        els.passwordToggle.addEventListener('click', () => {
            els.passwordSection.classList.toggle('visible');
        });
    }
}

async function handleFile(file) {
    showProgress('Uploading & extracting...');

    const formData = new FormData();
    formData.append('file', file);

    const password = els.passwordInput?.value?.trim();
    if (password) {
        formData.append('password', password);
    }

    try {
        updateProgress(30, 'Uploading PDF...');

        const response = await fetch(`${API_BASE}/documents/extract`, {
            method: 'POST',
            body: formData,
        });

        updateProgress(70, 'Processing response...');

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Upload failed');
        }

        const data = await response.json();
        updateProgress(100, 'Complete!');

        state.documentId = data.document_id;
        state.transactions = data.transactions || [];
        state.originalTransactions = JSON.parse(JSON.stringify(state.transactions));
        state.deletedRows.clear();
        state.modifiedCells.clear();

        setTimeout(() => {
            hideProgress();
            showDocInfo(data);
            renderGrid();
            showToast(`Extracted ${data.transaction_count} transactions`, 'success');
        }, 500);

    } catch (err) {
        hideProgress();
        showToast(err.message, 'error');
    }
}

// ─── Progress ────────────────────────────────────────────────────────────────

function showProgress(text) {
    els.progressBar.classList.add('visible');
    els.progressText.textContent = text || '';
    els.progressFill.style.width = '10%';
}

function updateProgress(percent, text) {
    els.progressFill.style.width = `${percent}%`;
    if (text) els.progressText.textContent = text;
}

function hideProgress() {
    els.progressBar.classList.remove('visible');
}

// ─── Document Info ───────────────────────────────────────────────────────────

function showDocInfo(data) {
    els.docInfo.classList.add('visible');
    $('#info-filename').textContent = data.filename || '-';
    $('#info-bank').textContent = data.bank_detected || 'Unknown';
    $('#info-pages').textContent = data.total_pages || '-';
    $('#info-status').textContent = data.status || '-';
    $('#info-txn-count').textContent = data.transaction_count || 0;
}

// ─── Transaction Grid ───────────────────────────────────────────────────────

function renderGrid() {
    els.toolbar.classList.add('visible');
    els.gridContainer.classList.add('visible');
    els.txnTableBody.innerHTML = '';

    state.transactions.forEach((txn, idx) => {
        const row = createTransactionRow(txn, idx);
        els.txnTableBody.appendChild(row);
    });

    updateTxnCount();
}

function createTransactionRow(txn, idx) {
    const tr = document.createElement('tr');
    tr.dataset.index = idx;

    if (state.deletedRows.has(idx)) {
        tr.classList.add('deleted');
    }

    const confidenceAvg = txn.confidence
        ? (txn.confidence.date + txn.confidence.description + txn.confidence.amount + txn.confidence.balance) / 4
        : 0;

    const confClass = confidenceAvg >= 0.7 ? 'high' : confidenceAvg >= 0.4 ? 'medium' : 'low';

    tr.innerHTML = `
        <td style="width:40px; text-align:center">
            <span class="confidence-dot confidence-${confClass}" title="Confidence: ${(confidenceAvg * 100).toFixed(0)}%"></span>
            ${txn.sequence}
        </td>
        <td class="editable">${editableCell(idx, 'txn_date', txn.txn_date || '')}</td>
        <td class="editable">${editableCell(idx, 'value_date', txn.value_date || '')}</td>
        <td class="editable" style="min-width:200px">${editableCell(idx, 'description', txn.description || '')}</td>
        <td class="editable">${editableCell(idx, 'reference_no', txn.reference_no || '')}</td>
        <td class="editable cell-debit">${editableCell(idx, 'debit', formatAmount(txn.debit))}</td>
        <td class="editable cell-credit">${editableCell(idx, 'credit', formatAmount(txn.credit))}</td>
        <td class="editable cell-balance">${editableCell(idx, 'balance', formatAmount(txn.balance))}</td>
        <td>
            <div class="row-actions">
                <button class="row-action-btn delete" onclick="deleteRow(${idx})" title="Delete row">✕</button>
            </div>
        </td>
    `;

    // Click to select
    tr.addEventListener('click', (e) => {
        if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'BUTTON') {
            selectRow(idx);
        }
    });

    return tr;
}

function editableCell(rowIdx, field, value) {
    const key = `${rowIdx}:${field}`;
    const modified = state.modifiedCells.has(key) ? ' modified' : '';
    return `<input class="cell-input${modified}" data-row="${rowIdx}" data-field="${field}" 
            value="${escapeHtml(value)}" oninput="onCellEdit(this)" 
            onkeydown="onCellKeydown(event, this)" />`;
}

function onCellEdit(input) {
    const rowIdx = parseInt(input.dataset.row);
    const field = input.dataset.field;
    const key = `${rowIdx}:${field}`;

    const original = state.originalTransactions[rowIdx];
    const originalValue = original ? String(original[field] || '') : '';

    if (input.value !== originalValue) {
        state.modifiedCells.set(key, true);
        input.classList.add('modified');
    } else {
        state.modifiedCells.delete(key);
        input.classList.remove('modified');
    }

    // Update state
    state.transactions[rowIdx][field] = input.value;
}

function onCellKeydown(event, input) {
    const rowIdx = parseInt(input.dataset.row);

    if (event.key === 'Tab' || event.key === 'Enter') {
        // Navigate to next cell/row
        event.preventDefault();
        const allInputs = Array.from($$('.cell-input'));
        const currentIdx = allInputs.indexOf(input);
        const nextIdx = event.shiftKey ? currentIdx - 1 : currentIdx + 1;
        if (nextIdx >= 0 && nextIdx < allInputs.length) {
            allInputs[nextIdx].focus();
            allInputs[nextIdx].select();
        }
    }

    if (event.key === 'ArrowDown') {
        // Move to same field in next row
        const nextRow = rowIdx + 1;
        const nextInput = $(`input[data-row="${nextRow}"][data-field="${input.dataset.field}"]`);
        if (nextInput) {
            nextInput.focus();
            nextInput.select();
        }
    }

    if (event.key === 'ArrowUp') {
        const prevRow = rowIdx - 1;
        const prevInput = $(`input[data-row="${prevRow}"][data-field="${input.dataset.field}"]`);
        if (prevInput) {
            prevInput.focus();
            prevInput.select();
        }
    }
}

function selectRow(idx) {
    $$('.txn-table tbody tr').forEach(r => r.classList.remove('selected'));
    const row = $(`tr[data-index="${idx}"]`);
    if (row) {
        row.classList.add('selected');
        state.selectedRow = idx;
    }
}

function deleteRow(idx) {
    if (state.deletedRows.has(idx)) {
        state.deletedRows.delete(idx);
    } else {
        state.deletedRows.add(idx);
    }
    renderGrid();
}

function addRow() {
    const newTxn = {
        id: null,
        sequence: state.transactions.length + 1,
        txn_date: '',
        value_date: '',
        description: '',
        reference_no: '',
        debit: null,
        credit: null,
        balance: null,
        txn_type: 'unknown',
        currency: 'INR',
        raw_text: '',
        _isNew: true,
    };
    state.transactions.push(newTxn);
    renderGrid();

    // Focus on the first cell of the new row
    setTimeout(() => {
        const newIdx = state.transactions.length - 1;
        const firstInput = $(`input[data-row="${newIdx}"][data-field="txn_date"]`);
        if (firstInput) firstInput.focus();
    }, 50);

    showToast('New row added', 'info');
}

function resetGrid() {
    if (!confirm('Reset all changes? This cannot be undone.')) return;
    state.transactions = JSON.parse(JSON.stringify(state.originalTransactions));
    state.deletedRows.clear();
    state.modifiedCells.clear();
    renderGrid();
    showToast('Grid reset to original', 'info');
}

// ─── Corrections ─────────────────────────────────────────────────────────────

async function confirmCorrections() {
    if (!state.documentId) return;

    const corrections = [];

    state.transactions.forEach((txn, idx) => {
        if (state.deletedRows.has(idx)) {
            corrections.push({
                predicted_id: txn.id || null,
                sequence: txn.sequence,
                correction_type: 'row_delete',
                corrections: [],
                ...txn,
            });
            return;
        }

        const fieldCorrections = [];
        const original = state.originalTransactions[idx];

        if (original) {
            for (const field of ['txn_date', 'value_date', 'description', 'reference_no', 'debit', 'credit', 'balance']) {
                const oldVal = String(original[field] || '');
                const newVal = String(txn[field] || '');
                if (oldVal !== newVal) {
                    fieldCorrections.push({ field_name: field, old_value: oldVal, new_value: newVal });
                }
            }
        }

        corrections.push({
            predicted_id: txn.id || null,
            sequence: txn.sequence,
            correction_type: txn._isNew ? 'row_add' : 'field_edit',
            corrections: fieldCorrections,
            txn_date: txn.txn_date || null,
            value_date: txn.value_date || null,
            description: txn.description || '',
            reference_no: txn.reference_no || null,
            debit: parseFloat(String(txn.debit || '').replace(/,/g, '')) || null,
            credit: parseFloat(String(txn.credit || '').replace(/,/g, '')) || null,
            balance: parseFloat(String(txn.balance || '').replace(/,/g, '')) || null,
            txn_type: txn.txn_type || 'unknown',
            currency: txn.currency || 'INR',
        });
    });

    try {
        els.btnConfirm.disabled = true;
        els.btnConfirm.textContent = 'Submitting...';

        const response = await fetch(`${API_BASE}/transactions/confirm`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                document_id: state.documentId,
                transactions: corrections,
            }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Failed to submit corrections');
        }

        const result = await response.json();
        showToast(`Confirmed! ${result.corrected_count} transactions saved as training data.`, 'success');

        state.modifiedCells.clear();
        renderGrid();

    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        els.btnConfirm.disabled = false;
        els.btnConfirm.textContent = '✓ Confirm';
    }
}

// ─── Utilities ───────────────────────────────────────────────────────────────

function formatAmount(val) {
    if (val === null || val === undefined || val === '') return '';
    const num = parseFloat(val);
    if (isNaN(num)) return String(val);
    return num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function updateTxnCount() {
    const active = state.transactions.length - state.deletedRows.size;
    els.txnCount.textContent = `${active} transaction${active !== 1 ? 's' : ''}`;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    els.toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ─── Init ────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initUpload();

    els.btnConfirm?.addEventListener('click', confirmCorrections);
    els.btnAddRow?.addEventListener('click', addRow);
    els.btnReset?.addEventListener('click', resetGrid);

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            confirmCorrections();
        }
        if (e.ctrlKey && e.key === 'n') {
            e.preventDefault();
            addRow();
        }
    });
});
