const RACE_COLORS = {
    'Protoss': '#FFD700',
    'Terran': '#4A90D9',
    'Zerg': '#9B59B6',
};

document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const statusEl = document.getElementById('status');
    const statusText = document.getElementById('status-text');
    const progressBar = document.getElementById('progress-bar');
    const resultsSection = document.getElementById('results');
    const logOutput = document.getElementById('log-output');
    const downloadBtn = document.getElementById('download-btn');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    let currentLog = '';
    let pyodideLoaded = false;

    // Tab switching
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`tab-${target}`).classList.add('active');
        });
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

        try {
            if (!pyodideLoaded) {
                showStatus('Loading Python runtime...', 10);
                await initPyodide((msg) => {
                    const progressMap = {
                        'Loading Python runtime...': 20,
                        'Installing sc2reader...': 50,
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
            renderCharts(result.charts);

            resultsSection.classList.remove('hidden');
            hideStatus();

            // Reset to log tab
            tabBtns[0].click();

        } catch (err) {
            hideStatus();
            console.error(err);
            alert('Error parsing replay: ' + err.message);
        }
    }

    function renderCharts(charts) {
        renderEconomyChart(charts);
        renderSupplyChart(charts);
        renderArmyChart(charts);
    }

    function getPlayerColor(player) {
        return RACE_COLORS[player.race] || '#CCCCCC';
    }

    function renderEconomyChart(charts) {
        const ctx = document.getElementById('economy-chart').getContext('2d');
        if (window.economyChart) window.economyChart.destroy();

        const datasets = [];
        charts.players.forEach(player => {
            const data = charts.economy[player.name] || [];
            const color = getPlayerColor(player);
            datasets.push({
                label: `${player.name} - Workers`,
                data: data.map(d => ({ x: d.minute, y: d.workers })),
                borderColor: color,
                backgroundColor: color + '33',
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
            const color = getPlayerColor(player);
            datasets.push({
                label: `${player.name} - Supply Used`,
                data: data.map(d => ({ x: d.minute, y: d.used })),
                borderColor: color,
                backgroundColor: color + '33',
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
            const color = getPlayerColor(player);
            datasets.push({
                label: `${player.name} - Army Value`,
                data: data.map(d => ({ x: d.minute, y: d.minerals + d.gas })),
                borderColor: color,
                backgroundColor: color + '33',
                tension: 0.3,
                fill: true,
            });
        });

        window.armyChart = new Chart(ctx, {
            type: 'line',
            data: { datasets },
            options: chartOptions('Army Value (estimated)', 'Resources'),
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
