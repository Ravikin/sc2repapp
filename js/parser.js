let pyodideReady = false;
let pyodideInstance = null;

async function initPyodide(onProgress) {
    if (pyodideInstance) return pyodideInstance;

    onProgress('Loading Python runtime...');
    pyodideInstance = await loadPyodide();

    onProgress('Installing dependencies...');
    await pyodideInstance.loadPackage('micropip');

    // Install mpyq from bundled wheel (not available as pure wheel on PyPI)
    // then install sc2reader which depends on it
    const baseUrl = window.location.href.replace(/\/[^/]*$/, '/');
    await pyodideInstance.runPythonAsync(`
import micropip
await micropip.install('${baseUrl}python/wheels/mpyq-0.2.5-py3-none-any.whl')
await micropip.install('sc2reader')
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
