/**
 * Script auxiliar Node.js (CommonJS) para invocar la verificación de base de datos (NW-13).
 */
const { spawnSync } = require('child_process');
const path = require('path');

const pyScript = path.join(__dirname, 'verificar-bd.py');
const repoRoot = path.resolve(__dirname, '../../../../..');
const pythonExe = process.platform === 'win32'
    ? path.join(repoRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(repoRoot, '.venv', 'bin', 'python');

console.log(`[verificar-bd.cjs] Ejecutando: ${pyScript}`);
const res = spawnSync(pythonExe, [pyScript], { stdio: 'inherit', cwd: __dirname });

if (res.error) {
    console.error(`[verificar-bd.cjs] Error al invocar Python:`, res.error);
    process.exit(1);
}

process.exit(res.status || 0);
