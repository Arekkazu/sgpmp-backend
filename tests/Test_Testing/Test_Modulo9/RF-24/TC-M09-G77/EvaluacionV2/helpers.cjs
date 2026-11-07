// TC-M09-G77 / TC-M09-148 — REEVALUACION V2 (RF-24, CU-05).
// Utilidades read-only de descubrimiento y saneamiento. Ningun secreto se
// escribe a disco: las contrasenas llegan por variable de proceso y los tokens
// viven solo en memoria.
const fs = require('fs');
const path = require('path');

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const BASE_HTTP_SUMINISTRADA = 'http://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

const CASO = 'TC-M09-148';
const GRUPO = 'TC-M09-G77';
const RECURSO_SENSORES = 12;
const ACCION_CREAR = 1;
const ACCION_LEER = 2;

const ACTOR_NEGATIVO = 'm2m.nuevo@ejemplo.com';   // rol esperado: Productor
const ACTOR_DISCOVERY = 'ingeniero@pecuaria.co';  // solo GET read-only
// RF-24 §11: el Administrador solo se habilita para GET cuando el Ingeniero no
// alcanza el dato. En TEST el Ingeniero no tiene fincas asignadas, asi que el
// alcance de finca le oculta dispositivos y asociaciones (404 / total 0).
const ACTOR_DISCOVERY_GLOBAL = 'administador.dev@gmail.com';
const ROLES_AUTORIZADOS_RF24 = ['Administrador', 'Ingeniero de Campo'];

const META = {
  caso: CASO,
  grupo: GRUPO,
  rf: 'RF-24',
  cu: 'CU-05',
  tipo: 'REEVALUACION V2',
  rama: 'qa/juan-esteban-re-evaluacion-M02',
  entorno: 'TEST',
  base: BASE,
};

function settings() {
  const runId = process.env.G77_REEVAL_V2_RUN_ID;
  const intento = Number(process.env.G77_INTENTO || 1);
  const caso = process.env.G77_CASE || CASO;
  if (caso !== CASO) throw Error(`G77_CASE debe ser ${CASO}`);
  if (!runId || !/^[\w-]+$/.test(runId)) throw Error('G77_REEVAL_V2_RUN_ID requerido');
  if (![1, 2].includes(intento)) throw Error('G77_INTENTO solo puede ser 1 o 2: maximo dos POST');
  if (!process.env.TEST_PRODUCTOR_PASSWORD) throw Error('TEST_PRODUCTOR_PASSWORD requerida');
  if (!process.env.TEST_ENGINEER_PASSWORD) throw Error('TEST_ENGINEER_PASSWORD requerida');
  if (!process.env.TEST_ADMIN_PASSWORD) throw Error('TEST_ADMIN_PASSWORD requerida (solo GET de descubrimiento)');
  return { caso, runId, intento };
}

// Redaccion defensiva: contrasenas suministradas, JWT, Bearer y cookies.
function clean(s) {
  if (s == null) return s;
  s = String(s);
  for (const secreto of [process.env.TEST_PRODUCTOR_PASSWORD, process.env.TEST_ENGINEER_PASSWORD, process.env.TEST_ADMIN_PASSWORD].filter(Boolean)) {
    s = s.split(secreto).join('[REDACTED]');
  }
  return s
    .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9_.\-]+/gi, 'Bearer [REDACTED]')
    .replace(/refresh_token=[^;"\s]+/gi, 'refresh_token=[REDACTED]');
}

function dir(runId, sub) {
  const d = sub ? path.join(__dirname, 'RESULTADOS', runId, sub) : path.join(__dirname, 'RESULTADOS', runId);
  fs.mkdirSync(d, { recursive: true });
  return d;
}

function save(runId, name, value) {
  const destino = path.join(dir(runId), name);
  if (fs.existsSync(destino) && !/^estado/.test(name)) throw Error(`No sobrescribir evidencia existente: ${name}`);
  fs.writeFileSync(destino, clean(JSON.stringify({ ...META, runId, fecha: new Date().toISOString(), ...value }, null, 2)));
  return destino;
}

async function pedir(endpoint, token) {
  const r = await fetch(BASE + endpoint, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal: AbortSignal.timeout(25000),
  });
  let body = null;
  try { body = await r.json(); } catch { /* respuesta sin JSON */ }
  return { status: r.status, body };
}

async function get(endpoint, token) {
  const r = await pedir(endpoint, token);
  if (r.status !== 200) throw Error(`GET ${endpoint} HTTP ${r.status}`);
  return r.body;
}

async function login(email, password) {
  const r = await fetch(BASE + '/sesiones/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo_electronico: email, contrasena: password }),
    signal: AbortSignal.timeout(25000),
  });
  let body = null;
  try { body = await r.json(); } catch { /* respuesta sin JSON */ }
  return { status: r.status, token: body?.token || null, errorCode: body?.error_code || null, mensaje: clean(body?.message || body?.detail || '') };
}

// Valor decimal claramente interior al rango tecnico (punto medio), compatible
// con numeric(10,4). G77 no prueba fronteras.
function valorInterior(min, max) {
  const esc = (v) => {
    const [ent, dec = ''] = String(v).split('.');
    return BigInt(ent + (dec + '0000').slice(0, 4));
  };
  const medio = (esc(min) + esc(max)) / 2n;
  const neg = medio < 0n;
  const abs = (neg ? -medio : medio).toString().padStart(5, '0');
  return (neg ? '-' : '') + abs.slice(0, -4) + '.' + abs.slice(-4);
}

// Descubrimiento dinamico: dispositivo activo asociado a estructura productiva,
// con sensor activo, asociacion de area vigente y rango tecnico conocido.
async function discover(tokenLectura) {
  const rangos = Object.fromEntries(
    (await get('/configuracion/sensores/rangos-calibracion', tokenLectura)).items
      .map((r) => [r.categoria, { min: String(r.valor_min), max: String(r.valor_max) }])
  );

  const dispositivos = (await get('/configuracion/dispositivos-iot?solo_activos=true', tokenLectura)).items
    .filter((d) => d.es_activo && d.id_infraestructura != null);
  if (!dispositivos.length) throw Error('BLOCKED: TEST no expone dispositivos IoT activos');

  const descartados = [];
  for (const dispositivo of dispositivos) {
    let sensores = [];
    try {
      sensores = (await get(`/configuracion/dispositivos-iot/${dispositivo.id_dispositivo_iot}/sensores`, tokenLectura)).items || [];
    } catch (e) {
      descartados.push({ dispositivo: dispositivo.id_dispositivo_iot, motivo: clean(e.message) });
      continue;
    }
    for (const sensor of sensores.filter((s) => s.es_activo && s.categoria && rangos[s.categoria])) {
      let asociaciones = [];
      try {
        asociaciones = (await get(`/configuracion/sensores/${sensor.id_sensores}/asociaciones`, tokenLectura)).items || [];
      } catch (e) {
        descartados.push({ sensor: sensor.id_sensores, motivo: clean(e.message) });
        continue;
      }
      const vigente = asociaciones.find((a) => a.tiene_estado && !a.fecha_finalizacion);
      if (!vigente) {
        descartados.push({ sensor: sensor.id_sensores, motivo: 'sin asociacion de area vigente' });
        continue;
      }
      if (vigente.id_dispositivo_iot !== dispositivo.id_dispositivo_iot || sensor.id_dispositivo_iot !== dispositivo.id_dispositivo_iot) {
        descartados.push({ sensor: sensor.id_sensores, motivo: 'sensor no pertenece al dispositivo evaluado' });
        continue;
      }
      const rango = rangos[sensor.categoria];
      return {
        dispositivo: {
          id_dispositivo_iot: dispositivo.id_dispositivo_iot,
          serial: dispositivo.serial,
          es_activo: dispositivo.es_activo,
          id_infraestructura: dispositivo.id_infraestructura,
        },
        sensor: {
          id_sensores: sensor.id_sensores,
          nombre: sensor.nombre,
          categoria: sensor.categoria,
          es_activo: sensor.es_activo,
          id_dispositivo_iot: sensor.id_dispositivo_iot,
        },
        areaCorrecta: {
          id_infraestructura: vigente.id_infraestructura,
          id_asociacion: vigente.id_sensores_area_asociada,
          punto_instalacion: vigente.punto_instalacion,
          vigente: true,
        },
        rangoTecnico: rango,
        valor: valorInterior(rango.min, rango.max),
        descartados,
      };
    }
  }
  throw Error('BLOCKED: ningun sensor activo con asociacion de area vigente y rango tecnico conocido');
}

function construirCuerpo(plan, runId) {
  const objeto = {
    id_dispositivo_iot: plan.dispositivo.id_dispositivo_iot,
    id_infraestructura: plan.areaCorrecta.id_infraestructura,
    valor_referencia: plan.valor,
    ganancia: '1.0000',
    offset: plan.valor,
    fecha_calibracion: new Date().toISOString(),
    observaciones: `QA TC-M09-148 REEVALUACION V2 ${runId}`,
  };
  return { objeto, texto: JSON.stringify(objeto) };
}

module.exports = {
  BASE, FRONT, BASE_HTTP_SUMINISTRADA, CASO, GRUPO, META,
  RECURSO_SENSORES, ACCION_CREAR, ACCION_LEER,
  ACTOR_NEGATIVO, ACTOR_DISCOVERY, ACTOR_DISCOVERY_GLOBAL, ROLES_AUTORIZADOS_RF24,
  settings, clean, dir, save, pedir, get, login, valorInterior, discover, construirCuerpo,
};
