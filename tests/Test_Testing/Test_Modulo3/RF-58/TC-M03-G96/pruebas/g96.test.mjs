import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { CAPACIDADES, CATALOGO, clasificar, PRESUPUESTO } from '../lib/g96_escenario.mjs';
import { comprobar, descubrir, evaluar, evaluarNewman, esOficial, informe, leerPagina } from '../g96.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';

const dispositivos = Object.fromEntries(CATALOGO.map((estado, i) => [estado,
  [{ id_dispositivo_iot: i + 1, id_infraestructura: i + 1 }]]));
const paginas = CATALOGO.map((estado, i) => ({ unidad: i + 1, pagina: 1, total: 1, http: 200, eco: true,
  sensores: [{ id_dispositivo_iot: i + 1, estado_conectividad: estado }] }));

test('informe generado no menciona la matriz interna de QA', () => {
  const resultado = JSON.parse(fs.readFileSync(new URL('../Resultados/RUN-G96-V1-20261031-153625/resultado.json', import.meta.url), 'utf8'));
  assert.doesNotMatch(informe(resultado), /matriz|CSV|Casos_Prueba/i);
});

test('catálogo RF-60 y cobertura pública por cinco estados', () => {
  assert.deepEqual(CAPACIDADES.comprobaciones_obligatorias['TC-M03-187'].API, ['API-187-01', 'API-187-02']);
  assert.equal(PRESUPUESTO.solicitudes_en_run, 38);
  assert.equal(clasificar({ paginas, dispositivos }).estado, 'APROBADO');
  assert.equal(clasificar({ paginas: [{ ...paginas[0], sensores: [{ id_dispositivo_iot: 1, estado_conectividad: 'ONLINE' }] }, ...paginas.slice(1)], dispositivos }).estado, 'RECHAZADO');
  const desconocido = clasificar({ paginas: [{ ...paginas[0], sensores: [...paginas[0].sensores,
    { id_dispositivo_iot: 999, estado_conectividad: 'DESCONOCIDO' }] }, ...paginas.slice(1)], dispositivos });
  assert.equal(desconocido.estado, 'APROBADO');
  assert.equal(desconocido.desconocido, 1);
  const buffer = clasificar({ paginas: paginas.map(p => p.unidad === 3 ? { ...p,
    sensores: [{ id_dispositivo_iot: 3, estado_conectividad: 'SIN_SEÑAL' }] } : p), dispositivos });
  assert.equal(buffer.estado, 'RECHAZADO');
  assert.equal(buffer.cobertura.BUFFER_ACTIVO.estado, 'RECHAZADO');
  const ausente = clasificar({ paginas, dispositivos: { ...dispositivos, EN_MANTENIMIENTO: [] } });
  assert.equal(ausente.estado, 'NO_CONCLUYENTE');
  assert.equal(ausente.cobertura.EN_MANTENIMIENTO.estado, 'NO_CONCLUYENTE');
});

test('transporte Newman es incidencia técnica y no defecto funcional', () => {
  const n = evaluarNewman({ paginas: [], fallos: [{ tipo: 'Error', mensaje: 'connect ECONNREFUSED', test: '' }],
    proceso: { error: 'ECONNREFUSED' }, dispositivos });
  assert.equal(n.datos.estado, 'NO_CONCLUYENTE');
  assert.ok(n.problemasTecnicos.some(x => x.includes('TRANSPORTE') || x.includes('ECONNREFUSED')));
});

test('candidata sin sensores avanza; reutiliza área y respalda con Administrador', async () => {
  const original = globalThis.fetch;
  const llamadas = [];
  const filas = [
    { id_dispositivo_iot: 6, id_infraestructura: 6, estado_actual: 'ACTIVO' },
    { id_dispositivo_iot: 1, id_infraestructura: 1, estado_actual: 'ACTIVO' },
    { id_dispositivo_iot: 3, id_infraestructura: 3, estado_actual: 'BUFFER_ACTIVO' },
    { id_dispositivo_iot: 4, id_infraestructura: 1, estado_actual: 'INACTIVO' },
    { id_dispositivo_iot: 5, id_infraestructura: 5, estado_actual: 'EN_MANTENIMIENTO' },
  ];
  globalThis.fetch = async (url, opciones) => {
    const u = new URL(url);
    const rol = opciones.headers.Authorization === 'Bearer ADMIN' ? 'Administrador' : 'Productor';
    llamadas.push({ ruta: u.pathname, area: Number(u.searchParams.get('id_infraestructura')), rol,
      por_pagina: u.searchParams.get('por_pagina') });
    let cuerpo;
    if (u.pathname === '/iot/dispositivos') {
      cuerpo = rol === 'Productor' ? filas.filter(d => d.id_dispositivo_iot !== 5) : filas;
      if (u.searchParams.has('estado')) cuerpo = cuerpo.filter(d => d.estado_actual === u.searchParams.get('estado'));
    } else {
      const area = Number(u.searchParams.get('id_infraestructura'));
      const ids = area === 1 ? [1, 4] : area === 6 ? [] : [area];
      const pagina = Number(u.searchParams.get('pagina'));
      cuerpo = { total: ids.length, sensores: ids.slice(pagina - 1, pagina).map(id => ({ id_dispositivo_iot: id,
        estado_semaforo: 'VERDE', dato_desactualizado: false })) };
    }
    return { status: 200, headers: { get: () => 'ENSAYO' }, json: async () => cuerpo };
  };
  try {
    const r = { bitacora: [], listados: [], canarios: [], problemas_tecnicos: [] };
    const unidades = await descubrir('http://127.0.0.1:1', 'ADMIN', 'PROD',
      { QA_SANDBOX_SECRET: 'ENSAYO_SECRET' }, { runId: 'ENSAYO' }, r);
    assert.deepEqual(unidades, [{ area: 3, rol: 'Productor' }, { area: 1, rol: 'Productor' },
      { area: 5, rol: 'Administrador' }]);
    assert.equal(r.canarios[0].area, 6);
    assert.equal(r.canarios[0].total, 0);
    assert.deepEqual(r.dispositivos.INACTIVO.map(d => d.id_dispositivo_iot), [4]);
    assert.equal(r.dispositivos['SIN_SEÑAL'].length, 0);
    assert.equal(llamadas.filter(x => x.ruta === '/iot/dispositivos').length, 6);
    assert.equal(llamadas.find(x => x.area === 5 && x.por_pagina === '1').rol, 'Administrador');
    assert.ok(r.bitacora.length <= PRESUPUESTO.solicitudes_en_run);
    const paginasLocales = [
      { unidad: 1, rol: 'Productor', pagina: 1, total: 2, http: 200, eco: true, sensores: [
        { id_dispositivo_iot: 1, estado_conectividad: 'ACTIVO' },
        { id_dispositivo_iot: 4, estado_conectividad: 'INACTIVO' }] },
      { unidad: 3, rol: 'Productor', pagina: 1, total: 1, http: 200, eco: true,
        sensores: [{ id_dispositivo_iot: 3, estado_conectividad: 'BUFFER_ACTIVO' }] },
      { unidad: 5, rol: 'Administrador', pagina: 1, total: 1, http: 200, eco: true,
        sensores: [{ id_dispositivo_iot: 5, estado_conectividad: 'EN_MANTENIMIENTO' }] },
    ];
    const decision = clasificar({ paginas: paginasLocales, dispositivos: r.dispositivos, disponibles: r.disponibles });
    assert.equal(decision.cobertura.INACTIVO.estado, 'APROBADO');
    assert.equal(decision.cobertura.INACTIVO.sensores_cotejados, 1);
    assert.equal(decision.cobertura.EN_MANTENIMIENTO.rol, 'Administrador');
    assert.equal(decision.cobertura['SIN_SEÑAL'].estado, 'NO_CONCLUYENTE');
    assert.match(decision.cobertura['SIN_SEÑAL'].motivo, /sin escrituras/);
  } finally { globalThis.fetch = original; }
});

test('EN_MANTENIMIENTO recorre tres dispositivos y excluye GRIS E7', async () => {
  const original = globalThis.fetch;
  const filas = CATALOGO.map((estado, i) => ({ id_dispositivo_iot: i + 1,
    id_infraestructura: i + 1, estado_actual: estado })).concat([
    { id_dispositivo_iot: 7, id_infraestructura: 6, estado_actual: 'EN_MANTENIMIENTO' },
    { id_dispositivo_iot: 8, id_infraestructura: 7, estado_actual: 'EN_MANTENIMIENTO' },
  ]);
  try {
    for (const gris of [false, true]) {
      const consultas = [];
      globalThis.fetch = async (url, opciones) => {
        const u = new URL(url);
        const area = Number(u.searchParams.get('id_infraestructura'));
        if (u.pathname === '/iot/dispositivos') {
          const estado = u.searchParams.get('estado');
          const cuerpo = estado ? filas.filter(d => d.estado_actual === estado) : filas;
          return { status: 200, headers: { get: () => 'ENSAYO' }, json: async () => cuerpo };
        }
        consultas.push({ area, pagina: Number(u.searchParams.get('pagina')),
          por_pagina: Number(u.searchParams.get('por_pagina')) });
        const sensor = { id_dispositivo_iot: area === 5 || area === 6 ? 999 : area === 7 ? 8 : area,
          estado_conectividad: gris && area === 5 ? 'DESCONOCIDO' : 'ACTIVO',
          estado_semaforo: gris && area === 5 ? 'GRIS' : 'VERDE',
          dato_desactualizado: false, sin_umbral: gris && area === 5 };
        return { status: 200, headers: { get: () => 'ENSAYO' },
          json: async () => ({ total: 1, sensores: [sensor] }) };
      };
      const r = { bitacora: [], listados: [], canarios: [], problemas_tecnicos: [] };
      const unidades = await descubrir('http://127.0.0.1:1', 'ADMIN', 'PROD',
        { QA_SANDBOX_SECRET: 'ENSAYO_SECRET' }, { runId: 'ENSAYO' }, r);
      assert.deepEqual(r.canarios.filter(x => [5, 6, 7].includes(x.area)).map(x => x.area), [5, 6, 7]);
      assert.deepEqual(r.dispositivos.EN_MANTENIMIENTO.map(x => x.id_dispositivo_iot), [8]);
      assert.ok(unidades.some(x => x.area === 7));
      assert.ok(!unidades.some(x => [5, 6].includes(x.area)));
      assert.ok(r.descartadas.some(x => x.area === 6 && x.dispositivo === 7));
      assert.ok(r.descartadas.some(x => x.area === 5 && (gris ? /E7/.test(x.motivo) : x.dispositivo === 5)));
      if (gris) assert.equal(r.canarios.find(x => x.area === 5).desconocido, 1);
      assert.ok(consultas.every(x => x.por_pagina === 1));
    }
  } finally { globalThis.fetch = original; }
});

test('sin sensores propios en ningún dispositivo queda NO_CONCLUYENTE', async () => {
  const original = globalThis.fetch;
  const filas = CATALOGO.map((estado, i) => ({ id_dispositivo_iot: i + 1,
    id_infraestructura: i + 1, estado_actual: estado }));
  globalThis.fetch = async url => {
    const u = new URL(url);
    const estado = u.searchParams.get('estado');
    const cuerpo = u.pathname === '/iot/dispositivos'
      ? estado ? filas.filter(d => d.estado_actual === estado) : filas
      : { total: 1, sensores: [{ id_dispositivo_iot: 999, estado_semaforo: 'VERDE' }] };
    return { status: 200, headers: { get: () => 'ENSAYO' }, json: async () => cuerpo };
  };
  try {
    const r = { bitacora: [], listados: [], canarios: [], problemas_tecnicos: [] };
    const unidades = await descubrir('http://127.0.0.1:1', 'ADMIN', 'PROD',
      { QA_SANDBOX_SECRET: 'ENSAYO_SECRET' }, { runId: 'ENSAYO' }, r);
    assert.deepEqual(unidades, []);
    const decision = clasificar({ dispositivos: r.dispositivos, disponibles: r.disponibles });
    assert.equal(decision.estado, 'NO_CONCLUYENTE');
    assert.match(decision.cobertura.EN_MANTENIMIENTO.motivo, /Ningún dispositivo.*sensores propios/);
    assert.equal(r.descartadas.length, 5);
  } finally { globalThis.fetch = original; }
});

test('guarda de colección restringe el ensayo a 127.0.0.1', () => {
  const col = JSON.parse(fs.readFileSync(new URL('../G96.postman_collection.json', import.meta.url), 'utf8'));
  const script = col.item[0].event.find(x => x.listen === 'prerequest').script.exec.join('\n');
  const probar = base => {
    let omitida = false;
    const valores = { autorizado_run: 'SI', run_id: 'RUN-G96-V1-20261031-000001',
      ensayo_loopback: 'SI', base_url: base };
    try { vm.runInNewContext(script, { pm: { environment: { get: k => valores[k] },
      execution: { skipRequest: () => { omitida = true; } } } }); }
    catch (e) { assert.match(e.message, /BLOQUEO_G96/); }
    return omitida;
  };
  assert.equal(probar('http://127.0.0.1:3456'), false);
  assert.equal(probar('http://localhost:3456'), true);
  assert.equal(probar('https://www.api.inmero.co/api-sgpmp-test'), true);
});

test('colección cambia al token Administrador al avanzar de área', () => {
  const col = JSON.parse(fs.readFileSync(new URL('../G96.postman_collection.json', import.meta.url), 'utf8'));
  const script = col.item[0].event.find(x => x.listen === 'test').script.exec.join('\n');
  const valores = new Map(Object.entries({ unidades: JSON.stringify([
    { area: 1, rol: 'Productor' }, { area: 5, rol: 'Administrador' }]), indice: '0', pagina: '1',
    por_pagina: '50', limite_paginas: '12', paginas_usadas: '0', vistos: '[]', token_prod: 'PROD',
    token_admin: 'ADMIN', token: 'PROD', run_id: 'ENSAYO' }));
  const pm = { environment: { get: k => valores.get(k), set: (k, v) => valores.set(k, v) },
    response: { code: 200, headers: { get: () => 'ENSAYO' }, json: () => ({ total: 1,
      sensores: [{ id_dispositivo_iot: 1, estado_conectividad: 'ACTIVO' }] }) },
    test: (_, fn) => fn(), expect: lista => ({ to: { include: valor => assert.ok(lista.includes(valor)) } }),
    execution: { setNextRequest: () => {} }, info: { requestName: 'API-187-01' } };
  vm.runInNewContext(script, { pm });
  assert.equal(valores.get('unidad'), '5');
  assert.equal(valores.get('token'), 'ADMIN');
});

test('modo ensayo escribe solo en el directorio del contexto temporal', async () => {
  const directorio = path.dirname(fileURLToPath(new URL('../g96.mjs', import.meta.url)));
  const resultados = path.join(directorio, 'Resultados');
  const antes = fs.existsSync(resultados) ? fs.readdirSync(resultados) : null;
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g96-ruta-'));
  try {
    const runId = 'ENSAYO-G96-20261031-000001-ruta';
    const archivo = path.join(temporal, 'contexto_operacion.json');
    fs.writeFileSync(archivo, JSON.stringify({ grupo: 'G96', version: 1, intento: 1,
      run_id: runId, operacion: 'EVALUAR', referencia: 'ENSAYO_LOCAL', casos: ['TC-M03-187'] }));
    const argumentos = ['--operacion', 'evaluar', '--version', '1', '--intento', '1',
      '--run-id', runId, '--autorizacion', 'ENSAYO_LOCAL', '--contexto', archivo];
    const contexto = contextoEjecucion(argumentos, { grupo: 'G96', casos: ['TC-M03-187'],
      directorio, modoEnsayo: true });
    assert.equal(contexto.directorio, temporal);
    assert.throws(() => contextoEjecucion(argumentos.map(x => x === runId
      ? 'RUN-G96-V1-20261031-000001' : x), { grupo: 'G96', casos: ['TC-M03-187'],
      directorio, modoEnsayo: true }), /Ruta de contexto fuera del RUN/);
    await evaluar(contexto, { env: {}, ensayo: true });
    assert.ok(fs.existsSync(path.join(temporal, 'preflight.json')));
    assert.ok(fs.existsSync(path.join(temporal, 'resultado.json')));
    assert.deepEqual(fs.existsSync(resultados) ? fs.readdirSync(resultados) : null, antes);
  } finally {
    fs.rmSync(temporal, { recursive: true, force: true });
  }
});

test('colección y ejecutor comparten filtro de área y una ejecución Newman', () => {
  const col = JSON.parse(fs.readFileSync(new URL('../G96.postman_collection.json', import.meta.url), 'utf8'));
  assert.equal(col.item.length, 1);
  assert.equal(col.item[0].request.method, 'GET');
  assert.match(col.item[0].request.url, /id_infraestructura=\{\{unidad\}\}/);
  const script = col.item[0].event.map(x => x.script.exec.join('\n')).join('\n');
  new vm.Script(script);
  assert.match(script, /API-187-01/);
  assert.doesNotMatch(script, /ONLINE','OFFLINE','SIN_SENAL/);
  assert.equal(comprobar(), 0);
  const extraida = leerPagina({ request: { url: { raw: 'http://127.0.0.1:1/iot/monitoreo/dashboard?id_infraestructura=3&pagina=1&por_pagina=50' } },
    response: { code: 200, header: [{ key: 'X-Test-Run-Id', value: 'ENSAYO' }],
      stream: { data: Buffer.from(JSON.stringify({ total: 1, sensores: [{ id_dispositivo_iot: 3, estado_conectividad: 'BUFFER_ACTIVO' }] })) } } }, 'ENSAYO');
  assert.equal(extraida.unidad, 3);
  assert.equal(extraida.sensores[0].id_dispositivo_iot, 3);
});

test('oficialidad exige dos ASSERT terminales, cierre y solo lectura acreditados', () => {
  const r = { cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } },
    problemas_tecnicos: [], comprobaciones: ['API-187-01', 'API-187-02'].map(id =>
      ({ caso: 'TC-M03-187', fuente: 'API', id, tipo: 'ASSERT', estado: 'APROBADO' })) };
  assert.equal(esOficial('APROBADO', r, true), true);
  assert.equal(esOficial('APROBADO', { ...r, comprobaciones: r.comprobaciones.slice(0, 1) }, true), false);
  assert.equal(esOficial('APROBADO', { ...r, cierre: { run: { cierre_http: 500 }, rollback: { verificado: true } } }, true), false);
});
