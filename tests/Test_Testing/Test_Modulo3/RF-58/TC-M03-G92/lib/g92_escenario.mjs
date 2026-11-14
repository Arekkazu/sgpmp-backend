export const CASOS = Object.freeze(['TC-M03-181', 'TC-M03-182', 'TC-M03-183']);
export const OBLIGATORIAS = Object.freeze({
  'TC-M03-181': { API: ['API-181-01', 'API-181-02'] },
  'TC-M03-182': { API: ['API-182-01', 'API-182-02'] },
  'TC-M03-183': { API: ['API-183-01', 'API-183-02'] },
});
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1',
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: '1..n',
  comprobaciones_obligatorias: OBLIGATORIAS });
export const SEMILLA = Object.freeze({ finca: 184, especie: 126,
  areas: [697, 698], dispositivos: [785, 786],
  sensoresA: Array.from({ length: 60 }, (_, i) => 1142 + i), sensoresB: [1202, 1203, 1204],
  asociacionInicial: 804, calibracionInicial: 319,
  asociadaDesde: '2026-10-30T01:44:00Z' });
export const LIMITE = Object.freeze({ solicitudes_directas: 415, margen_cierre: 4, newman: 1,
  areas: 0, dispositivos: 0, sensores: 2, asociaciones: 0, calibraciones: 0,
  telemetrias: 63, alertas: 2, transiciones: 0 });
export const ORACULO = Object.freeze({
  'TC-M03-181': 'El resumen de la unidad presenta ROJO como estado general (peor estado presente), incluyendo variables en atención/críticas, alertas activas asociadas y timestamp de actualización.',
  'TC-M03-182': 'El monitoreo filtrado muestra solo sensores e información de la unidad seleccionada, sin datos de otras unidades.',
  'TC-M03-183': 'Con 60 sensores y único ROJO en posición 55, pagina=1&por_pagina=50 mantiene estado_general=ROJO aunque el sensor ROJO no figura en la página.',
});
export const VALORES = Object.freeze({ VERDE: 25 });
export const VALORES_ALERTA = Object.freeze({ ROJO: 29 });
export const cuerpoSensor = (indice) => ({ nombre: `QA G92 sensor ${indice}`,
  categoria: 'TEMPERATURA' });
export function validarSemillaPersistente(datos, seriales, apertura) {
  const errores = [];
  const exigir = (si, codigo) => { if (!si) errores.push(codigo); };
  exigir(Number(datos.finca?.id_finca) === SEMILLA.finca && datos.finca?.es_activo === true, 'FINCA');
  for (const [i, area] of SEMILLA.areas.entries()) {
    const a = datos.areas?.[i], d = datos.dispositivos?.[i];
    exigir(Number(a?.id_infraestructura) === area && Number(a?.id_finca) === SEMILLA.finca &&
      Number(a?.especie_id) === SEMILLA.especie && a?.es_activo === true &&
      a?.nombre_infraestructura === `QA G92 Unidad ${i ? 'B' : 'A'}` &&
      a?.id_activo_biologico == null, `AREA_${area}`);
    exigir(Number(d?.id_dispositivo_iot) === SEMILLA.dispositivos[i] &&
      Number(d?.id_infraestructura) === area && d?.es_activo === true &&
      d?.categoria === 'SENSOR' &&
      d?.id_dispositivo_gateway == null && d?.serial === seriales[i], `DISPOSITIVO_${SEMILLA.dispositivos[i]}`);
    const esperados = i ? SEMILLA.sensoresB : SEMILLA.sensoresA;
    const lista = datos.sensores?.[i] ?? [];
    exigir(lista.length === esperados.length && lista.every((s, pos) =>
      Number(s.id_sensores) === esperados[pos] &&
      Number(s.id_dispositivo_iot) === SEMILLA.dispositivos[i] &&
      s.es_activo === true && s.categoria === 'TEMPERATURA'), `SENSORES_${area}`);
  }
  const ids = [...SEMILLA.sensoresA, ...SEMILLA.sensoresB];
  for (const [i, id] of ids.entries()) {
    const a = datos.asociaciones?.[i] ?? [], c = datos.calibraciones?.[i] ?? [];
    const area = i < 60 ? 697 : 698, dispositivo = i < 60 ? 785 : 786;
    exigir(a.length === 1 && Number(a[0]?.id_sensores_area_asociada) === SEMILLA.asociacionInicial + i &&
      Number(a[0]?.id_sensor) === id && Number(a[0]?.id_dispositivo_iot) === dispositivo &&
      Number(a[0]?.id_infraestructura) === area && a[0]?.tiene_estado === true &&
      a[0]?.fecha_finalizacion == null && Number.isFinite(Date.parse(a[0]?.fecha_asociacion)) &&
      Date.parse(a[0]?.fecha_asociacion) >= Date.parse(SEMILLA.asociadaDesde) &&
      Date.parse(a[0]?.fecha_asociacion) < Date.parse('2026-10-30T01:45:00Z') &&
      Date.parse(a[0]?.fecha_asociacion) < apertura - 60_000, `ASOCIACION_${id}`);
    exigir(c.length === 1 && Number(c[0]?.id_calibracion) === SEMILLA.calibracionInicial + i &&
      Number(c[0]?.id_sensor) === id && Number(c[0]?.id_dispositivo_iot) === dispositivo &&
      Number(c[0]?.valor_referencia) === 25 && Number(c[0]?.ganancia) === 1 &&
      Number(c[0]?.offset) === 0 && c[0]?.modo_calibracion === 'SENSOR' &&
      Number.isFinite(Date.parse(c[0]?.fecha_calibracion)) &&
      String(c[0]?.fecha_calibracion).startsWith('2026-10-30') &&
      Date.parse(c[0]?.fecha_calibracion) < apertura - 60_000, `CALIBRACION_${id}`);
  }
  exigir((datos.alertas ?? []).every((x) => Number(x.total) === 0 && x.items?.length === 0), 'ALERTAS_PREVIAS');
  exigir((datos.historial ?? []).every((x) => Number(x.total_encontrado ?? x.total) === 0 && x.items?.length === 0), 'HISTORIAL_PREVIO');
  return errores;
}
export function cuerpoTelemetria({ dispositivo, sensor, serial, marca, color = 'VERDE', valor = VALORES[color] }) {
  return { device_id: dispositivo, sensor_id: sensor, serial,
    tipo_variable: 'TEMPERATURA_AMBIENTAL', valor, unidad: '°C',
    timestamp_captura: marca, nivel_bateria: 81, calidad_senal_rssi: -71,
    calidad_senal_snr: 7.5 };
}
export function cuerpoAlerta({ dispositivo, sensor, serial, marca, telemetria, color }) {
  const severidad = color === 'ROJO' ? 'CRITICO' : 'LEVE';
  return { device_id: dispositivo, sensor_id: sensor, serial,
    tipo_variable: 'TEMPERATURA_AMBIENTAL', valor: VALORES_ALERTA[color], unidad: '°C',
    timestamp_evento: marca, estado_dato: 'LECTURA_VALIDA', severidad_edge: severidad,
    origen_evento: 'EDGE', id_telemetria: telemetria, reglas_activadas: [],
    correlacion_variables: { HUMEDAD_RELATIVA: 100 } };
}
export function registrarAlertaDeArea(respuesta, area, creadas) {
  if (!Number.isSafeInteger(area) || area <= 0) throw new Error('ALERTA_AREA_INVALIDA');
  const id = Number(respuesta?.id_alerta);
  if (!Number.isSafeInteger(id) || id <= 0) throw new Error('ALERTA_SIN_ID');
  if (respuesta.es_duplicado === true) {
    if (Number(respuesta.alerta_existente_id) !== id || creadas.get(id) !== area)
      throw new Error('ALERTA_DUPLICADA_ERROR_QA');
    return { id, nueva: false, consolidada: true };
  }
  if (respuesta.es_duplicado !== false || creadas.has(id) || [...creadas.values()].includes(area))
    throw new Error('ALERTA_DUPLICADA_ERROR_QA');
  creadas.set(id, area);
  return { id, nueva: true, consolidada: false };
}
export function estadoDashboard(v) {
  if (!v || !Array.isArray(v.sensores) || !Array.isArray(v.resumen_unidades)) return null;
  return {
    total: Number(v.total),
    sensores: v.sensores.map((s) => ({ id: Number(s.id_sensor),
      color: s.estado_semaforo ?? null, valor: s.ultimo_valor ?? null,
      captura: s.ultimo_timestamp_captura ?? null, alerta: s.id_alerta ?? null })),
    resumen: v.resumen_unidades.map((u) => ({ id: Number(u.id_infraestructura),
      estado: u.estado_general ?? null, alertas: Number(u.alertas_activas_count) }))
  };
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
  const criticosB = (inicial?.sensores ?? []).filter((s) => s.estado_semaforo === 'ROJO');
  const alertasB = inicial?.panel_alertas_activas?.alertas ?? [];
  const alertaAsociada = criticosB.some((s) => Number.isSafeInteger(Number(s.id_alerta)) &&
    Number(s.id_alerta) > 0 && s.severidad_alerta === 'CRITICO' &&
    alertasB.some((a) => Number(a.id_alerta) === Number(s.id_alerta) &&
      Number(a.id_infraestructura) === areaB && a.severidad === 'CRITICO'));
  const coloresIniciales = new Set((inicial?.sensores ?? []).map((s) => s.estado_semaforo));
  const pre181 = Number(inicial?.total) === 3 && inicial?.sensores?.length === 3 &&
    (inicial.sensores ?? []).every((s) => Number(s.id_infraestructura) === areaB) &&
    ['VERDE', 'ROJO'].every((x) => coloresIniciales.has(x));
  const pre182 = alcanceA === true && alcanceB === true &&
    Number(a1?.total) === 60 && a1?.sensores?.length === 50 &&
    (a1?.resumen_unidades ?? []).some((x) => Number(x.id_infraestructura) === areaA) &&
    Number(b1?.total) === 3 && b1?.sensores?.length === 3 &&
    (b1?.resumen_unidades ?? []).some((x) => Number(x.id_infraestructura) === areaB);
  const pre183 = Number(a1?.total) === 60 && Number(a2?.total) === 60 &&
    a1?.sensores?.length === 50 && a2?.sensores?.length === 10 && unicos.size === 60 &&
    rojos.length === 1 && Number(rojos[0]?.id_sensor) === 1196 &&
    Number(a2.sensores[4]?.id_sensor) === 1196 &&
    sensoresA.every((s) => s === rojos[0] || s.estado_semaforo === 'VERDE');
  const checks = {
    'PRE-181-01': pre181,
    'API-181-01': pre181 && rInicial?.estado_general === 'ROJO',
    'API-181-02': Number(rInicial?.alertas_activas_count) >= 1 && alertaAsociada,
    'API-181-03': Number.isFinite(Date.parse(rInicial?.ultimo_dato_recibido)) &&
      criticosB.some((s) => Boolean(s.tipo_variable)),
    'PRE-182-01': pre182,
    'API-182-01': pre182 && Number(a1.total) === 60 && Number(a2.total) === 60 &&
      sensoresA.every((s) => Number(s.id_infraestructura) === areaA) &&
      (b1.sensores ?? []).every((s) => Number(s.id_infraestructura) === areaB) &&
      !(b1.sensores ?? []).some((s) => unicos.has(Number(s.id_sensor))) &&
      Number(rA1?.total_sensores) === 60 && Number(rB?.total_sensores) === 3,
    'API-182-02': pre182 && a1.resumen_unidades.length === 1 && rA1 != null &&
      a2.resumen_unidades.length === 1 && rA2 != null &&
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
    ids_ajenos: [...(a1?.sensores ?? []).filter((s) => Number(s.id_infraestructura) !== areaA),
      ...(a2?.sensores ?? []).filter((s) => Number(s.id_infraestructura) !== areaA),
      ...(b1?.sensores ?? []).filter((s) => Number(s.id_infraestructura) !== areaB),
      ...(a1?.resumen_unidades ?? []).filter((u) => Number(u.id_infraestructura) !== areaA),
      ...(a2?.resumen_unidades ?? []).filter((u) => Number(u.id_infraestructura) !== areaA),
      ...(b1?.resumen_unidades ?? []).filter((u) => Number(u.id_infraestructura) !== areaB)]
      .map((x) => Number(x.id_infraestructura)),
    pagina1: a1?.sensores?.length, pagina2: a2?.sensores?.length,
    posicion_rojo: rojos.length === 1 ? sensoresA.findIndex((s) => s === rojos[0]) + 1 : null,
    colores: [...colores], resumen_inicial: exponerResumen(rInicial),
    resumen_a_p1: exponerResumen(rA1), resumen_a_p2: exponerResumen(rA2),
    resumen_b: exponerResumen(rB), alerta_critica_asociada: alertaAsociada,
    amarillo_no_construible_sandbox: 'Clasificación RF-17 en worker postcommit; lecturas sin confirmar permanecen VERDE',
    variables_en_atencion_criticas_sensores: (inicial?.sensores ?? [])
      .filter((s) => ['AMARILLO', 'ROJO'].includes(s.estado_semaforo))
      .map((s) => ({ id_sensor: s.id_sensor, tipo_variable: s.tipo_variable,
        estado_semaforo: s.estado_semaforo })),
    unidad_a_pagina2_estado_general: rA2?.estado_general ?? null,
    unidad_a_peor_60: ['ROJO', 'AMARILLO', 'GRIS', 'VERDE'].find((c) => sensoresA.some((s) => s.estado_semaforo === c)) ?? null,
    sensores_con_tipo_variable: (inicial?.sensores ?? []).filter((s) => s.tipo_variable != null).length,
    alertas_activas_creadas: alertasActivas } };
}
