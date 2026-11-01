export const CASO = 'TC-M03-185';
export const ORACULO = 'HTTP 200 con arreglos vacíos. La interfaz muestra "No tiene unidades productivas asignadas" y sugiere contactar al administrador; no se devuelve ningún dato de otras granjas ni error interno.';
export const IDS = ['API-185-01', 'API-185-02', 'UI-185-01'];
export const SESION_LOCAL = Object.freeze(['POST /sesiones/', 'POST /sesiones/refresh']);
export const LIMITE = Object.freeze({ solicitudes_directas: 22, margen_cierre: 5, ui_api: 20, inactividad_segundos: 180 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G94', casos: [CASO],
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: { [CASO]: { API: IDS.filter(x => x.startsWith('API-')), UI: IDS.filter(x => x.startsWith('UI-')) } },
  limite: LIMITE });

export function idsFincas(respuesta) {
  if (respuesta?.http !== 200 || !Array.isArray(respuesta.cuerpo?.items)
    || respuesta.cuerpo.total !== respuesta.cuerpo.items.length) throw new Error('PRE_FINCAS_NO_VERIFICABLES');
  const ids = respuesta.cuerpo.items.map(x => Number(x.id_finca));
  if (ids.some(x => !Number.isSafeInteger(x) || x < 1) || new Set(ids).size !== ids.length)
    throw new Error('PRE_FINCAS_INVALIDAS');
  return ids.sort((a, b) => a - b);
}

export function evaluarApi(id, respuesta) {
  const { http, cuerpo: j } = respuesta ?? {};
  if (http == null) return { estado: 'NO_EJECUTADA', motivo: 'Sin respuesta' };
  if (http >= 500) return { estado: 'RECHAZADO', motivo: `HTTP ${http}, error interno` };
  if (id === 'API-185-02' && [403, 404].includes(http))
    return { estado: 'APROBADO', motivo: `HTTP ${http}; unidad antes asignada no accesible` };
  if (http !== 200) return { estado: 'RECHAZADO', motivo: `HTTP ${http}; respuesta no conforme` };
  if (j?.total !== 0 || !Array.isArray(j?.resumen_unidades) || j.resumen_unidades.length
    || !Array.isArray(j?.sensores) || j.sensores.length)
    return { estado: 'RECHAZADO', motivo: 'Respuesta contiene datos o no acredita arreglos vacíos y total cero' };
  return { estado: 'APROBADO', motivo: 'HTTP 200, total 0 y arreglos vacíos' };
}

export function clasificarUi(acta) {
  if (!acta) return { estado: 'ERROR_QA', motivo: 'Cypress sin acta; automatización por revisar' };
  if (acta.estado === 'ERROR_QA') return { estado: 'ERROR_QA', motivo: acta.motivo || 'BLOQUEO_G94' };
  if (!Array.isArray(acta.peticiones)) return { estado: 'ERROR_QA', motivo: 'Acta sin peticiones verificables' };
  if (acta.peticiones.some(x => x.en_sandbox !== true))
    return { estado: 'ERROR_QA', motivo: 'Petición UI fuera del RUN' };
  if (acta.peticiones.some(x => ['/usuarios/me', '/sesiones/me/permisos'].includes(x.ruta) && x.http >= 500))
    return { estado: 'NO_CONCLUYENTE', motivo: 'SESION_5XX dentro del RUN' };
  if (acta.peticiones.some(x => x.http != null && !x.eco_run))
    return { estado: 'NO_CONCLUYENTE', motivo: 'Eco RUN ausente en petición UI' };
  if (acta.pendiente_al_terminar || acta.carga_sin_terminar)
    return { estado: 'NO_CONCLUYENTE', motivo: 'Carga o peticiones UI sin terminar' };
  if (acta.dashboard?.http >= 500 && acta.dashboard.eco_run)
    return { estado: 'RECHAZADO', motivo: `Dashboard HTTP ${acta.dashboard.http}; error interno` };
  if (!acta.dashboard || acta.dashboard.http == null)
    return { estado: 'NO_CONCLUYENTE', motivo: 'dashboard no recibido en el plazo' };
  if (acta.dashboard.http !== 200 || !acta.dashboard.eco_run)
    return { estado: 'NO_CONCLUYENTE', motivo: 'Dashboard UI sin respuesta válida y eco RUN' };
  if (acta.mensaje_exacto && acta.contacto_admin && acta.sin_tarjetas && acta.sin_error_interno
    && !acta.datos_ajenos && acta.canario_e7 !== 'SENSORES_DEVUELTOS')
    return { estado: 'APROBADO', motivo: 'Oráculo visual completo' };
  return { estado: 'RECHAZADO', motivo: 'La pantalla cargó y difiere del oráculo visual' };
}

export function evaluarResultadoCypress(ui) {
  const s = ui?.resumen;
  const contadores = [s?.totalTests, s?.totalPassed, s?.totalFailed,
    s?.totalPending, s?.totalSkipped, s?.specs];
  if (ui?.error || !s || contadores.some(n => !Number.isInteger(n) || n < 0)
    || s.totalTests !== 1 || s.totalPassed + s.totalFailed !== 1
    || s.totalPending !== 0 || s.totalSkipped !== 0 || s.specs !== 1)
    return { estado: 'ERROR_QA', motivo: 'CYPRESS_CONTEO_INVALIDO: se exige 1 prueba ejecutada, 0 pending y 0 skipped' };
  if (!ui.acta || ui.rel !== 'cypress/UI-185-01.json'
    || ui.acta.caso !== CASO || ui.acta.id !== 'UI-185-01')
    return { estado: 'ERROR_QA', motivo: 'CYPRESS_SIN_ACTA_UI-185-01' };
  if (ui.proceso !== s.totalFailed)
    return { estado: 'ERROR_QA', motivo: 'CYPRESS_SALIDA_INCOHERENTE' };
  return clasificarUi(ui.acta);
}
