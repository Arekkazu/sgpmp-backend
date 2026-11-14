import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contrastarRespuesta } from '../g37.mjs';
import { entrada } from '../lib/g37_core.mjs';

const require = createRequire(import.meta.url);
export const directorioNewman = path.join(path.dirname(process.execPath), 'node_modules', 'newman');
export function sanearReporte(contenido, secretos, esJson = false) {
  if (esJson) {
    const limpiar = (v, k = '') => {
      if (/^(stream|body|headers|header|cookies|auth|authorization|raw)$/i.test(k)) return '[REDACTADO]';
      if (Array.isArray(v)) return v.map(x => limpiar(x));
      if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([clave, x]) => [clave, limpiar(x, clave)]));
      return v;
    };
    contenido = JSON.stringify(limpiar(JSON.parse(contenido)), null, 2);
  }
  for (const secreto of secretos) contenido = contenido.split(secreto).join('[REDACTADO]');
  return contenido.replace(/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g, '[JWT_REDACTADO]')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[CORREO_REDACTADO]');
}
export function resumirEjecuciones(summary, input) {
  return (summary?.run?.executions ?? []).map(e => {
    const nombre = e.item?.name, http = e.response?.code ?? null;
    const actor = nombre === 'ficha' ? 'admin' : 'contador';
    const parametro = key => input.environment.values.find(x => x.key === key)?.value;
    const ruta = nombre === 'acumulado' ? `/finanzas/periodos/${parametro('periodo')}/estado-resultados/acumulado` :
        `/finanzas/lineas/${parametro('linea')}/cadena`;
    const contraste = { contraste_contrato: [], discrepancias_contrato: [], problemas_tecnicos: [] };
    if (http === 200) {
      let body = null; try { body = e.response.json(); } catch { /* Se registra el esquema null. */ }
      contrastarRespuesta(contraste, nombre, actor, http, body, ruta);
    } else contraste.contraste_contrato.push({ id: nombre, ruta: entrada(nombre).ruta,
      actor, http, resultado: 'no_contrastable' });
    return { nombre, http, contraste: contraste.contraste_contrato[0] ?? null,
      aserciones: (e.assertions ?? []).map(a => ({ nombre: a.assertion, error: a.error?.message ?? null })) };
  });
}
export async function ejecutarNewman(input, modulo = null) {
  const destino = path.resolve(input.salida);
  if (path.basename(destino) !== 'newman' || !destino.includes(`${path.sep}RUN-G37-V`)) throw Error('Reporte fuera del RUN');
  fs.mkdirSync(destino, { recursive: true });
  const newman = modulo ?? require(directorioNewman);
  const json = path.join(destino, 'newman-G37.json'), html = path.join(destino, 'newman-G37.html');
  const { error, summary } = await new Promise(resolve => newman.run({ collection: input.coleccion,
    environment: input.environment, reporters: ['json', 'htmlextra'], reporter: { json: { export: json },
      htmlextra: { export: html, skipSensitiveData: true } }, silent: true, timeoutRequest: input.timeout,
    timeout: 160000, ignoreRedirects: true, color: 'off' }, (error, summary) => resolve({ error, summary })));
  const solicitudes = resumirEjecuciones(summary, input);
  const secretos = (input.environment?.values ?? []).filter(x => /token|secret|password|correo|email/i.test(x.key))
    .map(x => String(x.value ?? '')).filter(x => x.length > 3);
  for (const archivo of [json, html]) if (fs.existsSync(archivo)) {
    const contenido = sanearReporte(fs.readFileSync(archivo, 'utf8'), secretos, archivo === json);
    fs.writeFileSync(archivo, contenido, 'utf8');
  }
  return { error: error?.code ?? null, solicitudes, reportes: { json: fs.existsSync(json), html: fs.existsSync(html) },
    fallido: Boolean(error || !summary || !fs.existsSync(json) || !fs.existsSync(html)) };
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { const { fallido, ...r } = await ejecutarNewman(JSON.parse(fs.readFileSync(0, 'utf8')));
    process.stdout.write(JSON.stringify(r)); if (fallido) process.exitCode = 2;
  } catch (e) { process.stdout.write(JSON.stringify({ error: e.code ?? 'NEWMAN_ERROR', solicitudes: [] })); process.exitCode = 2; }
}
