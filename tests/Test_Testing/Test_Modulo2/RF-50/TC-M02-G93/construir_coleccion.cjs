// Genera test_tc_m02_g93.json - TC-M02-G93 (RF-50): reglas negativas de datos consolidados.
// TC-M02-155   modulo sin scope        -> BLOQUEADO: no existe identidad de modulo ni scope por tipo_dato
// TC-M02-156-A fecha_inicio > fecha_fin -> ficha: 400
// TC-M02-156-B fechas futuras           -> ficha: 400
// TC-M02-157   NIC41 sin metricas PESO  -> BLOQUEADO: M06 no existe como consumidor autenticable
// Caso enteramente de lectura: 0 escrituras de QA.
const fs = require('fs');
const path = require('path');

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const RUTA = '/activos-biologicos/{id_activo}/datos-consolidados';

// Consumidor autorizado y activo verificados en la Etapa 1.
const ACTIVO = 279;                 // QAJE-CREC-OK · ACTIVO · finca 57 · ciclo desde 2026-06-01
const TIPO_DATO = 'metricas';       // valor real del contrato: eventos | fases | estado | metricas | todos

// TC-M02-156-A: ambas fechas en el pasado; la unica invalidez es el orden.
const A_INICIO = '2026-08-20';
const A_FIN = '2026-08-10';

// Diagnostico de TC-M02-157: rango valido, no futuro, dentro del ciclo de vida del activo
// (que arranca el 2026-06-01) y sin ninguna metrica PESO. El activo si tiene pesos en
// septiembre, fuera del rango, de modo que la ausencia es especifica del periodo.
const NIC_INICIO = '2026-06-01';
const NIC_FIN = '2026-08-31';

const PRELUDIO = [
  "const norm = (s) => String(s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();",
  "const cuerpo = () => { try { return JSON.stringify(pm.response.json()); } catch (e) { return pm.response.text(); } };",
].join('\n');

const raw = (obj) => ({ mode: 'raw', raw: JSON.stringify(obj, null, 2), options: { raw: { language: 'json' } } });
const test = (lines) => ({ listen: 'test', script: { type: 'text/javascript', exec: (PRELUDIO + '\n' + lines.join('\n')).split('\n') } });
const auth = () => [{ key: 'Authorization', value: 'Bearer {{token_consumidor}}' }];

// Ninguna respuesta de rechazo debe filtrar datos consolidados del activo.
const sinExposicion = (id) => [
  "pm.test('" + id + ": la respuesta no expone datos consolidados del activo', () => {",
  "  const b = (() => { try { return pm.response.json(); } catch (e) { return {}; } })();",
  "  ['historial_eventos', 'historial_fases', 'historico_estados', 'metricas_actuales', 'infraestructura_asociada'].forEach((campo) => {",
  "    pm.expect(b, 'la respuesta incluye ' + campo).to.not.have.property(campo);",
  "  });",
  "});",
];

// ---------- 00-SETUP-LECTURA ----------
const setup = { name: '00-SETUP-LECTURA', item: [] };

setup.item.push({
  name: 'Contrato vivo OpenAPI por HTTPS',
  request: { method: 'GET', header: [], url: BASE + '/openapi.json' },
  event: [test([
    "pm.test('El ambiente TEST HTTPS responde 200', () => pm.response.to.have.status(200));",
    "const spec = pm.response.json();",
    "const ruta = '" + RUTA + "';",
    "pm.test('El contrato declara GET ' + ruta, () => pm.expect(spec.paths).to.have.property(ruta));",
    "const op = spec.paths[ruta].get;",
    "const params = Object.fromEntries((op.parameters || []).map((p) => [p.name, p]));",
    "pm.test('El endpoint acepta tipo_dato, fecha_inicio y fecha_fin', () => {",
    "  ['tipo_dato', 'fecha_inicio', 'fecha_fin'].forEach((n) => pm.expect(params, 'falta ' + n).to.have.property(n));",
    "});",
    "pm.test('tipo_dato admite los valores documentados por el contrato', () => {",
    "  pm.expect(norm(params.tipo_dato.schema.description)).to.include('metricas');",
    "  pm.collectionVariables.set('tipos_dato', params.tipo_dato.schema.description);",
    "});",
    "pm.test('El formato de fecha declarado es YYYY-MM-DD', () => {",
    "  pm.expect(params.fecha_inicio.schema.description).to.include('YYYY-MM-DD');",
    "});",
    "const resp = Object.keys(op.responses);",
    "pm.collectionVariables.set('respuestas_declaradas', resp.join(','));",
    "pm.test('El contrato declara 400, exigido por TC-M02-156', () => pm.expect(resp).to.include('400'));",
    "pm.test('El contrato declara 403, exigido por TC-M02-155', () => pm.expect(resp).to.include('403'));",
    "pm.test('El contrato declara 422, exigido por TC-M02-157', () => pm.expect(resp).to.include('422'));",
    // Evidencia contractual del bloqueo de TC-M02-155.
    "pm.test('BLOQUEO TC-M02-155: el contrato no define ningun esquema de seguridad con scopes', () => {",
    "  pm.expect(spec.components.securitySchemes, 'securitySchemes declarado').to.eql(undefined);",
    "  pm.expect(spec.security, 'security global declarado').to.eql(undefined);",
    "  pm.expect(op.security, 'security del endpoint declarado').to.eql(undefined);",
    "});",
    "pm.test('BLOQUEO TC-M02-155: el endpoint no recibe ningun identificador de modulo consumidor', () => {",
    "  const nombres = Object.keys(params);",
    "  pm.expect(nombres.filter((n) => /modulo|scope|client|consumidor/i.test(n))).to.eql([]);",
    "});",
  ])],
});

setup.item.push({
  name: 'Login del consumidor autorizado (Productor)',
  request: {
    method: 'POST', header: [{ key: 'Content-Type', value: 'application/json' }],
    url: BASE + '/sesiones/',
    body: raw({ correo_electronico: 'm2m.nuevo@ejemplo.com', contrasena: '{{password}}' }),
  },
  event: [test([
    "pm.test('Login exitoso del consumidor', () => pm.response.to.have.status(200));",
    "const t = pm.response.json().token;",
    "pm.collectionVariables.set('token_consumidor', t);",
    "const sub = JSON.parse(atob(t.split('.')[1])).sub;",
    "pm.test('La credencial es valida y corresponde al usuario 35', () => pm.expect(String(sub)).to.eql('35'));",
  ])],
});

setup.item.push({
  name: 'Consumidor autorizado: consulta valida de referencia',
  request: {
    method: 'GET', header: auth(),
    url: BASE + '/activos-biologicos/' + ACTIVO + '/datos-consolidados?tipo_dato=' + TIPO_DATO,
  },
  event: [test([
    // Demuestra que el consumidor esta autenticado, autorizado y tiene acceso al activo:
    // asi, cualquier rechazo posterior no puede atribuirse a autenticacion ni a permisos.
    "pm.test('El consumidor esta autorizado para el endpoint y el activo (no 401 ni 403 ni 404)', () => pm.response.to.have.status(200));",
    "const b = pm.response.json();",
    "pm.test('El activo " + ACTIVO + " existe y responde con sus datos consolidados', () => pm.expect(b.id_activo_biologico).to.eql(" + ACTIVO + "));",
    "pm.collectionVariables.set('identificador_activo', b.identificador);",
    "pm.test('La consulta sin filtros temporales devuelve la seccion solicitada', () => pm.expect(b).to.have.property('metricas_actuales'));",
  ])],
});

// ---------- 01-CASO-PRINCIPAL ----------
const principal = { name: '01-CASO-PRINCIPAL', item: [] };

// --- TC-M02-156-A : fecha_inicio > fecha_fin ---
principal.item.push({
  name: 'TC-M02-156-A - fecha_inicio posterior a fecha_fin',
  request: {
    method: 'GET', header: auth(),
    url: BASE + '/activos-biologicos/' + ACTIVO + '/datos-consolidados?tipo_dato=' + TIPO_DATO +
         '&fecha_inicio=' + A_INICIO + '&fecha_fin=' + A_FIN,
  },
  event: [test([
    "const code = pm.response.code;",
    "const b = (() => { try { return pm.response.json(); } catch (e) { return {}; } })();",
    "const txt = norm(cuerpo());",
    "const url = pm.request.url.toString();",
    "pm.test('TC-M02-156-A: el consumidor esta autenticado y autorizado', () => {",
    "  pm.expect(String(pm.request.headers.get('Authorization'))).to.match(/^Bearer .+/);",
    "  pm.expect(code, 'un 401 o 403 probaria autenticacion o permisos, no la regla temporal').to.not.be.oneOf([401, 403]);",
    "});",
    "pm.test('TC-M02-156-A: el activo existe y el tipo_dato es valido', () => {",
    "  pm.expect(url).to.include('/activos-biologicos/" + ACTIVO + "/datos-consolidados');",
    "  pm.expect(url).to.include('tipo_dato=" + TIPO_DATO + "');",
    "  pm.expect(code, 'un 404 probaria activo inexistente').to.not.eql(404);",
    "});",
    "pm.test('TC-M02-156-A: la unica condicion invalida es el orden de las fechas', () => {",
    "  const ini = new Date('" + A_INICIO + "T00:00:00Z').getTime();",
    "  const fin = new Date('" + A_FIN + "T00:00:00Z').getTime();",
    "  pm.expect(ini, 'inicio debe ser posterior a fin').to.be.above(fin);",
    "  pm.expect(ini, 'ninguna de las dos fechas debe ser futura').to.be.at.most(Date.now());",
    "});",
    "pm.test('TC-M02-156-A: HTTP 400 segun la ficha', () => pm.expect(code).to.eql(400));",
    "pm.test('TC-M02-156-A: el mensaje corresponde a fecha_inicio posterior a fecha_fin', () => {",
    "  pm.expect(txt).to.include('fecha de inicio');",
    "  pm.expect(txt).to.match(/posterior|superior/);",
    "});",
    "pm.test('TC-M02-156-A: el rechazo no se debe a otra validacion', () => {",
    "  ['activo_no_encontrado', 'tipo de dato invalido', 'pagina', 'tamano de pagina'].forEach((otro) => {",
    "    pm.expect(txt, 'rechazo atribuido a ' + otro).to.not.include(norm(otro));",
    "  });",
    "});",
  ].concat(sinExposicion('TC-M02-156-A')).concat([
    "pm.collectionVariables.set('http_156a', code);",
    "pm.collectionVariables.set('body_156a', pm.response.text().slice(0, 600));",
  ]))],
});

// --- TC-M02-156-B : ambas fechas futuras, con inicio < fin ---
principal.item.push({
  name: 'TC-M02-156-B - fechas futuras con inicio anterior a fin',
  request: {
    method: 'GET', header: auth(),
    url: BASE + '/activos-biologicos/' + ACTIVO + '/datos-consolidados?tipo_dato=' + TIPO_DATO +
         '&fecha_inicio={{futuro_inicio}}&fecha_fin={{futuro_fin}}',
  },
  event: [test([
    "const code = pm.response.code;",
    "const b = (() => { try { return pm.response.json(); } catch (e) { return {}; } })();",
    "const txt = norm(cuerpo());",
    "const ini = pm.collectionVariables.get('futuro_inicio');",
    "const fin = pm.collectionVariables.get('futuro_fin');",
    "const hoy = pm.collectionVariables.get('fecha_hoy');",
    "pm.test('TC-M02-156-B: el consumidor esta autenticado y autorizado', () => {",
    "  pm.expect(String(pm.request.headers.get('Authorization'))).to.match(/^Bearer .+/);",
    "  pm.expect(code).to.not.be.oneOf([401, 403]);",
    "});",
    "pm.test('TC-M02-156-B: el activo existe y el tipo_dato es valido', () => {",
    "  pm.expect(pm.request.url.toString()).to.include('/activos-biologicos/" + ACTIVO + "/datos-consolidados');",
    "  pm.expect(code).to.not.eql(404);",
    "});",
    // Regla critica de aislamiento: inicio < fin, para no mezclarse con la variante A.
    "pm.test('TC-M02-156-B: fecha_inicio es anterior a fecha_fin, para aislar solo la condicion futura', () => {",
    "  pm.expect(new Date(ini + 'T00:00:00Z').getTime()).to.be.below(new Date(fin + 'T00:00:00Z').getTime());",
    "});",
    "pm.test('TC-M02-156-B: ambas fechas son realmente futuras respecto de la fecha actual (' + hoy + ')', () => {",
    "  const hoyMs = new Date(hoy + 'T00:00:00Z').getTime();",
    "  pm.expect(new Date(ini + 'T00:00:00Z').getTime(), 'inicio ' + ini).to.be.above(hoyMs);",
    "  pm.expect(new Date(fin + 'T00:00:00Z').getTime(), 'fin ' + fin).to.be.above(hoyMs);",
    "});",
    "pm.test('TC-M02-156-B: HTTP 400 segun la ficha', () => pm.expect(code).to.eql(400));",
    "pm.test('TC-M02-156-B: el motivo corresponde a una validacion temporal de fecha futura', () => {",
    "  pm.expect(txt).to.match(/futur|posterior a la fecha actual|fecha actual/);",
    "});",
  ].concat(sinExposicion('TC-M02-156-B')).concat([
    "pm.collectionVariables.set('http_156b', code);",
    "pm.collectionVariables.set('body_156b', pm.response.text().slice(0, 600));",
  ]))],
});

// ---------- 02-DIAGNOSTICO ----------
// TC-M02-155 y TC-M02-157 quedan bloqueados y NO se ejecutan como peticiones oficiales.
// Esta unica peticion es diagnostica: caracteriza el hueco de la regla NIC41 sin sustituir
// a M06 ni contar como el sub-caso oficial.
const diagnostico = { name: '02-DIAGNOSTICO', item: [] };

diagnostico.item.push({
  name: 'DIAGNOSTICO (no oficial) - rango valido sin metricas PESO, con consumidor autorizado',
  request: {
    method: 'GET', header: auth(),
    url: BASE + '/activos-biologicos/' + ACTIVO + '/datos-consolidados?tipo_dato=' + TIPO_DATO +
         '&fecha_inicio=' + NIC_INICIO + '&fecha_fin=' + NIC_FIN,
  },
  event: [test([
    "const code = pm.response.code;",
    "const b = (() => { try { return pm.response.json(); } catch (e) { return {}; } })();",
    // Este bloque NO afirma el resultado esperado de TC-M02-157: el sub-caso exige M06 con
    // scope NIC41, identidad que el sistema no ofrece. Solo documenta el comportamiento.
    "pm.test('DIAGNOSTICO: el rango " + NIC_INICIO + " a " + NIC_FIN + " es valido y no futuro', () => {",
    "  pm.expect(new Date('" + NIC_INICIO + "T00:00:00Z').getTime()).to.be.below(new Date('" + NIC_FIN + "T00:00:00Z').getTime());",
    "  pm.expect(new Date('" + NIC_FIN + "T00:00:00Z').getTime()).to.be.at.most(Date.now());",
    "});",
    "pm.test('DIAGNOSTICO: el comportamiento observado queda registrado (HTTP ' + code + ')', () => pm.expect(code).to.be.a('number'));",
    "pm.collectionVariables.set('http_diag_nic41', code);",
    "pm.collectionVariables.set('body_diag_nic41', pm.response.text().slice(0, 800));",
  ])],
});

const coleccion = {
  info: {
    name: 'TC-M02-G93 - RF-50 reglas negativas de datos consolidados',
    description:
      'RF-50 / TC-M02-G93. TC-M02-156-A (fecha_inicio > fecha_fin) y TC-M02-156-B (fechas futuras) se ejecutan ' +
      'como peticiones oficiales sobre GET /activos-biologicos/{id_activo}/datos-consolidados. TC-M02-155 queda ' +
      'BLOQUEADO porque el sistema no implementa identidad de modulo consumidor ni scopes por tipo_dato, y ' +
      'TC-M02-157 queda BLOQUEADO porque M06 no existe como consumidor autenticable. Caso enteramente de lectura.',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
  },
  item: [setup, principal, diagnostico],
  event: [{
    listen: 'prerequest',
    script: {
      type: 'text/javascript',
      exec: [
        '// Fechas futuras de TC-M02-156-B, calculadas contra la fecha actual observada al',
        '// ejecutar. No se modifico el reloj de ningun equipo.',
        "const hoy = new Date();",
        "const mas = (d) => new Date(hoy.getTime() + d * 86400000).toISOString().slice(0, 10);",
        "pm.collectionVariables.set('fecha_hoy', mas(0));",
        "pm.collectionVariables.set('futuro_inicio', mas(1));",
        "pm.collectionVariables.set('futuro_fin', mas(2));",
      ],
    },
  }],
  variable: [{ key: 'password', value: 'Test1234!' }],
};

const destino = path.join(__dirname, 'test_tc_m02_g93.json');
fs.writeFileSync(destino, JSON.stringify(coleccion, null, 2), 'utf8');

const oficiales = principal.item.length;
console.log('Coleccion escrita en ' + destino);
console.log('Peticiones oficiales ejecutables: ' + oficiales + ' de 4 (TC-M02-155 y TC-M02-157 bloqueados)');
