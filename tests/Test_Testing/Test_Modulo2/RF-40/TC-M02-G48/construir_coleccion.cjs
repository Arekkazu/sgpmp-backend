// Genera test_tc_m02_g48.json - TC-M02-G48 (RF-40): existencia y estado del activo.
// TC-M02-304: POST sobre el activo 99999, confirmado inexistente -> HTTP 404.
// TC-M02-305: POST sobre un activo existente en estado CERRADO   -> HTTP 409.
// SETUP de solo lectura; las 6 peticiones oficiales son negativas y no deben crear eventos.
const fs = require('fs');
const path = require('path');

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

// ID oficial de la ficha para el escenario de activo inexistente. No se sustituye.
const ID_INEXISTENTE = 99999;

const ACTORES = [
  {
    key: 'productor', nombre: 'Productor',
    correo: 'm2m.nuevo@ejemplo.com', pwdVar: 'password', usuario: 35,
    cerrado: 288, identificador: 'QAJE-CREC-CERRADO', finca: 57,
  },
  {
    key: 'veterinario', nombre: 'Veterinario',
    correo: 'juan.carlos.qa133@sgpmp-test.com', pwdVar: 'password', usuario: 3,
    cerrado: 329, identificador: 'QAJE-RF40-CERRADO-VET', finca: 64,
  },
  {
    key: 'ingeniero', nombre: 'Ingeniero de campo',
    correo: 'ingeniero@pecuaria.co', pwdVar: 'engineer_password', usuario: 4,
    cerrado: 336, identificador: 'QAJE-RF40-CERRADO-ING', finca: 65,
  },
];

const PRELUDIO = [
  "const norm = (s) => String(s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();",
  "const cuerpo = () => { try { return JSON.stringify(pm.response.json()); } catch (e) { return pm.response.text(); } };",
].join('\n');

// Payload base valido, identico en los dos sub-casos. Los seis activos de referencia son
// INDIVIDUAL de la especie 40, que tiene PESO/kg configurado en modulo9.metricas_produccion
// con rango 0.1 - 2000, por lo que 250 kg es una medicion valida. `tipo_agregacion` se omite
// deliberadamente: no aplica a activos INDIVIDUAL (ver TC-M02-G45).
const payloadBase = (a, subcaso) => ({
  tipo_medicion: 'PESO',
  valor_medicion: 250,
  unidad_medida: 'kg',
  fecha: '{{fecha_evento}}',
  descripcion: subcaso + ' ' + a.nombre + ': payload valido, unica condicion invalida en el activo',
});

const raw = (obj) => ({ mode: 'raw', raw: JSON.stringify(obj, null, 2), options: { raw: { language: 'json' } } });
const test = (lines) => ({ listen: 'test', script: { type: 'text/javascript', exec: (PRELUDIO + '\n' + lines.join('\n')).split('\n') } });

// ---------- 00-SETUP-LECTURA ----------
const setup = { name: '00-SETUP-LECTURA', item: [] };

setup.item.push({
  name: 'Contrato vivo OpenAPI por HTTPS',
  request: { method: 'GET', header: [], url: BASE + '/openapi.json' },
  event: [test([
    "pm.test('El ambiente TEST HTTPS responde 200', () => pm.response.to.have.status(200));",
    "const spec = pm.response.json();",
    "const ruta = '/activos-biologicos/{id_activo}/eventos/crecimiento';",
    // Necesario para la regla critica de la seccion 4.1: la ruta existe, luego un 404
    // no puede atribuirse a un endpoint mal escrito.
    "pm.test('La ruta POST ' + ruta + ' existe en el contrato', () => {",
    "  pm.expect(spec.paths).to.have.property(ruta);",
    "  pm.expect(spec.paths[ruta]).to.have.property('post');",
    "});",
    "const resp = Object.keys(spec.paths[ruta].post.responses);",
    "pm.collectionVariables.set('respuestas_declaradas', resp.join(','));",
    "pm.test('El contrato declara 404 para este endpoint', () => pm.expect(resp).to.include('404'));",
    // Discrepancia documentada: la ficha exige 409 y el contrato no lo declara.
    "pm.test('DISCREPANCIA DOCUMENTADA: el contrato no declara 409 pese a que la ficha lo exige', () => {",
    "  pm.expect(resp, 'respuestas declaradas: ' + resp.join(',')).to.not.include('409');",
    "});",
  ])],
});

for (const a of ACTORES) {
  setup.item.push({
    name: 'Login (lectura de sesion) - ' + a.nombre,
    request: {
      method: 'POST', header: [{ key: 'Content-Type', value: 'application/json' }],
      url: BASE + '/sesiones/',
      body: raw({ correo_electronico: a.correo, contrasena: '{{' + a.pwdVar + '}}' }),
    },
    event: [test([
      "pm.test('Login exitoso - " + a.nombre + "', () => pm.response.to.have.status(200));",
      "const t = pm.response.json().token;",
      "pm.collectionVariables.set('token_" + a.key + "', t);",
      "const sub = JSON.parse(atob(t.split('.')[1])).sub;",
      "pm.test('El token pertenece al usuario " + a.usuario + " (" + a.nombre + ")', () => pm.expect(String(sub)).to.eql('" + a.usuario + "'));",
    ])],
  });

  // Precondicion de TC-M02-304, comprobada por cada actor inmediatamente antes de ejecutar.
  setup.item.push({
    name: 'Precondicion TC-M02-304: el activo ' + ID_INEXISTENTE + ' no existe - ' + a.nombre,
    request: {
      method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
      url: BASE + '/activos-biologicos/' + ID_INEXISTENTE,
    },
    event: [test([
      "pm.test('El activo " + ID_INEXISTENTE + " no existe: la consulta devuelve 404 (" + a.nombre + ")', () => pm.response.to.have.status(404));",
      "pm.test('El 404 es de negocio (ACTIVO_NO_ENCONTRADO), no de ruta inexistente', () => {",
      "  const b = pm.response.json();",
      "  pm.expect(b.error_code).to.eql('ACTIVO_NO_ENCONTRADO');",
      "});",
      "pm.collectionVariables.set('inexistente_" + a.key + "', 'CONFIRMADO');",
    ])],
  });

  // Precondiciones de TC-M02-305.
  setup.item.push({
    name: 'Precondicion TC-M02-305: activo ' + a.cerrado + ' existente y CERRADO - ' + a.nombre,
    request: {
      method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
      url: BASE + '/activos-biologicos/' + a.cerrado,
    },
    event: [test([
      "pm.test('Acceso legitimo al activo " + a.cerrado + " - " + a.nombre + " (no 403 ni 404)', () => pm.response.to.have.status(200));",
      "const b = pm.response.json();",
      "pm.test('El activo " + a.cerrado + " existe y su identificador es " + a.identificador + "', () => pm.expect(b.identificador).to.eql('" + a.identificador + "'));",
      "pm.test('El estado real del activo " + a.cerrado + " es CERRADO', () => pm.expect(b.nombre_estado).to.eql('CERRADO'));",
      "pm.test('El activo " + a.cerrado + " es INDIVIDUAL, por lo que no aplica tipo_agregacion', () => pm.expect(b.tipo).to.eql('INDIVIDUAL'));",
      "pm.collectionVariables.set('estado_" + a.key + "', b.nombre_estado);",
    ])],
  });

  setup.item.push({
    name: 'Conteo ANTES del activo ' + a.cerrado + ' - ' + a.nombre,
    request: {
      method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
      url: BASE + '/activos-biologicos/' + a.cerrado + '/historial?page_size=100',
    },
    event: [test([
      "pm.test('Historial legible del activo " + a.cerrado + "', () => pm.response.to.have.status(200));",
      "const n = pm.response.json().registros.filter((r) => r.categoria === 'CRECIMIENTO').length;",
      "pm.collectionVariables.set('base_" + a.key + "', n);",
      "pm.test('Conteo ANTES del activo " + a.cerrado + " (" + a.nombre + "): ' + n, () => pm.expect(n).to.be.a('number'));",
    ])],
  });
}

// ---------- 01-CASO-PRINCIPAL ----------
const principal = { name: '01-CASO-PRINCIPAL', item: [] };

for (const a of ACTORES) {
  const carpeta = { name: a.nombre, item: [] };

  // --- TC-M02-304: activo inexistente ---
  carpeta.item.push({
    name: 'TC-M02-304 - activo ' + ID_INEXISTENTE + ' inexistente - ' + a.nombre,
    request: {
      method: 'POST',
      header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }, { key: 'Content-Type', value: 'application/json' }],
      url: BASE + '/activos-biologicos/' + ID_INEXISTENTE + '/eventos/crecimiento',
      body: raw(payloadBase(a, 'TC-M02-304')),
    },
    event: [test([
      "const enviado = JSON.parse(pm.request.body.raw);",
      "const code = pm.response.code;",
      "const b = (() => { try { return pm.response.json(); } catch (e) { return {}; } })();",
      "const txt = norm(cuerpo());",
      // 1 - la precondicion se confirmo antes de ejecutar
      "pm.test('TC-M02-304 / " + a.nombre + ": el activo " + ID_INEXISTENTE + " fue confirmado inexistente antes del POST', () => pm.expect(pm.collectionVariables.get('inexistente_" + a.key + "')).to.eql('CONFIRMADO'));",
      // 2 - el actor esta autenticado
      "pm.test('TC-M02-304 / " + a.nombre + ": la peticion viaja autenticada', () => pm.expect(String(pm.request.headers.get('Authorization'))).to.match(/^Bearer .+/));",
      // 3 - el payload es valido: el ID es la unica condicion invalida
      "pm.test('TC-M02-304 / " + a.nombre + ": el payload es valido, el ID es la unica condicion invalida', () => {",
      "  pm.expect(enviado.tipo_medicion).to.eql('PESO');",
      "  pm.expect(enviado.valor_medicion).to.be.above(0);",
      "  pm.expect(enviado.unidad_medida).to.eql('kg');",
      "  pm.expect(enviado.fecha).to.match(/^\\d{4}-\\d{2}-\\d{2}T/);",
      "  pm.expect(enviado).to.not.have.property('tipo_agregacion');",
      "});",
      "pm.test('TC-M02-304 / " + a.nombre + ": la URL apunta realmente al ID " + ID_INEXISTENTE + "', () => pm.expect(pm.request.url.toString()).to.include('/activos-biologicos/" + ID_INEXISTENTE + "/eventos/crecimiento'));",
      // 4 - HTTP 404 segun la ficha
      "pm.test('TC-M02-304 / " + a.nombre + ": HTTP 404 segun la ficha', () => pm.expect(code).to.eql(404));",
      // 5 y 6 - el 404 corresponde a activo inexistente, no a ruta incorrecta
      "pm.test('TC-M02-304 / " + a.nombre + ": el mensaje corresponde a activo inexistente', () => {",
      "  pm.expect(b.error_code).to.eql('ACTIVO_NO_ENCONTRADO');",
      "  pm.expect(txt).to.include('no existe');",
      "  pm.expect(txt).to.include('" + ID_INEXISTENTE + "');",
      "});",
      "pm.test('TC-M02-304 / " + a.nombre + ": el 404 no proviene de una ruta inexistente', () => {",
      "  pm.expect(b, 'un 404 de enrutado responderia {\"detail\":\"Not Found\"}').to.not.have.property('detail');",
      "  pm.expect(b).to.have.property('error_code');",
      "});",
      "pm.collectionVariables.set('http_" + a.key + "_304', code);",
      "pm.collectionVariables.set('body_" + a.key + "_304', pm.response.text().slice(0, 600));",
    ])],
  });

  // 7 y 8 - no se persiste evento ni se crea el activo
  carpeta.item.push({
    name: 'Verificacion tras TC-M02-304: el activo ' + ID_INEXISTENTE + ' sigue sin existir - ' + a.nombre,
    request: {
      method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
      url: BASE + '/activos-biologicos/' + ID_INEXISTENTE,
    },
    event: [test([
      "pm.test('TC-M02-304 / " + a.nombre + ": el POST rechazado no creo el activo " + ID_INEXISTENTE + "', () => pm.response.to.have.status(404));",
      "pm.test('TC-M02-304 / " + a.nombre + ": el activo sigue reportandose como inexistente', () => pm.expect(pm.response.json().error_code).to.eql('ACTIVO_NO_ENCONTRADO'));",
    ])],
  });

  // --- TC-M02-305: activo no ACTIVO ---
  carpeta.item.push({
    name: 'TC-M02-305 - activo ' + a.cerrado + ' CERRADO - ' + a.nombre,
    request: {
      method: 'POST',
      header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }, { key: 'Content-Type', value: 'application/json' }],
      url: BASE + '/activos-biologicos/' + a.cerrado + '/eventos/crecimiento',
      body: raw(payloadBase(a, 'TC-M02-305')),
    },
    event: [test([
      "const enviado = JSON.parse(pm.request.body.raw);",
      "const code = pm.response.code;",
      "const b = (() => { try { return pm.response.json(); } catch (e) { return {}; } })();",
      "const txt = norm(cuerpo());",
      // 1 y 2 - el activo existe y su estado real es CERRADO
      "pm.test('TC-M02-305 / " + a.nombre + ": el activo " + a.cerrado + " existe y su estado real es CERRADO', () => pm.expect(pm.collectionVariables.get('estado_" + a.key + "')).to.eql('CERRADO'));",
      // 3 - acceso legitimo: el SETUP obtuvo 200, no 403 ni 404
      "pm.test('TC-M02-305 / " + a.nombre + ": el actor tiene acceso legitimo al activo " + a.cerrado + "', () => pm.expect(code, 'un 403 impediria evaluar la regla de estado').to.not.eql(403));",
      // 4 - los demas datos del request son validos
      "pm.test('TC-M02-305 / " + a.nombre + ": el payload es valido, el estado es la unica condicion invalida', () => {",
      "  pm.expect(enviado.tipo_medicion).to.eql('PESO');",
      "  pm.expect(enviado.valor_medicion).to.be.above(0);",
      "  pm.expect(enviado.unidad_medida).to.eql('kg');",
      "  pm.expect(enviado.fecha).to.match(/^\\d{4}-\\d{2}-\\d{2}T/);",
      "  pm.expect(enviado).to.not.have.property('tipo_agregacion');",
      "});",
      // 5 - HTTP 409 segun la ficha
      "pm.test('TC-M02-305 / " + a.nombre + ": HTTP 409 segun la ficha', () => pm.expect(code).to.eql(409));",
      // 6 - el mensaje corresponde a la regla de estado
      "pm.test('TC-M02-305 / " + a.nombre + ": el mensaje corresponde a activo no ACTIVO', () => {",
      "  pm.expect(b.error_code).to.eql('ESTADO_NO_PERMITE_EVENTOS');",
      "  pm.expect(txt).to.include('no se encuentra en estado activo');",
      "});",
      "pm.test('TC-M02-305 / " + a.nombre + ": la respuesta identifica el estado real CERRADO', () => pm.expect(txt).to.include('cerrado'));",
      // El rechazo no puede deberse a otra regla de RF-40 (seccion 17.4).
      "pm.test('TC-M02-305 / " + a.nombre + ": el rechazo no se debe a otra regla de RF-40', () => {",
      "  ['sin_fase_activa', 'fecha_futura', 'fecha_anterior', 'tipo_medicion_no_configurado', 'valor_fuera_de_rango', 'agregacion_no_permitida', 'tipo_agregacion_requerido', 'activo_no_encontrado'].forEach((otro) => {",
      "    pm.expect(txt, 'rechazo atribuido a ' + otro).to.not.include(otro);",
      "  });",
      "});",
      "pm.collectionVariables.set('http_" + a.key + "_305', code);",
      "pm.collectionVariables.set('body_" + a.key + "_305', pm.response.text().slice(0, 600));",
    ])],
  });

  // 7 y 8 - no se crea evento; DESPUES = ANTES
  carpeta.item.push({
    name: 'Verificacion de no persistencia tras TC-M02-305 - ' + a.nombre,
    request: {
      method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
      url: BASE + '/activos-biologicos/' + a.cerrado + '/historial?page_size=100',
    },
    event: [test([
      "pm.test('Historial legible', () => pm.response.to.have.status(200));",
      "const n = pm.response.json().registros.filter((r) => r.categoria === 'CRECIMIENTO').length;",
      "const base = Number(pm.collectionVariables.get('base_" + a.key + "'));",
      "pm.test('TC-M02-305 / " + a.nombre + ": el rechazo no persistio ningun evento (' + base + ' -> ' + n + ', delta 0)', () => pm.expect(n).to.eql(base));",
      "pm.collectionVariables.set('post_" + a.key + "_305', n);",
    ])],
  });

  principal.item.push(carpeta);
}

const coleccion = {
  info: {
    name: 'TC-M02-G48 - RF-40 existencia y estado del activo',
    description:
      'RF-40 / TC-M02-G48. Sub-casos TC-M02-304 (activo inexistente, ID oficial 99999) y TC-M02-305 ' +
      '(activo existente en estado CERRADO) sobre POST /activos-biologicos/{id_activo}/eventos/crecimiento, ' +
      'ejecutados con Productor, Veterinario e Ingeniero de campo. El payload es identico y valido en los seis ' +
      'casos: la unica condicion invalida es el activo destino. El SETUP es de solo lectura.',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
  },
  item: [setup, principal, { name: '02-DIAGNOSTICO', item: [] }],
  event: [{
    listen: 'prerequest',
    script: {
      type: 'text/javascript',
      exec: [
        '// Fecha valida: no futura (el backend la rechaza con FECHA_FUTURA) y posterior a',
        '// cualquier evento previo de los activos utilizados, que no tienen eventos de crecimiento.',
        "pm.collectionVariables.set('fecha_evento', new Date(Date.now() - 120000).toISOString().replace(/\\.\\d{3}Z$/, 'Z'));",
      ],
    },
  }],
  variable: [
    { key: 'password', value: 'Test1234!' },
    { key: 'engineer_password', value: 'Pruebas12#' },
  ],
};

const destino = path.join(__dirname, 'test_tc_m02_g48.json');
fs.writeFileSync(destino, JSON.stringify(coleccion, null, 2), 'utf8');

const posts = principal.item.reduce((acc, f) => acc + f.item.filter((i) => i.request.method === 'POST').length, 0);
console.log('Coleccion escrita en ' + destino);
console.log('POST oficiales del caso principal: ' + posts);
