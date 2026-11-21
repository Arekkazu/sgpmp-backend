import presupuesto from './g95_presupuesto.cjs';

export const { LIMITE_LECTURAS_DASHBOARD } = presupuesto;
export const CASO = 'TC-M03-186';
export const ORACULO = 'La actualización automática se detiene, se muestra el aviso de sesión expirada y se redirige al login sin pérdida del estado visual; al reingresar, el dashboard se recarga con el estado más reciente.';
export const DECISION_METODOLOGICA = Object.freeze({
  fecha: '2026-10-26',
  texto: 'Acepto el segundo login real como mecanismo equivalente para G95. Corrige los detalles pendientes y deja listo el ensayo.',
  mecanismo: 'segundo_login_real',
  limite: 'No prueba el vencimiento temporal del JWT ni el temporizador de inactividad de 30 min.',
  fecha_mensaje: '2026-10-26',
  texto_mensaje: 'No quiero que seas tan estricto con la evaluación, no rechaces la prueba simplemente porque no dice exactamente lo que se espera, Sesión cerrada o sesión expirada dan a entender lo mismo.',
  mensaje: 'Sesión cerrada equivale a sesión expirada cuando el aviso visible comunica que la sesión terminó y hay que volver a ingresar.',
  fecha_recarga: '2026-10-26',
  texto_recarga: 'Sí, ajusta UI-186-02: aprueba si tras reingresar el dashboard de monitoreo se recarga con datos nuevos (navegando a él si hace falta); la página de aterrizaje y la pérdida de filtro/Auto ON van como observación.',
  fuente_recarga: 'tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo3.md:5338-5350,5442-5446',
});
export const IDS = ['API-186-01', 'UI-186-01', 'UI-186-02'];
export const CAPACIDADES = Object.freeze({
  contrato: 'sigab-qa-ejecutor/1', grupo: 'G95', casos: [CASO],
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: { [CASO]: { API: ['API-186-01'], UI: ['UI-186-01', 'UI-186-02'] } },
  limite: { solicitudes_directas: 5, margen_cierre: 2, ui_api: 60, duracion_segundos: 360 },
});

export function clasificarApi(respuestas) {
  if (!Array.isArray(respuestas) || !respuestas.length || respuestas[0]?.http == null)
    return { estado: 'NO_CONCLUYENTE', motivo: 'Newman no recibió respuesta del dashboard' };
  const [dashboard, refresh] = respuestas;
  if (dashboard.http === 200)
    return { estado: 'RECHAZADO', motivo: 'Token anterior obtuvo HTTP 200 con el dashboard tras el cierre' };
  if (respuestas.length !== 2 || refresh?.http == null)
    return { estado: 'NO_CONCLUYENTE', motivo: 'Newman no recibió respuesta del refresh' };
  if (respuestas.some(x => x.http >= 500))
    return { estado: 'BLOQUEADO', motivo: 'Infraestructura/sesión respondió 5xx' };
  if (![401, 410].includes(dashboard.http) || ![401, 410].includes(refresh.http))
    return { estado: 'RECHAZADO', motivo: `Token anterior: dashboard HTTP ${dashboard.http}; refresh HTTP ${refresh.http}` };
  return { estado: 'APROBADO', motivo: `Token anterior rechazado: dashboard HTTP ${dashboard.http}; refresh HTTP ${refresh.http}` };
}

export function avisoSesionTerminada(texto) {
  const aviso = String(texto ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  return /(?:\bsesion\b.{0,100}\b(?:expir\w*|venc\w*|cerr\w*|finaliz\w*)\b|\b(?:expir\w*|venc\w*|cerr\w*|finaliz\w*)\b.{0,100}\bsesion\b|\b(?:inicia\w*|ingresa\w*|vuelve\w*|volver)\b.{0,60}\b(?:sesion|de nuevo|nuevamente|otra vez)\b)/i.test(aviso);
}

export function clasificarUi(acta) {
  const estado = (nombre, motivo) => ({ estado: nombre, motivo });
  const ambos = (nombre, motivo) => Object.fromEntries(['UI-186-01', 'UI-186-02'].map(id => [id, estado(nombre, motivo)]));
  if (!acta || acta.caso !== CASO || acta.id !== 'UI-186-01/UI-186-02' || !acta.captura)
    return ambos('ERROR_QA', 'Acta o captura Cypress ausente');
  if (!Number.isInteger(acta.lecturas_dashboard) || acta.lecturas_dashboard < 0)
    return ambos('ERROR_QA', 'CONTEO_DASHBOARD_INVALIDO');
  if (acta.error_selector) return ambos('ERROR_QA', `ERROR_SELECTOR:${acta.error_selector.etapa}:${acta.error_selector.selector}`);
  if (acta.lecturas_dashboard > LIMITE_LECTURAS_DASHBOARD) return ambos('ERROR_QA', 'PRESUPUESTO_DASHBOARD_SUPERADO');
  if (acta.error_qa) return ambos('ERROR_QA', acta.error_qa);
  if (acta.infra_5xx) return ambos('BLOQUEADO', 'Sesión o dashboard respondió 5xx');
  if (acta.bloqueo_datos) return ambos('BLOQUEADO', acta.bloqueo_datos);
  if (!acta.dashboard_inicial_200 || !acta.auto_on || !acta.periodica_200 || !acta.filtro_fijado)
    return ambos('NO_CONCLUYENTE', acta.auto_motivo || 'No se acreditó Auto ON, petición periódica 200 y filtro por ID');
  if (!acta.segundo_login_200 || !acta.dashboard_rechazado_401)
    return ambos('NO_CONCLUYENTE', 'No se observó cierre de sesión con 401');
  const observaciones = [];
  if (acta.ruta_aterrizaje && acta.ruta_aterrizaje !== '/telemetria/monitoreo')
    observaciones.push(`Reingreso aterrizó en ${acta.ruta_aterrizaje}; navegación manual al monitoreo: ${acta.navegacion_manual ? 'sí' : 'no'}`);
  if (acta.filtro_conservado === false) observaciones.push('Filtro por unidad no conservado');
  if (acta.auto_conservado === false) observaciones.push('Auto ON no conservado');
  return {
    'UI-186-01': acta.redirigido_login && acta.aviso_sesion_terminada
      && avisoSesionTerminada(acta.aviso_texto) && acta.sin_200_vencida && acta.auto_detenido
      ? estado('APROBADO', 'Sin GET 200 tras 401, Auto detenido, aviso de sesión terminada y login')
      : estado('RECHAZADO', 'Falta detención, aviso de sesión terminada o redirección a login'),
    'UI-186-02': {
      ...(acta.reingreso_200 && acta.monitoreo_cargado && !acta.error_interno_visible
        && acta.recarga_200_posterior
        ? estado('APROBADO', 'Tras reingreso, monitoreo cargado con nuevo GET dashboard 200')
        : acta.reingreso_200 && acta.monitoreo_cargado
          ? estado('RECHAZADO', 'Monitoreo sin recarga GET 200 posterior o con error interno visible')
          : estado('NO_CONCLUYENTE', 'No se acreditó reingreso o carga del monitoreo')),
      observaciones,
    },
  };
}

export function evaluarResultadoCypress(ui) {
  const s = ui?.resumen;
  if (ui?.error || !s || s.totalTests !== 1 || s.totalPending !== 0 || s.totalSkipped !== 0
    || s.specs !== 1 || s.totalPassed + s.totalFailed !== 1 || !ui.acta || !ui.capturas?.length)
    return Object.fromEntries(['UI-186-01', 'UI-186-02'].map(id => [id, { estado: 'ERROR_QA', motivo: 'CYPRESS_CONTEO_O_EVIDENCIA_INVALIDA' }]));
  return clasificarUi(ui.acta);
}

export function decidir(comprobaciones, { uiPruebas = 0, captura = false, cierreHttp = null } = {}) {
  const estados = comprobaciones.map(x => x.estado);
  const completa = IDS.every(id => comprobaciones.some(x => x.id === id && ['APROBADO', 'RECHAZADO'].includes(x.estado)));
  if (estados.includes('RECHAZADO')) return 'RECHAZADO';
  if (estados.includes('BLOQUEADO')) return 'BLOQUEADO';
  if (!completa || uiPruebas !== 1 || !captura) return 'NO_CONCLUYENTE';
  if (cierreHttp !== 200) return 'BLOQUEADO';
  return 'APROBADO';
}
