// Genera test_tc_m02_g94.json - TC-M02-G94 (RF-50): evidencia de metodos y autenticacion.
// 01-TC-M02-164: POST y PUT sobre la API de exposicion deben rechazarse (403/405).
// 02-TC-M02-165: GET sin credencial y con credencial invalida deben devolver 401.
// TC-M02-158 (rate limiting) no se cubre aqui: exige M04 y un modulo de control, que no existen.
const fs = require('fs');
const path = require('path');

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const ACTIVO = 279;
const TIPO_DATO = 'metricas';
const RUTA = '/activos-biologicos/' + ACTIVO + '/datos-consolidados';

// Credencial deliberadamente invalida: valor ficticio, no un secreto real alterado.
const TOKEN_INVALIDO = 'qa.credencial.invalida.tc-m02-165-b';

const PRELUDIO = [
  "const norm = (s) => String(s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();",
  "const cuerpo = () => { try { return JSON.stringify(pm.response.json()); } catch (e) { return pm.response.text(); } };",
  // Secciones de datos que ninguna respuesta de rechazo debe incluir.
  "const PROTEGIDOS = ['historial_eventos', 'historial_fases', 'historico_estados', 'metricas_actuales', 'infraestructura_asociada', 'fase_productiva_activa'];",
  "const sinExposicion = (etiqueta) => {",
  "  pm.test(etiqueta + ': la respuesta no expone datos del activo', () => {",
  "    const b = (() => { try { return pm.response.json(); } catch (e) { return {}; } })();",
  "    PROTEGIDOS.forEach((c) => pm.expect(b, 'expone ' + c).to.not.have.property(c));",
  "    pm.expect(pm.response.text()).to.not.include('QAJE-CREC-OK');",
  "  });",
  "};",
].join('\n');

const raw = (obj) => ({ mode: 'raw', raw: JSON.stringify(obj, null, 2), options: { raw: { language: 'json' } } });
const test = (lines) => ({ listen: 'test', script: { type: 'text/javascript', exec: (PRELUDIO + '\n' + lines.join('\n')).split('\n') } });

// ---------- 00-SETUP-LECTURA ----------
const setup = { name: '00-SETUP-LECTURA', item: [] };

setup.item.push({
  name: 'OpenAPI - metodos y codigos declarados',
  request: { method: 'GET', header: [], url: BASE + '/openapi.json' },
  event: [test([
    "pm.test('El ambiente TEST HTTPS responde 200', () => pm.response.to.have.status(200));",
    "const spec = pm.response.json();",
    "const ruta = '/activos-biologicos/{id_activo}/datos-consolidados';",
    "pm.test('El contrato declara la ruta de exposicion', () => pm.expect(spec.paths).to.have.property(ruta));",
    // V14: el contrato no expone escritura.
    "pm.test('V14: el contrato declara UNICAMENTE el metodo GET, ninguna escritura', () => {",
    "  pm.expect(Object.keys(spec.paths[ruta])).to.eql(['get']);",
    "});",
    "const resp = Object.keys(spec.paths[ruta].get.responses);",
    "pm.collectionVariables.set('respuestas_declaradas', resp.join(','));",
    "pm.test('El contrato declara 401, exigido por TC-M02-165', () => pm.expect(resp).to.include('401'));",
    // Discrepancias documentadas frente a RF-50.
    "pm.test('DISCREPANCIA DOCUMENTADA: el contrato no declara 429 pese a que RF-50 fija 100 req/min', () => {",
    "  pm.expect(resp, 'respuestas: ' + resp.join(',')).to.not.include('429');",
    "});",
    "pm.test('BLOQUEO TC-M02-158: el contrato no define esquemas de seguridad con identidad de modulo', () => {",
    "  pm.expect(spec.components.securitySchemes).to.eql(undefined);",
    "});",
  ])],
});

setup.item.push({
  name: 'Login del consumidor con acceso de lectura',
  request: {
    method: 'POST', header: [{ key: 'Content-Type', value: 'application/json' }],
    url: BASE + '/sesiones/',
    body: raw({ correo_electronico: 'm2m.nuevo@ejemplo.com', contrasena: '{{password}}' }),
  },
  event: [test([
    "pm.test('Login exitoso del consumidor', () => pm.response.to.have.status(200));",
    "const t = pm.response.json().token;",
    "pm.collectionVariables.set('token_consumidor', t);",
    "pm.test('La credencial es valida y corresponde al usuario 35', () => pm.expect(String(JSON.parse(atob(t.split('.')[1])).sub)).to.eql('35'));",
  ])],
});

setup.item.push({
  name: 'V9 - GET valido del mismo consumidor (acceso de lectura confirmado)',
  request: {
    method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_consumidor}}' }],
    url: BASE + RUTA + '?tipo_dato=' + TIPO_DATO,
  },
  event: [test([
    // Sin este 200, un 403/405 posterior podria confundirse con falta de acceso (A8).
    "pm.test('V9: el consumidor tiene acceso de lectura al recurso', () => pm.response.to.have.status(200));",
    "pm.test('El GET devuelve el activo " + ACTIVO + "', () => pm.expect(pm.response.json().id_activo_biologico).to.eql(" + ACTIVO + "));",
    "pm.collectionVariables.set('get_lectura_ok', 'SI');",
  ])],
});

// ---------- 01-TC-M02-164 ----------
const solo_lectura = { name: '01-TC-M02-164', item: [] };

for (const [metodo, etiqueta] of [['POST', 'TC-M02-164-A'], ['PUT', 'TC-M02-164-B']]) {
  solo_lectura.item.push({
    name: etiqueta + ' - ' + metodo + ' rechazado sobre la API de exposicion',
    request: {
      method: metodo,
      header: [
        { key: 'Authorization', value: 'Bearer {{token_consumidor}}' },
        { key: 'Content-Type', value: 'application/json' },
      ],
      url: BASE + RUTA,
      // Body simple y sintacticamente valido: se verifica que el metodo este prohibido,
      // no un contrato de escritura que no existe.
      body: raw({ qa_intento_escritura: true, caso: etiqueta }),
    },
    event: [test([
      "const code = pm.response.code;",
      "pm.test('" + etiqueta + ": el consumidor tiene acceso de lectura confirmado', () => pm.expect(pm.collectionVariables.get('get_lectura_ok')).to.eql('SI'));",
      "pm.test('" + etiqueta + ": la URL apunta a la API de exposicion', () => pm.expect(pm.request.url.toString()).to.include('" + RUTA + "'));",
      "pm.test('" + etiqueta + ": " + metodo + " es rechazado con 403 o 405', () => {",
      "  pm.expect([403, 405], 'HTTP ' + code).to.include(code);",
      "});",
      // Un 400/422 significaria que el metodo llego a validar el body: no probaria solo lectura.
      "pm.test('" + etiqueta + ": el rechazo es por metodo, no por validacion del body', () => {",
      "  pm.expect(code, 'un 400 o 422 indicaria que el metodo alcanzo la validacion de entrada').to.not.be.oneOf([400, 422]);",
      "  pm.expect(code, 'un 2xx significaria que la API acepta escrituras').to.not.be.within(200, 299);",
      "});",
      "if (code === 405) {",
      "  pm.test('" + etiqueta + ": la cabecera Allow confirma que solo se admite GET', () => {",
      "    pm.expect(String(pm.response.headers.get('Allow'))).to.include('GET');",
      "  });",
      "}",
      "sinExposicion('" + etiqueta + "');",
      "pm.collectionVariables.set('http_" + etiqueta.replace(/-/g, '_') + "', code);",
    ])],
  });
}

// ---------- 02-TC-M02-165 ----------
const autenticacion = { name: '02-TC-M02-165', item: [] };

autenticacion.item.push({
  name: 'TC-M02-165-A - GET sin credencial',
  request: {
    method: 'GET',
    // Sin ninguna cabecera de autenticacion. La coleccion no define auth heredable (A11).
    header: [],
    url: BASE + RUTA + '?tipo_dato=' + TIPO_DATO,
  },
  event: [test([
    "const code = pm.response.code;",
    "pm.test('TC-M02-165-A: la peticion no lleva cabecera Authorization', () => {",
    "  pm.expect(pm.request.headers.get('Authorization'), 'se filtro una credencial heredada').to.eql(undefined);",
    "});",
    "pm.test('TC-M02-165-A: el request es valido en todo lo demas', () => {",
    "  pm.expect(pm.request.url.toString()).to.include('" + RUTA + "');",
    "  pm.expect(pm.request.url.toString()).to.include('tipo_dato=" + TIPO_DATO + "');",
    "});",
    "pm.test('TC-M02-165-A: HTTP 401 segun la ficha', () => pm.expect(code).to.eql(401));",
    "pm.test('TC-M02-165-A: es un fallo de autenticacion, no de autorizacion', () => {",
    "  pm.expect(code, 'un 403 seria autorizacion y corresponde a G93').to.not.eql(403);",
    "  pm.expect(norm(cuerpo())).to.match(/token|autenticacion/);",
    "});",
    "sinExposicion('TC-M02-165-A');",
    "pm.collectionVariables.set('http_165a', code);",
  ])],
});

autenticacion.item.push({
  name: 'TC-M02-165-B - GET con credencial invalida',
  request: {
    method: 'GET',
    header: [{ key: 'Authorization', value: 'Bearer ' + TOKEN_INVALIDO }],
    url: BASE + RUTA + '?tipo_dato=' + TIPO_DATO,
  },
  event: [test([
    "const code = pm.response.code;",
    "pm.test('TC-M02-165-B: la peticion lleva una credencial inequivocamente invalida', () => {",
    "  pm.expect(String(pm.request.headers.get('Authorization'))).to.include('" + TOKEN_INVALIDO + "');",
    "});",
    "pm.test('TC-M02-165-B: HTTP 401 segun la ficha', () => pm.expect(code).to.eql(401));",
    "pm.test('TC-M02-165-B: es un fallo de autenticacion, no de autorizacion', () => {",
    "  pm.expect(code).to.not.eql(403);",
    "  pm.expect(norm(cuerpo())).to.match(/token|autenticacion/);",
    "});",
    "sinExposicion('TC-M02-165-B');",
    "pm.collectionVariables.set('http_165b', code);",
  ])],
});

const coleccion = {
  info: {
    name: 'TC-M02-G94 - RF-50 metodos de escritura y autenticacion servicio a servicio',
    description:
      'RF-50 / TC-M02-G94. TC-M02-164 (POST y PUT rechazados sobre la API de exposicion) y ' +
      'TC-M02-165 (GET sin credencial y con credencial invalida devuelven 401 sin exponer datos). ' +
      'TC-M02-158 se ejecuta con k6 y queda BLOQUEADO: exige M04 como consumidor autenticado y un ' +
      'segundo modulo de control, identidades que el sistema no implementa. La coleccion no define ' +
      'autenticacion heredable, para que la variante sin credencial sea realmente sin credencial.',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
  },
  // Sin bloque `auth`: ninguna peticion hereda credenciales.
  item: [setup, solo_lectura, autenticacion, { name: '03-DIAGNOSTICO', item: [] }],
  variable: [{ key: 'password', value: 'Test1234!' }],
};

const destino = path.join(__dirname, 'test_tc_m02_g94.json');
fs.writeFileSync(destino, JSON.stringify(coleccion, null, 2), 'utf8');
console.log('Coleccion escrita en ' + destino);
console.log('Peticiones negativas oficiales: 4 (TC-M02-164 A/B y TC-M02-165 A/B)');
