import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const dir = path.join(path.dirname(process.execPath), 'node_modules', 'newman');

export async function ejecutarNewman(input) {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g32-newman-'));
  try {
    const newman = require(dir);
    const reporte = path.join(temporal, 'newman-report.json');
    // Equivale a --reporter-json-export; Newman nunca usa su ruta implícita en cwd.
    const { error, summary } = await new Promise(resolve => newman.run({
      collection: input.coleccion, environment: input.environment, reporters: ['json'],
      reporter: { json: { export: reporte } },
      silent: true, timeoutRequest: input.timeout, timeout: 160000, ignoreRedirects: true,
      color: 'off',
    }, (error, summary) => resolve({ error, summary })));
    const solicitudes = (summary?.run?.executions ?? []).map(e => ({ nombre: e.item?.name,
      http: e.response?.code ?? null, duracion_ms: e.response?.responseTime ?? null,
      aserciones: (e.assertions ?? []).map(a => ({ nombre: a.assertion, error: a.error?.message ?? null })) }));
    const exportado = fs.existsSync(reporte);
    return { error: error?.code ?? (exportado ? null : 'REPORTE_NO_EXPORTADO'), solicitudes,
      estadisticas: summary?.run?.stats ?? null, reporte_exportado: exportado,
      fallido: Boolean(error || !summary || !exportado) };
  } finally {
    fs.rmSync(temporal, { recursive: true, force: true });
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const { fallido, ...resultado } = await ejecutarNewman(JSON.parse(fs.readFileSync(0, 'utf8')));
    process.stdout.write(JSON.stringify(resultado));
    if (fallido) process.exitCode = 2;
  } catch (e) {
    process.stdout.write(JSON.stringify({ error: e.code ?? 'NEWMAN_ERROR', solicitudes: [] }));
    process.exitCode = 2;
  }
}
