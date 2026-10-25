export const CASOS = Object.freeze(['TC-M03-181', 'TC-M03-182', 'TC-M03-183']);
export const OBLIGATORIAS = Object.freeze({
  'TC-M03-181': { API: ['API-181-01', 'API-181-02', 'API-181-03'] },
  'TC-M03-182': { API: ['API-182-01', 'API-182-02'] },
  'TC-M03-183': { API: ['API-183-01', 'API-183-02'] },
});
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1',
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: '1..n',
  comprobaciones_obligatorias: OBLIGATORIAS });
export const LIMITE = Object.freeze({ solicitudes_directas: 296, newman: 5,
  areas: 2, dispositivos: 2, sensores: 63, asociaciones: 63, calibraciones: 63,
  telemetrias: 63, alertas: 3, transiciones: 0 });
export const ORACULO = Object.freeze({
  'TC-M03-181': 'Resumen ROJO como peor estado entre VERDE, AMARILLO y ROJO; variables en atención/críticas, alertas activas y timestamp de actualización.',
  'TC-M03-182': 'El monitoreo filtrado muestra solo sensores e información de la unidad seleccionada, sin datos de otras unidades.',
  'TC-M03-183': 'Con 60 sensores y único ROJO en posición 55, pagina=1&por_pagina=50 mantiene estado_general=ROJO aunque el sensor ROJO no figura en la página.',
});
export function planTemporal(inicio = new Date().toISOString()) {
  const t = Date.parse(inicio) - 120_000;
  if (!Number.isFinite(t)) throw new Error('INICIO_INVALIDO');
  return { inicio, ancla: new Date(t).toISOString(),
    marcas: [10, 5, 0].map((s) => new Date(t - s * 1000).toISOString()) };
}
export function diagnosticarPagina({ inicial, a1, a2, b1, libre, areaA, areaB, alertasActivas }) {
  const sensoresA = [...(a1?.sensores ?? []), ...(a2?.sensores ?? [])];
  const unicos = new Set(sensoresA.map((s) => Number(s.id_sensor)));
  const rojos = sensoresA.filter((s) => s.estado_semaforo === 'ROJO');
  const rA1 = (a1?.resumen_unidades ?? []).find((x) => Number(x.id_infraestructura) === areaA);
  const rA2 = (a2?.resumen_unidades ?? []).find((x) => Number(x.id_infraestructura) === areaA);
  const rB = (b1?.resumen_unidades ?? []).find((x) => Number(x.id_infraestructura) === areaB);
  const colores = new Set((inicial?.sensores ?? []).map((s) => s.estado_semaforo));
  const rInicial = (inicial?.resumen_unidades ?? []).find((x) => Number(x.id_infraestructura) === areaB);
  const presente = (v) => v != null && (Array.isArray(v) ? v.length > 0
    : typeof v === 'object' ? Object.keys(v).length > 0 : Boolean(v));
  const campoVariable = rInicial && Object.entries(rInicial).find(([k, v]) =>
    /variable/i.test(k) && presente(v) && (/(atenci[oó]n|cr[ií]tic)/i.test(k)
      || (typeof v === 'object' && v !== null && Object.entries(v)
        .some(([subclave, subvalor]) => /(atenci[oó]n|cr[ií]tic)/i.test(subclave) && presente(subvalor)))));
  const coloresIniciales = new Set((inicial?.sensores ?? []).map((s) => s.estado_semaforo));
  const pre181 = Number(inicial?.total) === 3 && inicial?.sensores?.length === 3 &&
    (inicial.sensores ?? []).every((s) => Number(s.id_infraestructura) === areaB) &&
    ['VERDE', 'AMARILLO', 'ROJO'].every((x) => coloresIniciales.has(x));
  const pre182 = (libre?.resumen_unidades ?? []).some((x) => Number(x.id_infraestructura) === areaA)
    && (libre?.resumen_unidades ?? []).some((x) => Number(x.id_infraestructura) === areaB)
    && Number(b1?.total) === 3 && b1?.sensores?.length === 3;
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
    sensores_con_tipo_variable: (inicial?.sensores ?? []).filter((s) => s.tipo_variable != null).length,
    alertas_activas_creadas: alertasActivas } };
}
