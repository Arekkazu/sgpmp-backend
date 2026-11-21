const normalizarBase = ruta => ruta.replace(/\/+$/, '');
const bajoBase = (ruta, base) => !base || ruta === base || ruta.startsWith(base + '/');

function selectorPorEtiqueta(raiz, nombre) {
  const label = [...raiz.querySelectorAll('label')].find(x => x.textContent.trim() === nombre);
  if (label) {
    const id = label.getAttribute('for');
    const control = id
      ? (raiz.ownerDocument || raiz).getElementById(id)
      : label.querySelector('select,[role="combobox"]') || label.parentElement?.querySelector('select,[role="combobox"]');
    if (control) return control;
  }
  return [...raiz.querySelectorAll('select,[role="combobox"]')].find(x => x.getAttribute('aria-label') === nombre) || null;
}

function clasificarIntercepcion(url, metodo, apiBase, frontBase, ensayo = false) {
  const u = new URL(url), api = new URL(apiBase), front = new URL(frontBase);
  const apiPath = normalizarBase(api.pathname), frontPath = normalizarBase(front.pathname);
  const esApi = (ensayo ? u.origin === api.origin : /^https:\/\/(?:www\.)?api\.inmero\.co$/.test(u.origin)) &&
    bajoBase(u.pathname, apiPath);
  if (esApi) return { destino: 'API', ruta: (u.pathname.slice(apiPath.length) || '/').replace(/^\/+/, '/') };
  const esFront = metodo === 'GET' && u.origin === front.origin &&
    bajoBase(u.pathname, frontPath);
  return { destino: esFront ? 'FRONTAL' : 'BLOQUEADO', ruta: null };
}

function mesPeriodo(fecha) {
  const partes = String(fecha || '').match(/^(\d{4})-(\d{2})-\d{2}/);
  if (!partes) return null;
  const fechaUtc = new Date(Date.UTC(Number(partes[1]), Number(partes[2]) - 1, 1));
  if (Number.isNaN(fechaUtc.getTime())) return null;
  const texto = new Intl.DateTimeFormat('es-CO', {month:'long', year:'numeric', timeZone:'UTC'}).format(fechaUtc);
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function opcionTitular(numero, opciones) {
  return opciones.find(x => String(x.texto || '').match(/\bNIT\s+([^\s·]+)/i)?.[1] === String(numero)) || null;
}

function opcionPeriodo(periodo, fecha, opciones) {
  const porId = opciones.find(x => String(x.value) === String(periodo));
  if (porId) return porId;
  const mes = mesPeriodo(fecha);
  if (!mes) return null;
  const candidatas = opciones.filter(x => String(x.texto || '').startsWith(mes + ' ·') || String(x.texto || '') === mes);
  return candidatas.length === 1 ? candidatas[0] : null;
}

function evaluarSeleccionPeriodo(periodo, respuesta, opciones, vencido = false, fecha = null) {
  const enApi = Array.isArray(respuesta) && respuesta.some(x => Number(x.id_periodo_contable) === Number(periodo));
  if (!enApi) return 'AUSENTE_API';
  if (opcionPeriodo(periodo, fecha, opciones)) return 'SELECCIONAR';
  return vencido ? 'AUSENTE_SELECTOR' : 'ESPERAR_OPCION';
}

function requiereCambioExplicito(periodo, seleccionado, ensayo) {
  return ensayo && String(seleccionado) === String(periodo);
}

module.exports = { clasificarIntercepcion, evaluarSeleccionPeriodo, requiereCambioExplicito, mesPeriodo, opcionTitular, opcionPeriodo, selectorPorEtiqueta };
