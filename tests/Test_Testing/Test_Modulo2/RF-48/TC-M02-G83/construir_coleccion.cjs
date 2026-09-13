// Genera test_tc_m02_g83.json - TC-M02-G83 (RF-48): existencia del activo, origen y destino.
// TC-M02-306   activo inexistente          -> ficha: 404 E-02
// TC-M02-307   activo ACTIVO sin origen    -> ficha: 422 E-04
// TC-M02-308-A destino inexistente         -> ficha: 422 E-05
// TC-M02-308-B destino existente INACTIVO  -> ficha: 422 E-05
// SETUP de solo lectura; las 8 peticiones oficiales deben ser rechazadas sin dejar cambios.
const fs = require('fs');
const path = require('path');

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

// --- Recursos verificados por SELECT en la Etapa 1 (todos en la finca 57) -------------
const ACTIVO_INEXISTENTE = 99999;   // 0 filas en modulo2.activos_biologicos
const ACTIVO_SIN_ORIGEN = 287;      // QAJE-TRF-SINORIG · ACTIVO · 0 asociaciones vigentes
const ACTIVO_BASE = 279;            // QAJE-CREC-OK · ACTIVO · asociacion vigente en 48
const ORIGEN = 48;                  // Corral QA JE Origen · activa · cap 1000
const DESTINO_VALIDO = 51;          // Corral QA JE Destino OK · activa · cap 200 · especie 40
const DESTINO_INEXISTENTE = 99999;  // 0 filas en modulo9.infraestructuras (max real: 61)
const DESTINO_INACTIVO = 50;        // Corral QA JE Inactivo · es_activo = false · cap 50 · ocupacion 0

const ACTORES = [
  { key: 'productor', nombre: 'Productor', correo: 'm2m.nuevo@ejemplo.com', usuario: 35 },
  { key: 'admin', nombre: 'Administrador', correo: 'admin@pecuaria.co', usuario: 1 },
];

const PRELUDIO = [
  "const norm = (s) => String(s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();",
  "const cuerpo = () => { try { return JSON.stringify(pm.response.json()); } catch (e) { return pm.response.text(); } };",
].join('\n');

const raw = (obj) => ({ mode: 'raw', raw: JSON.stringify(obj, null, 2), options: { raw: { language: 'json' } } });
const test = (lines) => ({ listen: 'test', script: { type: 'text/javascript', exec: (PRELUDIO + '\n' + lines.join('\n')).split('\n') } });
const auth = (k) => [{ key: 'Authorization', value: 'Bearer {{token_' + k + '}}' }];
const authJson = (k) => auth(k).concat([{ key: 'Content-Type', value: 'application/json' }]);

// Payload base: todo valido salvo la unica condicion que cada variante introduce.
const payload = (variante, actor, destino) => ({
  infraestructura_origen_id: ORIGEN,
  infraestructura_destino_id: destino,
  fecha_transferencia: '{{fecha_hoy}}',
  motivo_transferencia: variante + ' ' + actor + ': verificacion de RF-48',
});

// ---------- 00-SETUP-LECTURA ----------
const setup = { name: '00-SETUP-LECTURA', item: [] };

setup.item.push({
  name: 'Contrato vivo OpenAPI por HTTPS',
  request: { method: 'GET', header: [], url: BASE + '/openapi.json' },
  event: [test([
    "pm.test('El ambiente TEST HTTPS responde 200', () => pm.response.to.have.status(200));",
    "const spec = pm.response.json();",
    "const ruta = '/activos-biologicos/{id_activo}/transferencias';",
    "pm.test('El contrato declara POST ' + ruta, () => pm.expect(spec.paths).to.have.property(ruta));",
    "const resp = Object.keys(spec.paths[ruta].post.responses);",
    "pm.collectionVariables.set('respuestas_declaradas', resp.join(','));",
    "pm.test('El contrato declara 404, exigido por TC-M02-306', () => pm.expect(resp).to.include('404'));",
    "pm.test('El contrato declara 422, exigido por TC-M02-307 y TC-M02-308', () => pm.expect(resp).to.include('422'));",
    "const dto = spec.components.schemas.RegistrarTransferenciaDTO;",
    "pm.test('El campo de destino se llama infraestructura_destino_id', () => pm.expect(dto.properties).to.have.property('infraestructura_destino_id'));",
    "pm.test('fecha_transferencia se declara con formato date', () => pm.expect(dto.properties.fecha_transferencia.format).to.eql('date'));",
  ])],
});

for (const a of ACTORES) {
  setup.item.push({
    name: 'Login (lectura de sesion) - ' + a.nombre,
    request: {
      method: 'POST', header: [{ key: 'Content-Type', value: 'application/json' }],
      url: BASE + '/sesiones/',
      body: raw({ correo_electronico: a.correo, contrasena: '{{password}}' }),
    },
    event: [test([
      "pm.test('Login exitoso - " + a.nombre + "', () => pm.response.to.have.status(200));",
      "const t = pm.response.json().token;",
      "pm.collectionVariables.set('token_" + a.key + "', t);",
      "const sub = JSON.parse(atob(t.split('.')[1])).sub;",
      "pm.test('El token pertenece al usuario " + a.usuario + " (" + a.nombre + ")', () => pm.expect(String(sub)).to.eql('" + a.usuario + "'));",
    ])],
  });
}

// D1/D6: el activo 99999 y la infraestructura 99999 no existen.
setup.item.push({
  name: 'Precondicion TC-M02-306: el activo ' + ACTIVO_INEXISTENTE + ' no existe',
  request: { method: 'GET', header: auth('productor'), url: BASE + '/activos-biologicos/' + ACTIVO_INEXISTENTE },
  event: [test([
    "pm.test('El activo " + ACTIVO_INEXISTENTE + " no existe: la consulta devuelve 404', () => pm.response.to.have.status(404));",
    "pm.test('El 404 es de negocio (ACTIVO_NO_ENCONTRADO), no de ruta inexistente', () => pm.expect(pm.response.json().error_code).to.eql('ACTIVO_NO_ENCONTRADO'));",
    "pm.collectionVariables.set('activo_inexistente_confirmado', 'SI');",
  ])],
});

// D2: activo ACTIVO sin asociacion de origen vigente.
setup.item.push({
  name: 'Precondicion TC-M02-307: activo ' + ACTIVO_SIN_ORIGEN + ' ACTIVO y sin origen vigente',
  request: { method: 'GET', header: auth('productor'), url: BASE + '/activos-biologicos/' + ACTIVO_SIN_ORIGEN },
  event: [test([
    "pm.test('Acceso legitimo al activo " + ACTIVO_SIN_ORIGEN + "', () => pm.response.to.have.status(200));",
    "const b = pm.response.json();",
    "pm.test('El activo " + ACTIVO_SIN_ORIGEN + " existe y es QAJE-TRF-SINORIG', () => pm.expect(b.identificador).to.eql('QAJE-TRF-SINORIG'));",
    "pm.test('El activo " + ACTIVO_SIN_ORIGEN + " esta ACTIVO', () => pm.expect(b.nombre_estado).to.eql('ACTIVO'));",
    "pm.collectionVariables.set('estado_" + ACTIVO_SIN_ORIGEN + "', b.nombre_estado);",
  ])],
});

// Confirmacion por API de que el activo sin origen no tiene historial de ubicacion.
setup.item.push({
  name: 'Precondicion TC-M02-307: el activo ' + ACTIVO_SIN_ORIGEN + ' no registra ubicacion previa',
  request: { method: 'GET', header: auth('productor'), url: BASE + '/activos-biologicos/' + ACTIVO_SIN_ORIGEN + '/historial?page_size=100' },
  event: [test([
    "pm.test('Historial legible del activo " + ACTIVO_SIN_ORIGEN + "', () => pm.response.to.have.status(200));",
    "const infra = pm.response.json().registros.filter((r) => r.categoria === 'INFRAESTRUCTURA');",
    "pm.test('El activo " + ACTIVO_SIN_ORIGEN + " no tiene ningun registro de infraestructura', () => pm.expect(infra.length).to.eql(0));",
    "pm.collectionVariables.set('sin_origen_confirmado', 'SI');",
  ])],
});

// D3: escenario base con origen valido para TC-M02-308.
setup.item.push({
  name: 'Precondicion TC-M02-308: activo ' + ACTIVO_BASE + ' ACTIVO con origen ' + ORIGEN,
  request: { method: 'GET', header: auth('productor'), url: BASE + '/activos-biologicos/' + ACTIVO_BASE },
  event: [test([
    "pm.test('Acceso legitimo al activo " + ACTIVO_BASE + "', () => pm.response.to.have.status(200));",
    "const b = pm.response.json();",
    "pm.test('El activo " + ACTIVO_BASE + " esta ACTIVO', () => pm.expect(b.nombre_estado).to.eql('ACTIVO'));",
    "pm.test('El activo " + ACTIVO_BASE + " tiene como origen vigente la infraestructura " + ORIGEN + "', () => pm.expect(b.id_infraestructura).to.eql(" + ORIGEN + "));",
    "pm.collectionVariables.set('origen_" + ACTIVO_BASE + "', b.id_infraestructura);",
  ])],
});

// D4/D7/D8/D9: el destino INACTIVO existe y aisla E-05.
setup.item.push({
  name: 'Precondicion TC-M02-308-B: el destino ' + DESTINO_INACTIVO + ' existe pero esta INACTIVO',
  request: { method: 'GET', header: auth('productor'), url: BASE + '/activos-biologicos/' + ACTIVO_BASE + '/transferencias/disponibles' },
  event: [test([
    "pm.test('El endpoint de destinos disponibles responde 200', () => pm.response.to.have.status(200));",
    "const porId = Object.fromEntries(pm.response.json().map((i) => [i.id_infraestructura, i]));",
    // El listado solo ofrece infraestructuras activas: que 50 no aparezca confirma que no lo esta.
    "pm.test('El destino INACTIVO " + DESTINO_INACTIVO + " no figura entre los destinos disponibles', () => pm.expect(porId).to.not.have.property('" + DESTINO_INACTIVO + "'));",
    "pm.test('El destino inexistente " + DESTINO_INEXISTENTE + " tampoco figura', () => pm.expect(porId).to.not.have.property('" + DESTINO_INEXISTENTE + "'));",
    "pm.test('El destino valido " + DESTINO_VALIDO + " si figura, con Corral, especie 40 y capacidad 200', () => {",
    "  pm.expect(porId[" + DESTINO_VALIDO + "], 'destino " + DESTINO_VALIDO + " ausente').to.be.an('object');",
    "  pm.expect(porId[" + DESTINO_VALIDO + "].tipo).to.eql('Corral');",
    "  pm.expect(porId[" + DESTINO_VALIDO + "].id_especie).to.eql(40);",
    "  pm.expect(porId[" + DESTINO_VALIDO + "].capacidad_maxima).to.eql(200);",
    "});",
  ])],
});

// ---------- 01-CASO-PRINCIPAL ----------
const principal = { name: '01-CASO-PRINCIPAL', item: [] };

// Aserciones comunes a las ocho peticiones oficiales.
const comunes = (id, actor, destino) => [
  "const enviado = JSON.parse(pm.request.body.raw);",
  "const code = pm.response.code;",
  "const b = (() => { try { return pm.response.json(); } catch (e) { return {}; } })();",
  "const txt = norm(cuerpo());",
  "pm.test('" + id + " / " + actor + ": la peticion viaja autenticada', () => pm.expect(String(pm.request.headers.get('Authorization'))).to.match(/^Bearer .+/));",
  "pm.test('" + id + " / " + actor + ": el resto del payload es valido (origen real y activo, fecha no futura, motivo presente)', () => {",
  "  pm.expect(enviado.infraestructura_origen_id).to.eql(" + ORIGEN + ");",
  "  pm.expect(enviado.infraestructura_destino_id).to.eql(" + destino + ");",
  "  pm.expect(enviado.infraestructura_destino_id).to.not.eql(enviado.infraestructura_origen_id);",
  "  pm.expect(enviado.fecha_transferencia).to.match(/^\\d{4}-\\d{2}-\\d{2}$/);",
  "  pm.expect(new Date(enviado.fecha_transferencia + 'T00:00:00Z').getTime()).to.be.at.most(Date.now());",
  "  pm.expect(String(enviado.motivo_transferencia).trim()).to.not.eql('');",
  "});",
  "pm.test('" + id + " / " + actor + ": la peticion es rechazada, no se crea la transferencia', () => pm.expect(code).to.not.be.within(200, 299));",
  "pm.test('" + id + " / " + actor + ": el actor autorizado no recibe 403', () => pm.expect(code).to.not.eql(403));",
  "pm.test('" + id + " / " + actor + ": no se produce un error de servidor', () => pm.expect(code).to.be.below(500));",
];

// Descarta que el rechazo provenga de otra regla de RF-48.
const noOtraRegla = (id, actor, excluir) =>
  "pm.test('" + id + " / " + actor + ": el rechazo no se debe a otra regla de RF-48', () => {" +
  " [" + excluir.map((c) => "'" + c + "'").join(', ') + "].forEach((otro) => {" +
  " pm.expect(txt, 'rechazo atribuido a ' + otro).to.not.include(otro); }); });";

// Verificacion de ausencia de cambios sobre el activo utilizado.
const verificacion = (id, actorKey, actorNombre, activo, origenEsperado) => ({
  name: 'Verificacion sin cambios tras ' + id + ' - ' + actorNombre,
  request: { method: 'GET', header: auth(actorKey), url: BASE + '/activos-biologicos/' + activo },
  event: [test([
    "pm.test('Activo legible', () => pm.response.to.have.status(200));",
    "const b = pm.response.json();",
    "pm.test('" + id + " / " + actorNombre + ": el activo " + activo + " sigue ACTIVO', () => pm.expect(b.nombre_estado).to.eql('ACTIVO'));",
    "pm.test('" + id + " / " + actorNombre + ": la ubicacion del activo " + activo + " no cambio (" + origenEsperado + ")', () => pm.expect(b.id_infraestructura).to.eql(" + origenEsperado + "));",
  ])],
});

for (const a of ACTORES) {
  const carpeta = { name: a.nombre, item: [] };

  // ---- TC-M02-306 : E-02 activo inexistente ----
  carpeta.item.push({
    name: 'TC-M02-306 - activo ' + ACTIVO_INEXISTENTE + ' inexistente - ' + a.nombre,
    request: {
      method: 'POST', header: authJson(a.key),
      url: BASE + '/activos-biologicos/' + ACTIVO_INEXISTENTE + '/transferencias',
      body: raw(payload('TC-M02-306', a.nombre, DESTINO_VALIDO)),
    },
    event: [test(comunes('TC-M02-306', a.nombre, DESTINO_VALIDO).concat([
      "pm.test('TC-M02-306 / " + a.nombre + ": el activo " + ACTIVO_INEXISTENTE + " fue confirmado inexistente antes del POST', () => pm.expect(pm.collectionVariables.get('activo_inexistente_confirmado')).to.eql('SI'));",
      "pm.test('TC-M02-306 / " + a.nombre + ": la URL apunta realmente al activo " + ACTIVO_INEXISTENTE + "', () => pm.expect(pm.request.url.toString()).to.include('/activos-biologicos/" + ACTIVO_INEXISTENTE + "/transferencias'));",
      "pm.test('TC-M02-306 / " + a.nombre + ": HTTP 404 segun la ficha (E-02)', () => pm.expect(code).to.eql(404));",
      "pm.test('TC-M02-306 / " + a.nombre + ": el error corresponde a E-02 (ACTIVO_NO_ENCONTRADO)', () => pm.expect(b.error_code).to.eql('ACTIVO_NO_ENCONTRADO'));",
      "pm.test('TC-M02-306 / " + a.nombre + ": el mensaje corresponde a activo inexistente y nombra el ID', () => {",
      "  pm.expect(txt).to.match(/no fue encontrado|no existe/);",
      "  pm.expect(txt).to.include('" + ACTIVO_INEXISTENTE + "');",
      "});",
      "pm.test('TC-M02-306 / " + a.nombre + ": el 404 no proviene de una ruta inexistente', () => {",
      "  pm.expect(b, 'un 404 de enrutado responderia {detail: Not Found}').to.not.have.property('detail');",
      "  pm.expect(b).to.have.property('error_code');",
      "});",
      noOtraRegla('TC-M02-306', a.nombre, ['sin_infraestructura_origen', 'infraestructura_origen_incorrecta', 'infraestructura_destino_invalida', 'destino_igual_origen', 'incompatibilidad_especie', 'capacidad_excedida', 'activo_no_activo', 'transferencia_concurrente']),
      "pm.collectionVariables.set('http_" + a.key + "_306', code);",
      "pm.collectionVariables.set('body_" + a.key + "_306', pm.response.text().slice(0, 600));",
    ]))],
  });
  carpeta.item.push({
    name: 'Verificacion tras TC-M02-306: el activo ' + ACTIVO_INEXISTENTE + ' sigue sin existir - ' + a.nombre,
    request: { method: 'GET', header: auth(a.key), url: BASE + '/activos-biologicos/' + ACTIVO_INEXISTENTE },
    event: [test([
      "pm.test('TC-M02-306 / " + a.nombre + ": el POST rechazado no creo el activo " + ACTIVO_INEXISTENTE + "', () => pm.response.to.have.status(404));",
      "pm.test('TC-M02-306 / " + a.nombre + ": sigue reportandose como inexistente', () => pm.expect(pm.response.json().error_code).to.eql('ACTIVO_NO_ENCONTRADO'));",
    ])],
  });

  // ---- TC-M02-307 : E-04 activo ACTIVO sin infraestructura origen ----
  carpeta.item.push({
    name: 'TC-M02-307 - activo sin infraestructura origen - ' + a.nombre,
    request: {
      method: 'POST', header: authJson(a.key),
      url: BASE + '/activos-biologicos/' + ACTIVO_SIN_ORIGEN + '/transferencias',
      body: raw(payload('TC-M02-307', a.nombre, DESTINO_VALIDO)),
    },
    event: [test(comunes('TC-M02-307', a.nombre, DESTINO_VALIDO).concat([
      "pm.test('TC-M02-307 / " + a.nombre + ": el activo " + ACTIVO_SIN_ORIGEN + " existe y esta ACTIVO', () => pm.expect(pm.collectionVariables.get('estado_" + ACTIVO_SIN_ORIGEN + "')).to.eql('ACTIVO'));",
      "pm.test('TC-M02-307 / " + a.nombre + ": se confirmo que no tiene origen vigente antes del POST', () => pm.expect(pm.collectionVariables.get('sin_origen_confirmado')).to.eql('SI'));",
      "pm.test('TC-M02-307 / " + a.nombre + ": HTTP 422 segun la ficha (E-04)', () => pm.expect(code).to.eql(422));",
      "pm.test('TC-M02-307 / " + a.nombre + ": el error corresponde a E-04 (SIN_INFRAESTRUCTURA_ORIGEN)', () => pm.expect(b.error_code).to.eql('SIN_INFRAESTRUCTURA_ORIGEN'));",
      "pm.test('TC-M02-307 / " + a.nombre + ": el mensaje identifica la ausencia de infraestructura origen', () => {",
      "  pm.expect(txt).to.include('infraestructura origen');",
      "  pm.expect(txt).to.match(/no tiene|asocie/);",
      "});",
      noOtraRegla('TC-M02-307', a.nombre, ['activo_no_encontrado', 'infraestructura_origen_incorrecta', 'infraestructura_destino_invalida', 'destino_igual_origen', 'incompatibilidad_especie', 'capacidad_excedida', 'activo_no_activo', 'transferencia_concurrente']),
      "pm.collectionVariables.set('http_" + a.key + "_307', code);",
      "pm.collectionVariables.set('body_" + a.key + "_307', pm.response.text().slice(0, 600));",
    ]))],
  });
  carpeta.item.push(verificacion('TC-M02-307', a.key, a.nombre, ACTIVO_SIN_ORIGEN, ORIGEN));

  // ---- TC-M02-308-A : E-05 destino inexistente ----
  carpeta.item.push({
    name: 'TC-M02-308-A - destino ' + DESTINO_INEXISTENTE + ' inexistente - ' + a.nombre,
    request: {
      method: 'POST', header: authJson(a.key),
      url: BASE + '/activos-biologicos/' + ACTIVO_BASE + '/transferencias',
      body: raw(payload('TC-M02-308-A', a.nombre, DESTINO_INEXISTENTE)),
    },
    event: [test(comunes('TC-M02-308-A', a.nombre, DESTINO_INEXISTENTE).concat([
      "pm.test('TC-M02-308-A / " + a.nombre + ": el activo base " + ACTIVO_BASE + " esta ACTIVO y su origen vigente es " + ORIGEN + "', () => pm.expect(Number(pm.collectionVariables.get('origen_" + ACTIVO_BASE + "'))).to.eql(" + ORIGEN + "));",
      "pm.test('TC-M02-308-A / " + a.nombre + ": HTTP 422 segun la ficha (E-05)', () => pm.expect(code).to.eql(422));",
      "pm.test('TC-M02-308-A / " + a.nombre + ": el error corresponde a E-05 (INFRAESTRUCTURA_DESTINO_INVALIDA)', () => pm.expect(b.error_code).to.eql('INFRAESTRUCTURA_DESTINO_INVALIDA'));",
      "pm.test('TC-M02-308-A / " + a.nombre + ": el mensaje corresponde a destino inexistente o inactivo', () => {",
      "  pm.expect(txt).to.match(/no existe|no esta activa/);",
      "  pm.expect(txt).to.include('" + DESTINO_INEXISTENTE + "');",
      "});",
      noOtraRegla('TC-M02-308-A', a.nombre, ['activo_no_encontrado', 'sin_infraestructura_origen', 'infraestructura_origen_incorrecta', 'destino_igual_origen', 'incompatibilidad_especie', 'capacidad_excedida', 'activo_no_activo', 'transferencia_concurrente']),
      "pm.collectionVariables.set('http_" + a.key + "_308a', code);",
      "pm.collectionVariables.set('body_" + a.key + "_308a', pm.response.text().slice(0, 600));",
    ]))],
  });
  carpeta.item.push(verificacion('TC-M02-308-A', a.key, a.nombre, ACTIVO_BASE, ORIGEN));

  // ---- TC-M02-308-B : E-05 destino existente pero INACTIVO ----
  carpeta.item.push({
    name: 'TC-M02-308-B - destino ' + DESTINO_INACTIVO + ' INACTIVO - ' + a.nombre,
    request: {
      method: 'POST', header: authJson(a.key),
      url: BASE + '/activos-biologicos/' + ACTIVO_BASE + '/transferencias',
      body: raw(payload('TC-M02-308-B', a.nombre, DESTINO_INACTIVO)),
    },
    event: [test(comunes('TC-M02-308-B', a.nombre, DESTINO_INACTIVO).concat([
      "pm.test('TC-M02-308-B / " + a.nombre + ": el activo base " + ACTIVO_BASE + " esta ACTIVO y su origen vigente es " + ORIGEN + "', () => pm.expect(Number(pm.collectionVariables.get('origen_" + ACTIVO_BASE + "'))).to.eql(" + ORIGEN + "));",
      "pm.test('TC-M02-308-B / " + a.nombre + ": el destino " + DESTINO_INACTIVO + " es distinto del origen', () => pm.expect(enviado.infraestructura_destino_id).to.not.eql(" + ORIGEN + "));",
      "pm.test('TC-M02-308-B / " + a.nombre + ": HTTP 422 segun la ficha (E-05)', () => pm.expect(code).to.eql(422));",
      "pm.test('TC-M02-308-B / " + a.nombre + ": el error corresponde a E-05 (INFRAESTRUCTURA_DESTINO_INVALIDA)', () => pm.expect(b.error_code).to.eql('INFRAESTRUCTURA_DESTINO_INVALIDA'));",
      "pm.test('TC-M02-308-B / " + a.nombre + ": el mensaje corresponde a destino no activo', () => {",
      "  pm.expect(txt).to.match(/no existe|no esta activa/);",
      "  pm.expect(txt).to.include('" + DESTINO_INACTIVO + "');",
      "});",
      noOtraRegla('TC-M02-308-B', a.nombre, ['activo_no_encontrado', 'sin_infraestructura_origen', 'infraestructura_origen_incorrecta', 'destino_igual_origen', 'incompatibilidad_especie', 'capacidad_excedida', 'activo_no_activo', 'transferencia_concurrente']),
      "pm.collectionVariables.set('http_" + a.key + "_308b', code);",
      "pm.collectionVariables.set('body_" + a.key + "_308b', pm.response.text().slice(0, 600));",
    ]))],
  });
  carpeta.item.push(verificacion('TC-M02-308-B', a.key, a.nombre, ACTIVO_BASE, ORIGEN));

  principal.item.push(carpeta);
}

const coleccion = {
  info: {
    name: 'TC-M02-G83 - RF-48 existencia de activo, origen y destino',
    description:
      'RF-48 / TC-M02-G83. Cuatro variantes sobre POST /activos-biologicos/{id_activo}/transferencias: ' +
      'TC-M02-306 (E-02 activo inexistente), TC-M02-307 (E-04 activo ACTIVO sin infraestructura origen), ' +
      'TC-M02-308-A (E-05 destino inexistente) y TC-M02-308-B (E-05 destino existente pero INACTIVO), ' +
      'ejecutadas con Productor y Administrador: 8 peticiones oficiales. Cada peticion aisla una unica causa ' +
      'de rechazo sobre un payload base valido. El SETUP es de solo lectura.',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
  },
  item: [setup, principal, { name: '02-DIAGNOSTICO', item: [] }],
  event: [{
    listen: 'prerequest',
    script: {
      type: 'text/javascript',
      exec: [
        '// Fecha de hoy: el DTO rechaza cualquier fecha posterior a la actual (E-10), que queda',
        '// fuera del alcance de este caso.',
        "pm.collectionVariables.set('fecha_hoy', new Date().toISOString().slice(0, 10));",
      ],
    },
  }],
  variable: [{ key: 'password', value: 'Test1234!' }],
};

const destino = path.join(__dirname, 'test_tc_m02_g83.json');
fs.writeFileSync(destino, JSON.stringify(coleccion, null, 2), 'utf8');

const posts = principal.item.reduce((acc, f) => acc + f.item.filter((i) => i.request.method === 'POST').length, 0);
console.log('Coleccion escrita en ' + destino);
console.log('POST oficiales del caso principal: ' + posts);
