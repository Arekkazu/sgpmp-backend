// Utilidades de TC-M09-G77-v2.0 (RF-24 v2.0, CU05 Flujo D) — Seguridad OWASP API5.
//
// Discovery de SOLO LECTURA. Las únicas escrituras que este módulo puede realizar son las
// autorizadas por el caso sobre el estado de cuenta (activar para poder probar y restaurar
// después el estado original), y nunca sobre datos funcionales. Sin SQL.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Protección de aislamiento: no puede ejecutarse desde la carpeta histórica TC-M09-G77/
// ni desde su EvaluacionV2/.
const FOLDER = 'TC-M09-G77-v2.0';
if (path.basename(__dirname) !== FOLDER) {
  throw new Error(`Directorio no autorizado para ${FOLDER}`);
}

const GROUP_ID = 'TC-M09-G77-v2.0';
const CASO = 'TC-M09-148-v2.0';
const RF = 'RF-24 v2.0';
const CU = 'CU05 — Gestionar Dispositivos IoT, Flujo D';
const TIPO = 'Seguridad — OWASP API5';
const OBSERVACIONES = 'QA TC-M09-148-v2.0'; // Texto exacto, sin RUN_ID.

// Subescenarios obligatorios: roles que NO deben poder calibrar.
const ACTORES = [
  { key: 'productor', rolEsperado: 'Productor', envEmail: 'TEST_PRODUCTOR_EMAIL', envPass: 'TEST_PRODUCTOR_PASSWORD' },
  { key: 'contador', rolEsperado: 'Contador', envEmail: 'TEST_CONTADOR_EMAIL', envPass: 'TEST_CONTADOR_PASSWORD' }
];

const POST_CALIBRACION_BUDGET = 2; // 1 por subescenario. Sin reintentos.
const RECURSO_CALIBRACIONES = 12;

// Mensaje exigido por el FA de RF-24 v2.0. No se adapta al backend.
const MENSAJE_403 =
  'Acceso denegado: La calibración de sensores es una función crítica restringida exclusivamente al Ingeniero de Campo o al Administrador.';

// Fixture oficial preferido; se valida por GET y no se asume vigente.
const FIXTURE_PREF = {
  dispositivo: Number(process.env.G77_DEVICE_ID || 3),
  sensor: Number(process.env.G77_SENSOR_ID || 6),
  area: Number(process.env.G77_AREA_ID || 3),
  categoria: process.env.G77_CATEGORY || 'TEMPERATURA',
  valor: process.env.G77_VALOR || '22.5000'
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
const interior = (min, max) => formatear((escalar(min) + escalar(max)) / 2n);

// ------------------------------------------------------------------ sanitización
const secretos = () => [
  process.env.TEST_PRODUCTOR_PASSWORD, process.env.TEST_CONTADOR_PASSWORD,
  process.env.TEST_ENGINEER_PASSWORD, process.env.TEST_ADMIN_PASSWORD
].filter(Boolean);

function clean(texto) {
  let s = String(texto);
  for (const x of new Set(secretos())) s = s.split(x).join('[REDACTED]');
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
  return { status: r.status, token: c?.token || null, errorCode: c?.error_code || null, mensaje: c?.message || null };
}
async function loginOk(email, password, quien) {
  const r = await login(email, password);
  if (r.status !== 200 || !r.token) {
    throw new Error(`login de ${quien} HTTP ${r.status}${r.errorCode ? ' ' + r.errorCode : ''}`);
  }
  return r.token;
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
// Escritura administrativa sobre el estado de cuenta: la única que este módulo realiza.
async function postJson(endpoint, token, body) {
  const r = await fetch(base() + endpoint, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(25000)
  });
  return { status: r.status, cuerpo: await r.json().catch(() => null) };
}

const sensorIdOf = (x) => (x && x.id_sensor !== undefined ? x.id_sensor : x && x.id_sensores);
const vigente = (a) => a && a.tiene_estado === true && (a.fecha_finalizacion === null || a.fecha_finalizacion === undefined);

// Lectura con el actor de discovery y, si su alcance no lo permite, con Administrador.
// En TEST el Ingeniero no tiene fincas asignadas: el listado de dispositivos responde
// HTTP 200 con una lista VACÍA, no 404, así que un fallback guiado solo por el status no
// se activaría. Con exigirNoVacio=true una colección vacía también lo activa.
function lectorConFallback(tokenIng, tokenAdmin, registro) {
  return async (endpoint, exigirNoVacio = false) => {
    const ing = await get(endpoint, tokenIng);
    const vacio = exigirNoVacio && Array.isArray(ing.cuerpo?.items) && ing.cuerpo.items.length === 0;
    if (ing.status === 200 && !vacio) return { fuente: 'Ingeniero', cuerpo: ing.cuerpo, statusIngeniero: 200 };
    if (!tokenAdmin) {
      if (ing.status === 200) return { fuente: 'Ingeniero', cuerpo: ing.cuerpo, statusIngeniero: 200 };
      const e = new Error(`GET ${endpoint} HTTP ${ing.status} con el Ingeniero y sin Administrador disponible`);
      e.status = ing.status; throw e;
    }
    const adm = await get(endpoint, tokenAdmin);
    if (adm.status !== 200) {
      if (ing.status === 200) return { fuente: 'Ingeniero', cuerpo: ing.cuerpo, statusIngeniero: 200 };
      const e = new Error(`GET ${endpoint} HTTP ${adm.status} también con Administrador`);
      e.status = adm.status; throw e;
    }
    registro.push({
      endpoint, statusConIngeniero: ing.status,
      motivo: vacio ? 'el Ingeniero recibe 200 con listado vacío por alcance de finca' : 'fuera del alcance del Ingeniero'
    });
    return { fuente: 'Administrador', cuerpo: adm.cuerpo, statusIngeniero: ing.status };
  };
}

// ----------------------------------------------------------------- fixture
async function construirFixture(tokenIng, tokenAdmin, usoAdmin) {
  const leer = lectorConFallback(tokenIng, tokenAdmin, usoAdmin);
  const rangos = await leer('/configuracion/sensores/rangos-calibracion');
  const porCategoria = Object.fromEntries((rangos.cuerpo.items || []).map(r => [r.categoria, { min: String(r.valor_min), max: String(r.valor_max) }]));

  const armar = async (idDispositivo, idSensor, idArea, categoriaEsperada) => {
    const dispositivo = await leer(`/configuracion/dispositivos-iot/${idDispositivo}`);
    if (dispositivo.cuerpo?.es_activo !== true) return null;
    const sensores = await leer(`/configuracion/dispositivos-iot/${idDispositivo}/sensores`, true);
    const s = (sensores.cuerpo.items || []).find(x => sensorIdOf(x) === idSensor && x.es_activo === true);
    if (!s) return null;
    if (categoriaEsperada && s.categoria !== categoriaEsperada) return null;
    const rango = porCategoria[s.categoria];
    if (!rango) return null;
    const asoc = await leer(`/configuracion/sensores/${idSensor}/asociaciones`, true);
    const a = (asoc.cuerpo.items || []).find(x => vigente(x) && sensorIdOf(x) === idSensor &&
      x.id_dispositivo_iot === idDispositivo && (idArea === null || x.id_infraestructura === idArea));
    if (!a) return null;
    const valor = entre(FIXTURE_PREF.valor, rango.min, rango.max) ? FIXTURE_PREF.valor : interior(rango.min, rango.max);
    if (!entre(valor, rango.min, rango.max)) return null;
    return {
      dispositivo: { id: dispositivo.cuerpo.id_dispositivo_iot, serial: dispositivo.cuerpo.serial, es_activo: dispositivo.cuerpo.es_activo },
      sensor: { id: sensorIdOf(s), nombre: s.nombre, categoria: s.categoria, es_activo: s.es_activo, id_dispositivo_iot: s.id_dispositivo_iot },
      area: { id_infraestructura: a.id_infraestructura, tiene_estado: a.tiene_estado, fecha_finalizacion: a.fecha_finalizacion },
      rango: { categoria: s.categoria, min: rango.min, max: rango.max },
      valor
    };
  };

  const preferido = await armar(FIXTURE_PREF.dispositivo, FIXTURE_PREF.sensor, FIXTURE_PREF.area, FIXTURE_PREF.categoria);
  if (preferido) return { fixture: preferido, origen: `oficial sensor ${FIXTURE_PREF.sensor} / dispositivo ${FIXTURE_PREF.dispositivo} / infraestructura ${FIXTURE_PREF.area}` };

  // Equivalente ya existente. No se crea ni se modifica nada del ambiente.
  const listado = await leer('/configuracion/dispositivos-iot?solo_activos=true', true);
  const candidatos = [];
  for (const d of (listado.cuerpo.items || [])) {
    let sensores;
    try { sensores = await leer(`/configuracion/dispositivos-iot/${d.id_dispositivo_iot}/sensores`, true); } catch { continue; }
    for (const s of (sensores.cuerpo.items || []).filter(x => x.es_activo === true)) {
      try {
        const f = await armar(d.id_dispositivo_iot, sensorIdOf(s), null, null);
        if (f) candidatos.push(f);
      } catch { /* descartado */ }
    }
    if (candidatos.some(c => c.sensor.categoria === FIXTURE_PREF.categoria)) break;
  }
  if (!candidatos.length) {
    const e = new Error('BLOQUEADO: no existe en TEST un fixture equivalente (dispositivo activo + sensor activo + asociación vigente + rango publicado + valor interior).');
    e.bloqueado = true; throw e;
  }
  // Se prefiere TEMPERATURA por fidelidad con el caso.
  candidatos.sort((a, b) => (a.sensor.categoria === FIXTURE_PREF.categoria ? 0 : 1) - (b.sensor.categoria === FIXTURE_PREF.categoria ? 0 : 1) || a.sensor.id - b.sensor.id);
  return { fixture: candidatos[0], origen: `equivalente descubierto: sensor ${candidatos[0].sensor.id} / dispositivo ${candidatos[0].dispositivo.id}` };
}

// --------------------------------------------------------- cuentas de los actores
async function localizarCuenta(correo, tokenAdmin) {
  const r = await get(`/usuarios/admin?correo=${encodeURIComponent(correo)}`, tokenAdmin);
  if (r.status !== 200) { const e = new Error(`GET /usuarios/admin HTTP ${r.status} para ${correo}`); e.status = r.status; throw e; }
  const items = r.cuerpo?.items || [];
  const fila = items.find(x => String(x.correo_electronico).toLowerCase() === correo.toLowerCase());
  if (!fila) { const e = new Error(`La cuenta ${correo} no existe en TEST.`); e.bloqueado = true; throw e; }
  return {
    id_usuario: fila.id_usuario, correo_electronico: fila.correo_electronico,
    nombre_rol: fila.nombre_rol, estado_cuenta: fila.estado_cuenta
  };
}

// Estados desde los que el caso autoriza activar temporalmente, porque existe una acción
// oficial que permite volver EXACTAMENTE al estado original.
const RESTAURABLE = { Inactivo: 'inactivar', Bloqueado: 'bloquear' };

function planDeEstado(estadoOriginal) {
  if (estadoOriginal === 'Activo') {
    return { requiereActivacion: false, accionRestauracion: null, permitido: true, motivo: 'la cuenta ya está Activa: no se modifica su estado' };
  }
  if (RESTAURABLE[estadoOriginal]) {
    return { requiereActivacion: true, accionRestauracion: RESTAURABLE[estadoOriginal], permitido: true, motivo: `estado original ${estadoOriginal}: restaurable con accion_cuenta=${RESTAURABLE[estadoOriginal]}` };
  }
  // Pendiente / Pendiente de datos / Eliminado: no se activa, porque no se podría volver
  // exactamente al estado original mediante la API oficial.
  return {
    requiereActivacion: false, accionRestauracion: null, permitido: false,
    motivo: `estado original ${estadoOriginal}: no se activa porque no existe una operación oficial que permita restaurar exactamente ese estado`
  };
}

async function gestionarCuenta(idUsuario, accion, tokenAdmin, motivo) {
  const body = motivo ? { accion_cuenta: accion, motivo_accion: motivo } : { accion_cuenta: accion };
  return postJson(`/usuarios/${idUsuario}/gestionar`, tokenAdmin, body);
}

module.exports = {
  FOLDER, GROUP_ID, CASO, RF, CU, TIPO, OBSERVACIONES, ACTORES,
  POST_CALIBRACION_BUDGET, RECURSO_CALIBRACIONES, MENSAJE_403, FIXTURE_PREF, RESTAURABLE,
  igualDecimal, entre, interior,
  clean, cleanHtml, runDir, save, sha256,
  base, login, loginOk, get, getOk, postJson,
  sensorIdOf, vigente, lectorConFallback, construirFixture,
  localizarCuenta, planDeEstado, gestionarCuenta
};
