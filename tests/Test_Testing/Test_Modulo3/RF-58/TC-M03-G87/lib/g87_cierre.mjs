// Cierre y verificación con dependencias inyectables para validación local sin red.
export function estadoMarcador(cierre) {
  return [200, 404].includes(cierre?.run?.cierre_http) && cierre?.rollback?.verificado === true
    ? 'CERRADO' : cierre?.run?.cierre_http != null ? 'CIERRE_INTENTADO' : 'PENDIENTE';
}

export async function asegurarSesionVigente(rol, tokens, solicitar, credenciales) {
  const prueba = tokens[rol] ? await solicitar('GET', '/usuarios/me', { token: tokens[rol], etiqueta: `Vigencia ${rol}` })
    : { status: 401 };
  if (prueba.status === 200) return true;
  const cuenta = credenciales[rol];
  const login = await solicitar('POST', '/sesiones/', { cuerpo: { correo_electronico: cuenta.correo, contrasena: cuenta.clave },
    etiqueta: `Renovación ${rol}` });
  if (login.status !== 200 || !login.json?.token) return false;
  tokens[rol] = login.json.token;
  return true;
}

export function cierreUnico(accion) {
  let pendiente;
  return () => { if (!pendiente) pendiente = Promise.resolve().then(accion); return pendiente; };
}

export function instalarSenales(cerrar, salir = (codigo) => { process.exitCode = codigo; }) {
  const nombres = ['SIGINT', 'SIGTERM', ...(process.platform === 'win32' ? ['SIGBREAK'] : [])];
  const manejador = () => { void cerrar().finally(() => salir(130)); };
  for (const n of nombres) process.on(n, manejador);
  return () => { for (const n of nombres) process.off(n, manejador); };
}

export async function cerrarYVerificar({ runId, secreto, datos, tokens, credenciales, solicitar, onToken = () => {}, solicitarCierre = true,
  cierrePrevioHttp = null }) {
  const salida = { run: { intentos: [], cierre_http: null }, rollback: { verificado: false, conclusion: 'NO_CONCLUYENTE', asociaciones_actuales: {},
    ocupacion_area: null, historial: {} }, errores: [] };
  // Una solicitud de cierre por host: repetir DELETE no aporta evidencia y puede confundir la bitácora.
  if (solicitarCierre) {
    try {
      const x = await solicitar('DELETE', `/test-control/runs/${runId}`, { secreto, etiqueta: 'Cierre del RUN' });
      salida.run.cierre_http = x.status;
      salida.run.intentos.push({ host: 'API', http: x.status });
    } catch (e) { salida.errores.push(`Cierre API: ${e.message}`); }
  } else salida.run.cierre_http = cierrePrevioHttp;
  if (salida.run.cierre_http !== 200 && salida.run.cierre_http !== 404) return salida;
  // El DELETE termina la sesión de BD del RUN. Validar después del cierre y renovar
  // fuera del sandbox si el token inicial quedó revocado; solo entonces leer rollback.
  let vigente = false;
  try { vigente = await asegurarSesionVigente('admin', tokens, solicitar, credenciales); if (vigente) onToken(tokens.admin); }
  catch (e) { salida.errores.push(`Renovación Administrador: ${e.message}`); }
  try {
    if (!vigente) { salida.errores.push('Administrador sin sesión vigente.'); return salida; }
    for (const s of [datos.bloqueo_s1 ? null : datos.s1, datos.bloqueo_s2 ? null : datos.s2].filter(Boolean)) {
      const x = await solicitar('GET', `/configuracion/sensores/${s.id}/asociaciones`,
        { token: tokens.admin, etiqueta: `Rollback asociación ${s.id}` });
      if (x.status !== 200 || !Array.isArray(x.json?.items)) { salida.errores.push(`Asociaciones ${s.id}: HTTP ${x.status}`); continue; }
      salida.rollback.asociaciones_actuales[s.id] = x.json.items.find((a) => !a.fecha_finalizacion)?.id_infraestructura ?? null;
    }
    const dashboard = await solicitar('GET', `/iot/monitoreo/dashboard?id_infraestructura=${datos.area}&por_pagina=50`,
      { token: tokens.admin, etiqueta: 'Rollback dashboard' });
    salida.rollback.dashboard_http = dashboard.status;
    if (dashboard.status === 200 && Number.isInteger(dashboard.json?.total))
      salida.rollback.ocupacion_area = dashboard.json.total;
    const ts = Object.values(datos.lecturas?.ts ?? {}).map(Date.parse);
    if (ts.length && ts.every(Number.isFinite)) {
      const fechas = [new Date(Math.min(...ts) - 600000).toISOString().slice(0, 10),
        new Date(Math.max(...ts) + 600000).toISOString().slice(0, 10)];
      for (const s of [datos.bloqueo_s1 ? null : datos.s1, datos.bloqueo_s2 ? null : datos.s2].filter(Boolean)) {
        const ruta = `/iot/monitoreo/historial?sensor_id=${s.id}&fecha_inicio=${fechas[0]}&fecha_fin=${fechas[1]}`;
        const h = await solicitar('GET', ruta, { token: tokens.admin, etiqueta: `Rollback historial ${s.id}` });
        const items = h.json?.items;
        const ids = new Set(datos.ids_telemetria ?? []);
        const encontrados = Array.isArray(items) ? items.filter((x) => ids.has(x.id_telemetria)
          || (Date.parse(x.timestamp_captura) >= Math.min(...ts) - 600000 && Date.parse(x.timestamp_captura) <= Math.max(...ts) + 600000)) : [];
        salida.rollback.historial[s.id] = { http: h.status, completo: h.status === 200 && Array.isArray(items)
          && h.json.total === items.length, coincidencias: encontrados.map((x) => x.id_telemetria) };
      }
    }
    const h = Object.values(salida.rollback.historial);
    const cantidadSensores = Number(!datos.bloqueo_s1 && !!datos.s1) + Number(!datos.bloqueo_s2 && !!datos.s2);
    const baseConforme = [200, 404].includes(salida.run.cierre_http) && dashboard.status === 200
      && salida.rollback.ocupacion_area === datos.ocupacion_inicial
      && (datos.bloqueo_s1 || salida.rollback.asociaciones_actuales[datos.s1.id] === datos.s1.area_original)
      && (datos.bloqueo_s2 || salida.rollback.asociaciones_actuales[datos.s2.id] === datos.s2.area_original);
    const historialCompleto = h.length === cantidadSensores
      && h.every((x) => x.completo && x.coincidencias.length === 0);
    salida.rollback.verificado = baseConforme && historialCompleto;
    salida.rollback.conclusion = salida.rollback.verificado ? 'ROLLBACK_CONFIRMADO'
      : baseConforme && h.length === cantidadSensores
        && h.every((x) => [403, 404].includes(x.http) && x.coincidencias.length === 0)
        ? 'ROLLBACK_RESPALDADO_INDIRECTO' : 'NO_CONCLUYENTE';
  } catch (e) { salida.errores.push(`Verificación: ${e.message}`); }
  return salida;
}
