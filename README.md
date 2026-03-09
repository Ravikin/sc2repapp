# SC2 Replay Analyzer

A client-side StarCraft 2 replay analyzer that runs entirely in the browser. Upload `.SC2Replay` files and get detailed game breakdowns — no server required.

**Live site:** [ravikin.github.io/sc2repapp](https://ravikin.github.io/sc2repapp/)

## Features

- **Game Summary** — Map, duration, player names, races, in-game colors, league, and match result
- **Event Log** — Timestamped log of buildings, units, upgrades, economy stats, and big fight detection
- **Interactive Minimap** — Canvas visualization of unit positions over time with play/pause and timeline scrubber
- **Build Order** — Side-by-side chronological build orders for both players (buildings, units, upgrades)
- **Economy Charts** — Workers, income rates, resource bank (floating minerals/gas)
- **Supply Chart** — Supply used vs supply cap over time
- **Army Value Chart** — Engine-tracked army value over time
- **Resources Lost vs Killed** — Trade efficiency comparison
- **APM Chart** — Actions per minute for each player
- **Download Log** — Export the full event log as a `.txt` file

## How It Works

The app uses [Pyodide](https://pyodide.org/) to run Python directly in the browser via WebAssembly. The [sc2reader](https://github.com/ggtracker/sc2reader) library parses the binary `.SC2Replay` format client-side — no data is uploaded to any server.

### Tech Stack

- **Pyodide** — Python runtime in the browser (WebAssembly)
- **sc2reader** — SC2 replay parsing library (installed via micropip)
- **Chart.js** — Charts and graphs
- **HTML5 Canvas** — Minimap rendering
- Vanilla JS, no build step

## Project Structure

```
├── index.html              # Main page
├── css/style.css           # Dark theme styles
├── js/
│   ├── parser.js           # Pyodide initialization and sc2reader setup
│   ├── minimap.js          # Canvas-based minimap with timeline controls
│   └── app.js              # UI logic, charts, build order rendering
├── python/
│   ├── parse_replay.py     # Replay parsing logic (runs in Pyodide)
│   └── wheels/             # Bundled mpyq wheel (dependency of sc2reader)
├── main.py                 # Legacy CLI parser
└── streamlit_app.py        # Legacy Streamlit UI
```

## Local Development

Just serve the files with any static HTTP server:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000` in your browser. First load takes a few seconds while Pyodide downloads and initializes.

## Deployment

The app is deployed via GitHub Pages from the `main` branch. Any push to `main` automatically updates the live site.
