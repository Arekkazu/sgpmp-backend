export const CASOS = Object.freeze(['TC-M03-181', 'TC-M03-182', 'TC-M03-183']);
export const OBLIGATORIAS = Object.freeze({
  'TC-M03-181': { API: ['API-181-01', 'API-181-02'] },
  'TC-M03-182': { API: ['API-182-01', 'API-182-02'] },
  'TC-M03-183': { API: ['API-183-01', 'API-183-02'] },
});
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1',
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: '1..n',
  comprobaciones_obligatorias: OBLIGATORIAS });
export const LIMITE = Object.freeze({ solicitudes_directas: 525, margen_cierre: 4, newman: 4,
  sensores_referencia: 5,
  areas: 2, dispositivos: 2, sensores: 63, asociaciones: 63, calibraciones: 63,
  telemetrias: 63, alertas: 3, transiciones: 0 });
export const ORACULO = Object.freeze({
  'TC-M03-181': 'Resumen ROJO como peor estado entre VERDE, AMARILLO y ROJO; alertas activas y timestamp de actualización.',
  'TC-M03-182': 'El monitoreo filtrado muestra solo sensores e información de la unidad seleccionada, sin datos de otras unidades.',
  'TC-M03-183': 'Con 60 sensores y único ROJO en posición 55, pagina=1&por_pagina=50 mantiene estado_general=ROJO aunque el sensor ROJO no figura en la página.',
});
export function planTemporal(inicio = new Date().toISOString()) {
  const t = Date.parse(inicio) - 120_000;
  if (!Number.isFinite(t)) throw new Error('INICIO_INVALIDO');
  return { inicio, ancla: new Date(t).toISOString(),
    marcas: [10, 5, 0].map((s) => new Date(t - s * 1000).toISOString()) };
}
export function identidadDashboard(paginas) {
  if (!paginas.length || !paginas.every((p) => Number.isInteger(Number(p.total)) &&
    Array.isArray(p.sensores) && Array.isArray(p.resumen_unidades))) return null;
  const ids = paginas.flatMap((p) => p.sensores.map((s) => [Number(s.id_sensor), Number(s.id_infraestructura)]));
  const total = Number(paginas[0].total);
  if (ids.length !== total || ids.some(([sensor, area]) => !Number.isSafeInteger(sensor) || sensor <= 0 ||
    !Number.isSafeInteger(area) || area <= 0) || new Set(ids.map(([id]) => id)).size !== total ||
    !paginas.every((p) => Number(p.total) === total)) return null;
  const resumen = paginas[0].resumen_unidades.map((u) => [Number(u.id_infraestructura),
    Number(u.total_sensores), Number(u.alertas_activas_count)]).sort((a, b) => a[0] - b[0]);
  if (resumen.some(([area, sensores, alertas]) => !Number.isSafeInteger(area) || area <= 0 ||
    !Number.isSafeInteger(sensores) || sensores < 0 || !Number.isSafeInteger(alertas) || alertas < 0) ||
    new Set(resumen.map(([area]) => area)).size !== resumen.length) return null;
  return { total, sensores: ids.sort((a, b) => a[0] - b[0]), resumen };
}
export function compararDashboard(pre, post) {
  const a = identidadDashboard(pre), b = identidadDashboard(post);
  return a !== null && b !== null && JSON.stringify(a) === JSON.stringify(b);
}
export function semillaEstable(tipo, x) {
  if (!x) return null;
  const campos = { finca: ['id_finca', 'nombre', 'es_activo'], area: ['id_infraestructura', 'id_finca', 'especie_id', 'nombre_infraestructura', 'es_activo', 'tipo_area'],
    dispositivo: ['id_dispositivo_iot', 'id_infraestructura', 'id_tipo_dispositivo', 'serial', 'categoria', 'es_activo'],
    sensor: ['id_sensores', 'id_dispositivo_iot', 'nombre', 'es_activo', 'categoria'],
    asociacion: ['id_sensores_area_asociada', 'id_sensor', 'id_dispositivo_iot', 'id_infraestructura', 'punto_instalacion', 'tiene_estado', 'fecha_asociacion', 'fecha_finalizacion'],
    calibracion: ['id_calibracion', 'id_dispositivo_iot', 'id_sensor', 'valor_referencia', 'ganancia', 'offset', 'fecha_calibracion', 'modo_calibracion'],
    umbral: ['id_umbral_ambiental', 'id_especie', 'id_variable_ambiental', 'es_activo', 'niveles'] }[tipo];
  return Object.fromEntries(campos.filter((k) => Object.hasOwn(x, k)).map((k) => [k, x[k]]));
}
export function diagnosticarPagina({ inicial, a1, a2, b1, alcanceA, alcanceB, areaA, areaB, alertasActivas }) {
  const sensoresA = [...(a1?.sensores ?? []), ...(a2?.sensores ?? [])];
  const unicos = new Set(sensoresA.map((s) => Number(s.id_sensor)));
  const rojos = sensoresA.filter((s) => s.estado_semaforo === 'ROJO');
  const rA1 = (a1?.resumen_unidades ?? []).find((x) => Number(x.id_infraestructura) === areaA);
  const rA2 = (a2?.resumen_unidades ?? []).find((x) => Number(x.id_infraestructura) === areaA);
  const rB = (b1?.resumen_unidades ?? []).find((x) => Number(x.id_infraestructura) === areaB);
  const colores = new Set((inicial?.sensores ?? []).map((s) => s.estado_semaforo));
  const rInicial = (inicial?.resumen_unidades ?? []).find((x) => Number(x.id_infraestructura) === areaB);
  const campoVariable = rInicial && Object.entries(rInicial).find(([k, v]) =>
    /variable/i.test(k) && (/(atenci[oó]n|cr[ií]tic)/i.test(k)
      || (typeof v === 'object' && v !== null && Object.entries(v)
        .some(([subclave]) => /(atenci[oó]n|cr[ií]tic)/i.test(subclave)))));
  const coloresIniciales = new Set((inicial?.sensores ?? []).map((s) => s.estado_semaforo));
  const pre181 = Number(inicial?.total) === 3 && inicial?.sensores?.length === 3 &&
    (inicial.sensores ?? []).every((s) => Number(s.id_infraestructura) === areaB) &&
    ['VERDE', 'AMARILLO', 'ROJO'].every((x) => coloresIniciales.has(x));
  const pre182 = alcanceA === true && alcanceB === true &&
    Number(a1?.total) === 60 && a1?.sensores?.length === 50 &&
    (a1?.resumen_unidades ?? []).some((x) => Number(x.id_infraestructura) === areaA) &&
    Number(b1?.total) === 3 && b1?.sensores?.length === 3 &&
    (b1?.resumen_unidades ?? []).some((x) => Number(x.id_infraestructura) === areaB);
  const pre183 = Number(a1?.total) === 60 && Number(a2?.total) === 60 &&
    a1?.sensores?.length === 50 && a2?.sensores?.length === 10 && unicos.size === 60 &&
    rojos.length === 1 && Number(a2.sensores[4]?.id_sensor) === Number(rojos[0]?.id_sensor) &&
    sensoresA.every((s) => s === rojos[0] || s.estado_semaforo === 'VERDE');
  const checks = {
    'PRE-181-01': pre181,
    'API-181-01': pre181 && rInicial?.estado_general === 'ROJO',
    'API-181-02': Number(rInicial?.alertas_activas_count) === 2 && rInicial?.ultimo_dato_recibido != null,
    'API-181-03': Boolean(campoVariable),
    'PRE-182-01': pre182,
    'API-182-01': pre182 && Number(a1.total) === 60 && Number(a2.total) === 60 &&
      sensoresA.every((s) => Number(s.id_infraestructura) === areaA) &&
      (b1.sensores ?? []).every((s) => Number(s.id_infraestructura) === areaB) &&
      !(b1.sensores ?? []).some((s) => unicos.has(Number(s.id_sensor))) &&
      Number(rA1?.total_sensores) === 60 && Number(rB?.total_sensores) === 3,
    'API-182-02': pre182 && a1.resumen_unidades.length === 1 && rA1 != null &&
      b1.resumen_unidades.length === 1 && rB != null,
    'PRE-183-01': pre183,
    'API-183-01': pre183,
    'API-183-02': pre183 && rA1?.estado_general === 'ROJO',
  };
  const exponerResumen = (u) => u ? {
    id_infraestructura: u.id_infraestructura, total_sensores: u.total_sensores,
    estado_general: u.estado_general, alertas_activas_count: u.alertas_activas_count,
    ultimo_dato_recibido: u.ultimo_dato_recibido } : null;
  return { checks, observado: { total_a: a1?.total, total_b: b1?.total,
    pagina1: a1?.sensores?.length, pagina2: a2?.sensores?.length,
    posicion_rojo: rojos.length === 1 ? sensoresA.findIndex((s) => s === rojos[0]) + 1 : null,
    colores: [...colores], resumen_inicial: exponerResumen(rInicial),
    resumen_a_p1: exponerResumen(rA1), resumen_a_p2: exponerResumen(rA2),
    resumen_b: exponerResumen(rB), variable_en_resumen: campoVariable?.[0] ?? null,
    variables_en_atencion_criticas_sensores: (inicial?.sensores ?? [])
      .filter((s) => ['AMARILLO', 'ROJO'].includes(s.estado_semaforo))
      .map((s) => ({ id_sensor: s.id_sensor, tipo_variable: s.tipo_variable,
        estado_semaforo: s.estado_semaforo })),
    unidad_a_pagina2_estado_general: rA2?.estado_general ?? null,
    unidad_a_peor_60: ['ROJO', 'AMARILLO', 'GRIS', 'VERDE'].find((c) => sensoresA.some((s) => s.estado_semaforo === c)) ?? null,
    sensores_con_tipo_variable: (inicial?.sensores ?? []).filter((s) => s.tipo_variable != null).length,
    alertas_activas_creadas: alertasActivas } };
}
