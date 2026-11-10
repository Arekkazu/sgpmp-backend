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

module.exports = { clasificarIntercepcion };
