// Global UI enhancements: theme toggle, persistence, prefers-color-scheme sync, subtle transitions
(function () {
    const root = document.documentElement;
    const STORAGE_KEY = 'stackUpdaterTheme';
    function applyTheme(theme) {
        if (theme !== 'light' && theme !== 'dark') theme = 'dark';
        if (theme === 'light') root.setAttribute('data-theme', 'light'); else root.removeAttribute('data-theme');
        localStorage.setItem(STORAGE_KEY, theme);
        const icon = document.querySelector('#themeToggle i');
        if (icon) { icon.setAttribute('data-lucide', theme === 'dark' ? 'sun' : 'moon'); if (window.lucide?.createIcons) lucide.createIcons(); }
    }
    function initTheme() {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) { applyTheme(stored); return; }
        const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
        applyTheme(prefersLight ? 'light' : 'dark');
    }

    // Accessibility helpers
    function announce(msg) {
        let region = document.getElementById('aria-live-region');
        if (!region) {
            region = document.createElement('div');
            region.id = 'aria-live-region';
            region.setAttribute('aria-live', 'polite');
            region.className = 'sr-only';
            document.body.appendChild(region);
        }
        region.textContent = msg;
    }

    // Table/state logic
    let stacks = [];
    let sortKey = 'name';
    let sortDir = 'asc';
    let filterText = '';
    let filterStatus = 'all';

    const statusClass = (s) => {
        if (!s) return 'unknown';
        // Normalize the status string: trim whitespace and convert to lowercase
        const normalized = s.toString().trim().toLowerCase();
        const map = {
            'processing': 'processing',
            'preparing': 'processing',
            'updated': 'ok',
            'outdated': 'warn',
            'skipped': 'unknown',
            'error': 'error'
        };
        return map[normalized] || 'unknown';
    };
    const statusIcon = (cls) => ({
        ok: 'check-circle',
        warn: 'alert-triangle',
        error: 'x-circle',
        processing: 'loader-circle',
        unknown: 'help-circle'
    })[cls] || 'help-circle';
    function badge(status) {
        const cls = statusClass(status);
        const icon = statusIcon(cls);
        const spin = (cls === 'processing') ? 'spin' : '';
        return `<span class="badge-icon ${cls}" title="${status || 'Unknown'}" role="status" aria-label="${status || 'unknown'} status">
            <i data-lucide="${icon}" class="icon ${spin}" aria-hidden="true"></i>
        </span>`;
    }
    function fmt(dt) {
        if (!dt) return 'N/A';
        try { return new Date(dt).toLocaleString(); } catch { return dt; }
    }
    function applyFilters(data) {
        return data.filter(s => {
            const matchText = !filterText || s.name.toLowerCase().includes(filterText);
            const sc = statusClass(s.image_status);
            const matchStatus = filterStatus === 'all' || sc === filterStatus;
            return matchText && matchStatus;
        });
    }
    function applySort(data) {
        return [...data].sort((a, b) => {
            let av = a[sortKey]; let bv = b[sortKey];
            if (av == null) av = ''; if (bv == null) bv = '';
            if (typeof av === 'string') av = av.toLowerCase();
            if (typeof bv === 'string') bv = bv.toLowerCase();
            if (av < bv) return sortDir === 'asc' ? -1 : 1;
            if (av > bv) return sortDir === 'asc' ? 1 : -1;
            return 0;
        });
    }
    function renderTable() {
        const tbody = document.getElementById('stackTableBody');
        if (!tbody) return;
        const filtered = applyFilters(stacks);
        const sorted = applySort(filtered);
        tbody.innerHTML = '';
        for (const s of sorted) {
            const tr = document.createElement('tr');
            tr.setAttribute('tabindex', '0');
            tr.innerHTML = `
                <td class="name"><i data-lucide="layers" class="muted" aria-hidden="true"></i><span>${s.name}</span></td>
                <td data-col="indicator">${badge(s.image_status)}</td>
                <td data-col="lastChecked">${fmt(s.image_last_checked)}</td>
                <td>${fmt(s.last_updated_at)}</td>
                <td class="action-buttons">
                    <button data-action="get" data-id="${s.id}" class="ghost" aria-label="Get status for ${s.name}"><i data-lucide="scan"></i><span>Get Status</span></button>
                    <button data-action="refresh" data-id="${s.id}" class="ghost" aria-label="Refresh status for ${s.name}"><i data-lucide="rotate-cw"></i><span>Refresh</span></button>
                    <button data-action="update" data-id="${s.id}" class="primary" aria-label="Update ${s.name}"><i data-lucide="download-cloud"></i><span>Update</span></button>
                </td>`;
            tbody.appendChild(tr);
        }
        if (window.lucide?.createIcons) lucide.createIcons();

        // Update stats
        updateStats(sorted);
        announce(`Rendered ${sorted.length} stacks`);
    }

    function updateStats(data) {
        const total = data.length;
        const updated = data.filter(s => statusClass(s.image_status) === 'ok').length;
        const outdated = data.filter(s => statusClass(s.image_status) === 'warn').length;
        const errors = data.filter(s => statusClass(s.image_status) === 'error').length;

        const statTotal = document.getElementById('statTotal');
        const statUpdated = document.getElementById('statUpdated');
        const statOutdated = document.getElementById('statOutdated');
        const statErrors = document.getElementById('statErrors');

        if (statTotal) statTotal.textContent = total;
        if (statUpdated) statUpdated.textContent = updated;
        if (statOutdated) statOutdated.textContent = outdated;
        if (statErrors) statErrors.textContent = errors;
    }

    async function fetchStacks() {
        const res = await fetch('/api/stacks');
        stacks = await res.json();
        renderTable();
    }

    async function getIndicator(id, refresh) {
        const res = await fetch(`/api/stacks/${id}/indicator?refresh=${refresh ? 'true' : 'false'}`);
        if (!res.ok) throw new Error('indicator failed');
        return res.json();
    }
    async function updateStack(id) {
        const res = await fetch(`/api/stacks/${id}/update`, { method: 'POST' });
        if (!res.ok) throw new Error('update failed');
        return res.json();
    }

    function onTableClick(e) {
        const btn = e.target.closest('button');
        if (!btn) return;
        const id = btn.getAttribute('data-id');
        const action = btn.getAttribute('data-action');
        const row = btn.closest('tr');
        const indCell = row.querySelector('[data-col="indicator"]');
        const lcCell = row.querySelector('[data-col="lastChecked"]');
        (async () => {
            try {
                indCell.innerHTML = badge('Processing');
                if (window.lucide?.createIcons) lucide.createIcons();
                if (action === 'get') {
                    const r = await getIndicator(id, false);
                    updateLocalStack(r.id, { image_status: r.status, image_last_checked: r.last_checked });
                } else if (action === 'refresh') {
                    const r = await getIndicator(id, true);
                    updateLocalStack(r.id, { image_status: r.status, image_last_checked: r.last_checked });
                } else if (action === 'update') {
                    await updateStack(id);
                    const r = await getIndicator(id, false);
                    updateLocalStack(r.id, { image_status: r.status, image_last_checked: r.last_checked });
                }
                renderTable();
            } catch (err) {
                indCell.innerHTML = badge('Error');
                if (window.lucide?.createIcons) lucide.createIcons();
            }
        })();
    }

    function updateLocalStack(id, patch) {
        const idx = stacks.findIndex(s => s.id == id);
        if (idx >= 0) {
            stacks[idx] = { ...stacks[idx], ...patch };
        }
    }

    function initSortingFiltering() {
        const searchInput = document.getElementById('filterSearch');
        const statusSelect = document.getElementById('filterStatus');
        if (searchInput) searchInput.addEventListener('input', () => { filterText = searchInput.value.toLowerCase(); renderTable(); });
        if (statusSelect) statusSelect.addEventListener('change', () => { filterStatus = statusSelect.value; renderTable(); });
        document.querySelectorAll('thead th').forEach(th => {
            th.setAttribute('role', 'button'); th.tabIndex = 0;
            th.addEventListener('click', () => toggleSort(th.dataset.key));
            th.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSort(th.dataset.key); } });
        });
    }
    function toggleSort(key) {
        if (!key) return;
        if (sortKey === key) { sortDir = sortDir === 'asc' ? 'desc' : 'asc'; } else { sortKey = key; sortDir = 'asc'; }
        announce(`Sorting by ${key} ${sortDir}`);
        renderTable();
    }

    function initWebSocket() {
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        let ws = null;
        let reconnectTimeout = null;

        function connect() {
            ws = new WebSocket(`${proto}://${location.host}/ws`);

            ws.onmessage = (ev) => {
                try {
                    const msg = JSON.parse(ev.data);

                    if (msg.type === 'stack_update') {
                        // Single stack update
                        const p = msg.payload;
                        updateLocalStack(p.id, p);
                        updateStackRow(p);
                        updateStats(stacks);
                    } else if (msg.type === 'stacks_sync') {
                        // Full sync - replace entire stacks array
                        stacks = msg.payload;
                        renderTable();
                        announce('Stacks synced');
                    } else if (msg.type === 'staleness') {
                        // Legacy staleness updates - just update local data
                        for (const r of msg.payload) {
                            updateLocalStack(r.id, { is_outdated: r.is_outdated });
                        }
                    }
                } catch (err) {
                    console.error('WebSocket message parse error:', err);
                }
            };

            ws.onopen = () => {
                announce('Realtime connected');
                if (reconnectTimeout) {
                    clearTimeout(reconnectTimeout);
                    reconnectTimeout = null;
                }
            };

            ws.onclose = () => {
                announce('Realtime disconnected');
                // Attempt to reconnect after 3 seconds
                reconnectTimeout = setTimeout(connect, 3000);
            };

            ws.onerror = (err) => {
                console.error('WebSocket error:', err);
            };
        }

        connect();
    }

    function updateStackRow(stackData) {
        // Find the row for this stack and update only the changed cells
        const rows = document.querySelectorAll('#stackTableBody tr');
        for (const row of rows) {
            const btn = row.querySelector('button[data-id]');
            if (btn && btn.getAttribute('data-id') == stackData.id) {
                // Update indicator cell
                if (stackData.image_status) {
                    const indCell = row.querySelector('[data-col="indicator"]');
                    if (indCell) {
                        indCell.innerHTML = badge(stackData.image_status);
                        if (window.lucide?.createIcons) lucide.createIcons();
                    }
                }
                // Update last checked cell
                if (stackData.image_last_checked) {
                    const lcCell = row.querySelector('[data-col="lastChecked"]');
                    if (lcCell) {
                        lcCell.textContent = fmt(stackData.image_last_checked);
                    }
                }
                break;
            }
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        initTheme();
        const btn = document.getElementById('themeToggle');
        if (btn) { btn.addEventListener('click', () => { const current = localStorage.getItem(STORAGE_KEY) === 'light' ? 'dark' : 'light'; applyTheme(current); }); }
        window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', (e) => { const stored = localStorage.getItem(STORAGE_KEY); if (!stored) applyTheme(e.matches ? 'light' : 'dark'); });

        const importBtn = document.getElementById('importBtn');
        if (importBtn) importBtn.addEventListener('click', async () => {
            const original = importBtn.innerHTML;
            importBtn.disabled = true;
            importBtn.innerHTML = '<i data-lucide="loader-circle" class="spin"></i><span>Importing...</span>';
            if (window.lucide?.createIcons) lucide.createIcons();

            try {
                const res = await fetch('/api/stacks/import');
                const data = await res.json();
                announce(`Import completed: ${data.imported} new stacks`);
                // Fetch fresh data
                await fetchStacks();
            } catch (err) {
                announce('Import failed');
            } finally {
                importBtn.disabled = false;
                importBtn.innerHTML = original;
                if (window.lucide?.createIcons) lucide.createIcons();
            }
        });
        const refreshAllBtn = document.getElementById('refreshAllBtn');
        if (refreshAllBtn) refreshAllBtn.addEventListener('click', async () => {
            const original = refreshAllBtn.innerHTML;
            refreshAllBtn.disabled = true;
            refreshAllBtn.innerHTML = '<i data-lucide="loader-circle" class="spin"></i><span>Refreshing...</span>';
            if (window.lucide?.createIcons) lucide.createIcons();

            try {
                // Use the bulk refresh endpoint
                const res = await fetch('/api/stacks/refresh-all?force=true', { method: 'POST' });
                if (res.ok) {
                    // Fetch fresh data
                    await fetchStacks();
                    announce('Bulk refresh complete');
                } else {
                    announce('Bulk refresh failed');
                }
            } catch (err) {
                announce('Bulk refresh failed');
            } finally {
                refreshAllBtn.disabled = false;
                refreshAllBtn.innerHTML = original;
                if (window.lucide?.createIcons) lucide.createIcons();
            }
        });

        document.getElementById('stackTableBody')?.addEventListener('click', onTableClick);
        initSortingFiltering();
        initWebSocket();
        fetchStacks();
    });
})();
