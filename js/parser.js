let pyodideReady = false;
let pyodideInstance = null;

async function initPyodide(onProgress) {
    if (pyodideInstance) return pyodideInstance;

    onProgress('Loading Python runtime...');
    pyodideInstance = await loadPyodide();

    onProgress('Installing dependencies...');
    await pyodideInstance.loadPackage('micropip');

    // mpyq doesn't have a pure Python wheel on PyPI, so we load it manually
    const mpyqResponse = await fetch('python/mpyq.py');
    const mpyqCode = await mpyqResponse.text();
    pyodideInstance.FS.writeFile('/lib/python3.12/site-packages/mpyq.py', mpyqCode);

    // Install sc2reader without deps (mpyq already placed manually)
    await pyodideInstance.runPythonAsync(`
import micropip
await micropip.install('sc2reader', deps=False)
    `);

    onProgress('Loading parser...');
    const parserResponse = await fetch('python/parse_replay.py');
    const parserCode = await parserResponse.text();
    await pyodideInstance.runPythonAsync(parserCode);

    pyodideReady = true;
    onProgress('Ready');
    return pyodideInstance;
}

async function parseReplay(fileBytes) {
    if (!pyodideInstance) {
        throw new Error('Pyodide not initialized');
    }

    pyodideInstance.globals.set('_replay_bytes', fileBytes);

    const resultJson = await pyodideInstance.runPythonAsync(`
parse_replay_bytes(bytes(_replay_bytes))
    `);

    return JSON.parse(resultJson);
}
