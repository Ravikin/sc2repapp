const LEAGUE_NAMES = ['', 'Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Master', 'Grandmaster'];

document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const statusEl = document.getElementById('status');
    const statusText = document.getElementById('status-text');
    const progressBar = document.getElementById('progress-bar');
    const resultsSection = document.getElementById('results');
    const gameSummary = document.getElementById('game-summary');
    const logOutput = document.getElementById('log-output');
    const downloadBtn = document.getElementById('download-btn');

    let currentLog = '';
    let pyodideLoaded = false;

    // Tab switching (use event delegation for dynamically queried elements)
    document.querySelector('.tabs').addEventListener('click', (e) => {
        const btn = e.target.closest('.tab-btn');
        if (!btn) return;
        const target = btn.dataset.tab;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${target}`).classList.add('active');
    });

    // Drag and drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    });

    dropZone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', () => {
        if (fileInput.files[0]) handleFile(fileInput.files[0]);
    });

    // Download
    downloadBtn.addEventListener('click', () => {
        const blob = new Blob([currentLog], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'replay_events.txt';
        a.click();
        URL.revokeObjectURL(url);
    });

    function showStatus(message, progress) {
        statusEl.classList.remove('hidden');
        statusText.textContent = message;
        if (progress !== undefined) {
            progressBar.style.width = progress + '%';
        }
    }

    function hideStatus() {
        statusEl.classList.add('hidden');
        progressBar.style.width = '0%';
    }

    async function handleFile(file) {
        if (!file.name.toLowerCase().endsWith('.sc2replay')) {
            alert('Please upload a .SC2Replay file');
            return;
        }

        resultsSection.classList.add('hidden');
        gameSummary.classList.add('hidden');
        resetMinimap();

        try {
            if (!pyodideLoaded) {
                showStatus('Loading Python runtime...', 10);
                await initPyodide((msg) => {
                    const progressMap = {
                        'Loading Python runtime...': 20,
                        'Installing dependencies...': 50,
                        'Loading parser...': 80,
                        'Ready': 100,
                    };
                    showStatus(msg, progressMap[msg] || 50);
                });
                pyodideLoaded = true;
            }

            showStatus('Parsing replay...', 90);

            const arrayBuffer = await file.arrayBuffer();
            const uint8Array = new Uint8Array(arrayBuffer);

            const result = await parseReplay(uint8Array);

            currentLog = result.log;
            logOutput.textContent = result.log;

            renderSummary(result.summary);
            renderCharts(result.charts);
            renderBuildOrder(result.build_order, result.charts.players);

            if (result.minimap) {
                initMinimap(result.minimap);
            }

            gameSummary.classList.remove('hidden');
            resultsSection.classList.remove('hidden');
            hideStatus();

            // Reset to log tab
            document.querySelector('.tab-btn[data-tab="log"]').click();

        } catch (err) {
            hideStatus();
            console.error(err);
            alert('Error parsing replay: ' + err.message);
        }
    }

    // === GAME SUMMARY ===
    function renderSummary(summary) {
        const dur = summary.duration_seconds;
        const durStr = `${Math.floor(dur / 60)}:${String(dur % 60).padStart(2, '0')}`;

        let html = `<div class="summary-header">
            <span class="summary-map">${summary.map}</span>
            <span class="summary-duration">${durStr}</span>
            ${summary.date ? `<span class="summary-date">${summary.date}</span>` : ''}
        </div>
        <div class="player-cards">`;

        for (const p of summary.players) {
            const [r, g, b] = p.color;
            const resultClass = p.result === 'Win' ? 'result-win' : 'result-loss';
            const league = LEAGUE_NAMES[p.highest_league] || '';

            html += `<div class="player-card" style="border-left: 4px solid rgb(${r},${g},${b})">
                <div class="player-name">${p.clan_tag ? `[${p.clan_tag}] ` : ''}${p.name}</div>
                <div class="player-details">
                    <span class="player-race">${p.race}</span>
                    ${league ? `<span class="player-league">${league}</span>` : ''}
                    <span class="player-result ${resultClass}">${p.result}</span>
                </div>
            </div>`;
        }

        html += '</div>';
        gameSummary.innerHTML = html;
    }

    // === BUILD ORDER ===
    function renderBuildOrder(buildOrder, players) {
        const container = document.getElementById('build-order-content');
        if (!buildOrder || !players.length) {
            container.innerHTML = '<p>No build order data available.</p>';
            return;
        }

        let html = '<div class="build-order-grid">';
        for (const player of players) {
            const entries = buildOrder[player.name] || [];
            const [r, g, b] = player.color;

            html += `<div class="build-order-column">
                <h3 class="build-order-player" style="color: rgb(${r},${g},${b})">${player.name}</h3>
                <div class="build-order-list">`;

            for (const entry of entries) {
                const timeStr = `${Math.floor(entry.second / 60)}:${String(entry.second % 60).padStart(2, '0')}`;
                const typeClass = `bo-${entry.type}`;
                html += `<div class="build-order-entry">
                    <span class="bo-time">${timeStr}</span>
                    <span class="bo-supply">${entry.supply}</span>
                    <span class="bo-name ${typeClass}">${entry.name}</span>
                </div>`;
            }

            html += '</div></div>';
        }
        html += '</div>';
        container.innerHTML = html;
    }

    // === CHARTS ===
    function renderCharts(charts) {
        renderEconomyChart(charts);
        renderSupplyChart(charts);
        renderArmyChart(charts);
        renderTradesChart(charts);
        renderBankChart(charts);
        renderApmChart(charts);
    }

    function playerColor(player) {
        if (player.color) {
            const [r, g, b] = player.color;
            return `rgb(${r},${g},${b})`;
        }
        return '#CCCCCC';
    }

    function playerColorAlpha(player, alpha) {
        if (player.color) {
            const [r, g, b] = player.color;
            return `rgba(${r},${g},${b},${alpha})`;
        }
        return `rgba(204,204,204,${alpha})`;
    }

    function renderEconomyChart(charts) {
        const ctx = document.getElementById('economy-chart').getContext('2d');
        if (window.economyChart) window.economyChart.destroy();

        const datasets = [];
        charts.players.forEach(player => {
            const data = charts.economy[player.name] || [];
            const color = playerColor(player);
            datasets.push({
                label: `${player.name} - Workers`,
                data: data.map(d => ({ x: d.minute, y: d.workers })),
                borderColor: color,
                backgroundColor: playerColorAlpha(player, 0.2),
                tension: 0.3,
                fill: false,
            });
            datasets.push({
                label: `${player.name} - Minerals/min`,
                data: data.map(d => ({ x: d.minute, y: d.minerals_income })),
                borderColor: color,
                borderDash: [5, 5],
                backgroundColor: 'transparent',
                tension: 0.3,
                fill: false,
                hidden: true,
            });
        });

        window.economyChart = new Chart(ctx, {
            type: 'line',
            data: { datasets },
            options: chartOptions('Economy', 'Count / Rate'),
        });
    }

    function renderSupplyChart(charts) {
        const ctx = document.getElementById('supply-chart').getContext('2d');
        if (window.supplyChart) window.supplyChart.destroy();

        const datasets = [];
        charts.players.forEach(player => {
            const data = charts.supply[player.name] || [];
            const color = playerColor(player);
            datasets.push({
                label: `${player.name} - Supply Used`,
                data: data.map(d => ({ x: d.minute, y: d.used })),
                borderColor: color,
                backgroundColor: playerColorAlpha(player, 0.2),
                tension: 0.3,
                fill: false,
            });
            datasets.push({
                label: `${player.name} - Supply Cap`,
                data: data.map(d => ({ x: d.minute, y: d.made })),
                borderColor: color,
                borderDash: [5, 5],
                backgroundColor: 'transparent',
                tension: 0.3,
                fill: false,
            });
        });

        window.supplyChart = new Chart(ctx, {
            type: 'line',
            data: { datasets },
            options: chartOptions('Supply', 'Supply'),
        });
    }

    function renderArmyChart(charts) {
        const ctx = document.getElementById('army-chart').getContext('2d');
        if (window.armyChart) window.armyChart.destroy();

        const datasets = [];
        charts.players.forEach(player => {
            const data = charts.army_value[player.name] || [];
            const color = playerColor(player);
            datasets.push({
                label: `${player.name} - Army Value`,
                data: data.map(d => ({ x: d.minute, y: d.value })),
                borderColor: color,
                backgroundColor: playerColorAlpha(player, 0.15),
                tension: 0.3,
                fill: true,
            });
        });

        window.armyChart = new Chart(ctx, {
            type: 'line',
            data: { datasets },
            options: chartOptions('Army Value (engine-tracked)', 'Resources'),
        });
    }

    function renderTradesChart(charts) {
        const ctx = document.getElementById('trades-chart').getContext('2d');
        if (window.tradesChart) window.tradesChart.destroy();

        const datasets = [];
        charts.players.forEach(player => {
            const data = charts.resources_lost_killed[player.name] || [];
            const color = playerColor(player);
            datasets.push({
                label: `${player.name} - Killed`,
                data: data.map(d => ({ x: d.minute, y: d.killed })),
                borderColor: color,
                backgroundColor: 'transparent',
                tension: 0.3,
                fill: false,
            });
            datasets.push({
                label: `${player.name} - Lost`,
                data: data.map(d => ({ x: d.minute, y: d.lost })),
                borderColor: color,
                borderDash: [5, 5],
                backgroundColor: 'transparent',
                tension: 0.3,
                fill: false,
            });
        });

        window.tradesChart = new Chart(ctx, {
            type: 'line',
            data: { datasets },
            options: chartOptions('Resources Lost vs Killed', 'Resources'),
        });
    }

    function renderBankChart(charts) {
        const ctx = document.getElementById('bank-chart').getContext('2d');
        if (window.bankChart) window.bankChart.destroy();

        const datasets = [];
        charts.players.forEach(player => {
            const data = charts.resource_bank[player.name] || [];
            const color = playerColor(player);
            datasets.push({
                label: `${player.name} - Minerals`,
                data: data.map(d => ({ x: d.minute, y: d.minerals })),
                borderColor: color,
                backgroundColor: 'transparent',
                tension: 0.3,
                fill: false,
            });
            datasets.push({
                label: `${player.name} - Vespene`,
                data: data.map(d => ({ x: d.minute, y: d.vespene })),
                borderColor: color,
                borderDash: [5, 5],
                backgroundColor: 'transparent',
                tension: 0.3,
                fill: false,
            });
        });

        window.bankChart = new Chart(ctx, {
            type: 'line',
            data: { datasets },
            options: chartOptions('Resource Bank', 'Resources'),
        });
    }

    function renderApmChart(charts) {
        const ctx = document.getElementById('apm-chart').getContext('2d');
        if (window.apmChart) window.apmChart.destroy();

        const datasets = [];
        charts.players.forEach(player => {
            const data = charts.apm[player.name] || [];
            const color = playerColor(player);
            datasets.push({
                label: `${player.name}`,
                data: data.map(d => ({ x: d.minute, y: d.actions })),
                borderColor: color,
                backgroundColor: playerColorAlpha(player, 0.15),
                tension: 0.3,
                fill: true,
            });
        });

        window.apmChart = new Chart(ctx, {
            type: 'line',
            data: { datasets },
            options: chartOptions('Actions Per Minute', 'APM'),
        });
    }

    function chartOptions(title, yLabel) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: title,
                    color: '#E0E0E0',
                    font: { size: 16 },
                },
                legend: {
                    labels: { color: '#C0C0C0' },
                },
            },
            scales: {
                x: {
                    type: 'linear',
                    title: {
                        display: true,
                        text: 'Game Time (minutes)',
                        color: '#C0C0C0',
                    },
                    ticks: { color: '#999' },
                    grid: { color: '#333' },
                },
                y: {
                    title: {
                        display: true,
                        text: yLabel,
                        color: '#C0C0C0',
                    },
                    ticks: { color: '#999' },
                    grid: { color: '#333' },
                },
            },
        };
    }
});
