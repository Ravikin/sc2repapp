let minimapData = null;
let minimapCanvas = null;
let minimapCtx = null;
let playInterval = null;
let showBuildings = true;
let showWorkers = false;

function initMinimap(data) {
    minimapData = data;
    if (!minimapData || !minimapData.snapshots.length) return;

    minimapCanvas = document.getElementById('minimap-canvas');
    minimapCtx = minimapCanvas.getContext('2d');

    const slider = document.getElementById('minimap-slider');
    const playBtn = document.getElementById('minimap-play');
    const buildingsCheck = document.getElementById('minimap-show-buildings');
    const workersCheck = document.getElementById('minimap-show-workers');

    slider.min = 0;
    slider.max = minimapData.snapshots.length - 1;
    slider.value = 0;

    slider.addEventListener('input', () => {
        drawFrame(parseInt(slider.value));
    });

    playBtn.addEventListener('click', () => {
        if (playInterval) {
            clearInterval(playInterval);
            playInterval = null;
            playBtn.textContent = 'Play';
        } else {
            playBtn.textContent = 'Pause';
            playInterval = setInterval(() => {
                let val = parseInt(slider.value) + 1;
                if (val >= minimapData.snapshots.length) {
                    val = 0;
                }
                slider.value = val;
                drawFrame(val);
            }, 100);
        }
    });

    buildingsCheck.addEventListener('change', () => {
        showBuildings = buildingsCheck.checked;
        drawFrame(parseInt(slider.value));
    });

    workersCheck.addEventListener('change', () => {
        showWorkers = workersCheck.checked;
        drawFrame(parseInt(slider.value));
    });

    // Render legend
    renderMinimapLegend();

    // Draw first frame
    drawFrame(0);
}

function renderMinimapLegend() {
    const legend = document.getElementById('minimap-legend');
    legend.innerHTML = '';
    for (const [pid, info] of Object.entries(minimapData.players)) {
        const item = document.createElement('div');
        item.className = 'legend-item';

        const swatch = document.createElement('span');
        swatch.className = 'legend-swatch';
        const [r, g, b] = info.color;
        swatch.style.backgroundColor = `rgb(${r},${g},${b})`;

        const label = document.createElement('span');
        label.textContent = info.name;

        item.appendChild(swatch);
        item.appendChild(label);
        legend.appendChild(item);
    }
}

function drawFrame(index) {
    if (!minimapData || !minimapCtx) return;

    const snapshot = minimapData.snapshots[index];
    const bounds = minimapData.bounds;
    const w = minimapCanvas.width;
    const h = minimapCanvas.height;

    // Update time display
    const timeEl = document.getElementById('minimap-time');
    const sec = snapshot.second;
    timeEl.textContent = `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;

    // Clear
    minimapCtx.fillStyle = '#0a0a0a';
    minimapCtx.fillRect(0, 0, w, h);

    // Draw grid
    minimapCtx.strokeStyle = '#1a1a2e';
    minimapCtx.lineWidth = 0.5;
    const gridStep = 20;
    for (let gx = 0; gx <= w; gx += gridStep) {
        minimapCtx.beginPath();
        minimapCtx.moveTo(gx, 0);
        minimapCtx.lineTo(gx, h);
        minimapCtx.stroke();
    }
    for (let gy = 0; gy <= h; gy += gridStep) {
        minimapCtx.beginPath();
        minimapCtx.moveTo(0, gy);
        minimapCtx.lineTo(w, gy);
        minimapCtx.stroke();
    }

    const rangeX = bounds.max_x - bounds.min_x;
    const rangeY = bounds.max_y - bounds.min_y;

    // Draw units - buildings first (below), then workers, then army (on top)
    const layers = [];
    if (showBuildings) layers.push('building');
    if (showWorkers) layers.push('worker');
    layers.push('army');

    for (const layer of layers) {
        for (const unit of snapshot.units) {
            if (unit.type !== layer) continue;

            const cx = ((unit.x - bounds.min_x) / rangeX) * w;
            // Flip Y: SC2 origin is bottom-left, canvas is top-left
            const cy = h - ((unit.y - bounds.min_y) / rangeY) * h;

            const playerInfo = minimapData.players[String(unit.pid)];
            if (!playerInfo) continue;
            const [r, g, b] = playerInfo.color;
            const colorStr = `rgb(${r},${g},${b})`;

            if (unit.type === 'building') {
                minimapCtx.fillStyle = `rgba(${r},${g},${b},0.5)`;
                minimapCtx.fillRect(cx - 4, cy - 4, 8, 8);
            } else if (unit.type === 'worker') {
                minimapCtx.fillStyle = `rgba(${r},${g},${b},0.6)`;
                minimapCtx.beginPath();
                minimapCtx.arc(cx, cy, 2, 0, Math.PI * 2);
                minimapCtx.fill();
            } else {
                // army
                minimapCtx.fillStyle = colorStr;
                minimapCtx.beginPath();
                minimapCtx.arc(cx, cy, 3.5, 0, Math.PI * 2);
                minimapCtx.fill();
            }
        }
    }
}

function resetMinimap() {
    if (playInterval) {
        clearInterval(playInterval);
        playInterval = null;
    }
    const playBtn = document.getElementById('minimap-play');
    if (playBtn) playBtn.textContent = 'Play';
}
