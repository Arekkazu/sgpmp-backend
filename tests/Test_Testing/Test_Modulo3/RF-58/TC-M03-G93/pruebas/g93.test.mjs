import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { comprobar, evaluar, informe, newman, cypress as ejecutarCypress } from '../g93.mjs';
import { evaluarApi, revisarCandidataV2, IDS, ORACULO } from '../lib/g93_escenario.mjs';
import { evaluarRegistro } from '../lib/registro_local.mjs';
import ui from '../lib/g93_ui.cjs';

const grupo = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const coleccion = JSON.parse(fs.readFileSync(path.join(grupo, 'G93.postman_collection.json'), 'utf8'));
const unidadV1 = { id_infraestructura: 900, id_finca: 184, nombre_infraestructura: 'G93 local',
  estado_general: 'GRIS', total_sensores: 0, mensaje_estado: 'Sin datos disponibles',
  ultimo_dato_recibido: null };
const unidadV2 = { id_infraestructura: 1, id_finca: 184, nombre_infraestructura: 'Area local 1',
  estado_general: 'GRIS', total_sensores: 1, ultimo_dato_recibido: '2026-10-20T10:00:00Z' };
const sensorV2 = { id_infraestructura: 1, estado_conectividad: 'INACTIVO',
  dato_desactualizado: true, ultimo_timestamp_captura: '2026-10-20T10:00:00Z' };
const cuerpoV1 = { resumen_unidades: [unidadV1], sensores: [] };
const cuerpoV2 = { resumen_unidades: [unidadV2], sensores: [sensorV2] };

test('modo informe oficial: decisión por caso, detalle, evidencias y ausencia de JSON crudo', () => {
  const directorio = path.join(grupo, 'Resultados', 'RUN-G93-V1-20261031-080847');
  const resultado = JSON.parse(fs.readFileSync(path.join(directorio, 'resultado.json'), 'utf8'));
  const generado = informe({ ...resultado, directorio });
  const oficial = fs.readFileSync(path.join(directorio, 'TC-M03-G93_resultado.md'), 'utf8');
  assert.equal(oficial, generado);
  assert.match(oficial, /^## 3\. Detalle por caso y comprobaciones API\/UI$/m);
  assert.match(oficial, /^### TC-M03-184$/m);
  for (const campo of ['Caso original y objetivo', 'Precondiciones', 'Pasos ejecutados',
    'Entradas', 'Esperado', 'Observado por API pública', 'Observado por UI',
    'Decisión del caso', 'Qué falta o cambió']) {
    assert.match(oficial, new RegExp(`^\\*\\*${campo}:\\*\\*`, 'm'));
  }
  const resumen = oficial.split('## 2. Resumen ejecutivo y decisión del grupo')[1]
    .split('## 3. Detalle por caso')[0];
  assert.match(resumen, /\| Caso \| Funcional \| Técnico \|/);
  assert.match(resumen, /\| TC-M03-184 \| RECHAZADO \| OK \|/);
  assert.doesNotMatch(resumen, /\| (?:API|UI)-184-/);
  assert.match(oficial, /\| UI-184-01 \| UI \|[^\n]*\| RECHAZADO \|/);
  assert.doesNotMatch(oficial, /\{\s*"(?:cargando|unidades_visibles|estado_general)"\s*:/);
  for (const [, rel] of oficial.matchAll(/\]\(([^)]+)\)/g)) {
    assert.ok(fs.existsSync(path.join(directorio, rel)), `Enlace sin archivo: ${rel}`);
  }
  assert.deepEqual(fs.readdirSync(directorio).filter(x => x.endsWith('.md')),
    ['TC-M03-G93_resultado.md']);
});

test('cola UI libera el turno tras respuesta, error sincrono, rechazo y espera agotada', async () => {
  const cola = ui.crearColaPeticiones();
  const eventos = [];
  await assert.rejects(cola.tomar(() => { throw new Error('inicio'); }), /inicio/);
  await assert.rejects(cola.tomar(() => Promise.reject(new Error('red'))), /red/);
  await cola.tomar(liberar => {
    eventos.push('respuesta');
    liberar();
    liberar();
  });
  let vencimientos = 0;
  await cola.tomar(() => {}, { esperaMaximaMs: 10, alVencer: () => { vencimientos++; } });
  await cola.tomar(liberar => { eventos.push('siguiente'); liberar(); });
  assert.deepEqual(eventos, ['respuesta', 'siguiente']);
  assert.equal(vencimientos, 1);
});

test('acta distingue respuestas completas de una solicitud sin cierre', () => {
  assert.deepEqual(ui.peticionesSinRespuesta([
    { ruta: '/usuarios/me', fin: '2026-10-31T00:00:00Z' },
    { ruta: '/sesiones/me/permisos', fin: '2026-10-31T00:00:01Z' },
  ]), []);
  assert.deepEqual(ui.peticionesSinRespuesta([{ ruta: '/sesiones/me/permisos', fin: null }]),
    [{ ruta: '/sesiones/me/permisos', fin: null }]);
  const spec = fs.readFileSync(path.join(grupo, 'g93.cy.js'), 'utf8');
  assert.match(spec, /registro\.cabecera_run_enviada = true/);
  assert.doesNotMatch(spec, /expect\(request\.headers\['x-test-run-id'\]/);
  assert.match(spec, /PETICIONES_API_SIN_RESPUESTA/);
  assert.match(spec, /req\.reply\([\s\S]*?return;[\s\S]*?colaApi\.tomar/);
});

test('matriz y colección conservan ids, oráculo y un solo plan Newman filtrado', () => {
  assert.match(ORACULO, /estado GRIS y el mensaje "Sin datos disponibles"/);
  assert.deepEqual(IDS, ['API-184-01', 'API-184-02', 'API-184-03', 'UI-184-01', 'UI-184-02']);
  assert.equal(coleccion.item.length, 2);
  for (const item of coleccion.item) {
    assert.match(item.request.url, /dashboard\?id_infraestructura=\{\{id_v[12]\}\}/);
    for (const evento of item.event) new vm.Script(evento.script.exec.join('\n'));
  }
  assert.equal(comprobar(), 0);
  for (const archivo of ['G93.postman_collection.json', 'g93.mjs', 'g93.cy.js']) {
    assert.notEqual(fs.readFileSync(path.join(grupo, archivo)).subarray(0, 3).toString('hex'), 'efbbbf');
  }
});

test('variante nueva exige resumen GRIS, cero sensores, mensaje y fecha no fabricada', () => {
  assert.equal(evaluarApi('V1', { http: 200, cuerpo: cuerpoV1 }, 900).estado, 'APROBADO');
  assert.equal(evaluarApi('V1', { http: 200, cuerpo: { resumen_unidades: [{ ...unidadV1,
    ultimo_dato_recibido: '2020-10-25T12:34:00Z' }], sensores: [] } }, 900).estado, 'APROBADO');
  for (const cambio of [
    { mensaje_estado: null }, { estado_general: 'VERDE' },
    { total_sensores: 1 }, { ultimo_dato_recibido: 'fecha inventada' },
  ]) {
    const cuerpo = { resumen_unidades: [{ ...unidadV1, ...cambio }], sensores: [] };
    assert.equal(evaluarApi('V1', { http: 200, cuerpo }, 900).estado, 'RECHAZADO');
  }
  assert.equal(evaluarApi('V1', { http: 200, cuerpo: { resumen_unidades: [], sensores: [] } }, 900).estado, 'RECHAZADO');
  assert.equal(evaluarApi('V1', { http: 500, cuerpo: {} }, 900).estado, 'RECHAZADO');
});

test('variante con todos los sensores INACTIVO conserva histórico real', () => {
  assert.equal(evaluarApi('V2', { http: 200, cuerpo: cuerpoV2 }, 1).estado, 'APROBADO');
  assert.equal(evaluarApi('V2', { http: 200, cuerpo: {
    resumen_unidades: [unidadV2], sensores: [{ ...sensorV2, estado_conectividad: 'ACTIVO' }],
  } }, 1).estado, 'NO_CONCLUYENTE');
});

test('BUFFER_ACTIVO acredita ausencia de señal solo si todos los sensores cumplen; ACTIVO descarta', () => {
  const mezcla = { ...cuerpoV2, resumen_unidades: [{ ...unidadV2, total_sensores: 3 }],
    sensores: [sensorV2, { ...sensorV2, estado_conectividad: 'BUFFER_ACTIVO' },
      { ...sensorV2, estado_conectividad: 'SIN_SEÑAL' }] };
  const opciones = { fincasVisibles: [184] };
  assert.equal(revisarCandidataV2({ http: 200, cuerpo: mezcla }, 1, opciones).motivo, 'aceptada');
  assert.equal(evaluarApi('V2', { http: 200, cuerpo: mezcla }, 1).estado, 'APROBADO');
  const activo = { ...mezcla, sensores: mezcla.sensores.map((s, i) =>
    i === 1 ? { ...s, estado_conectividad: 'ACTIVO' } : s) };
  assert.equal(revisarCandidataV2({ http: 200, cuerpo: activo }, 1, opciones).motivo,
    'sensor_fuera_estados_sin_comunicacion');
  assert.equal(evaluarApi('V2', { http: 200, cuerpo: activo }, 1).estado, 'NO_CONCLUYENTE');
  const script = coleccion.item[1].event.find(x => x.listen === 'test').script.exec.join('\n');
  assert.match(script, /'SIN_SEÑAL','INACTIVO','BUFFER_ACTIVO'/);
});

test('cola UI evita 500 de un servidor local que rechaza peticiones simultáneas', async () => {
  const cola = ui.crearColaPeticiones();
  let activas = 0;
  let maximas = 0;
  const servidor = () => new Promise(resolve => {
    activas++;
    maximas = Math.max(maximas, activas);
    const status = activas > 1 ? 500 : 200;
    setTimeout(() => { activas--; resolve(status); }, 5);
  });
  const resultados = await Promise.all([1, 2, 3].map(() => new Promise(resolve =>
    cola.tomar(liberar => servidor().then(status => { liberar(); resolve(status); })))));
  assert.deepEqual(resultados, [200, 200, 200]);
  assert.equal(maximas, 1);
});

test('fallo de sesión UI 5xx se identifica sin declarar rechazo funcional', () => {
  for (const ruta of ['/sesiones/refresh', '/usuarios/me', '/sesiones/me/permisos']) {
    assert.equal(ui.sesionCon5xx([{ ruta, http: 500 }])?.ruta, ruta);
  }
  assert.equal(ui.sesionCon5xx([{ ruta: '/iot/monitoreo/dashboard', http: 500 }]), null);
  assert.equal(ui.mensajeAusenciaEquivalente('Sin datos'), true);
  assert.equal(ui.mensajeAusenciaEquivalente('Sin datos disponibles'), true);
});

test('acta Cypress con 5xx de sesión conserva UI NO_CONCLUYENTE aun con salida fallida', () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-sesion-local-'));
  try {
    for (const ruta of ['/sesiones/refresh', '/usuarios/me', '/sesiones/me/permisos']) {
      const salida = ejecutarCypress({ directorio: temporal, runId: 'RUN-G93-V1-20261031-000000' }, {
        fase: 'V1', id: 900, nombre: 'G93 local', fecha: null, base: 'http://127.0.0.1',
        front: 'http://127.0.0.1', cookie: 'LOCAL_COOKIE', secreto: 'LOCAL_SECRET',
        invocar() {
          fs.writeFileSync(path.join(temporal, 'cypress/UI-184-V1.json'), JSON.stringify({
            caso: 'TC-M03-184', id: 'UI-184-01', fase: 'V1',
            estado: 'NO_CONCLUYENTE', criterio: 'SESION_5XX', motivo: 'Sesión no evaluable',
            peticiones: [{ ruta, http: 503 }],
          }));
          return { proceso: { status: 1 } };
        },
      });
      assert.equal(salida.estado, 'NO_CONCLUYENTE');
      assert.equal(salida.proceso_fallido, true);
    }
    const salidaCero = ejecutarCypress({ directorio: temporal, runId: 'RUN-G93-V1-20261031-000000' }, {
      fase: 'V1', id: 900, nombre: 'G93 local', fecha: null, base: 'http://127.0.0.1',
      front: 'http://127.0.0.1', cookie: 'LOCAL_COOKIE', secreto: 'LOCAL_SECRET',
      invocar() { return { proceso: { status: 0 } }; },
    });
    assert.equal(salidaCero.estado, 'NO_CONCLUYENTE');
    assert.equal(salidaCero.proceso_fallido, false);
    assert.equal(salidaCero.ejecutadas, 1);
    const spec = fs.readFileSync(path.join(grupo, 'g93.cy.js'), 'utf8');
    assert.match(spec, /if \(acta\.criterio === 'SESION_5XX'\) return;/);
    const esperaSesion = spec.slice(spec.indexOf('const esperarSesion'), spec.indexOf('return login.then'));
    assert.doesNotMatch(esperaSesion, /throw new Error\(acta\.motivo\)/);
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});

test('acta válida conserva su estado con salida Cypress fallida; sin acta queda ERROR_QA', () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-acta-local-'));
  const opciones = { fase: 'V1', id: 900, nombre: 'G93 local', fecha: null,
    base: 'http://127.0.0.1', front: 'http://127.0.0.1',
    cookie: 'LOCAL_COOKIE', secreto: 'LOCAL_SECRET' };
  const contrato = { directorio: temporal, runId: 'RUN-G93-V1-20261031-000000' };
  try {
    const sinActa = ejecutarCypress(contrato, { ...opciones, invocar() {
      return { proceso: { status: 0 } };
    } });
    assert.equal(sinActa.estado, 'ERROR_QA');
    assert.equal(sinActa.ejecutadas, 0);
    for (const estado of ['APROBADO', 'RECHAZADO']) {
      const salida = ejecutarCypress(contrato, { ...opciones, invocar() {
        fs.writeFileSync(path.join(temporal, 'cypress/UI-184-V1.json'), JSON.stringify({
          caso: 'TC-M03-184', id: 'UI-184-01', fase: 'V1', estado,
          motivo: 'Acta local', peticiones: [],
        }));
        return { proceso: { status: 1 } };
      } });
      assert.equal(salida.estado, estado);
      assert.equal(salida.proceso_fallido, true);
    }
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});

test('adaptación UI usa filtro real y selector vigente; ausencia de tarjeta no aprueba', () => {
  const spec = fs.readFileSync(path.join(grupo, 'g93.cy.js'), 'utf8');
  assert.match(spec, /urlFiltrada\.searchParams\.set\('id_infraestructura'/);
  assert.match(spec, /filtro_aplicado_por_spec/);
  assert.match(spec, /cy\.get\('#monitoreo-area'\)/);
  const base = { unidad_objetivo_presente: true, gris: true, mensaje_ausencia: 'Sin datos',
    fecha_historica: true, sin_valores_fabricados: true, desde_cache: false };
  assert.equal(ui.evaluarOraculoUi(base, base).estado, 'APROBADO');
  assert.equal(ui.evaluarOraculoUi({ ...base, unidad_objetivo_presente: false }, base).estado, 'RECHAZADO');
  assert.equal(ui.evaluarOraculoUi(base, { ...base, sin_valores_fabricados: false }).estado, 'RECHAZADO');
});

test('carga lenta se evalúa tras render; vencimientos no producen falso RECHAZADO', async () => {
  const cuerpo = { textContent: 'Cargando…', querySelectorAll: () => [] };
  const ventana = { document: { body: cuerpo }, setTimeout };
  setTimeout(() => { cuerpo.textContent = 'Unidad local G93 Sin datos'; }, 35);
  assert.equal(await ui.esperarRenderEstable(ventana,
    { limiteMs: 150, estableMs: 20, intervaloMs: 5 }), false);
  cuerpo.textContent = 'Cargando…';
  assert.equal(await ui.esperarRenderEstable(ventana,
    { limiteMs: 35, estableMs: 20, intervaloMs: 5 }), true);
  const vista = { cargando: false, unidad_objetivo_presente: true, gris: true,
    mensaje_ausencia: 'Sin datos', fecha_historica: true,
    sin_valores_fabricados: true, desde_cache: false };
  assert.equal(ui.clasificarCarga({ http: 200, eco: true, ui: vista }).estado, 'EVALUAR_UI');
  assert.deepEqual(ui.clasificarCarga({ http: 200, eco: true,
    ui: { ...vista, cargando: true } }),
  { estado: 'NO_CONCLUYENTE', criterio: 'CARGA_SIN_TERMINAR' });
  assert.deepEqual(ui.clasificarCarga({ http: 200, eco: true, renderVencio: true, ui: vista }),
    { estado: 'NO_CONCLUYENTE', criterio: 'CARGA_SIN_TERMINAR' });
  assert.equal(ui.evaluarOraculoUi({ ...vista, cargando: true,
    unidad_objetivo_presente: false }, vista).estado, 'NO_CONCLUYENTE');
  assert.equal(ui.evaluarOraculoUi(vista, { ...vista, cargando: true }).estado, 'NO_CONCLUYENTE');
  const ensayo = fs.readFileSync(path.join(grupo, 'pruebas/g93_ensayo_spec_real.mjs'), 'utf8');
  assert.match(ensayo, /ejecutar\('cargalenta', 'V1', 'APROBADO'\)/);
  assert.match(ensayo, /ejecutar\('vencimiento', 'V1', 'NO_CONCLUYENTE', true\)/);
  assert.match(ensayo, /ejecutar\('cargainfinita', 'V1', 'NO_CONCLUYENTE', true\)/);
});

test('regresión V2: fecha histórica y ausencia no fabrican lecturas en ninguna vista', () => {
  const global = 'Unidad local G93 Finca local · último dato 25/10/2020 12:34Sin datos';
  const filtrada = `${global}Sensor INACTIVO desactualizado Requiere calibración`;
  assert.equal(ui.sinValoresFabricados(global), true);
  assert.equal(ui.sinValoresFabricados(filtrada), true);
  const vista = texto => ({ unidad_objetivo_presente: true, gris: true,
    mensaje_ausencia: 'Sin datos', fecha_historica: true,
    sin_valores_fabricados: ui.sinValoresFabricados(texto), desde_cache: false });
  assert.equal(ui.evaluarOraculoUi(vista(global), vista(filtrada)).estado, 'APROBADO');
});

test('regresión V2: contador global y lectura filtrada sí son valores fabricados', () => {
  const global = 'Unidad local G93 último dato 25/10/2020 12:34Sin datos';
  assert.equal(ui.sinValoresFabricados(`${global}0 sensores en línea`), false);
  assert.equal(ui.sinValoresFabricados(`${global}Sensor INACTIVO Temperatura: 12.5 °C`), false);
  const vista = texto => ({ unidad_objetivo_presente: true, gris: true,
    mensaje_ausencia: 'Sin datos', fecha_historica: true,
    sin_valores_fabricados: ui.sinValoresFabricados(texto), desde_cache: false });
  assert.equal(ui.evaluarOraculoUi(vista(`${global}0 sensores en línea`), vista(global)).criterio,
    'ORACULO_PANEL_GLOBAL_INCUMPLIDO');
  assert.equal(ui.evaluarOraculoUi(vista(global),
    vista(`${global}Sensor INACTIVO Temperatura: 12.5 °C`)).criterio, 'ORACULO_UI_INCUMPLIDO');
});

test('Newman ejecuta una colección con dos respuestas y conserva el JSON saneado', () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-newman-local-'));
  const cuerpo = j => ({ data: [...Buffer.from(JSON.stringify(j))] });
  let invocaciones = 0;
  try {
    const contrato = { runId: 'RUN-G93-V1-20261031-000000', directorio: temporal };
    const salida = newman(contrato, { idV1: 900, idV2: 1,
      base: 'https://www.api.inmero.co/api-sgpmp-test', token: 'LOCAL_TOKEN',
      secreto: 'LOCAL_SECRET', secretos: ['LOCAL_TOKEN', 'LOCAL_SECRET'],
      tempDir: temporal, invocar(args) {
        invocaciones++;
        const destino = args[args.indexOf('--reporter-json-export') + 1];
        fs.writeFileSync(destino, JSON.stringify({ run: { failures: [], executions: [
          { response: { code: 200, stream: cuerpo(cuerpoV1),
            header: [{ key: 'X-Test-Run-Id', value: contrato.runId }] } },
          { response: { code: 200, stream: cuerpo(cuerpoV2),
            header: [{ key: 'X-Test-Run-Id', value: contrato.runId }] } },
        ] } }));
        return { status: 0 };
      } });
    assert.equal(invocaciones, 1);
    assert.deepEqual(salida.respuestas.map(x => x.http), [200, 200]);
    assert.ok(salida.respuestas.every(x => x.eco));
    assert.equal(salida.respuestas[0].cuerpo.resumen_unidades[0].mensaje_estado, 'Sin datos disponibles');
    assert.ok(fs.existsSync(path.join(temporal, salida.rel)));
    assert.doesNotMatch(fs.readFileSync(path.join(temporal, salida.rel), 'utf8'), /LOCAL_TOKEN|LOCAL_SECRET/);
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});

test('API V1 y V2 completas anteceden a ambas UI; Newman se invoca una vez', async () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-local-'));
  const eventos = [];
  let cerrado = false;
  let logins = 0;
  const runId = 'RUN-G93-V1-20261031-000000';
  const respuesta = (status, cuerpo, cookie = null) => ({
    status, json: async () => cuerpo,
    headers: { get: k => k.toLowerCase() === 'x-test-run-id' ? runId
      : k.toLowerCase() === 'set-cookie' ? cookie : null },
  });
  const fetcher = async (url, opciones) => {
    const ruta = new URL(url).pathname.replace('/api-sgpmp-test', '') + new URL(url).search;
    const metodo = opciones.method;
    eventos.push(`${metodo} ${ruta}`);
    if (ruta === '/sesiones/' && metodo === 'POST') {
      logins++;
      return respuesta(200, { token: `LOCAL_TOKEN_${logins}` }, 'refresh_token=LOCAL_COOKIE; Path=/');
    }
    if (ruta === `/test-control/runs/${runId}` && metodo === 'DELETE') {
      cerrado = true; return respuesta(200, {});
    }
    if (ruta === '/usuarios/me') return respuesta(200, {
      nombre_rol: opciones.headers.Authorization === 'Bearer LOCAL_TOKEN_1' ? 'Administrador' : 'Productor',
    });
    if (ruta === '/configuracion/fincas/184') return respuesta(200, { id_finca: 184, es_activo: true });
    if (ruta === '/configuracion/fincas?solo_activas=true') return respuesta(200, { items: [{ id_finca: 184 }] });
    if (ruta === '/configuracion/infraestructuras/349') return respuesta(200, {
      id_infraestructura: 349, id_finca: 184, es_activo: true,
      especies: [126], superficie: 10, tipo_area: 'LOTE' });
    if (ruta === '/configuracion/infraestructuras' && metodo === 'POST')
      return respuesta(201, { id_infraestructura: 900 });
    if (ruta === '/configuracion/infraestructuras/900')
      return respuesta(cerrado ? 404 : 200, cerrado ? {} : unidadV1);
    if (ruta === '/configuracion/infraestructuras/1') return respuesta(200, {
      id_infraestructura: 1, nombre_infraestructura: 'Area local 1', id_finca: 184,
      es_activo: true, especies: [126] });
    if (ruta === '/iot/dispositivos?estado=INACTIVO') return respuesta(200, []);
    if (ruta.startsWith('/iot/monitoreo/dashboard?id_infraestructura=1&'))
      return respuesta(200, cuerpoV2);
    if (ruta.startsWith('/iot/monitoreo/dashboard?id_infraestructura=900&'))
      return respuesta(200, cerrado ? { total: 0, resumen_unidades: [], sensores: [] } : cuerpoV1);
    if (ruta.startsWith('/iot/monitoreo/dashboard?id_infraestructura=2&')
      || ruta.startsWith('/iot/monitoreo/dashboard?id_infraestructura=3&'))
      return respuesta(200, { resumen_unidades: [], sensores: [] });
    throw new Error(`Ruta local imprevista: ${metodo} ${ruta}`);
  };
  const contrato = { operacion: 'reintentar', version: 1, runId,
    referencia: 'LOCAL_SINTETICO', directorio: temporal };
  const env = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test',
    SIGAB_FRONT_TEST_URL: 'https://api.inmero.co/sigab-test', QA_SANDBOX_SECRET: 'LOCAL_SECRET',
    QA_ADMIN_EMAIL: 'admin@local.test', QA_ADMIN_PASSWORD: 'LOCAL_ADMIN',
    QA_PROD_EMAIL: 'productor@local.test', QA_PROD_PASSWORD: 'LOCAL_PROD' };
  const runNewman = async (c, opciones) => {
    eventos.push('NEWMAN');
    assert.deepEqual([opciones.idV1, opciones.idV2], [900, 1]);
    fs.mkdirSync(path.join(temporal, 'newman'));
    fs.writeFileSync(path.join(temporal, 'newman/newman-G93.json'), '{}');
    return { rel: 'newman/newman-G93.json', respuestas: [
      { http: 200, cuerpo: cuerpoV1, eco: true },
      { http: 200, cuerpo: cuerpoV2, eco: true },
    ], fallos: [] };
  };
  const runCypress = async (c, opciones) => {
    eventos.push(`CYPRESS_${opciones.fase}`);
    const rel = `cypress/UI-184-${opciones.fase}.json`;
    fs.mkdirSync(path.join(temporal, 'cypress'), { recursive: true });
    fs.writeFileSync(path.join(temporal, rel), '{}');
    return { rel, estado: 'APROBADO', motivo: 'UI local', ejecutadas: 1,
      peticiones: [{ ruta: '/sesiones/refresh', http: 200 }],
      ui_inicial: { mensaje_ausencia: 'Sin datos disponibles' },
      ui_objetivo: { mensaje_ausencia: 'Sin datos disponibles' } };
  };
  try {
    const r = await evaluar(contrato, { env, fetcher, runNewman, runCypress, modoEnsayo: 'local' });
    assert.equal(r.casos['TC-M03-184'].estado, 'APROBADO');
    assert.deepEqual(r.comprobaciones.filter(x => x.tipo === 'ASSERT').map(x => [x.id, x.estado]),
      IDS.map(id => [id, 'APROBADO']));
    assert.deepEqual(eventos.filter(x => x === 'NEWMAN' || x.startsWith('CYPRESS_')),
      ['NEWMAN', 'CYPRESS_V1', 'CYPRESS_V2']);
    assert.equal(r.newman.length, 1);
    assert.equal(r.cypress.total_pruebas, 2);
    assert.equal(r.cierre.rollback.verificado, true);
    assert.equal(logins, 3);
    assert.equal(r.oficial, false);
    assert.equal(r.rls.estado, 'NO_CONCLUYENTE');
    assert.equal(r.bitacora.length, 21); // más dos GET de la única ejecución Newman: 23
    assert.ok(eventos.filter(x => x.includes('/iot/monitoreo/dashboard')).every(x =>
      x.includes('id_infraestructura=')));
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});

test('oficialidad exige cinco ASSERT resueltas, UI ejecutada y cierre verificado', () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-registro-'));
  try {
    fs.writeFileSync(path.join(temporal, 'TC-M03-G93_resultado.md'), '# local');
    fs.writeFileSync(path.join(temporal, 'resultado.json'), '{}');
    const base = { run_id: 'RUN-G93-V1-20261031-000000', version: 1, oficial: false,
      consume_version: true, datos: {}, casos: { 'TC-M03-184': { estado: 'RECHAZADO' } },
      comprobaciones: IDS.map(id => ({ caso: 'TC-M03-184', id,
        fuente: id.startsWith('UI') ? 'UI' : 'API', tipo: 'ASSERT', estado: 'APROBADO' })),
      cypress: { total_pruebas: 2 }, cierre: { run: { cierre_http: 200 },
        rollback: { verificado: true } }, evidencias: ['resultado.json'] };
    assert.equal(evaluarRegistro(base, temporal).oficialPosible, true);
    assert.equal(evaluarRegistro({ ...base, cypress: { total_pruebas: 0 } }, temporal).oficialPosible, false);
    assert.equal(evaluarRegistro({ ...base, comprobaciones: base.comprobaciones.slice(0, -1) }, temporal).oficialPosible, false);
    assert.equal(evaluarRegistro({ ...base, cierre: { run: { cierre_http: 200 },
      rollback: { verificado: false } } }, temporal).oficialPosible, false);
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});
