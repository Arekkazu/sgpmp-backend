// IDs de la colección original, cotejados con la fila TC-M03-G88 de la matriz.
export { PLAN_266, evaluar266 } from './g88_266_plan.mjs';
export const CASOS = Object.freeze({
  'TC-M03-169': { api: ['API-169-01', 'API-169-02', 'API-169-03', 'API-169-04'], ui: [],
    esperado: 'HTTP 200; 35, 37 y 39 en VERDE con umbral 35-39.' },
  'TC-M03-170': { api: ['API-170-01', 'API-170-02', 'API-170-03', 'API-170-04', 'API-170-05'], ui: [],
    esperado: 'HTTP 200; 19.1, 19.9, 30.1 y 30.9 en AMARILLO; T por defecto=1 (10 % de 20-30).' },
  'TC-M03-171': { api: ['API-171-01', 'API-171-02', 'API-171-03'], ui: [],
    esperado: 'HTTP 200; 18.9 y 31.1 en ROJO con umbral 20-30 y T=1.' },
  'TC-M03-172': { api: ['API-172-A'], ui: ['UI-172'],
    esperado: 'HTTP 200; 18.5 y 31.5 en AMARILLO con T=2 configurada en M09.' },
  'TC-M03-180': { api: ['API-180-01', 'API-180-02', 'API-180-03', 'API-180-04'],
    ui: ['UI-180-01', 'UI-180-02', 'UI-180-03'],
    esperado: 'HTTP 200; variable visible con valor, unidad, GRIS, etiqueta Sin umbral configurado y notificación al administrador.' },
  'TC-M03-266': { api: ['API-266-01', 'API-266-02'], ui: [],
    esperado: 'Lectura 15 VERDE con 10-20; sin cambiarla, al reconfigurar a 20-30 se recalcula a ROJO/AMARILLO.' },
});

export const IDS_CASOS = Object.keys(CASOS);
export function umbralesActivos180(items) {
  if (!Array.isArray(items)) throw new TypeError('Respuesta de umbrales no evaluable.');
  return items.filter((x) => x.es_activo && Number(x.id_variable_ambiental) === 11);
}
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1',
  operaciones: ['evaluar', 'reintentar', 'reevaluar', 'recuperar'], versiones: '1..n',
  comprobaciones_obligatorias: Object.fromEntries(IDS_CASOS.map((id) => [id,
    { API: CASOS[id].api, ...(CASOS[id].ui.length ? { UI: CASOS[id].ui } : {}) }])) });

export function estadoCaso(id, comprobaciones = [], bloqueos = [], totalUi = 0) {
  if (!CASOS[id]) throw new Error(`Caso desconocido: ${id}`);
  const propios = comprobaciones.filter((x) => x.caso === id && x.tipo !== 'APOYO');
  const faltantes = [...CASOS[id].api, ...CASOS[id].ui].filter((c) => !propios.some((x) => x.id === c && x.estado !== 'NO_EJECUTADO'));
  const uiFaltante = CASOS[id].ui.length > 0 && totalUi === 0;
  if (id === 'TC-M03-266') {
    if (bloqueos.length) return { estado: bloqueos.every((x) => x.tipo === 'AUTOMATIZACION') ? 'ERROR_QA' : 'BLOQUEADO',
      motivo: bloqueos.map((x) => x.motivo).join('; '), faltantes };
    const inicial = propios.find((x) => x.id === 'API-266-01');
    const final = propios.find((x) => x.id === 'API-266-02');
    if (propios.some((x) => x.estado === 'NO_CONCLUYENTE'))
      return { estado: 'NO_CONCLUYENTE', motivo: 'Escenario o lectura no acreditados.', faltantes };
    if (inicial?.estado === 'APROBADO' && final?.estado === 'APROBADO')
      return { estado: 'APROBADO', motivo: 'Misma lectura recalculada tras PATCH M09.', faltantes: [] };
    if (inicial?.estado === 'RECHAZADO' && inicial.naturaleza === 'PRODUCTO'
        && ['APROBADO', 'RECHAZADO'].includes(final?.estado))
      return { estado: 'RECHAZADO', motivo: 'Lectura 15 no estaba VERDE con umbral inicial 10-20.', faltantes: [] };
    if (inicial?.estado === 'APROBADO' && final?.estado === 'RECHAZADO' && final.naturaleza === 'PRODUCTO')
      return { estado: 'RECHAZADO', motivo: 'Misma lectura sigue VERDE tras PATCH M09.', faltantes: [] };
    if (propios.length) return { estado: 'NO_CONCLUYENTE', motivo: 'Escenario o lectura no acreditados.', faltantes };
    return { estado: 'NO_EJECUTADO', motivo: '266 desactivado por defecto o sin comprobación.', faltantes };
  }
  if (id === 'TC-M03-172' && !bloqueos.length) {
    const api = propios.find((x) => x.id === 'API-172-A');
    const ui = propios.find((x) => x.id === 'UI-172');
    if (api?.estado === 'RECHAZADO' && ui?.estado === 'RECHAZADO' && totalUi > 0)
      return { estado: 'RECHAZADO', motivo: 'Ausencia de T acreditada por API y UI en TEST.', faltantes: [] };
    return { estado: 'NO_CONCLUYENTE', motivo: 'La ausencia de T requiere API y UI concordantes.', faltantes };
  }
  if (bloqueos.length) return { estado: bloqueos.some((x) => x.tipo === 'REQUISITO_DEPENDIENTE')
    ? 'REQUISITO_DEPENDIENTE' : bloqueos.every((x) => x.tipo === 'AUTOMATIZACION') ? 'ERROR_QA' : 'BLOQUEADO',
    motivo: bloqueos.map((x) => x.motivo).join('; '), faltantes };
  if (!propios.length) return { estado: 'NO_EJECUTADO', motivo: 'Sin comprobaciones reales.', faltantes };
  if (propios.some((x) => x.tipo === 'PRE' && x.estado !== 'APROBADO'))
    return { estado: 'BLOQUEADO', motivo: 'Precondición del caso no cumplida.', faltantes };
  if (propios.some((x) => x.estado === 'RECHAZADO' && x.naturaleza === 'PRODUCTO'))
    return { estado: 'RECHAZADO', motivo: 'Discrepancia funcional comprobada.', faltantes };
  if (propios.some((x) => x.estado === 'ERROR_QA')) return { estado: 'ERROR_QA', motivo: 'Error de automatización.', faltantes };
  if (faltantes.length || uiFaltante || propios.some((x) => x.estado !== 'APROBADO'))
    return { estado: 'BLOQUEADO', motivo: `Faltan comprobaciones: ${faltantes.join(', ') || 'UI sin pruebas o PRE fallida'}.`, faltantes };
  return { estado: 'APROBADO', motivo: 'Todas las comprobaciones obligatorias aprobadas.', faltantes: [] };
}

// Los estados de ejecución no son veredictos funcionales del RUN.
export function resultadoOficial(id, comprobaciones = [], bloqueos = [], totalUi = 0, hallazgos = [], evidencias = []) {
  const calculado = estadoCaso(id, comprobaciones, bloqueos, totalUi);
  const propios = comprobaciones.filter((x) => x.caso === id && x.tipo !== 'APOYO');
  const parada = bloqueos.some((x) => x.tipo === 'PARADA_SEGURIDAD_SESION_COMPARTIDA');
  const obligatorias = [...CASOS[id].api, ...CASOS[id].ui];
  const faltantes = obligatorias.filter((clave) => !propios.some((x) => x.id === clave
    && ['APROBADO', 'RECHAZADO'].includes(x.estado)));
  const errores = bloqueos.filter((x) => x.tipo === 'AUTOMATIZACION');
  const indeterminados = bloqueos.filter((x) => x.tipo === 'ORIGEN_INDETERMINADO');
  const preFallida = propios.find((x) => x.tipo === 'PRE' && x.estado !== 'APROBADO');
  let estadoTecnico = 'OK';
  if (parada) estadoTecnico = propios.length ? 'NO_CONCLUYENTE' : 'NO_EJECUTADA';
  else if (errores.length || propios.some((x) => x.estado === 'ERROR_QA')
      || /ERROR_TIEMPO|fecha.*captura|expected 400 to deeply equal 201/i.test(preFallida?.observado ?? ''))
    estadoTecnico = 'ERROR_QA';
  else if (indeterminados.length || faltantes.length || propios.some((x) => x.estado === 'NO_CONCLUYENTE')
      || (CASOS[id].ui.length && totalUi === 0))
    estadoTecnico = propios.length || indeterminados.length ? 'NO_CONCLUYENTE' : 'NO_EJECUTADA';
  else if (!propios.length && !bloqueos.length) estadoTecnico = 'NO_EJECUTADA';
  const bloqueoReal = bloqueos.some((x) => ['DATOS', 'SEGURIDAD'].includes(x.tipo))
    && !propios.some((x) => x.estado === 'RECHAZADO' && x.naturaleza === 'PRODUCTO');
  if (bloqueoReal && estadoTecnico !== 'ERROR_QA') estadoTecnico = 'OK';
  const veredicto = estadoTecnico !== 'OK' ? null : bloqueoReal ? 'BLOQUEADO'
    : ['APROBADO', 'RECHAZADO'].includes(calculado.estado) ? calculado.estado : null;
  if (!veredicto && estadoTecnico === 'OK') estadoTecnico = 'NO_CONCLUYENTE';
  return { estado: veredicto, veredicto_funcional: veredicto, estado_tecnico: estadoTecnico,
    motivo: parada ? bloqueos.filter((x) => x.tipo === 'PARADA_SEGURIDAD_SESION_COMPARTIDA')
      .map((x) => x.motivo).join('; ')
      : bloqueoReal ? bloqueos.map((x) => x.motivo).join('; ') : calculado.motivo,
    justificacion_veredicto: veredicto ? calculado.motivo : null,
    evidencia_veredicto: veredicto ? [...new Set([
      ...propios.filter((x) => obligatorias.includes(x.id)).map((x) => x.id),
      ...evidencias.filter((x) => x === 'newman/newman-TC-M03-G88.json'
        || x.startsWith('cypress/') && x.includes(id))])] : [],
    faltantes, incidencias_automatizacion: errores.map((x) => x.motivo), hallazgos_producto: hallazgos };
}

export function bloqueosEscenario(escenario, cadenaPorCaso = {}) {
  return Object.fromEntries(IDS_CASOS.map((id) => {
    const faltas = [];
    const c = escenario.casos[id];
    if (id === 'TC-M03-266') faltas.push({ tipo: 'SEGURIDAD', motivo: c.motivo_bloqueo });
    if (c.estado_datos !== 'CONFIRMADO_EN_TEST' && !(id === 'TC-M03-172'
      && c.clasificacion_preparacion === 'DEFECTO_FUNCIONAL_CANDIDATO')
      && !(['TC-M03-169', 'TC-M03-170', 'TC-M03-171'].includes(id)
      && c.estado_datos === 'PRECONDICION_ACTIVO_RESUELTA_POR_RESPONSABLE_QA_2026-10-24'))
      faltas.push({ tipo: 'DATOS', motivo: `${id}: cadena sensor→dispositivo→infraestructura del dispositivo→especie→umbral/niveles→calibración POR_CONFIRMAR_EN_TEST.` });
    if (cadenaPorCaso[id]?.ok === false) faltas.push({ tipo: 'DATOS', motivo: `${id}: ${cadenaPorCaso[id].motivo}` });
    return [id, faltas];
  }));
}
