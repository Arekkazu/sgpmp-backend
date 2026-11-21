// Clasificación de la carga real del navegador; el oráculo visual se evalúa aparte.
const MENSAJE_MATRIZ = 'Sin datos disponibles';
const MENSAJES_AUSENCIA = new Set(['sin datos', 'sin datos disponibles']);
function mensajeAusenciaEquivalente(texto) {
  return MENSAJES_AUSENCIA.has(String(texto || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('es'));
}
// La fecha del último dato es metadato histórico. Buscar cifras presentadas como
// datos actuales, tanto en la cabecera como en las tarjetas de la unidad.
function sinValoresFabricados(texto) {
  const visible = String(texto || '').replace(/\s+/g, ' ');
  const contador = /(?:\d+\s+sensores?\s+(?:en\s+l[ií]nea|activos?|conectados?)|sensores?\s+(?:en\s+l[ií]nea|activos?|conectados?)\s*[:=]?\s*\d+)/iu;
  const lectura = /(?:\b(?:valor|lectura|temperatura|humedad|presi[oó]n|ph)\s*[:=]?\s*\d+(?:[.,]\d+)?\b|\b\d+(?:[.,]\d+)?\s*(?:°\s*[CF]|%|ppm|mg\/l|mS\/cm)(?!\p{L}))/iu;
  return !contador.test(visible) && !lectura.test(visible);
}
function observacionDocumental(fase, vista, texto) {
  if (!mensajeAusenciaEquivalente(texto) || texto === MENSAJE_MATRIZ) return null;
  return `${fase}, ${vista}: texto observado «${texto}»; equivalente a «${MENSAJE_MATRIZ}» por decisión QA de 2026-10-25. Sin incidencia ni efecto en el veredicto.`;
}

function clasificarCarga({ http, eco, vencio = false, renderVencio = false, errorRed = null, ui = {} }) {
  if (http >= 500) return { estado: 'RECHAZADO', criterio: 'HTTP_5XX' };
  if (http === 401 || http === 403 || (http != null && eco !== true))
    return { estado: 'ERROR_QA', criterio: 'SESION_O_ECO_RUN' };
  if (http === 200 && (renderVencio || ui.cargando))
    return { estado: 'NO_CONCLUYENTE', criterio: 'CARGA_SIN_TERMINAR' };
  if (http === 200) return { estado: 'EVALUAR_UI', criterio: 'HTTP_200' };
  if (vencio || errorRed || http == null) return {
    estado: ui.incumplimientoAcreditado ? 'RECHAZADO' : 'NO_CONCLUYENTE',
    criterio: ui.incumplimientoAcreditado ? 'ORACULO_VISUAL_INCUMPLIDO' : 'CARGA_SIN_RESPUESTA_DIAGNOSTICO_PENDIENTE',
  };
  return { estado: 'NO_CONCLUYENTE', criterio: `HTTP_${http}_DIAGNOSTICO_PENDIENTE` };
}

function sesionCon5xx(peticiones) {
  return (peticiones || []).find(x => ['/sesiones/refresh', '/usuarios/me', '/sesiones/me/permisos']
    .includes(x.ruta) && x.http >= 500) || null;
}

function crearColaPeticiones() {
  let cola = Promise.resolve();
  return {
    tomar(iniciar, { esperaMaximaMs = 90000, alVencer = () => {} } = {}) {
      let liberar;
      const turno = cola;
      cola = new Promise(resolve => {
        liberar = () => { if (liberar.cerrada) return; liberar.cerrada = true; resolve(); };
      });
      return turno.then(() => {
        const reloj = setTimeout(() => {
          try { alVencer(); } finally { liberar(); }
        }, esperaMaximaMs);
        const cerrar = () => { clearTimeout(reloj); liberar(); };
        try { return Promise.resolve(iniciar(cerrar)).catch(error => { cerrar(); throw error; }); }
        catch (error) { cerrar(); throw error; }
      });
    },
  };
}

function peticionesSinRespuesta(peticiones) {
  return (peticiones || []).filter(x => !x.fin);
}

function indicadorCargaActivo(texto) {
  return String(texto || '').includes('Cargando…');
}

function esperarRenderEstable(win, { limiteMs = 90000, estableMs = 300, intervaloMs = 100 } = {}) {
  return new Promise(resolve => {
    const inicio = Date.now();
    let anterior = null;
    let estableDesde = 0;
    const revisar = () => {
      const cuerpo = win.document.body;
      const texto = cuerpo?.textContent || '';
      const cargando = indicadorCargaActivo(texto);
      const firma = `${texto}|${cuerpo?.querySelectorAll('section').length || 0}`;
      if (cargando || firma !== anterior) estableDesde = Date.now();
      anterior = firma;
      if (!cargando && Date.now() - estableDesde >= estableMs) return resolve(false);
      if (Date.now() - inicio >= limiteMs) return resolve(true);
      win.setTimeout(revisar, intervaloMs);
    };
    revisar();
  });
}

function atributosValidos(ui) {
  return ui.gris && mensajeAusenciaEquivalente(ui.mensaje_ausencia) && ui.fecha_historica
    && ui.sin_valores_fabricados && !ui.desde_cache;
}

function evaluarOraculoUi(uiInicial, uiObjetivo) {
  if (uiInicial.cargando || uiObjetivo.cargando)
    return { estado: 'NO_CONCLUYENTE', criterio: 'CARGA_SIN_TERMINAR' };
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

module.exports = { MENSAJE_MATRIZ, mensajeAusenciaEquivalente, observacionDocumental, clasificarCarga,
  sesionCon5xx, crearColaPeticiones, peticionesSinRespuesta, indicadorCargaActivo,
  esperarRenderEstable, sinValoresFabricados,
  evaluarOraculoUi, intentarDesactivarAuto };
