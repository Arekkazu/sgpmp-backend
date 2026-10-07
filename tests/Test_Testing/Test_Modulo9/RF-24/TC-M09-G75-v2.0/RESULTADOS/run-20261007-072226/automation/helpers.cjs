// Utilidades de TC-M09-G75-v2.0 (RF-24 v2.0, CU05 Flujo D).
// Solo autenticación y GET. No crea, edita ni elimina datos. Sin SQL.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Protección de aislamiento: esta automatización no puede ejecutarse desde la carpeta
// histórica TC-M09-G75/ ni desde ninguna otra.
const FOLDER = 'TC-M09-G75-v2.0';
if (path.basename(__dirname) !== FOLDER) {
  throw new Error(`Directorio no autorizado para ${FOLDER}`);
}

const GROUP_ID = 'TC-M09-G75-v2.0';
const RF = 'RF-24 v2.0';
const CU = 'CU05 — Gestionar Dispositivos IoT, Flujo D';

// Las 7 variantes funcionales del grupo, en el orden obligatorio de ejecución.
const VARIANTS = [
  { key: '142', caso: 'TC-M09-142-v2.0', etiqueta: 'MIN', valido: true, observaciones: 'QA TC-M09-142-v2.0' },
  { key: '143', caso: 'TC-M09-143-v2.0', etiqueta: 'MAX', valido: true, observaciones: 'QA TC-M09-143-v2.0' },
  { key: '144_low', caso: 'TC-M09-144-v2.0', etiqueta: 'LOW', valido: false, observaciones: 'QA TC-M09-144-v2.0' },
  { key: '144_high', caso: 'TC-M09-144-v2.0', etiqueta: 'HIGH', valido: false, observaciones: 'QA TC-M09-144-v2.0' },
  { key: '145_empty', caso: 'TC-M09-145-v2.0', etiqueta: 'EMPTY', valido: false, observaciones: 'QA TC-M09-145-v2.0' },
  { key: '145_null', caso: 'TC-M09-145-v2.0', etiqueta: 'NULL', valido: false, observaciones: 'QA TC-M09-145-v2.0' },
  { key: '145_abc', caso: 'TC-M09-145-v2.0', etiqueta: 'ABC', valido: false, observaciones: 'QA TC-M09-145-v2.0' }
];

const POST_BUDGET = 7; // Presupuesto exacto del RUN. No existe un octavo POST.
const PASO = '0.0001'; // numeric(10,4): menor incremento representable.

// ---------------------------------------------------------------------------
// Aritmética decimal exacta (nunca coma flotante binaria).
// ---------------------------------------------------------------------------
const escalar = (v) => {
  const [entero, dec = ''] = String(v).replace('+', '').split('.');
  const negativo = entero.startsWith('-');
  const abs = BigInt((negativo ? entero.slice(1) : entero) + (dec + '0000').slice(0, 4));
  return negativo ? -abs : abs;
};
const formatear = (total) => {
  const negativo = total < 0n;
  const abs = (negativo ? -total : total).toString().padStart(5, '0');
  return (negativo ? '-' : '') + abs.slice(0, -4) + '.' + abs.slice(-4);
};
const sumaDecimal = (a, b) => formatear(escalar(a) + escalar(b));
const restaDecimal = (a, b) => formatear(escalar(a) - escalar(b));
const igualDecimal = (a, b) => escalar(a) === escalar(b);

// ---------------------------------------------------------------------------
// Sanitización
// ---------------------------------------------------------------------------
const secretos = () => [
  process.env.QA_PASSWORD,
  process.env.QA_ADMIN_PASSWORD
].filter(Boolean);

function clean(texto) {
  let s = String(texto);
  for (const secreto of secretos()) s = s.split(secreto).join('[REDACTED]');
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

// ---------------------------------------------------------------------------
// Rutas y escritura de evidencia
// ---------------------------------------------------------------------------
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
function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

// ---------------------------------------------------------------------------
// HTTP de discovery (solo lectura)
// ---------------------------------------------------------------------------
const base = () => {
  const b = process.env.QA_BASE_URL;
  if (!b) throw new Error('QA_BASE_URL requerido');
  return b.replace(/\/$/, '');
};

async function login(email, password) {
  const r = await fetch(base() + '/sesiones/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo_electronico: email, contrasena: password }),
    signal: AbortSignal.timeout(25000)
  });
  const cuerpo = await r.json().catch(() => null);
  if (r.status !== 200 || !cuerpo || !cuerpo.token) {
    const err = new Error(`login HTTP ${r.status}${cuerpo && cuerpo.error_code ? ' ' + cuerpo.error_code : ''}`);
    err.status = r.status;
    err.cuerpo = cuerpo;
    throw err;
  }
  return cuerpo.token;
}

async function get(endpoint, token) {
  const r = await fetch(base() + endpoint, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(25000)
  });
  const cuerpo = await r.json().catch(() => null);
  return { status: r.status, cuerpo };
}

async function getOk(endpoint, token) {
  const { status, cuerpo } = await get(endpoint, token);
  if (status !== 200) {
    const err = new Error(`GET ${endpoint} HTTP ${status}`);
    err.status = status;
    err.cuerpo = cuerpo;
    throw err;
  }
  return cuerpo;
}

// El identificador del sensor puede venir como id_sensor o id_sensores.
const sensorIdOf = (row) => (row && row.id_sensor !== undefined ? row.id_sensor : row && row.id_sensores);
const vigente = (a) => a && a.tiene_estado === true && (a.fecha_finalizacion === null || a.fecha_finalizacion === undefined);

// ---------------------------------------------------------------------------
// Mensajes esperados por el caso (RF-24 v2.0). El esperado NO se adapta al backend.
// ---------------------------------------------------------------------------
const mensajeFueraDeLimites = (valor, variable) =>
  `Valor fuera de límites: El ajuste de ${valor} excede los rangos de seguridad para la variable ${variable}. Verifique el estándar de calibración utilizado.`;

const mensajeFormato = (valorIngresado) =>
  `Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada '${valorIngresado}'.`;

// ---------------------------------------------------------------------------
// Plan del RUN: fixture efectivo, rango vigente y valores de frontera.
// ---------------------------------------------------------------------------
const FIXTURE_PREFERIDO = {
  dispositivo: Number(process.env.G75_DEVICE_ID || 3),
  sensor: Number(process.env.G75_SENSOR_ID || 6),
  area: Number(process.env.G75_AREA_ID || 3),
  categoria: process.env.G75_CATEGORY || 'TEMPERATURA'
};

// tokenIng: ejecuta el flujo funcional. tokenAdmin: solo GET que el Ingeniero no ve por alcance.
async function construirPlan(tokenIng, tokenAdmin) {
  const usoAdmin = [];
  const leer = async (endpoint) => {
    const conIng = await get(endpoint, tokenIng);
    if (conIng.status === 200) return { fuente: 'Ingeniero', cuerpo: conIng.cuerpo, statusIngeniero: 200 };
    if (!tokenAdmin) {
      const err = new Error(`GET ${endpoint} HTTP ${conIng.status} con el Ingeniero y sin Administrador disponible`);
      err.status = conIng.status;
      throw err;
    }
    const conAdmin = await get(endpoint, tokenAdmin);
    if (conAdmin.status !== 200) {
      const err = new Error(`GET ${endpoint} HTTP ${conAdmin.status} también con Administrador`);
      err.status = conAdmin.status;
      throw err;
    }
    usoAdmin.push({ endpoint, statusConIngeniero: conIng.status, motivo: 'fuera del alcance del Ingeniero' });
    return { fuente: 'Administrador', cuerpo: conAdmin.cuerpo, statusIngeniero: conIng.status };
  };

  const rangos = await getOk('/configuracion/sensores/rangos-calibracion', tokenIng);
  const porCategoria = Object.fromEntries(
    (rangos.items || []).map(r => [r.categoria, { min: String(r.valor_min), max: String(r.valor_max) }])
  );

  const evaluar = async (idDispositivo, idSensor, idArea, categoriaEsperada) => {
    const dispositivo = await leer(`/configuracion/dispositivos-iot/${idDispositivo}`);
    if (!dispositivo.cuerpo || dispositivo.cuerpo.es_activo !== true) return null;
    const sensores = await leer(`/configuracion/dispositivos-iot/${idDispositivo}/sensores`);
    const sensor = (sensores.cuerpo.items || []).find(x => sensorIdOf(x) === idSensor);
    if (!sensor || sensor.es_activo !== true) return null;
    if (categoriaEsperada && sensor.categoria !== categoriaEsperada) return null;
    if (!porCategoria[sensor.categoria]) return null;
    const asociaciones = await leer(`/configuracion/sensores/${idSensor}/asociaciones`);
    const asociacion = (asociaciones.cuerpo.items || []).find(
      a => vigente(a) && sensorIdOf(a) === idSensor && a.id_dispositivo_iot === idDispositivo &&
           (idArea === null || a.id_infraestructura === idArea)
    );
    if (!asociacion) return null;
    const historial = await getOk(`/configuracion/sensores/${idSensor}/calibraciones`, tokenIng);
    return {
      dispositivo: {
        id: dispositivo.cuerpo.id_dispositivo_iot,
        serial: dispositivo.cuerpo.serial,
        es_activo: dispositivo.cuerpo.es_activo,
        id_infraestructura_propia: dispositivo.cuerpo.id_infraestructura,
        fuenteLectura: dispositivo.fuente
      },
      sensor: {
        id: sensorIdOf(sensor),
        nombre: sensor.nombre,
        categoria: sensor.categoria,
        es_activo: sensor.es_activo,
        id_dispositivo_iot: sensor.id_dispositivo_iot,
        fuenteLectura: sensores.fuente
      },
      area: {
        id_infraestructura: asociacion.id_infraestructura,
        punto_instalacion: asociacion.punto_instalacion,
        tiene_estado: asociacion.tiene_estado,
        fecha_finalizacion: asociacion.fecha_finalizacion,
        fuenteLectura: asociaciones.fuente
      },
      rangoTecnico: {
        categoria: sensor.categoria,
        min: porCategoria[sensor.categoria].min,
        max: porCategoria[sensor.categoria].max,
        fuente: 'GET /configuracion/sensores/rangos-calibracion'
      },
      historialInicial: { total: historial.total, ids: (historial.items || []).map(c => c.id_calibracion) }
    };
  };

  // Prioridad 1: el fixture oficial del caso.
  let plan = null;
  let origenFixture = 'oficial 3/6/3';
  try {
    plan = await evaluar(
      FIXTURE_PREFERIDO.dispositivo, FIXTURE_PREFERIDO.sensor,
      FIXTURE_PREFERIDO.area, FIXTURE_PREFERIDO.categoria
    );
  } catch (e) {
    plan = null;
    origenFixture = `oficial 3/6/3 no verificable: ${e.message}`;
  }

  // Prioridad 2: un fixture equivalente ya existente en TEST (no se crea ni se modifica nada).
  if (!plan) {
    const alternativas = [];
    const dispositivos = await leer('/configuracion/dispositivos-iot');
    for (const d of (dispositivos.cuerpo.items || []).filter(x => x.es_activo === true)) {
      let sensores;
      try { sensores = await leer(`/configuracion/dispositivos-iot/${d.id_dispositivo_iot}/sensores`); } catch { continue; }
      for (const s of (sensores.cuerpo.items || []).filter(x => x.es_activo === true && x.categoria === FIXTURE_PREFERIDO.categoria)) {
        try {
          const candidato = await evaluar(d.id_dispositivo_iot, sensorIdOf(s), null, FIXTURE_PREFERIDO.categoria);
          if (candidato) alternativas.push(candidato);
        } catch { /* candidato descartado */ }
      }
      if (alternativas.length) break;
    }
    if (!alternativas.length) {
      const err = new Error(
        `BLOQUEADO: no existe en TEST un fixture ${FIXTURE_PREFERIDO.categoria} equivalente ` +
        `(dispositivo activo + sensor activo + asociación vigente + rango publicado). ${origenFixture}`
      );
      err.bloqueado = true;
      throw err;
    }
    alternativas.sort((a, b) => a.sensor.id - b.sensor.id);
    plan = alternativas[0];
    origenFixture = `equivalente descubierto: dispositivo ${plan.dispositivo.id} / sensor ${plan.sensor.id} / infraestructura ${plan.area.id_infraestructura}`;
  }

  const { min, max } = plan.rangoTecnico;
  const variable = plan.sensor.categoria;
  const valores = {
    paso: PASO,
    minExacto: min,
    maxExacto: max,
    bajoInvalido: restaDecimal(min, PASO),
    altoInvalido: sumaDecimal(max, PASO)
  };

  // Valor que viaja en el JSON por variante, conservando el literal decimal exacto.
  const literales = {
    '142': { json: valores.minExacto, enviado: valores.minExacto, tipo: 'number' },
    '143': { json: valores.maxExacto, enviado: valores.maxExacto, tipo: 'number' },
    '144_low': { json: valores.bajoInvalido, enviado: valores.bajoInvalido, tipo: 'number' },
    '144_high': { json: valores.altoInvalido, enviado: valores.altoInvalido, tipo: 'number' },
    '145_empty': { json: '""', enviado: '', tipo: 'string' },
    '145_null': { json: 'null', enviado: null, tipo: 'null' },
    '145_abc': { json: '"abc"', enviado: 'abc', tipo: 'string' }
  };

  // Mensaje esperado por variante inválida, construido con los valores reales.
  const esperados = {
    '144_low': mensajeFueraDeLimites(valores.bajoInvalido, variable),
    '144_high': mensajeFueraDeLimites(valores.altoInvalido, variable),
    '145_empty': mensajeFormato(''),
    '145_null': mensajeFormato('null'),
    '145_abc': mensajeFormato('abc')
  };

  // Cuerpo de cada POST. __FECHA__ lo sustituye la colección justo antes de enviar.
  const cuerpos = {};
  for (const v of VARIANTS) {
    cuerpos[v.key] =
      '{' +
      '"modo_calibracion":"SENSOR",' +
      `"id_dispositivo_iot":${plan.dispositivo.id},` +
      `"id_infraestructura":${plan.area.id_infraestructura},` +
      `"valor_referencia":${literales[v.key].json},` +
      `"observaciones":${JSON.stringify(v.observaciones)},` +
      '"fecha_calibracion":"__FECHA__"' +
      '}';
  }

  return { plan, origenFixture, usoAdmin, valores, literales, esperados, cuerpos, variable };
}

module.exports = {
  FOLDER, GROUP_ID, RF, CU, VARIANTS, POST_BUDGET, PASO, FIXTURE_PREFERIDO,
  sumaDecimal, restaDecimal, igualDecimal,
  clean, cleanHtml, runDir, save, sha256,
  base, login, get, getOk, sensorIdOf, vigente,
  mensajeFueraDeLimites, mensajeFormato, construirPlan
};
