// Cadenas de es-CO/finanzas.json: hecho.VARIACION_VR_TB y sentido.GANANCIA.
const normalizar = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();

function coincideCombinacion(mensaje, especieId, especieNombre = '', sentidoElegido = 'GANANCIA') {
  const texto = normalizar(mensaje);
  const hecho = texto.includes('VARIACION_VR_TB') || texto.includes('VARIACION POR TRANSFORMACION BIOLOGICA');
  const sentido = ['GANANCIA','PERDIDA'].includes(sentidoElegido) && new RegExp(`\\b${sentidoElegido}\\b`).test(texto);
  if (!hecho || !sentido) return false;
  const nombre = normalizar(especieNombre).trim();
  return Boolean(nombre && texto.includes(nombre));
}

const normalizarBase = ruta => ruta.replace(/\/+$/, '');
const bajoBase = (ruta, base) => !base || ruta === base || ruta.startsWith(base + '/');

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

module.exports = { coincideCombinacion, clasificarIntercepcion };
