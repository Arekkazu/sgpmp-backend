// Utilidades de TC-M09-G76-v2.0 (RF-24 v2.0, CU05 Flujo D).
// Discovery de SOLO LECTURA. La única escritura que este módulo puede realizar es el PATCH
// de desactivación de preparación de TC-146, y solo cuando no existe ningún dispositivo ya
// inactivo utilizable. Sin SQL.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Protección de aislamiento: no puede ejecutarse desde la carpeta histórica TC-M09-G76/.
const FOLDER = 'TC-M09-G76-v2.0';
if (path.basename(__dirname) !== FOLDER) {
  throw new Error(`Directorio no autorizado para ${FOLDER}`);
}

const GROUP_ID = 'TC-M09-G76-v2.0';
const RF = 'RF-24 v2.0';
const CU = 'CU05 — Gestionar Dispositivos IoT, Flujo D';

const CASOS = {
  '146': { caso: 'TC-M09-146-v2.0', titulo: 'Dispositivo inactivo', http: 422, observaciones: 'QA TC-M09-146-v2.0' },
  '147': { caso: 'TC-M09-147-v2.0', titulo: 'Área incorrecta', http: 400, observaciones: 'QA TC-M09-147-v2.0' }
};

const POST_BUDGET = 2;        // 2 POST de calibración. No hay reintentos.
const PATCH_SETUP_BUDGET = 1; // Máximo 1 PATCH de preparación, y solo si es imprescindible.

// Fixtures preferidos por la matriz. Se validan por GET; no se asumen vigentes.
const PREF_146_DEVICE = Number(process.env.G76_146_DEVICE_ID || 47);
const PREF_147 = {
  sensor: Number(process.env.G76_147_SENSOR_ID || 6),
  dispositivo: Number(process.env.G76_147_DEVICE_ID || 3),
  areaVigente: Number(process.env.G76_147_AREA_VIGENTE || 3),
  areaAlternativa: Number(process.env.G76_147_AREA_ALT || 1),
  valor: process.env.G76_147_VALOR || '22.5000'
};

// --------------------------------------------------------------- decimal exacto
const escalar = (v) => {
  const [e, d = ''] = String(v).replace('+', '').split('.');
  const neg = e.startsWith('-');
  const abs = BigInt((neg ? e.slice(1) : e) + (d + '0000').slice(0, 4));
  return neg ? -abs : abs;
};
const formatear = (t) => {
  const neg = t < 0n;
  const abs = (neg ? -t : t).toString().padStart(5, '0');
  return (neg ? '-' : '') + abs.slice(0, -4) + '.' + abs.slice(-4);
};
const igualDecimal = (a, b) => escalar(a) === escalar(b);
const entre = (v, min, max) => escalar(v) > escalar(min) && escalar(v) < escalar(max);
// Punto medio exacto del rango: garantiza un valor interior, nunca una frontera.
const interior = (min, max) => formatear((escalar(min) + escalar(max)) / 2n);

// ------------------------------------------------------------------ sanitización
const secretos = () => [process.env.QA_PASSWORD, process.env.QA_ADMIN_PASSWORD].filter(Boolean);
function clean(texto) {
  let s = String(texto);
  for (const x of secretos()) s = s.split(x).join('[REDACTED]');
  return s
    .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9_.-]{12,}/g, 'Bearer [REDACTED]');
}
function cleanHtml(html) {
  return clean(html)
    .replace(/Authorization/gi, '[REDACTED_HEADER]')
    .replace(/Bearer/gi, '[REDACTED_HEADER]')
    .replace(/access_token/gi, '[REDACTED]')
    .replace(/refresh_token/gi, '[REDACTED]')
    .replace(/contrasena/gi, '[REDACTED]')
    .replace(/password/gi, '[REDACTED]')
    .replace(/set-cookie/gi, '[REDACTED]')
    .replace(/\bjwt\b/gi, '[REDACTED]');
}

// ------------------------------------------------------------- rutas y evidencia
function runDir(runId, sub) {
  const d = sub ? path.join(__dirname, 'RESULTADOS', runId, sub) : path.join(__dirname, 'RESULTADOS', runId);
  fs.mkdirSync(d, { recursive: true });
  return d;
}
function save(runId, name, value) {
  const file = path.join(runDir(runId), name);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, clean(JSON.stringify(value, null, 2)));
  return file;
}
const sha256 = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');

// --------------------------------------------------------------------- HTTP
const base = () => {
  const b = process.env.QA_BASE_URL;
  if (!b) throw new Error('QA_BASE_URL requerido');
  return b.replace(/\/$/, '');
};
async function login(email, password) {
  const r = await fetch(base() + '/sesiones/', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo_electronico: email, contrasena: password }),
    signal: AbortSignal.timeout(25000)
  });
  const c = await r.json().catch(() => null);
  if (r.status !== 200 || !c?.token) {
    const e = new Error(`login HTTP ${r.status}${c?.error_code ? ' ' + c.error_code : ''}`);
    e.status = r.status; throw e;
  }
  return c.token;
}
async function get(endpoint, token) {
  const r = await fetch(base() + endpoint, { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(25000) });
  return { status: r.status, cuerpo: await r.json().catch(() => null) };
}
async function getOk(endpoint, token) {
  const { status, cuerpo } = await get(endpoint, token);
  if (status !== 200) { const e = new Error(`GET ${endpoint} HTTP ${status}`); e.status = status; e.cuerpo = cuerpo; throw e; }
  return cuerpo;
}
// Única escritura posible de este módulo, y solo como preparación autorizada de TC-146.
async function patch(endpoint, token) {
  const r = await fetch(base() + endpoint, {
    method: 'PATCH', headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(25000)
  });
  return { status: r.status, cuerpo: await r.json().catch(() => null) };
}

const sensorIdOf = (x) => (x && x.id_sensor !== undefined ? x.id_sensor : x && x.id_sensores);
const vigente = (a) => a && a.tiene_estado === true && (a.fecha_finalizacion === null || a.fecha_finalizacion === undefined);

// ------------------------------------------------- mensajes exigidos por RF-24 v2.0
const mensaje146 = (serial) =>
  `Operación rechazada: El dispositivo ${serial} está inactivo. Debe activar el dispositivo antes de proceder con el registro de nuevos parámetros de calibración.`;
const mensaje147 = (idSensor, idArea) =>
  `Conflicto de ubicación: El sensor ${idSensor} no está asociado al área ${idArea}. Verifique la ubicación física y lógica del equipo antes de calibrar.`;

// Lectura con Ingeniero y, si su alcance no lo permite, con Administrador (solo GET).
//
// Ojo: el alcance del Ingeniero no siempre se manifiesta como 404. En el listado de
// dispositivos responde HTTP 200 con una lista VACÍA, así que un fallback guiado solo por el
// status nunca se activaría y el discovery concluiría que no existe ningún dispositivo.
// Con exigirNoVacio=true, una colección vacía también activa la lectura auxiliar.
function lectorConFallback(tokenIng, tokenAdmin, registro) {
  return async (endpoint, exigirNoVacio = false) => {
    const ing = await get(endpoint, tokenIng);
    const vacio = exigirNoVacio && Array.isArray(ing.cuerpo?.items) && ing.cuerpo.items.length === 0;
    if (ing.status === 200 && !vacio) return { fuente: 'Ingeniero', cuerpo: ing.cuerpo, statusIngeniero: 200 };
    if (ing.status === 200 && vacio && tokenAdmin) {
      const adm = await get(endpoint, tokenAdmin);
      if (adm.status === 200 && (adm.cuerpo?.items || []).length > 0) {
        registro.push({ endpoint, statusConIngeniero: 200, motivo: 'el Ingeniero recibe 200 con listado vacío por alcance' });
        return { fuente: 'Administrador', cuerpo: adm.cuerpo, statusIngeniero: 200 };
      }
      return { fuente: 'Ingeniero', cuerpo: ing.cuerpo, statusIngeniero: 200 };
    }
    if (ing.status === 200) return { fuente: 'Ingeniero', cuerpo: ing.cuerpo, statusIngeniero: 200 };
    if (!tokenAdmin) { const e = new Error(`GET ${endpoint} HTTP ${ing.status} y sin Administrador disponible`); e.status = ing.status; throw e; }
    const adm = await get(endpoint, tokenAdmin);
    if (adm.status !== 200) { const e = new Error(`GET ${endpoint} HTTP ${adm.status} también con Administrador`); e.status = adm.status; throw e; }
    registro.push({ endpoint, statusConIngeniero: ing.status, motivo: 'fuera del alcance del Ingeniero' });
    return { fuente: 'Administrador', cuerpo: adm.cuerpo, statusIngeniero: ing.status };
  };
}

// ---------------------------------------------------------------- fixture TC-146
// Busca primero un dispositivo YA inactivo utilizable. Solo si no existe ninguno,
// devuelve candidatos seguros para la preparación autorizada por PATCH.
async function fixture146(tokenIng, tokenAdmin, usoAdmin) {
  const leer = lectorConFallback(tokenIng, tokenAdmin, usoAdmin);
  const rangos = await leer('/configuracion/sensores/rangos-calibracion');
  const porCategoria = Object.fromEntries((rangos.cuerpo.items || []).map(r => [r.categoria, { min: String(r.valor_min), max: String(r.valor_max) }]));

  const listado = await leer('/configuracion/dispositivos-iot?solo_activos=false', true);
  const todos = listado.cuerpo.items || [];
  const inactivos = todos.filter(d => d.es_activo === false);
  // Prioridad al dispositivo de la matriz, luego el resto de inactivos.
  inactivos.sort((a, b) => (a.id_dispositivo_iot === PREF_146_DEVICE ? -1 : b.id_dispositivo_iot === PREF_146_DEVICE ? 1 : a.id_dispositivo_iot - b.id_dispositivo_iot));

  const evaluar = async (d) => {
    const sensores = await leer(`/configuracion/dispositivos-iot/${d.id_dispositivo_iot}/sensores`, true);
    for (const s of (sensores.cuerpo.items || []).filter(x => x.es_activo === true && porCategoria[x.categoria])) {
      const sid = sensorIdOf(s);
      const asoc = await leer(`/configuracion/sensores/${sid}/asociaciones`, true);
      const a = (asoc.cuerpo.items || []).find(x => vigente(x) && sensorIdOf(x) === sid && x.id_dispositivo_iot === d.id_dispositivo_iot);
      if (!a) continue;
      const rango = porCategoria[s.categoria];
      const historial = await getOk(`/configuracion/sensores/${sid}/calibraciones`, tokenIng);
      return {
        dispositivo: { id: d.id_dispositivo_iot, serial: d.serial, es_activo: d.es_activo, descripcion: d.descripcion, id_dispositivo_gateway: d.id_dispositivo_gateway },
        sensor: { id: sid, nombre: s.nombre, categoria: s.categoria, es_activo: s.es_activo, id_dispositivo_iot: s.id_dispositivo_iot },
        area: { id_infraestructura: a.id_infraestructura, punto_instalacion: a.punto_instalacion, tiene_estado: a.tiene_estado, fecha_finalizacion: a.fecha_finalizacion },
        rango: { categoria: s.categoria, min: rango.min, max: rango.max },
        valorInterior: interior(rango.min, rango.max),
        historialInicial: { total: historial.total, ids: (historial.items || []).map(c => c.id_calibracion) }
      };
    }
    return null;
  };

  for (const d of inactivos) {
    try {
      const f = await evaluar(d);
      if (f) return { fixture: f, preexistenteInactivo: true, requierePatch: false, candidatosParaPatch: [], totalInactivosEnTest: inactivos.length };
    } catch { /* candidato descartado */ }
  }

  // No hay inactivo utilizable: se buscan candidatos SEGUROS para el PATCH autorizado.
  const conGatewayDependiente = new Set(todos.map(d => d.id_dispositivo_gateway).filter(x => x !== null && x !== undefined));
  const candidatos = [];
  for (const d of todos.filter(x => x.es_activo === true)) {
    // Debe ser claramente un dispositivo de prueba/QA.
    const esQA = /^(QA|TC-|TEST|DEBUG|BUGCHECK|IOT-TEST)/i.test(String(d.serial || ''));
    if (!esQA) continue;
    if (conGatewayDependiente.has(d.id_dispositivo_iot)) continue; // actúa como Gateway de otros
    let configuraciones = null;
    try { configuraciones = (await leer(`/configuracion/dispositivos-iot/${d.id_dispositivo_iot}/configuraciones`)).cuerpo; } catch { continue; }
    const pendientes = (configuraciones?.items || []).filter(c => /PENDIENTE|NO_CONF/i.test(String(c.estado ?? c.estado_configuracion ?? '')));
    if (pendientes.length) continue;
    let f = null;
    try { f = await evaluar(d); } catch { f = null; }
    if (!f) continue;
    candidatos.push({ ...f, dependientesDeGateway: 0, configuracionesPendientes: 0, serialEsQA: true });
  }
  return { fixture: null, preexistenteInactivo: false, requierePatch: true, candidatosParaPatch: candidatos, totalInactivosEnTest: inactivos.length };
}

// ---------------------------------------------------------------- fixture TC-147
async function fixture147(tokenIng, tokenAdmin, usoAdmin) {
  const leer = lectorConFallback(tokenIng, tokenAdmin, usoAdmin);
  const rangos = await leer('/configuracion/sensores/rangos-calibracion');
  const porCategoria = Object.fromEntries((rangos.cuerpo.items || []).map(r => [r.categoria, { min: String(r.valor_min), max: String(r.valor_max) }]));

  const armar = async (idDispositivo, idSensor, idAreaAlt) => {
    const dispositivo = await leer(`/configuracion/dispositivos-iot/${idDispositivo}`);
    if (dispositivo.cuerpo?.es_activo !== true) return null;
    const sensores = await leer(`/configuracion/dispositivos-iot/${idDispositivo}/sensores`, true);
    const s = (sensores.cuerpo.items || []).find(x => sensorIdOf(x) === idSensor && x.es_activo === true);
    if (!s || !porCategoria[s.categoria]) return null;
    const asoc = await leer(`/configuracion/sensores/${idSensor}/asociaciones`, true);
    const vig = (asoc.cuerpo.items || []).find(x => vigente(x) && sensorIdOf(x) === idSensor && x.id_dispositivo_iot === idDispositivo);
    if (!vig) return null;
    const areasAsociadasVigentes = (asoc.cuerpo.items || []).filter(vigente).map(x => x.id_infraestructura);

    // El área alternativa debe EXISTIR de verdad y no estar asociada de forma vigente.
    const candidatasAlt = [idAreaAlt, ...Array.from({ length: 30 }, (_, i) => i + 1)]
      .filter(a => a !== vig.id_infraestructura && !areasAsociadasVigentes.includes(a));
    let alternativa = null;
    for (const a of candidatasAlt) {
      const r = await leer(`/configuracion/infraestructuras/${a}`).catch(() => null);
      if (r && r.cuerpo && r.cuerpo.id_infraestructura === a) { alternativa = r.cuerpo; break; }
    }
    if (!alternativa) return null;

    const rango = porCategoria[s.categoria];
    const valorPreferido = PREF_147.valor;
    const valor = entre(valorPreferido, rango.min, rango.max) ? valorPreferido : interior(rango.min, rango.max);
    const historial = await getOk(`/configuracion/sensores/${idSensor}/calibraciones`, tokenIng);
    return {
      dispositivo: { id: dispositivo.cuerpo.id_dispositivo_iot, serial: dispositivo.cuerpo.serial, es_activo: dispositivo.cuerpo.es_activo },
      sensor: { id: sensorIdOf(s), nombre: s.nombre, categoria: s.categoria, es_activo: s.es_activo, id_dispositivo_iot: s.id_dispositivo_iot },
      areaVigente: { id_infraestructura: vig.id_infraestructura, tiene_estado: vig.tiene_estado, fecha_finalizacion: vig.fecha_finalizacion },
      areaAlternativa: {
        id_infraestructura: alternativa.id_infraestructura, es_activo: alternativa.es_activo,
        existeEnTest: true, distintaDeLaVigente: alternativa.id_infraestructura !== vig.id_infraestructura,
        asociadaAlSensor: areasAsociadasVigentes.includes(alternativa.id_infraestructura)
      },
      areasAsociadasVigentes,
      rango: { categoria: s.categoria, min: rango.min, max: rango.max },
      valor,
      historialInicial: { total: historial.total, ids: (historial.items || []).map(c => c.id_calibracion) }
    };
  };

  const preferido = await armar(PREF_147.dispositivo, PREF_147.sensor, PREF_147.areaAlternativa);
  if (preferido) return { fixture: preferido, origen: `oficial sensor ${PREF_147.sensor} / dispositivo ${PREF_147.dispositivo}` };

  // Alternativa: otro sensor activo de un dispositivo activo.
  const listado = await leer('/configuracion/dispositivos-iot?solo_activos=true', true);
  for (const d of (listado.cuerpo.items || [])) {
    const sensores = await leer(`/configuracion/dispositivos-iot/${d.id_dispositivo_iot}/sensores`).catch(() => null);
    for (const s of (sensores?.cuerpo?.items || []).filter(x => x.es_activo === true)) {
      const f = await armar(d.id_dispositivo_iot, sensorIdOf(s), PREF_147.areaAlternativa).catch(() => null);
      if (f) return { fixture: f, origen: `equivalente descubierto: sensor ${sensorIdOf(s)} / dispositivo ${d.id_dispositivo_iot}` };
    }
  }
  const e = new Error('BLOQUEADO: no se encontró un fixture válido para TC-147 (sensor activo de dispositivo activo con área real alternativa no asociada).');
  e.bloqueado = true; throw e;
}

module.exports = {
  FOLDER, GROUP_ID, RF, CU, CASOS, POST_BUDGET, PATCH_SETUP_BUDGET,
  PREF_146_DEVICE, PREF_147,
  igualDecimal, entre, interior,
  clean, cleanHtml, runDir, save, sha256,
  base, login, get, getOk, patch, sensorIdOf, vigente,
  mensaje146, mensaje147, lectorConFallback, fixture146, fixture147
};
