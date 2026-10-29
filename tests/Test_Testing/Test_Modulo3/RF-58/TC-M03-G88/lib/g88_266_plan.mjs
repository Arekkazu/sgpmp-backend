import { construirCuerpoIngesta } from './g88_ingesta.mjs';
import { sanearArtefacto } from './g88_seguridad.mjs';
import { asociacionVigente, lecturaVinculada, lecturaVinculadaHistorial,
  rangoHistorial } from './g88_entradas.mjs';
import { lecturaDelRun } from './g88_respuestas.mjs';

export const PLAN_266 = Object.freeze({ habilitado: false,
  pasos: Object.freeze(['semilla_preexistente', 'precondiciones', 'alta_umbral_10_20',
    'auditoria_propagacion_alta', 'ingesta_unica_15', 'dashboard_e_historial_inicial',
    'edicion_umbral_20_30', 'auditoria_propagacion_edicion',
    'dashboard_e_historial_sin_ingesta', 'desactivacion_y_verificacion']) });

const id = (x) => Number.isSafeInteger(Number(x)) && Number(x) > 0;
const n = (x) => Number(x);
const eq = (a, b) => n(a) === n(b);
const fail = (s) => { throw new Error(`266: ${s}`); };
const body = (x) => x?.json?.data ?? x?.json;

export function autorizacion266(c) {
  const expreso = c?.habilitar_266 === true || c?.alcance_reevaluacion?.habilitar_266 === true;
  return !PLAN_266.habilitado && expreso && c.version === 1
    && ['EVALUAR', 'REINTENTAR'].includes(c.operacion)
    && c.casos?.includes('TC-M03-266') && !!c.referencia;
}

export function motivoNoConcluyente266({ precondicionesValidas, calidad, inicial, final,
  mismaLectura, sinNuevaLectura, alerta, gris } = {}) {
  if (!precondicionesValidas) return 'Semilla, umbrales o identidad/valor de lectura no acreditados.';
  if (calidad !== 'LECTURA_VALIDA') return `Ingesta no válida: ${calidad ?? 'sin calidad'}.`;
  if (!mismaLectura) return 'La identidad o el valor de la lectura cambió.';
  if (!sinNuevaLectura) return 'Se detectó una lectura nueva tras reconfigurar M09.';
  if (alerta) return 'Una alerta activa contamina el semáforo.';
  if (gris || inicial === 'GRIS' || final === 'GRIS') return 'Dato desactualizado o semáforo GRIS.';
  if (!['VERDE', 'AMARILLO', 'ROJO'].includes(inicial)
    || !['VERDE', 'AMARILLO', 'ROJO'].includes(final)) return 'Semáforo inicial o final no legible.';
  return null;
}

export function evaluar266(datos = {}) {
  if (motivoNoConcluyente266(datos)) return 'NO_CONCLUYENTE';
  const { inicial, final } = datos;
  if (inicial !== 'VERDE') return 'RECHAZADO';
  if (final === 'ROJO' || final === 'AMARILLO') return 'APROBADO';
  if (final === 'VERDE') return 'RECHAZADO';
  return 'NO_CONCLUYENTE';
}

export function autorizarEscritura266({ metodo, ruta, cuerpo, fase, semilla: s, umbralId, serial }) {
  if (fase !== 'SEMILLA_VERIFICADA') return false;
  if (metodo === 'POST' && ruta === '/configuracion/umbrales') return eq(cuerpo?.id_especie, s?.especie_id)
    && eq(cuerpo?.id_variable_ambiental, s?.variable_id)
    && n(cuerpo?.valor_min) === 10 && n(cuerpo?.valor_max) === 20
    && JSON.stringify(cuerpo?.niveles) === JSON.stringify(niveles(10));
  if (metodo === 'PATCH' && ruta === `/configuracion/umbrales/${umbralId}`)
    return id(umbralId) && n(cuerpo?.valor_min) === 20 && n(cuerpo?.valor_max) === 30
      && JSON.stringify(cuerpo?.niveles) === JSON.stringify(niveles(20))
      && Object.hasOwn(cuerpo ?? {}, 'fecha_actualizacion')
      && (cuerpo.fecha_actualizacion === null || typeof cuerpo.fecha_actualizacion === 'string');
  if (metodo === 'PATCH' && ruta === `/configuracion/umbrales/${umbralId}/desactivar`) return id(umbralId);
  if (metodo === 'POST' && ruta === '/iot/telemetria') return eq(cuerpo?.device_id, s?.dispositivo_id)
    && eq(cuerpo?.sensor_id, s?.sensor_id) && cuerpo?.tipo_variable === 'TEMPERATURA_AMBIENTAL'
    && n(cuerpo?.valor) === 15 && typeof serial === 'string' && serial.length > 0
    && cuerpo?.serial === serial
    && !Object.hasOwn(cuerpo, 'access_key');
  return false;
}

const niveles = (min) => [{ nivel: 'critico', limite_inferior: min, limite_superior: min + 2 },
  { nivel: 'precaucion', limite_inferior: min + 2, limite_superior: min === 10 ? 13 : 24 },
  { nivel: 'normal', limite_inferior: min === 10 ? 13 : 24, limite_superior: min + 10 }];

async function get(req, ruta, token) {
  const x = await req('GET', ruta, { token, enRun: true });
  if (x.status !== 200) fail(`GET ${ruta} HTTP ${x.status}`);
  return x.json;
}
async function write(req, metodo, ruta, cuerpo, token, control, esperado) {
  const x = await req(metodo, ruta, { token, enRun: true, cuerpo, control266: control });
  if (x.status !== esperado) fail(`${metodo} ${ruta} HTTP ${x.status}`);
  return body(x);
}
function unico(xs, pred, nombre) {
  const ys = xs.filter(pred);
  if (ys.length > 1) fail(`${nombre} duplicado`);
  return ys[0];
}

export async function verificarSemillaPreexistente266({ solicitar: req, token, parametros: p, semilla, control }) {
  const campos = ['especie_id', 'area_id', 'activo_id', 'dispositivo_id', 'sensor_id',
    'asociacion_id', 'calibracion_id'];
  if (campos.some((k) => !id(p?.[k]))) fail(`faltan IDs de semilla preexistente: ${campos.filter((k) => !id(p?.[k])).join(', ')}`);
  const registrados = { especie_id: semilla?.especie, area_id: semilla?.area,
    activo_id: semilla?.activo_vinculable_unico, dispositivo_id: semilla?.dispositivo,
    sensor_id: semilla?.sensor, asociacion_id: semilla?.asociacion,
    calibracion_id: semilla?.calibracion };
  if (semilla?.estado !== 'ACREDITADA_POR_RESPONSABLE_QA_EN_TEST_2026-10-24'
    || campos.some((k) => !id(registrados[k]) || !eq(p[k], registrados[k]))
    || semilla.finca !== 184) fail('IDs de contexto distintos de semilla 266 acreditada; sin escrituras');
  if (!/^[A-Za-z0-9._-]{1,50}$/.test(p.serial ?? '')) fail('serial privado ausente');
  const s = Object.fromEntries(campos.map((k) => [k, n(p[k])]));
  s.finca_id = semilla.finca;
  control.semilla = s;
  control.serial = p.serial;
  control.fase = 'SEMILLA_PREEXISTENTE';
  const especies = await get(req, '/configuracion/especies', token);
  const especie = (especies.items ?? []).filter((x) => eq(x.id_especie, s.especie_id));
  if (especie.length !== 1 || especie[0].es_activo !== true)
    fail('R1 especie QA activa/ID no acreditados');
  const area = await get(req, `/configuracion/infraestructuras/${s.area_id}`, token);
  if (!eq(area.id_infraestructura, s.area_id)
    || !eq(area.id_finca ?? area.finca_id, s.finca_id) || !eq(area.especie_id, s.especie_id)
    || area.es_activo !== true) fail('R2 área QA activa en finca 184/especie QA no acreditada');
  const activos = await get(req, `/activos-biologicos?id_infraestructura=${s.area_id}&page_size=100`, token);
  const vinculables = (activos.registros ?? []).filter((x) => [1, 3, 4].includes(n(x.id_estado)));
  if (!Array.isArray(activos.registros) || n(activos.total_registros) !== activos.registros.length
    || vinculables.length !== 1 || !eq(vinculables[0].id_activo_biologico, s.activo_id)
    || !eq(vinculables[0].id_infraestructura, s.area_id)
    || !eq(vinculables[0].id_especie, s.especie_id)
    || n(vinculables[0].id_estado) !== 1
    || (vinculables[0].tipo ?? vinculables[0].tipo_activo) !== 'INDIVIDUAL')
    fail('R3 activo INDIVIDUAL vinculable único no acreditado');
  const dispositivos = await get(req, '/configuracion/dispositivos-iot', token);
  const delArea = (dispositivos.items ?? []).filter((x) => eq(x.id_infraestructura, s.area_id) && x.es_activo);
  const dispositivo = await get(req, `/configuracion/dispositivos-iot/${s.dispositivo_id}`, token);
  if (!Array.isArray(dispositivos.items) || (dispositivos.total != null
    && n(dispositivos.total) !== dispositivos.items.length)
    || delArea.length !== 1 || !eq(delArea[0].id_dispositivo_iot, s.dispositivo_id)
    || !eq(dispositivo.id_dispositivo_iot, s.dispositivo_id) || !dispositivo.es_activo
    || !eq(dispositivo.id_infraestructura, s.area_id)
    || dispositivo.id_dispositivo_gateway != null || dispositivo.serial !== p.serial)
    fail('R4 dispositivo único, activo y sin gateway no acreditado');
  const sensores = await get(req, `/configuracion/dispositivos-iot/${s.dispositivo_id}/sensores`, token);
  const sensor = (sensores.items ?? []).filter((x) => eq(x.id_sensores, s.sensor_id));
  if (sensor.length !== 1 || sensor[0].es_activo !== true
    || sensor[0].categoria !== 'TEMPERATURA') fail('R4 sensor TEMPERATURA activo/ID no acreditado');
  const asociaciones = await get(req, `/configuracion/sensores/${s.sensor_id}/asociaciones`, token);
  if (!asociacionVigente(asociaciones, s.asociacion_id, s.area_id))
    fail('R4 asociación vigente/ID no acreditados');
  const calibraciones = await get(req, `/configuracion/sensores/${s.sensor_id}/calibraciones`, token);
  const ultima = (calibraciones.items ?? []).filter((x) => eq(x.id_dispositivo_iot, s.dispositivo_id))
    .sort((a, b) => String(b.fecha_calibracion).localeCompare(String(a.fecha_calibracion)))[0];
  if (!ultima || !eq(ultima.id_calibracion, s.calibracion_id)
    || n(ultima.valor_referencia) !== 15 || n(ultima.ganancia) !== 1
    || n(ultima.offset ?? ultima.offset_calibracion) !== 0
    || (ultima.modo_calibracion != null && ultima.modo_calibracion !== 'SENSOR'))
    fail('R4 calibración SENSOR identidad vigente/ID no acreditados');
  const variable = unico((await get(req, '/configuracion/variables-ambientales', token)).items ?? [],
    (x) => String(x.tipo_variable ?? x.nombre ?? '').trim().toUpperCase().replace(/\s+/g, '_')
      === 'TEMPERATURA_AMBIENTAL' && x.es_activo !== false, 'variable');
  if (!variable || !id(variable.id_variable_ambiental)
    || variable.valor_fisico_min == null || variable.valor_fisico_max == null
    || !Number.isFinite(n(variable.valor_fisico_min))
    || !Number.isFinite(n(variable.valor_fisico_max))
    || n(variable.valor_fisico_min) > 10 || n(variable.valor_fisico_max) < 30
    || typeof variable.unidad !== 'string' || !variable.unidad)
    fail('R5 variable/rango físico no acreditados');
  const rango = unico((await get(req, '/configuracion/sensores/rangos-calibracion', token)).items ?? [],
    (x) => x.categoria === 'TEMPERATURA', 'rango de calibración');
  if (!rango || rango.valor_min == null || rango.valor_max == null
    || !Number.isFinite(n(rango.valor_min)) || !Number.isFinite(n(rango.valor_max))
    || n(rango.valor_min) > 15 || n(rango.valor_max) < 30)
    fail('R5 rango de calibración TEMPERATURA no acreditado');
  s.variable_id = variable.id_variable_ambiental;
  s.unidad = variable.unidad;
  const umbrales = await get(req, `/configuracion/umbrales?id_especie=${s.especie_id}`, token);
  const historial = await get(req,
    `/iot/monitoreo/historial?sensor_id=${s.sensor_id}&fecha_inicio=2000-01-01&fecha_fin=${rangoHistorial().fin}`, token);
  const dashboard = await get(req, `/iot/monitoreo/dashboard?id_infraestructura=${s.area_id}&por_pagina=50`, token);
  const alertasSensor = await get(req, `/iot/alertas?id_sensor=${s.sensor_id}`, token);
  const alertasActivo = await get(req, `/iot/alertas?id_activo_biologico=${s.activo_id}`, token);
  const estado = (dashboard.sensores ?? []).find((x) => eq(x.id_sensor, s.sensor_id));
  if (!Array.isArray(umbrales.items) || (umbrales.total != null
    && n(umbrales.total) !== umbrales.items.length)
    || umbrales.items.some((x) => x.es_activo
    && eq(x.id_variable_ambiental, s.variable_id)) || historial.total == null
    || n(historial.total) !== 0
    || !Array.isArray(historial.items) || historial.items.length !== 0
    || (estado && (estado.ultimo_valor != null || estado.id_alerta != null
      || estado.estado_semaforo != null || estado.id_telemetria != null
      || estado.ultimo_timestamp_captura != null))
    || alertasSensor.total == null || n(alertasSensor.total) !== 0
    || alertasActivo.total == null || n(alertasActivo.total) !== 0)
    fail('R5 umbral, lectura, estado o alerta previa');
  return s;
}

async function auditarEscritura266(req, token, umbralId, version, etapa, r, secretos = []) {
  const resumen = { caso: 'TC-M03-266', etapa, umbral_id: umbralId,
    version: version ?? null, id_evento: null, estado: null, motivo: null,
    gateways: null, gateways_count: null, evidencia: 'AUSENTE' };
  try {
    const x = await req('GET',
      `/iot/auditoria?tipo_evento=PROPAGACION_UMBRAL_EDGE&entidad_afectada_id=${umbralId}&por_pagina=200`,
      { token, enRun: true });
    if (x.status !== 200 || !Array.isArray(x.json?.items)) {
      resumen.motivo = `Auditoría no legible: HTTP ${x.status}`;
    } else {
      const eventos = x.json.items.filter((e) => e.tipo_evento === 'PROPAGACION_UMBRAL_EDGE');
      const e = eventos.find((item) => version && Date.parse(item.accion_detallada?.version) === Date.parse(version));
      const d = e?.accion_detallada;
      const algunGateway = eventos.some((item) => Array.isArray(item.accion_detallada?.gateways)
        && item.accion_detallada.gateways.length > 0);
      resumen.gateway_observado = algunGateway;
      resumen.gateways_observados_count = eventos.reduce((total, item) =>
        total + (Array.isArray(item.accion_detallada?.gateways) ? item.accion_detallada.gateways.length : 0), 0);
      resumen.id_evento = e?.id_evento ?? null;
      resumen.estado = d?.estado ?? null;
      resumen.motivo = d?.motivo == null ? null : sanearArtefacto(String(d.motivo).slice(0, 200), secretos);
      resumen.gateways = Array.isArray(d?.gateways) ? d.gateways.map((g) => {
        const identificador = g?.id_dispositivo_gateway ?? g?.id_gateway ?? g?.id_dispositivo_iot;
        return id(identificador) ? Number(identificador) : 'PRESENTE';
      }) : null;
      resumen.gateways_count = resumen.gateways?.length ?? null;
      resumen.evidencia = e && Array.isArray(d?.gateways) ? 'OBSERVADA' : 'AUSENTE';
      if (resumen.evidencia === 'AUSENTE') resumen.motivo = 'Evento de la versión ausente o ilegible.';
    }
  } catch (error) {
    resumen.motivo = sanearArtefacto(`Auditoría no legible: ${error.message}`, secretos);
  }
  r.bitacora.push(resumen);
  return { gatewayObservado: resumen.gateway_observado === true, resumen };
}

function fechasHistorial() {
  const { inicio, fin } = rangoHistorial();
  return `fecha_inicio=${inicio}&fecha_fin=${fin}`;
}
async function estadoLectura(req, token, s, telemetriaId) {
  const dash = await get(req, `/iot/monitoreo/dashboard?id_infraestructura=${s.area_id}&por_pagina=50`, token);
  const h = await get(req, `/iot/monitoreo/historial?sensor_id=${s.sensor_id}&${fechasHistorial()}`, token);
  const sensor = (dash.sensores ?? []).find((x) => eq(x.id_sensor, s.sensor_id));
  const lectura = (h.items ?? []).find((x) => eq(x.id_telemetria, telemetriaId));
  const dashboardDelRun = telemetriaId > 0 && lecturaDelRun(sensor, {
    id_telemetria: telemetriaId, id_sensor: s.sensor_id,
    timestamp_captura: lectura?.timestamp_captura,
    valor: lectura?.valor_ajustado ?? lectura?.valor,
  });
  return { sensor: sensor ? { id_sensor: sensor.id_sensor, valor: sensor.ultimo_valor,
    unidad: sensor.ultima_unidad, timestamp_captura: sensor.ultimo_timestamp_captura,
    estado_semaforo: sensor.estado_semaforo, dato_desactualizado: sensor.dato_desactualizado,
    id_alerta: sensor.id_alerta } : null,
    lectura: lectura ? { id_telemetria: lectura.id_telemetria, id_sensor: lectura.id_sensor,
      valor: lectura.valor, valor_ajustado: lectura.valor_ajustado, unidad: lectura.unidad_medida,
      timestamp_captura: lectura.timestamp_captura, estado_calidad: lectura.estado_calidad,
      estado_semaforo_historico: lectura.estado_semaforo_historico,
      id_activo_biologico: lectura.id_activo_biologico, id_alerta: lectura.id_alerta } : null,
    total_historial: h.total, dashboard_del_run: dashboardDelRun };
}

export async function ejecutar266({ solicitar: req, admin, productor, broker, serial, s, control, r, lecturas,
  conservarSemilla = true, newmanLectura, secretos = [], timestampCaptura, planTemporal }) {
  const caso = 'TC-M03-266';
  const prueba = (nombre, estado, observado, naturaleza = null) => r.comprobaciones.push({ caso,
    id: nombre, fuente: 'API', tipo: 'ASSERT', estado, naturaleza, observado });
  control.fase = 'SEMILLA_VERIFICADA';
  r.bitacora.push({ caso, semilla_api: 'VERIFICADA', especie_id: s.especie_id,
    conservar_semilla: conservarSemilla });
  let umbralId = null, previa, posterior;
  let omitirEscriturasPosteriores = true;
  try {
    const base = await estadoLectura(req, productor, s, 0);
    const alertasSensor = await get(req, `/iot/alertas?estado=ACTIVA&id_sensor=${s.sensor_id}`, admin);
    const alertasActivo = await get(req, `/iot/alertas?estado=ACTIVA&id_activo_biologico=${s.activo_id}`, admin);
    const umbrales = await get(req, `/configuracion/umbrales?id_especie=${s.especie_id}`, admin);
    const limpio = alertasSensor.total === 0 && alertasActivo.total === 0
      && !base.sensor?.id_alerta && base.sensor?.valor == null && base.total_historial === 0
      && !(umbrales.items ?? []).some((x) => x.es_activo && eq(x.id_variable_ambiental, s.variable_id));
    if (!limpio) { r.resultado266 = 'NO_CONCLUYENTE'; prueba('API-266-01', 'NO_CONCLUYENTE',
      'Hay alerta, estado/lectura previa o umbral activo en semilla.'); return; }
    r.umbral_run_266 = { alta_intentada: true, id: null, especie_id: Number(s.especie_id) };
    const alta = await req('POST', '/configuracion/umbrales', { token: admin, enRun: true, control266: control, cuerpo: {
      id_especie: s.especie_id, id_variable_ambiental: s.variable_id,
      valor_min: 10, valor_max: 20, niveles: niveles(10) } });
    umbralId = body(alta)?.id_umbral_ambiental;
    if (!id(umbralId)) {
      const posibles = (await get(req, `/configuracion/umbrales?id_especie=${s.especie_id}`, admin)).items
        ?.filter((x) => x.es_activo && eq(x.id_variable_ambiental, s.variable_id)) ?? [];
      if (posibles.length === 1) umbralId = posibles[0].id_umbral_ambiental;
    }
    control.umbralId = umbralId;
    r.umbral_run_266 = { alta_intentada: true, id: id(umbralId) ? Number(umbralId) : null,
      especie_id: Number(s.especie_id) };
    if (alta.status !== 201 || !id(umbralId)) {
      if (id(umbralId)) await auditarEscritura266(req, admin, umbralId,
        body(alta)?.fecha_actualizacion, 'ALTA_M09', r, secretos);
      else r.bitacora.push({ caso, etapa: 'ALTA_M09', evidencia: 'AUSENTE',
        motivo: 'No se obtuvo id de umbral para consultar la auditoría posterior.' });
      r.resultado266 = 'NO_CONCLUYENTE'; prueba('API-266-01', 'NO_CONCLUYENTE',
        `Alta M09 HTTP ${alta.status}; umbral identificable=${id(umbralId)}. Sin ingesta ni edición.`);
      r.bitacora.push({ caso, efecto_externo: 'ALTA_M09_HTTP_NO_201; verificar bitácora y destino antes de nuevo intento' });
      return;
    }
    let u1 = null;
    try { u1 = (await get(req, `/configuracion/umbrales?id_especie=${s.especie_id}`, admin)).items
      ?.find((x) => eq(x.id_umbral_ambiental, umbralId)); } catch { /* La auditoría posterior sigue. */ }
    const aud1 = await auditarEscritura266(req, admin, umbralId,
      u1?.fecha_actualizacion ?? body(alta)?.fecha_actualizacion, 'ALTA_M09', r, secretos);
    const altaConfirmada = !!u1 && u1.es_activo && eq(u1.valor_min, 10) && eq(u1.valor_max, 20);
    if (!altaConfirmada || aud1.gatewayObservado) { r.resultado266 = 'NO_CONCLUYENTE';
      prueba('API-266-01', 'NO_CONCLUYENTE', aud1.gatewayObservado
        ? 'Gateway observado tras alta M09; efecto externo impide continuar.'
        : 'Umbral inicial 10-20 no acreditado por GET tras alta M09.');
      omitirEscriturasPosteriores = true;
      if (aud1.gatewayObservado) r.bitacora.push({ caso,
        efecto_externo: 'GATEWAY_OBSERVADO_TRAS_ALTA; detener escrituras de 266' });
      return; }
    omitirEscriturasPosteriores = false;
    const cuerpoIngesta = construirCuerpoIngesta({ deviceId: s.dispositivo_id, sensorId: s.sensor_id,
      tipoVariable: 'TEMPERATURA_AMBIENTAL', valor: 15, unidad: s.unidad, serial, timestampCaptura });
    r.bitacora.push({ caso, etapa: 'INGESTA_266', timestamp_captura_enviado: cuerpoIngesta.timestamp_captura,
      ancla_temporal: planTemporal?.ancla ?? null, inicio_run: planTemporal?.inicio_run ?? null });
    const ingesta = await req('POST', '/iot/telemetria', { token: broker, enRun: true,
      cuerpo: cuerpoIngesta, control266: control });
    if (ingesta.status !== 201 || !id(ingesta.json?.id_telemetria)
      || ingesta.json?.estado_calidad !== 'LECTURA_VALIDA') {
      r.resultado266 = 'NO_CONCLUYENTE'; prueba('API-266-01', 'NO_CONCLUYENTE',
        `Ingesta oficial HTTP ${ingesta.status}; calidad=${ingesta.json?.estado_calidad ?? 'sin dato'}`); return;
    }
    const teleId = ingesta.json.id_telemetria;
    lecturas.push({ caso, sensor_id: s.sensor_id, id_telemetria: teleId,
      fecha_inicio: rangoHistorial().inicio, fecha_fin: rangoHistorial().fin });
    previa = await estadoLectura(req, productor, s, teleId);
    let vinculo = { ok: false, motivo: 'Consulta de vinculación no disponible.' };
    let fuenteVinculo = 'GET /iot/vinculaciones';
    try {
      const consulta = await req('GET', `/iot/vinculaciones?id_telemetria=${teleId}`,
        { token: admin, enRun: true });
      if (consulta.status === 200) vinculo = lecturaVinculada(consulta.json, Number(teleId),
        Number(s.activo_id), Number(s.area_id));
      else if (consulta.status === 404 || consulta.status === 405) {
        fuenteVinculo = 'GET historial por lectura (ruta de vinculaciones no disponible)';
        vinculo = lecturaVinculadaHistorial({ items: previa.lectura ? [previa.lectura] : [] },
          Number(teleId), Number(s.activo_id), Number(s.sensor_id));
      } else vinculo.motivo = `GET vinculación HTTP ${consulta.status}.`;
    } catch (error) { vinculo.motivo = `GET vinculación no legible: ${sanearArtefacto(error.message, secretos)}`; }
    r.bitacora.push({ caso, id_telemetria: teleId, vinculo_885: vinculo.ok ? 'VINCULADA' : 'NO_CONCLUYENTE',
      fuente: fuenteVinculo, motivo: vinculo.motivo });
    if (!vinculo.ok) r.hallazgos_producto.push({ caso, tipo: 'HALLAZGO_PRODUCTO',
      descripcion: 'Lectura sin vinculación RF-61-A pese a activo único vinculable',
      evidencia: fuenteVinculo, observado: vinculo.motivo, certeza: 'PROBABLE',
      nota: 'Posible defecto sujeto a RF-61-A; no condiciona el veredicto RF-58.' });
    const calidad = previa.lectura?.estado_calidad;
    const alertasDespuesIngesta = await get(req, `/iot/alertas?estado=ACTIVA&id_sensor=${s.sensor_id}`, admin);
    const alertasActivoDespuesIngesta = await get(req,
      `/iot/alertas?estado=ACTIVA&id_activo_biologico=${s.activo_id}`, admin);
    const sinAlerta = alertasDespuesIngesta.total === 0 && alertasActivoDespuesIngesta.total === 0
      && !previa.sensor?.id_alerta && !previa.lectura?.id_alerta;
    const inicialAcreditado = previa.dashboard_del_run && n(previa.sensor?.valor) === 15
      && n(previa.lectura?.valor_ajustado) === 15 && calidad === 'LECTURA_VALIDA'
      && sinAlerta && !previa.sensor?.dato_desactualizado
      && ['VERDE', 'AMARILLO', 'ROJO'].includes(previa.sensor?.estado_semaforo);
    const estadoInicial = inicialAcreditado
      ? previa.sensor.estado_semaforo === 'VERDE' ? 'APROBADO' : 'RECHAZADO' : 'NO_CONCLUYENTE';
    prueba('API-266-01', estadoInicial, JSON.stringify({ id_sensor: s.sensor_id,
        id_telemetria: previa.lectura?.id_telemetria, valor: previa.lectura?.valor_ajustado,
        unidad: previa.lectura?.unidad, timestamp_captura: previa.lectura?.timestamp_captura,
        semaforo: previa.sensor?.estado_semaforo,
        semaforo_historico: previa.lectura?.estado_semaforo_historico,
        dato_desactualizado: previa.sensor?.dato_desactualizado,
        id_alerta: previa.sensor?.id_alerta, vinculada: vinculo.ok, calidad,
        motivo: inicialAcreditado ? null : calidad !== 'LECTURA_VALIDA'
          ? `Ingesta no válida: ${calidad ?? 'sin calidad'}.`
          : !sinAlerta ? 'Una alerta activa contamina el semáforo.'
            : previa.sensor?.dato_desactualizado || previa.sensor?.estado_semaforo === 'GRIS'
              ? 'Dato desactualizado o semáforo GRIS.'
              : 'Identidad, valor 15 o semáforo inicial no acreditados.' }),
    estadoInicial === 'RECHAZADO' ? 'PRODUCTO' : null);
    if (!inicialAcreditado) { r.resultado266 = 'NO_CONCLUYENTE'; return; }
    const inmediato = (await get(req, `/configuracion/umbrales?id_especie=${s.especie_id}`, admin)).items
      ?.find((x) => eq(x.id_umbral_ambiental, umbralId));
    if (!inmediato) { r.resultado266 = 'NO_CONCLUYENTE';
      prueba('API-266-02', 'NO_CONCLUYENTE', 'Umbral creado ausente del GET inmediato para PATCH.'); return; }
    omitirEscriturasPosteriores = true;
    const respuestaEdicion = await req('PATCH', `/configuracion/umbrales/${umbralId}`, {
      token: admin, enRun: true, control266: control, cuerpo: {
      valor_min: 20, valor_max: 30, niveles: niveles(20),
      fecha_actualizacion: inmediato.fecha_actualizacion } });
    const editado = body(respuestaEdicion);
    let u2 = null;
    try { u2 = (await get(req, `/configuracion/umbrales?id_especie=${s.especie_id}`, admin)).items
      ?.find((x) => eq(x.id_umbral_ambiental, umbralId)); } catch { /* La auditoría posterior sigue. */ }
    const aud2 = await auditarEscritura266(req, admin, umbralId,
      u2?.fecha_actualizacion ?? editado?.fecha_actualizacion, 'EDICION_M09', r, secretos);
    const edicionConfirmada = respuestaEdicion.status === 200 && !!u2
      && eq(u2.valor_min, 20) && eq(u2.valor_max, 30)
      && editado?.fecha_actualizacion === u2.fecha_actualizacion
      && u2.fecha_actualizacion !== u1.fecha_actualizacion;
    if (!edicionConfirmada || aud2.gatewayObservado) { r.resultado266 = 'NO_CONCLUYENTE';
      prueba('API-266-02', 'NO_CONCLUYENTE', aud2.gatewayObservado
        ? 'Gateway observado tras edición M09; efecto externo impide continuar.'
        : 'Umbral final 20-30 no acreditado por GET tras edición M09.');
      omitirEscriturasPosteriores = true;
      if (aud2.gatewayObservado) r.bitacora.push({ caso,
        efecto_externo: 'GATEWAY_OBSERVADO_TRAS_EDICION; detener escrituras de 266' });
      return; }
    omitirEscriturasPosteriores = false;
    posterior = await estadoLectura(req, productor, s, teleId);
    const alertasDespuesPatch = await get(req, `/iot/alertas?estado=ACTIVA&id_sensor=${s.sensor_id}`, admin);
    const alertasActivoDespuesPatch = await get(req,
      `/iot/alertas?estado=ACTIVA&id_activo_biologico=${s.activo_id}`, admin);
    const misma = posterior.dashboard_del_run
      && eq(posterior.lectura?.id_telemetria, previa.lectura?.id_telemetria)
      && eq(posterior.lectura?.id_sensor, previa.lectura?.id_sensor)
      && n(posterior.lectura?.valor) === n(previa.lectura?.valor)
      && n(posterior.lectura?.valor_ajustado) === n(previa.lectura?.valor_ajustado)
      && posterior.lectura?.unidad === previa.lectura?.unidad
      && posterior.lectura?.timestamp_captura === previa.lectura?.timestamp_captura
      && posterior.sensor?.timestamp_captura === previa.sensor?.timestamp_captura
      && n(posterior.sensor?.valor) === n(previa.sensor?.valor)
      && posterior.sensor?.unidad === previa.sensor?.unidad;
    const evaluacion = { precondicionesValidas: true,
      calidad, inicial: previa.sensor.estado_semaforo, final: posterior.sensor?.estado_semaforo,
      mismaLectura: misma, sinNuevaLectura: posterior.total_historial === previa.total_historial,
      alerta: alertasDespuesPatch.total !== 0 || alertasActivoDespuesPatch.total !== 0
        || !!posterior.sensor?.id_alerta || !!posterior.lectura?.id_alerta,
      gris: posterior.sensor?.dato_desactualizado || posterior.sensor?.estado_semaforo === 'GRIS' };
    const verdict = evaluar266(evaluacion);
    r.resultado266 = verdict;
    prueba('API-266-02', verdict, JSON.stringify({ estado_inicial: previa.sensor?.estado_semaforo,
      estado_final: posterior.sensor?.estado_semaforo,
      historico_inicial: previa.lectura?.estado_semaforo_historico,
      historico_final: posterior.lectura?.estado_semaforo_historico,
      id_sensor: posterior.lectura?.id_sensor,
      id_telemetria: posterior.lectura?.id_telemetria, valor: posterior.lectura?.valor_ajustado,
      unidad: posterior.lectura?.unidad, timestamp_captura: posterior.lectura?.timestamp_captura,
      dato_desactualizado: posterior.sensor?.dato_desactualizado, id_alerta: posterior.sensor?.id_alerta,
      misma_lectura: misma, sin_nueva_ingesta: posterior.total_historial === previa.total_historial,
      bitacoras: { alta: aud1.resumen.evidencia, edicion: aud2.resumen.evidencia },
      motivo: motivoNoConcluyente266(evaluacion) }),
    verdict === 'RECHAZADO' ? 'PRODUCTO' : null);
    if (newmanLectura) await newmanLectura({ s, esperado: 'ROJO/AMARILLO' });
  } finally {
    if (umbralId && !omitirEscriturasPosteriores) {
      try {
        const x = await write(req, 'PATCH', `/configuracion/umbrales/${umbralId}/desactivar`,
          undefined, admin, control, 200);
        const auditoriaCierre = await auditarEscritura266(req, admin, umbralId,
          x?.fecha_actualizacion, 'DESACTIVACION_M09', r, secretos);
        if (auditoriaCierre.gatewayObservado) {
          r.resultado266 = 'NO_CONCLUYENTE';
          const final = r.comprobaciones.find((c) => c.caso === caso && c.id === 'API-266-02');
          if (final) { final.estado = 'NO_CONCLUYENTE'; final.naturaleza = null; }
          r.bitacora.push({ caso, efecto_externo: 'GATEWAY_OBSERVADO_TRAS_DESACTIVACION; sin más escrituras de 266' });
        }
        const posteriorUmbral = (await get(req, `/configuracion/umbrales?id_especie=${s.especie_id}`, admin)).items
          ?.find((u) => eq(u.id_umbral_ambiental, umbralId));
        r.bitacora.push({ caso, cierre_m09_en_run: x?.es_activo === false && posteriorUmbral?.es_activo === false
          ? 'DESACTIVADO_VERIFICADO_DENTRO_DEL_RUN' : 'NO_VERIFICADO', umbral_id: umbralId,
          rollback_pendiente: true, semilla_preexistente_sin_modificacion: conservarSemilla });
      } catch (e) { r.problemas_tecnicos.push(`266 cierre M09: ${e.message}`); }
    }
  }
}
