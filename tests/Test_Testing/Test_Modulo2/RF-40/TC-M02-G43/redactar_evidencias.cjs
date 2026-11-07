const fs = require('fs');
const path = require('path');
const resultados = path.join(__dirname, 'Resultados');

function ocultar(s) {
  return s
    .replaceAll('Test1234!', '[REDACTADO]')
    .replaceAll('Pruebas12#', '[REDACTADO]')
    .replace(/Bearer\s+eyJ[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2}/g, 'Bearer [JWT_REDACTADO]')
    .replace(/eyJ[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2}/g, '[JWT_REDACTADO]')
    .replace(/(refresh_token=)[^;\s"<>]+/gi, '$1[REDACTADO]');
}

function recorrer(v) {
  if (typeof v === 'string') return ocultar(v);
  if (Array.isArray(v)) return v.map(recorrer);
  if (!v || typeof v !== 'object') return v;
  if (v.type === 'Buffer' && Array.isArray(v.data)) {
    const saneado = ocultar(Buffer.from(v.data).toString('utf8'));
    return { type: 'Buffer', data: Array.from(Buffer.from(saneado, 'utf8')) };
  }
  return Object.fromEntries(Object.entries(v).map(([k, value]) => [k, recorrer(value)]));
}

for (const nombre of fs.readdirSync(resultados)) {
  const archivo = path.join(resultados, nombre);
  if (!fs.statSync(archivo).isFile()) continue;
  if (nombre.endsWith('.json')) {
    const doc = JSON.parse(fs.readFileSync(archivo, 'utf8'));
    fs.writeFileSync(archivo, JSON.stringify(recorrer(doc), null, 2) + '\n', 'utf8');
  } else if (nombre.endsWith('.html')) {
    fs.writeFileSync(archivo, ocultar(fs.readFileSync(archivo, 'utf8')), 'utf8');
  }
}
