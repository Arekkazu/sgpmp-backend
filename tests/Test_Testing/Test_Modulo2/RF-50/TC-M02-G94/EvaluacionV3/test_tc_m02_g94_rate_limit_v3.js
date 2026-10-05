// TC-M02-G94 V3 -- TC-M02-158: rate limiting de 100 solicitudes/minuto por modulo consumidor,
// con aislamiento entre M04 y M06. RF-50 / CU12.
//
// SOBRE LA HERRAMIENTA
// --------------------
// El paquete pide k6. k6 NO esta instalado en la estacion de QA (la misma limitacion que V1 ya
// registro), y QA no instala software en la estacion durante la ejecucion. Este arnes reproduce
// exactamente los parametros y el oraculo que el paquete define para k6:
//   - 101 solicitudes oficiales desde M04, ni una mas;
//   - concurrencia equivalente a shared-iterations con 5 VUs, para cerrar la ventana < 60 s;
//   - oraculo por CONTEOS GLOBALES (200 / 429 / otros), sin depender del orden de llegada;
//   - ninguna solicitud de setup al endpoint RF-50 antes de la rafaga (seccion 20);
//   - consulta de control de M06 inmediatamente despues de saturar M04.
// La salida se escribe con la forma de un resumen de k6 para que la evidencia sea comparable.
//
// Las contrasenas llegan por variables de entorno y no se escriben en ningun archivo. Los tokens
// se usan en memoria y no se persisten.
//
// Uso:
//   M04_RF50_PASSWORD=... M06_RF50_PASSWORD=... \
//   G94_ANCLA_ULTIMO_GET_M04=<ISO> G94_SALIDA=<ruta.json> node test_tc_m02_g94_rate_limit_v3.js
const fs = require('fs');

const BASE = process.env.G94_BASE_TEST || 'https://api.inmero.co/back-sigab-test';
const ID_ACTIVO = Number(process.env.G94_ID_ACTIVO || 279);
const SOLICITUDES = 101;   // minimo necesario para exceder 100/min; no se emiten mas
const VUS = 5;             // concurrencia para cerrar la ventana por debajo de 60 s
const VENTANA_S = 60;
const ESPERA_VENTANA_MS = 61000;

const M04 = { nombre: 'M04', correo: 'dev.m04.rf50@sgpmp-test.com', pass: process.env.M04_RF50_PASSWORD, tipo_dato: 'eventos' };
const M06 = { nombre: 'M06', correo: 'dev.m06.rf50@sgpmp-test.com', pass: process.env.M06_RF50_PASSWORD, tipo_dato: 'metricas' };

const ruta = (td) => `/activos-biologicos/${ID_ACTIVO}/datos-consolidados?tipo_dato=${td}&pagina=1&page_size=20`;
const CABECERAS_CUOTA = ['retry-after', 'ratelimit-remaining', 'ratelimit-limit', 'ratelimit-reset',
  'x-ratelimit-remaining', 'x-ratelimit-limit', 'x-ratelimit-reset'];

async function pedir(url, token) {
  const t0 = Date.now();
  const r = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
    signal: AbortSignal.timeout(45000),
  });
  let cuerpo = null; try { cuerpo = await r.json(); } catch { /* sin JSON */ }
  const cabeceras = {};
  for (const h of CABECERAS_CUOTA) { const v = r.headers.get(h); if (v !== null) cabeceras[h] = v; }
  return { status: r.status, cuerpo, ms: Date.now() - t0, cabeceras, inicio: t0, fin: Date.now() };
}

async function autenticar(id) {
  if (!id.pass) throw Error(`Falta la contrasena de ${id.nombre} en variable de entorno`);
  const r = await fetch(BASE + '/sesiones/', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo_electronico: id.correo, contrasena: id.pass }),
    signal: AbortSignal.timeout(45000),
  });
  const b = await r.json();
  if (!b.token) throw Error(`${id.nombre} no autentico: ${r.status}`);
  return b.token;
}

// Ejecuta `total` peticiones con `vus` trabajadores concurrentes. Cada respuesta se anota con el
// orden de LLEGADA real, no con el indice de iteracion: con varios VUs no coinciden.
async function rafaga(url, token, total, vus) {
  const respuestas = [];
  let emitidas = 0;
  const trabajador = async () => {
    while (true) {
      const mia = emitidas;
      if (mia >= total) return;
      emitidas += 1;
      const r = await pedir(url, token);
      respuestas.push({ ...r, ordenLanzamiento: mia + 1 });
    }
  };
  const t0 = Date.now();
  await Promise.all(Array.from({ length: vus }, trabajador));
  const t1 = Date.now();
  respuestas.sort((a, b) => a.fin - b.fin).forEach((r, i) => { r.ordenLlegada = i + 1; });
  return { respuestas, inicio: t0, fin: t1, duracionMs: t1 - t0 };
}

(async () => {
  // Los logins NO consumen el contador de datos-consolidados: se hacen antes de la espera.
  const tokenM04 = await autenticar(M04);
  const tokenM06 = await autenticar(M06);

  // Seccion 17: ventana limpia. Se espera 61 s desde el ultimo GET autenticado de M04 al
  // endpoint RF-50, sin emitir ningun GET de M04 durante la espera.
  const ancla = process.env.G94_ANCLA_ULTIMO_GET_M04 ? new Date(process.env.G94_ANCLA_ULTIMO_GET_M04).getTime() : Date.now();
  const objetivo = ancla + ESPERA_VENTANA_MS;
  const esperaMs = Math.max(0, objetivo - Date.now());
  console.log(`ancla ultimo GET M04: ${new Date(ancla).toISOString()} | esperando ${Math.round(esperaMs / 1000)} s para ventana limpia`);
  if (esperaMs > 0) await new Promise((r) => setTimeout(r, esperaMs));

  // --- Rafaga oficial: exactamente 101 solicitudes de M04, sin peticion de setup ---
  const inicioVentana = new Date().toISOString();
  const res = await rafaga(ruta(M04.tipo_dato), tokenM04, SOLICITUDES, VUS);

  const conteo = {};
  for (const r of res.respuestas) conteo[r.status] = (conteo[r.status] || 0) + 1;
  const total200 = conteo[200] || 0;
  const total429 = conteo[429] || 0;
  const otros = res.respuestas.filter((r) => r.status !== 200 && r.status !== 429);

  const primer429 = res.respuestas.filter((r) => r.status === 429).sort((a, b) => a.fin - b.fin)[0] || null;

  // --- Control de aislamiento: M06 inmediatamente despues de saturar M04 (seccion 23) ---
  const m06 = await pedir(ruta(M06.tipo_dato), tokenM06);
  // Confirmacion de que M04 sigue saturado en el instante del control de M06.
  const m04Tras = await pedir(ruta(M04.tipo_dato), tokenM04);

  const salida = {
    caso: 'TC-M02-158',
    herramienta: {
      solicitada: 'k6',
      utilizada: 'arnes equivalente en Node (fetch nativo)',
      motivo: 'k6 no esta instalado en la estacion de QA y QA no instala software durante la ejecucion',
      equivalencia: 'mismos 101 pedidos, misma concurrencia (5 trabajadores, shared-iterations), '
                  + 'mismo oraculo por conteos globales, sin peticion de setup al endpoint RF-50',
      nodeVersion: process.version,
    },
    configuracion: {
      base: BASE, ruta_m04: ruta(M04.tipo_dato), ruta_m06: ruta(M06.tipo_dato),
      solicitudes: SOLICITUDES, vus: VUS, limite_declarado: 100, ventana_declarada_s: VENTANA_S,
      peticion_de_setup_al_endpoint_rf50: 0,
    },
    ventana: {
      ancla_ultimo_get_m04_previo: new Date(ancla).toISOString(),
      espera_aplicada_s: Math.round(esperaMs / 1000),
      inicio_rafaga: inicioVentana,
      fin_rafaga: new Date(res.fin).toISOString(),
      duracion_ms: res.duracionMs,
      duracion_s: Number((res.duracionMs / 1000).toFixed(3)),
      dentro_de_60_s: res.duracionMs < VENTANA_S * 1000,
    },
    conteos: {
      total_solicitudes: res.respuestas.length,
      http_200: total200, http_429: total429,
      otros_total: otros.length,
      otros_detalle: otros.map((r) => ({ status: r.status, error_code: r.cuerpo?.error_code ?? null, ordenLlegada: r.ordenLlegada })),
      por_codigo: conteo,
    },
    primer_429: primer429 ? {
      ordenLlegada: primer429.ordenLlegada, ordenLanzamiento: primer429.ordenLanzamiento,
      status: primer429.status, error_code: primer429.cuerpo?.error_code ?? null,
      message: primer429.cuerpo?.message ?? null,
      expone_datos_del_activo: JSON.stringify(primer429.cuerpo ?? {}).includes('QAJE-CREC-OK')
        || JSON.stringify(primer429.cuerpo ?? {}).includes('"id_activo_biologico"'),
      cabeceras_de_cuota: primer429.cabeceras,
      instante: new Date(primer429.fin).toISOString(),
    } : null,
    aislamiento: {
      m06_despues_de_saturar_m04: {
        tipo_dato: M06.tipo_dato, http: m06.status, error_code: m06.cuerpo?.error_code ?? null,
        id_activo_devuelto: m06.cuerpo?.id_activo_biologico ?? null, ms: m06.ms,
        instante: new Date(m06.fin).toISOString(),
      },
      m04_reconfirmacion_en_el_mismo_instante: {
        tipo_dato: M04.tipo_dato, http: m04Tras.status, error_code: m04Tras.cuerpo?.error_code ?? null,
        instante: new Date(m04Tras.fin).toISOString(),
      },
      contadores_independientes: m06.status === 200 && m04Tras.status === 429,
    },
    latencias_ms: {
      min: Math.min(...res.respuestas.map((r) => r.ms)),
      max: Math.max(...res.respuestas.map((r) => r.ms)),
      media: Math.round(res.respuestas.reduce((a, r) => a + r.ms, 0) / res.respuestas.length),
    },
    secuencia: res.respuestas.sort((a, b) => a.ordenLlegada - b.ordenLlegada)
      .map((r) => ({ n: r.ordenLlegada, status: r.status, ms: r.ms })),
  };

  // Oraculo (secciones 21, 24 y 25): conteos globales, no orden de llegada.
  const checks = [
    ['las 101 solicitudes se completaron dentro de la ventana de 60 s', salida.ventana.dentro_de_60_s],
    ['se emitieron exactamente 101 solicitudes', salida.conteos.total_solicitudes === SOLICITUDES],
    ['aparecio al menos una respuesta HTTP 429 al exceder el limite', total429 >= 1],
    ['no aparecieron codigos inesperados (401/403/404/500)', otros.length === 0],
    ['el numero de respuestas permitidas no excede el limite declarado', total200 <= 100],
    ['el 429 no expone datos del activo', primer429 ? !salida.primer_429.expone_datos_del_activo : false],
    ['el 429 trae un error funcional identificable', Boolean(primer429?.cuerpo?.error_code)],
    ['M06 responde 200 inmediatamente despues de saturar M04', m06.status === 200],
    ['M06 no recibe 429 por la rafaga de M04', m06.status !== 429],
    ['M04 sigue saturado en ese mismo instante (contadores independientes)', m04Tras.status === 429],
  ];
  salida.oraculo = {
    items: checks.map(([descripcion, cumple]) => ({ descripcion, cumple: Boolean(cumple) })),
    total: checks.length,
    superadas: checks.filter(([, c]) => c).length,
    fallidas: checks.filter(([, c]) => !c).length,
  };
  salida.veredicto = salida.oraculo.fallidas === 0 ? 'APROBADO' : 'NO APROBADO';

  const destino = process.env.G94_SALIDA;
  if (destino) fs.writeFileSync(destino, JSON.stringify(salida, null, 2));
  console.log(JSON.stringify({
    duracion_s: salida.ventana.duracion_s, conteos: salida.conteos,
    primer_429: salida.primer_429 && { n: salida.primer_429.ordenLlegada, error_code: salida.primer_429.error_code, cabeceras: salida.primer_429.cabeceras_de_cuota },
    aislamiento: salida.aislamiento, oraculo: salida.oraculo, veredicto: salida.veredicto,
  }, null, 1));
})().catch((e) => { console.log('ERROR:', e.message); process.exitCode = 1; });
