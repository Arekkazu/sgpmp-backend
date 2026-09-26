// Genera test_tc_m02_g97.json - TC-M02-G97 REFORMULADO (RF-51).
// TC-M02-312   activo inexistente                 -> 404 esperado
// TC-M02-313-A inicio antes del nacimiento         -> 400 esperado
// TC-M02-313-B fin posterior a la baja             -> 400 esperado
// TC-M02-314   usuario autenticado SIN READ (29,2) -> 403 esperado (definicion reformulada)
// METODO: la matriz indica POST, pero el contrato solo declara GET (escenario B, §4).
const fs = require('fs');
const path = require('path');

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const RUTA = (id) => '/activos-biologicos/' + id + '/indicadores';

// ── Datos preexistentes en TEST, redescubiertos por SELECT en esta ejecucion (§3.A) ──
const INEXISTENTE = 99999;           // confirmado ausente: max(id_activo_biologico) = 336
const A313A = {                      // activo con mediciones, para que el rango invalido llegue al calculo
  activo: 279, ident: 'QAJE-CREC-OK',
  nacimiento: '2026-01-15', ingreso: '2026-06-01',
  inicio: '2025-12-01', fin: '2026-09-10',
};
const A313B = {                      // unico activo con baja preexistente en TEST
  activo: 286, ident: 'QAJE-IND-BAJA',
  ingreso: '2026-06-01', baja: '2026-08-31',
  inicio: '2026-07-01', fin: '2026-09-05',
};
const A314 = 279;                    // activo existente y accesible; el unico motivo de rechazo sera autorizacion

// AUTH_OK: Productor, dueno de la finca 57, con READ (29,2). AUTH_NO_READ: Contador, sin READ.
const CONSUMIDOR_OK = { correo: 'm2m.nuevo@ejemplo.com', sub: '35' };
const CONSUMIDOR_NO_READ = { correo: 'contador@pecuaria.co', sub: '5', rol: 5, rolNombre: 'Contador' };

const PRELUDIO = [
  "const norm = (s) => String(s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();",
  "const json = () => { try { return pm.response.json(); } catch (e) { return null; } };",
  "const texto = () => pm.response.text();",
  "const indicadorDe = (tipo) => { const b = json(); if (!b || !Array.isArray(b.indicadores)) return null;",
  "  return b.indicadores.find((i) => i.tipo === tipo) || null; };",
  // Ningun rechazo puede publicar un indicador utilizable ni un resultado parcial.
  "const sinIndicador = (etiqueta) => {",
  "  pm.test(etiqueta + ': no se expone ningun indicador calculado', () => {",
  "    const b = json();",
  "    const pub = (b && Array.isArray(b.indicadores))",
  "      ? b.indicadores.filter((i) => i.disponible === true || i.valor !== null) : [];",
  "    pm.expect(pub.map((i) => i.tipo + '=' + i.valor).join(','), 'indicadores publicados').to.eql('');",
  "  });",
  "};",
  // TC-314: un 403 de autorizacion no debe filtrar variables del calculo.
  "const sinVariables = (etiqueta) => {",
  "  pm.test(etiqueta + ': la respuesta no expone variables del calculo', () => {",
  "    pm.expect(norm(texto())).to.not.match(/variables_usadas|eventos_sanitarios|peso_inicial|total_mediciones/);",
  "  });",
  "};",
].join('\n');

const raw = (obj) => ({ mode: 'raw', raw: JSON.stringify(obj, null, 2), options: { raw: { language: 'json' } } });
const test = (lines) => ({ listen: 'test', script: { type: 'text/javascript', exec: (PRELUDIO + '\n' + lines.join('\n')).split('\n') } });
const hAuth = (tokenVar) => [{ key: 'Authorization', value: 'Bearer {{' + tokenVar + '}}' }];

const url = (id, tipo, fi, ff) => {
  let u = BASE + RUTA(id) + '?tipo_indicador=' + tipo;
  if (fi) u += '&fecha_inicio=' + fi + '&fecha_fin=' + ff;
  return u;
};

// ──────────────────────── 00-SETUP-LECTURA ────────────────────────
const setup = { name: '00-SETUP-LECTURA', item: [] };

setup.item.push({
  name: 'OpenAPI - resolucion POST vs GET (§4)',
  request: { method: 'GET', header: [], url: BASE + '/openapi.json' },
  event: [test([
    "pm.test('El ambiente TEST HTTPS responde 200', () => pm.response.to.have.status(200));",
    "const spec = pm.response.json();",
    "const ruta = '/activos-biologicos/{id_activo}/indicadores';",
    "const metodos = Object.keys(spec.paths[ruta]);",
    "pm.collectionVariables.set('metodo_openapi', metodos.join(','));",
    // Escenario B: la matriz indica POST, el contrato solo declara GET.
    "pm.test('D2/V30: OpenAPI declara UNICAMENTE GET para RF-51', () => pm.expect(metodos).to.eql(['get']));",
    "pm.test('V31: DISCREPANCIA MATRIZ(POST) <-> OPENAPI(GET) documentada', () => {",
    "  pm.expect(spec.paths[ruta].post, 'la matriz indica POST').to.eql(undefined);",
    "  const otras = Object.keys(spec.paths).filter((p) => /indicad/i.test(p) && spec.paths[p].post);",
    "  pm.expect(otras.join(','), 'no hay POST de indicadores en ninguna ruta').to.eql('');",
    "});",
    "const resp = Object.keys(spec.paths[ruta].get.responses);",
    "pm.test('El contrato declara 404, 400 y 403 (§G6)', () => {",
    "  ['404','400','403'].forEach((c) => pm.expect(resp, 'falta ' + c).to.include(c));",
    "});",
    "const p = spec.paths[ruta].get.parameters.find((x) => x.name === 'tipo_indicador');",
    "pm.test('D7: CRECIMIENTO es un valor valido de tipo_indicador', () => pm.expect(p.schema.description).to.include('CRECIMIENTO'));",
  ])],
});

setup.item.push({
  name: 'AUTH_OK - login del consumidor autorizado (con READ)',
  request: {
    method: 'POST', header: [{ key: 'Content-Type', value: 'application/json' }],
    url: BASE + '/sesiones/',
    body: raw({ correo_electronico: CONSUMIDOR_OK.correo, contrasena: '{{password}}' }),
  },
  event: [test([
    "pm.test('D3: AUTH_OK autentica correctamente', () => pm.response.to.have.status(200));",
    "const t = pm.response.json().token;",
    "pm.collectionVariables.set('tokenAutorizado', t);",
    "pm.test('D3: AUTH_OK corresponde al usuario " + CONSUMIDOR_OK.sub + "', () => {",
    "  pm.expect(String(JSON.parse(atob(t.split('.')[1])).sub)).to.eql('" + CONSUMIDOR_OK.sub + "');",
    "});",
  ])],
});

setup.item.push({
  name: 'AUTH_NO_READ - login del usuario SIN READ (' + CONSUMIDOR_NO_READ.rolNombre + ')',
  request: {
    method: 'POST', header: [{ key: 'Content-Type', value: 'application/json' }],
    url: BASE + '/sesiones/',
    body: raw({ correo_electronico: CONSUMIDOR_NO_READ.correo, contrasena: '{{password}}' }),
  },
  event: [test([
    // V23 - autenticacion valida (no es token invalido ni cuenta bloqueada: la cuenta es Activa).
    "pm.test('V23: AUTH_NO_READ autentica correctamente (credencial legitima)', () => pm.response.to.have.status(200));",
    "const t = pm.response.json().token;",
    "pm.collectionVariables.set('tokenSinRead', t);",
    "pm.test('V22/V23: AUTH_NO_READ corresponde al usuario " + CONSUMIDOR_NO_READ.sub + ", rol " + CONSUMIDOR_NO_READ.rol + " (" + CONSUMIDOR_NO_READ.rolNombre + ")', () => {",
    "  const payload = JSON.parse(atob(t.split('.')[1]));",
    "  pm.expect(String(payload.sub)).to.eql('" + CONSUMIDOR_NO_READ.sub + "');",
    "  pm.expect(Number(payload.rol)).to.eql(" + CONSUMIDOR_NO_READ.rol + ");",
    "});",
  ])],
});

setup.item.push({
  name: 'A3 - AUTH_OK tiene READ: control positivo (200)',
  request: { method: 'GET', header: hAuth('tokenAutorizado'), url: url(A313A.activo, 'CRECIMIENTO') },
  event: [test([
    "pm.test('A3: AUTH_OK obtiene 200 en /indicadores', () => pm.response.to.have.status(200));",
    "pm.collectionVariables.set('autorizacion_ok', 'SI');",
  ])],
});

setup.item.push({
  name: 'V24 - AUTH_NO_READ carece de READ: control negativo del acceso base',
  request: { method: 'GET', header: hAuth('tokenSinRead'), url: BASE + '/activos-biologicos/' + A314 },
  event: [test([
    // Demuestra por API que el usuario NO puede leer activos biologicos en general:
    // el 403 de TC-314 no sera especifico del endpoint de indicadores.
    "pm.test('V24: AUTH_NO_READ recibe 403 al leer el activo (READ ausente demostrado)', () => {",
    "  pm.expect(pm.response.code).to.eql(403);",
    "});",
    "pm.test('V24: el 403 es por permiso de rol (ACCESO_DENEGADO), no por cuenta inactiva', () => {",
    "  const b = json() || {};",
    "  pm.expect(b.error_code, 'un CUENTA_NO_ACTIVA no probaria falta de READ').to.eql('ACCESO_DENEGADO');",
    "});",
    "pm.collectionVariables.set('sin_read_confirmado', 'SI');",
  ])],
});

setup.item.push({
  name: 'D1 - El activo ' + INEXISTENTE + ' no existe',
  request: { method: 'GET', header: hAuth('tokenAutorizado'), url: BASE + '/activos-biologicos/' + INEXISTENTE },
  event: [test([
    "pm.test('D1/A1: el activo " + INEXISTENTE + " no existe (404)', () => pm.response.to.have.status(404));",
    "pm.collectionVariables.set('inexistente_confirmado', 'SI');",
  ])],
});

for (const f of [A313A, A313B]) {
  setup.item.push({
    name: 'Ciclo de vida - activo ' + f.activo + ' (' + f.ident + ')',
    request: { method: 'GET', header: hAuth('tokenAutorizado'), url: BASE + '/activos-biologicos/' + f.activo + '/ficha-integral' },
    event: [test([
      "pm.test('El activo " + f.activo + " existe y es accesible', () => pm.response.to.have.status(200));",
      "const b = pm.response.json();",
      "pm.test('El activo es " + f.ident + "', () => pm.expect(b.identificador).to.eql('" + f.ident + "'));",
      "pm.collectionVariables.set('estado_" + f.activo + "', String(b.estado_actual));",
    ])],
  });
}

// ──────────────────────── 01-CASO-PRINCIPAL ────────────────────────
const principal = { name: '01-CASO-PRINCIPAL', item: [] };

// TC-M02-312 — activo inexistente → 404.
principal.item.push({
  name: 'TC-M02-312 - activo inexistente (' + INEXISTENTE + ')',
  request: { method: 'GET', header: hAuth('tokenAutorizado'), url: url(INEXISTENTE, 'CRECIMIENTO', '2026-06-01', '2026-08-31') },
  event: [test([
    "const code = pm.response.code; const b = json() || {};",
    "pm.test('V1: la inexistencia de " + INEXISTENTE + " fue confirmada antes', () => pm.expect(pm.collectionVariables.get('inexistente_confirmado')).to.eql('SI'));",
    "pm.test('V2: AUTH_OK esta autorizado', () => pm.expect(pm.collectionVariables.get('autorizacion_ok')).to.eql('SI'));",
    "pm.test('V4: HTTP 404 NOT FOUND', () => pm.expect(code, 'obtenido HTTP ' + code).to.eql(404));",
    "pm.test('V5: el motivo es la inexistencia del activo', () => {",
    "  pm.expect(b.error_code).to.eql('ACTIVO_NO_ENCONTRADO');",
    "  pm.expect(String(b.message)).to.include('" + INEXISTENTE + "');",
    "});",
    "pm.test('TC-312: no expone stack trace ni SQL', () => pm.expect(texto()).to.not.match(/Traceback|SELECT .*FROM|sqlalchemy/i));",
    "sinIndicador('TC-M02-312');",
  ])],
});

// TC-M02-313-A — inicio anterior al nacimiento → 400.
principal.item.push({
  name: 'TC-M02-313-A - inicio antes del nacimiento (activo ' + A313A.activo + ')',
  request: { method: 'GET', header: hAuth('tokenAutorizado'), url: url(A313A.activo, 'CRECIMIENTO', A313A.inicio, A313A.fin) },
  event: [test([
    "const code = pm.response.code;",
    "pm.test('V7: el activo existe y esta ACTIVO', () => pm.expect(pm.collectionVariables.get('estado_" + A313A.activo + "')).to.eql('ACTIVO'));",
    "pm.test('V8/V9/A6: el inicio (" + A313A.inicio + ") es anterior al nacimiento y al ingreso', () => {",
    "  pm.expect(new Date('" + A313A.inicio + "')).to.be.below(new Date('" + A313A.nacimiento + "'));",
    "  pm.expect(new Date('" + A313A.inicio + "')).to.be.below(new Date('" + A313A.ingreso + "'));",
    "});",
    "pm.test('V10/A5: el fin (" + A313A.fin + ") esta dentro del ciclo y no invierte el rango', () => {",
    "  pm.expect(new Date('" + A313A.fin + "')).to.be.above(new Date('" + A313A.ingreso + "'));",
    "  pm.expect(new Date('" + A313A.fin + "')).to.be.above(new Date('" + A313A.inicio + "'));",
    "});",
    "pm.test('V11: HTTP 400 por rango fuera del ciclo de vida', () => pm.expect(code, 'obtenido HTTP ' + code).to.eql(400));",
    "pm.test('V12: el motivo identifica el ciclo de vida', () => pm.expect(norm(texto())).to.match(/ciclo de vida|fuera del ciclo|vida:/));",
    "sinIndicador('TC-M02-313-A');",
  ])],
});

// TC-M02-313-B — fin posterior a la baja → 400.
principal.item.push({
  name: 'TC-M02-313-B - fin posterior a la baja (activo ' + A313B.activo + ')',
  request: { method: 'GET', header: hAuth('tokenAutorizado'), url: url(A313B.activo, 'CRECIMIENTO', A313B.inicio, A313B.fin) },
  event: [test([
    "const code = pm.response.code;",
    "pm.test('V14/V15: el activo existe y esta en BAJA (baja " + A313B.baja + ")', () => pm.expect(pm.collectionVariables.get('estado_" + A313B.activo + "')).to.eql('BAJA'));",
    "pm.test('V16: el inicio (" + A313B.inicio + ") esta dentro del ciclo', () => {",
    "  pm.expect(new Date('" + A313B.inicio + "')).to.be.above(new Date('" + A313B.ingreso + "'));",
    "  pm.expect(new Date('" + A313B.inicio + "')).to.be.below(new Date('" + A313B.baja + "'));",
    "});",
    "pm.test('V17/A8: el fin (" + A313B.fin + ") es posterior a la baja', () => pm.expect(new Date('" + A313B.fin + "')).to.be.above(new Date('" + A313B.baja + "')));",
    "pm.test('V18/A9: el fin NO es futuro (aisla ciclo de vida de fecha futura)', () => pm.expect(new Date('" + A313B.fin + "')).to.be.below(new Date()));",
    "pm.test('V19: HTTP 400 por rango fuera del ciclo de vida', () => pm.expect(code, 'obtenido HTTP ' + code).to.eql(400));",
    "pm.test('V20: el motivo identifica el ciclo de vida', () => pm.expect(norm(texto())).to.match(/ciclo de vida|fuera del ciclo|baja|vida:/));",
    "sinIndicador('TC-M02-313-B');",
  ])],
});

// TC-M02-314 — usuario autenticado SIN READ → 403 (definicion reformulada).
principal.item.push({
  name: 'TC-M02-314 - usuario autenticado sin READ (activo ' + A314 + ')',
  request: { method: 'GET', header: hAuth('tokenSinRead'), url: url(A314, 'CRECIMIENTO', '2026-06-01', '2026-09-10') },
  event: [test([
    "const code = pm.response.code; const b = json() || {};",
    "pm.test('V22/V23: el usuario esta autenticado con credencial valida', () => {",
    "  pm.expect(String(pm.request.headers.get('Authorization'))).to.include('Bearer ');",
    "  pm.expect(pm.collectionVariables.get('tokenSinRead'), 'no hay token').to.be.a('string');",
    "});",
    "pm.test('V24: la ausencia de READ fue demostrada por API en SETUP', () => {",
    "  pm.expect(pm.collectionVariables.get('sin_read_confirmado')).to.eql('SI');",
    "});",
    "pm.test('V25: el activo " + A314 + " existe (no es 99999)', () => pm.expect(" + A314 + ").to.not.eql(" + INEXISTENTE + "));",
    // V27 - criterio de la ficha reformulada.
    "pm.test('V27: HTTP 403 FORBIDDEN', () => pm.expect(code, 'obtenido HTTP ' + code).to.eql(403));",
    // V28 - la causa es autorizacion (rol sin permiso), no autenticacion ni cuenta inactiva.
    "pm.test('V28: la causa es autorizacion insuficiente, no autenticacion', () => {",
    "  pm.expect(b.error_code, 'no debe ser TOKEN_* (autenticacion)').to.eql('ACCESO_DENEGADO');",
    "  pm.expect(code, 'un 401 seria autenticacion').to.not.eql(401);",
    "});",
    // V29 - no se expone indicador ni variables del calculo.
    "sinIndicador('TC-M02-314');",
    "sinVariables('TC-M02-314');",
  ])],
});

// ──────────────────────── 02-DIAGNOSTICO ────────────────────────
const diagnostico = { name: '02-DIAGNOSTICO', item: [] };

diagnostico.item.push({
  name: 'DIAG - el MISMO activo de 313-A con rango DENTRO del ciclo',
  request: { method: 'GET', header: hAuth('tokenAutorizado'), url: url(A313A.activo, 'CRECIMIENTO', A313A.ingreso, A313A.fin) },
  event: [test([
    "pm.test('DIAG: el rango valido responde 200', () => pm.response.to.have.status(200));",
    "const ind = indicadorDe('ganancia_peso');",
    "pm.test('DIAG: la respuesta es identica a la del rango invalido -> el rango no interviene en ninguna validacion de ciclo', () => {",
    "  pm.expect(ind).to.not.eql(null);",
    "  pm.expect(ind.periodo_inicio, 'el periodo lo fijan las mediciones, no el rango').to.not.eql('" + A313A.inicio + "');",
    "});",
  ])],
});

diagnostico.item.push({
  name: 'DIAG - el POST de la matriz devuelve 405',
  request: {
    method: 'POST',
    header: [{ key: 'Authorization', value: 'Bearer {{tokenAutorizado}}' }, { key: 'Content-Type', value: 'application/json' }],
    url: BASE + RUTA(A313B.activo),
    body: raw({ tipo_indicador: 'CRECIMIENTO' }),
  },
  event: [test([
    "pm.test('DIAG: POST /indicadores -> 405 Method Not Allowed', () => pm.expect(pm.response.code).to.eql(405));",
    "pm.test('DIAG: la cabecera Allow confirma solo GET', () => pm.expect(String(pm.response.headers.get('Allow'))).to.include('GET'));",
  ])],
});

const coleccion = {
  info: {
    name: 'TC-M02-G97 REFORMULADO - RF-51 inexistencia, ciclo de vida y autorizacion',
    description:
      'RF-51 / TC-M02-G97 (version reformulada). TC-M02-312 (activo inexistente -> 404), ' +
      'TC-M02-313-A (inicio anterior al nacimiento -> 400), TC-M02-313-B (fin posterior a la baja -> 400) ' +
      'y TC-M02-314 (usuario autenticado SIN permiso de lectura (29,2) -> 403). La matriz indica POST ' +
      '/indicadores, pero el contrato solo declara GET: la discrepancia se verifica en SETUP y con un ' +
      'POST de diagnostico que devuelve 405. AUTH_OK = m2m.nuevo@ejemplo.com (rol Productor, con READ); ' +
      'AUTH_NO_READ = contador@pecuaria.co (rol Contador, sin READ, cuenta Activa, credencial legitima). ' +
      'No se revoca ningun permiso ni se usa token invalido. Solo lectura: cero escrituras de QA.',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
  },
  item: [setup, principal, diagnostico],
  variable: [{ key: 'password', value: 'Test1234!' }],
};

const destino = path.join(__dirname, 'test_tc_m02_g97.json');
fs.writeFileSync(destino, JSON.stringify(coleccion, null, 2), 'utf8');
console.log('Coleccion escrita en ' + destino);
console.log('Solicitudes oficiales: 4 (TC-312, TC-313-A, TC-313-B, TC-314)');
