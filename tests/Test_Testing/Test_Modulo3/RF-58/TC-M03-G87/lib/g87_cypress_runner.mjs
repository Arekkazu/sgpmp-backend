import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const worker = path.join(path.dirname(fileURLToPath(import.meta.url)), 'g87_cypress_worker.mjs');
export const TIMEOUT_UI_MS = 600000;

export function chromeLocal() {
  if (process.platform !== 'win32') return { disponible: false, motivo: 'Plataforma no Windows.' };
  const rutas = [path.join(process.env.PROGRAMFILES ?? 'C:\\Program Files', 'Google', 'Chrome', 'Application', 'chrome.exe'),
    path.join(process.env['PROGRAMFILES(X86)'] ?? 'C:\\Program Files (x86)', 'Google', 'Chrome', 'Application', 'chrome.exe')];
  const ruta = rutas.find((p) => fs.existsSync(p));
  if (!ruta) return { disponible: false, motivo: 'Chrome no instalado.' };
  const ps = spawnSync('powershell', ['-NoProfile', '-Command', '(Get-Item -LiteralPath $args[0]).VersionInfo.ProductVersion', ruta],
    { encoding: 'utf8', timeout: 5000 });
  return { disponible: true, ruta, version: ps.status === 0 ? ps.stdout.trim() : null,
    reconocido_cypress: null, motivo: 'La disponibilidad en Cypress se confirma al arrancar el worker.' };
}

export async function ejecutarCypressControlado({ opciones, timeoutMs = TIMEOUT_UI_MS, spawnFn = spawn, signal,
  terminarArbol = (pid) => spawnSync('taskkill', ['/T', '/F', '/PID', String(pid)], { timeout: 10000 }) }) {
  const inicio = Date.now();
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'g87-cypress-'));
  const salida = path.join(tmp, 'resultado.json');
  try {
    const hijo = spawnFn(process.execPath, [worker, salida], { windowsHide: true, stdio: ['pipe', 'ignore', 'ignore'] });
    hijo.stdin?.on('error', () => {});
    hijo.stdin?.end(JSON.stringify(opciones));
    const fin = await new Promise((resolve) => {
      let terminado = false;
      const completar = (x) => { if (!terminado) { terminado = true; clearTimeout(reloj); signal?.removeEventListener('abort', abortar); resolve(x); } };
      const terminar = () => {
        if (!hijo.pid) return 'PID no disponible';
        try {
          const t = terminarArbol(hijo.pid);
          if (t?.error) return `taskkill: ${t.error.message}`;
          return t?.status && t.status !== 0 ? `taskkill exit ${t.status}` : null;
        } catch (e) { return `taskkill: ${e.message}`; }
      };
      const abortar = () => { const error = terminar(); completar({ exitCode: null, motivo: `Señal de interrupción${error ? `; ${error}` : ''}` }); };
      const reloj = setTimeout(() => {
        const error = terminar();
        completar({ timeout: true, exitCode: null, motivo: `Timeout Cypress ${timeoutMs} ms${error ? `; ${error}` : ''}` });
      }, timeoutMs);
      hijo.once('error', (e) => completar({ exitCode: null, motivo: e.message }));
      hijo.once('exit', (code, signal) => completar({ exitCode: code, motivo: signal ? `Señal ${signal}` : null }));
      signal?.addEventListener('abort', abortar, { once: true });
      if (signal?.aborted) abortar();
    });
    let reporte = {};
    if (fs.existsSync(salida)) try { reporte = JSON.parse(fs.readFileSync(salida, 'utf8')); } catch { /* informe incompleto */ }
    return { navegador: 'chrome', version: reporte.browserVersion ?? null, duracion_ms: Date.now() - inicio,
      exit_code: fin.exitCode, total_pruebas: reporte.totalTests ?? 0, fallidas: reporte.totalFailed ?? 0,
      motivo: fin.motivo ?? reporte.message ?? (reporte.totalTests ? null : 'Cypress no produjo comprobaciones'),
      timeout: !!fin.timeout, status: reporte.status ?? 'failed', runs: [{ tests: reporte.tests ?? [] }] };
  } finally { fs.rmSync(tmp, { recursive: true, force: true }); }
}
