// Clasificación de la carga real del navegador; el oráculo visual se evalúa aparte.
const MENSAJE_MATRIZ = 'Sin datos disponibles';
const MENSAJES_AUSENCIA = new Set(['sin datos', 'sin datos disponibles']);
function mensajeAusenciaEquivalente(texto) {
  return MENSAJES_AUSENCIA.has(String(texto || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('es'));
}
function observacionDocumental(fase, vista, texto) {
  if (!mensajeAusenciaEquivalente(texto) || texto === MENSAJE_MATRIZ) return null;
  return `${fase}, ${vista}: texto observado «${texto}»; equivalente a «${MENSAJE_MATRIZ}» por decisión QA de 2026-10-25. Sin incidencia ni efecto en el veredicto.`;
}

function clasificarCarga({ http, eco, vencio = false, errorRed = null, ui = {} }) {
  if (http >= 500) return { estado: 'RECHAZADO', criterio: 'HTTP_5XX' };
  if (http === 401 || http === 403 || (http != null && eco !== true))
    return { estado: 'ERROR_QA', criterio: 'SESION_O_ECO_RUN' };
  if (http === 200) return { estado: 'EVALUAR_UI', criterio: 'HTTP_200' };
  if (vencio || errorRed || http == null) return {
    estado: ui.incumplimientoAcreditado ? 'RECHAZADO' : 'NO_CONCLUYENTE',
    criterio: ui.incumplimientoAcreditado ? 'ORACULO_VISUAL_INCUMPLIDO' : 'CARGA_SIN_RESPUESTA_DIAGNOSTICO_PENDIENTE',
  };
  return { estado: 'NO_CONCLUYENTE', criterio: `HTTP_${http}_DIAGNOSTICO_PENDIENTE` };
}

function atributosValidos(ui) {
  return ui.gris && mensajeAusenciaEquivalente(ui.mensaje_ausencia) && ui.fecha_historica
    && ui.sin_valores_fabricados && !ui.desde_cache;
}

function evaluarOraculoUi(uiInicial, uiObjetivo) {
  if (!uiInicial.unidad_objetivo_presente)
    return { estado: 'RECHAZADO', criterio: 'UNIDAD_DESAPARECE_DEL_PANEL' };
  if (!atributosValidos(uiInicial))
    return { estado: 'RECHAZADO', criterio: 'ORACULO_PANEL_GLOBAL_INCUMPLIDO' };
  if (!uiObjetivo.unidad_objetivo_presente || !atributosValidos(uiObjetivo))
    return { estado: 'RECHAZADO', criterio: 'ORACULO_UI_INCUMPLIDO' };
  return { estado: 'APROBADO', criterio: 'ORACULOS_UI_ACREDITADOS' };
}

function intentarDesactivarAuto(cuerpo) {
  const boton = [...cuerpo.querySelectorAll('button')]
    .find(x => x.textContent.trim() === 'Auto ON');
  if (!boton) return 'CONTROL_AUTO_ON_AUSENTE';
  if (boton.disabled || !boton.getClientRects().length) return 'CONTROL_AUTO_ON_NO_PULSABLE';
  try { boton.click(); }
  catch { return 'CONTROL_AUTO_ON_NO_PULSABLE'; }
  return null;
}

module.exports = { MENSAJE_MATRIZ, mensajeAusenciaEquivalente, observacionDocumental, clasificarCarga, evaluarOraculoUi, intentarDesactivarAuto };
