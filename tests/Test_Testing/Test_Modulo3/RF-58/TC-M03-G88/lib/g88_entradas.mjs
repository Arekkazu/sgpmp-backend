// RF-58 CA-2/CA-16: datos derivados del umbral existente, sin modificar M09.
export function derivarEntradas(min, max, fisicoMin, fisicoMax, decimales = 2) {
  if (![min, max, fisicoMin, fisicoMax, decimales].every(Number.isFinite)
      || min >= max || fisicoMin >= fisicoMax || !Number.isInteger(decimales)
      || decimales < 0 || decimales > 6) throw new Error('Rango o precisión inválidos.');
  const T = (max - min) * 0.1;
  const redondear = (n) => Number(n.toFixed(decimales));
  const filas = [
    ['169a', min, 'VERDE', (v) => v === min], ['169b', (min + max) / 2, 'VERDE', (v) => v > min && v < max],
    ['169c', max, 'VERDE', (v) => v === max],
    ['170a', min - .9 * T, 'AMARILLO', (v) => v > min - T && v < min],
    ['170b', min - .1 * T, 'AMARILLO', (v) => v > min - T && v < min],
    ['170c', max + .1 * T, 'AMARILLO', (v) => v > max && v < max + T],
    ['170d', max + .9 * T, 'AMARILLO', (v) => v > max && v < max + T],
    ['171a', min - 1.1 * T, 'ROJO', (v) => v < min - T],
    ['171b', max + 1.1 * T, 'ROJO', (v) => v > max + T],
  ];
  return { min, max, T, decimales, entradas: filas.map(([clave, bruto, esperado, intervalo]) => {
    const valor = redondear(bruto);
    const preparable = valor >= fisicoMin && valor <= fisicoMax && intervalo(valor);
    return { clave, valor, esperado, preparable, motivo: preparable ? null : 'Redondeo o rango físico incompatible.' };
  }) };
}

export function invertirCalibracion(objetivo, ganancia, offset, fisicoMin, fisicoMax, decimales = 2) {
  const enviado = (objetivo - offset) / ganancia;
  const preparable = [objetivo, ganancia, offset, fisicoMin, fisicoMax, enviado].every(Number.isFinite)
    && ganancia !== 0 && enviado >= fisicoMin && enviado <= fisicoMax
    && Math.abs(Number((enviado * ganancia + offset).toFixed(decimales)) - objetivo) < 1e-8;
  return { valor_enviado: preparable ? enviado : null, preparable };
}

// RF-61-A: la lista completa del área permite acreditar la unicidad antes de ingerir.
export function activoUnicoVinculable(respuesta, areaId, activoId) {
  const registros = respuesta?.registros;
  const total = Number(respuesta?.total_registros);
  if (!Array.isArray(registros) || !Number.isInteger(total) || total < registros.length || total > 100)
    return { ok: false, motivo: 'Listado de activos incompleto o no verificable.' };
  const vinculables = registros.filter((x) => [1, 3, 4].includes(Number(x.id_estado)));
  const unico = vinculables[0];
  return vinculables.length === 1 && Number(unico.id_activo_biologico) === activoId
    && Number(unico.id_infraestructura) === areaId && Number(unico.id_estado) === 1
    && unico.identificador === 'QA-G88-IND-001' && (unico.tipo ?? unico.tipo_activo) === 'INDIVIDUAL'
    ? { ok: true, motivo: null }
    : { ok: false, motivo: `Área ${areaId}: ${vinculables.length} activos vinculables; no se acredita el activo ${activoId}.` };
}

export function lecturaVinculada(respuesta, telemetriaId, activoId, areaId = 349) {
  const items = respuesta?.items;
  if (!Array.isArray(items)) return { ok: false, motivo: 'Respuesta de vinculaciones no verificable.' };
  const propios = items.filter((x) => Number(x.id_telemetria) === telemetriaId
    && !x.fecha_fin_vinculacion && x.estado_vinculacion !== 'CORREGIDA');
  const x = propios[0];
  return propios.length === 1 && x.estado_vinculacion === 'VINCULADA'
    && Number(x.id_activo_biologico) === activoId && Number(x.id_infraestructura) === areaId
    ? { ok: true, motivo: null }
    : { ok: false, motivo: `Lectura ${telemetriaId}: estado=${x?.estado_vinculacion ?? 'SIN_VINCULACION'}, activo=${x?.id_activo_biologico ?? 'ausente'}, área=${x?.id_infraestructura ?? 'ausente'}, registros=${propios.length}; esperado VINCULADA a ${activoId} en ${areaId}.` };
}

export function lecturaVinculadaHistorial(respuesta, telemetriaId, activoId, sensorId) {
  const items = respuesta?.items;
  if (!Array.isArray(items)) return { ok: false, motivo: 'Historial no verificable.' };
  const propios = items.filter((x) => Number(x.id_telemetria) === telemetriaId
    && Number(x.id_sensor) === sensorId);
  return propios.length === 1 && Number(propios[0].id_activo_biologico) === activoId
    ? { ok: true, motivo: null }
    : { ok: false, motivo: `Historial de lectura ${telemetriaId}: ${propios.length} registros, activo=${propios[0]?.id_activo_biologico ?? 'ausente'}; esperado ${activoId}.` };
}

// Conservar la respuesta de la consulta para el caso actual aunque la ruta ya
// tenga una instantánea anterior para el rollback del RUN completo.
export function conservarAnterior(previos, actual) {
  const umbral = actual.umbral;
  const dashboard = actual.dashboard;
  for (const [rutaCampo, datoCampo] of [['ruta_asociaciones', 'asociaciones'],
    ['ruta_dashboard', 'dashboard'], ['ruta_umbral', 'umbral']]) {
    if (previos.some((p) => p[rutaCampo] === actual[rutaCampo])) {
      delete actual[rutaCampo]; delete actual[datoCampo];
    }
  }
  if (actual.ruta_asociaciones || actual.ruta_dashboard || actual.ruta_umbral) previos.push(actual);
  return { umbral, dashboard };
}

export function asociacionVigente(respuesta, asociacionId, areaId) {
  if (!Array.isArray(respuesta?.items) || (respuesta.total != null
    && Number(respuesta.total) !== respuesta.items.length)) return false;
  const vigentes = respuesta.items.filter((x) => x.tiene_estado === true && !x.fecha_finalizacion);
  const x = vigentes[0];
  const id = x?.id_sensores_area_asociada ?? x?.id_asociacion ?? x?.id_sensor_area_asociada
    ?? x?.id_sensores_areas_asociadas ?? x?.id_asociacion_sensor_area
    ?? x?.id_sensor_area ?? x?.id_asociacion_sensor;
  return vigentes.length === 1 && Number(id) === Number(asociacionId)
    && Number(x.id_infraestructura) === Number(areaId);
}

export function rangoHistorial(ahora = Date.now()) {
  return { inicio: new Date(ahora - 86400000).toISOString().slice(0, 10),
    fin: new Date(ahora).toISOString().slice(0, 10) };
}

export const campoT = (nombre) => /(?:toleran|toleranc|tolerancia|tolerance|^t$|^t_|_t$)/i.test(nombre);
export function camposUmbral(umbrales) {
  return umbrales.map((u) => ({
    campos: Object.keys(u).sort(),
    niveles: Array.isArray(u.niveles) ? u.niveles.map((n) => Object.keys(n).sort()) : [],
  }));
}
export function ausenciaT(umbrales) {
  const listas = camposUmbral(umbrales);
  return listas.length > 0 && listas.every((u) =>
    !u.campos.some(campoT) && u.niveles.every((n) => !n.some(campoT)));
}
