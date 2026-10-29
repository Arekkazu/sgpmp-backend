// Cierre por API oficial y comparación de datos anteriores, con transporte inyectable.
import { createHash } from 'node:crypto';
import { rangoHistorial } from './g88_entradas.mjs';
const huella = (x) => createHash('sha256').update(JSON.stringify(x)).digest('hex');
export function cierreUnico(accion) {
  let pendiente;
  return () => (pendiente ??= Promise.resolve().then(accion));
}

export async function cerrarYVerificar({ runId, secreto, solicitar, autenticar, anteriores = [], lecturas = [],
  umbralRun266 = null, solicitarCierre = true, cierrePrevioHttp = null, ahora = Date.now() }) {
  const salida = { cierre_http: null, rollback: { verificado: false, asociaciones: [], dashboard: [],
    umbrales: [], umbral_run_266: { estado: 'SIN_UMBRAL_DEL_RUN_QUE_VERIFICAR' },
    historial: [], conclusion: 'NO_CONCLUYENTE' }, errores: [] };
  if (solicitarCierre) {
    try { salida.cierre_http = (await solicitar('DELETE', `/test-control/runs/${runId}`, { secreto })).status; }
    catch (e) { salida.errores.push(`DELETE: ${e.message}`); }
  } else salida.cierre_http = cierrePrevioHttp;
  if (![200, 404].includes(salida.cierre_http)) return salida;
  let token;
  try { token = await autenticar(); } catch (e) { salida.errores.push(`Re-login: ${e.message}`); return salida; }
  for (const anterior of anteriores) {
    for (const [tipo, ruta, campo] of [
      ['asociaciones', anterior.ruta_asociaciones, 'asociaciones'],
      ['dashboard', anterior.ruta_dashboard, 'dashboard'],
      ['umbrales', anterior.ruta_umbral, 'umbral'],
    ]) {
      if (!ruta || (anterior[campo] === undefined && !anterior[`${campo}_sha256`])) continue;
      try {
        const x = await solicitar('GET', ruta, { token });
        const coincide = x.status === 200 && (anterior[`${campo}_sha256`]
          ? huella(x.json) === anterior[`${campo}_sha256`] : JSON.stringify(x.json) === JSON.stringify(anterior[campo]));
        salida.rollback[tipo].push({ caso: anterior.caso, ruta, http: x.status, coincide });
      } catch (e) { salida.errores.push(`${anterior.caso} ${tipo}: ${e.message}`); }
    }
  }
  if (umbralRun266?.alta_intentada && !umbralRun266.id) {
    salida.rollback.umbral_run_266 = { estado: 'NO_CONCLUYENTE', motivo: 'Alta M09 intentada sin ID para verificar tras DELETE.' };
    salida.errores.push('266: alta M09 sin ID; reversión no verificable por GET.');
  } else if (umbralRun266?.id) {
    const ruta = `/configuracion/umbrales?id_especie=${umbralRun266.especie_id}`;
    try {
      const x = await solicitar('GET', ruta, { token });
      const items = x.json?.items;
      const completo = x.status === 200 && Array.isArray(items)
        && (x.json.total == null || Number(x.json.total) === items.length);
      const ausente = completo && !items.some((u) => Number(u.id_umbral_ambiental) === Number(umbralRun266.id));
      salida.rollback.umbral_run_266 = { id: umbralRun266.id, ruta, http: x.status,
        completo, ausente, estado: ausente ? 'REVERTIDO_VERIFICADO'
          : completo ? 'PRESENTE_ROLLBACK_NO_CONFIRMADO' : 'NO_CONCLUYENTE' };
      if (!ausente) salida.errores.push(completo
        ? `266: umbral ${umbralRun266.id} sigue presente tras DELETE; rollback NO CONFIRMADO.`
        : `266: GET posterior al DELETE no permitió verificar el umbral ${umbralRun266.id}.`);
    } catch (e) {
      salida.rollback.umbral_run_266 = { id: umbralRun266.id, ruta, estado: 'NO_CONFIRMADO' };
      salida.errores.push(`266: GET posterior al DELETE: ${e.message}`);
    }
  }
  for (const lectura of lecturas) {
    try {
      const hoy = rangoHistorial(ahora).fin;
      const q = new URLSearchParams({ sensor_id: String(lectura.sensor_id), fecha_inicio: lectura.fecha_inicio,
        fecha_fin: lectura.fecha_fin > hoy ? hoy : lectura.fecha_fin });
      const ruta = `/iot/monitoreo/historial?${q}`;
      const x = await solicitar('GET', ruta, { token });
      const items = x.json?.items;
      const completo = x.status === 200 && Array.isArray(items) && Number(x.json.total) === items.length;
      const ausente = completo && !items.some((i) => Number(i.id_telemetria) === Number(lectura.id_telemetria));
      salida.rollback.historial.push({ caso: lectura.caso, ruta, http: x.status, completo, ausente });
    } catch (e) { salida.errores.push(`Historial ${lectura.caso}: ${e.message}`); }
  }
  const comparaciones = [...salida.rollback.asociaciones, ...salida.rollback.dashboard, ...salida.rollback.umbrales];
  salida.rollback.verificado = salida.errores.length === 0 && anteriores.length > 0 && lecturas.length > 0
    && comparaciones.length >= anteriores.length && comparaciones.every((x) => x.coincide)
    && salida.rollback.historial.length === lecturas.length && salida.rollback.historial.every((x) => x.ausente);
  salida.rollback.conclusion = salida.rollback.verificado ? 'ROLLBACK_CONFIRMADO'
    : salida.rollback.umbral_run_266.estado === 'PRESENTE_ROLLBACK_NO_CONFIRMADO'
      ? 'ROLLBACK_NO_CONFIRMADO_UMBRAL_266' : 'NO_CONCLUYENTE';
  return salida;
}
