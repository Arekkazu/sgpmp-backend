// Genera test_tc_m02_g81.json - TC-M02-G81 FASE A (TEST compartido).
// Cubre TC-M02-138 (activo no ACTIVO) y TC-M02-140 (fecha futura), cada uno con los dos
// actores de RF-48: Productor y Administrador.
// TC-M02-139 NO genera peticion: el gate contractual (§7) se resuelve en 00-SETUP-LECTURA.
// TC-M02-141 NO se ejecuta aqui: exige fault injection y corre en LOCAL AISLADO.
const fs = require('fs');
const path = require('path');

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

// ── Fixtures preexistentes en TEST, verificados por SELECT. Ninguno creado ni modificado ──
const ORIGEN = 48;   // Corral QA JE Origen (finca 57, capacidad 1000, sin especie fijada)
const DESTINO = 51;  // Corral QA JE Destino OK (especie 40, capacidad 200, ocupacion 1)

const ACTORES = {
  productor: { correo: 'm2m.nuevo@ejemplo.com', pass: 'Test1234!', sub: '35', etiqueta: 'Productor' },
  admin: { correo: 'admin@pecuaria.co', pass: 'Test1234!', sub: '1', etiqueta: 'Administrador' },
};

// TC-138: activos en estado distinto de ACTIVO, con asociacion vigente al origen 48.
const T138 = [
  { actor: 'productor', activo: 284, ident: 'QAJE-TRF-NOACT', estado: 'INACTIVO' },
  { actor: 'admin', activo: 288, ident: 'QAJE-CREC-CERRADO', estado: 'CERRADO' },
];
// TC-140: activos ACTIVOS y validos en todo lo demas; la fecha futura es la unica causa.
const T140 = [
  { actor: 'productor', activo: 292, ident: 'QAJE-TRF-OK' },
  { actor: 'admin', activo: 295, ident: 'QAJE-DAT-COMPL' },
];
// TC-139: lote con cantidad_actual = 100 (escenario de la ficha), documentado sin ejecutar.
const LOTE_139 = 281;

const TODOS = [284, 288, 292, 295];

const PRELUDIO = [
  "const norm = (s) => String(s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();",
  "const cuerpo = () => { try { return pm.response.json(); } catch (e) { return {}; } };",
  "const texto = () => pm.response.text();",
  // Ninguna respuesta de rechazo puede haber creado un movimiento.
  "const sinTransferencia = (etiqueta) => {",
  "  pm.test(etiqueta + ': la respuesta no confirma ninguna transferencia', () => {",
  "    const b = cuerpo();",
  "    pm.expect(b, 'se devolvio id_movimiento').to.not.have.property('id_movimiento');",
  "    pm.expect(norm(texto())).to.not.include('transferencia registrada exitosamente');",
  "  });",
  "};",
].join('\n');

const raw = (obj) => ({ mode: 'raw', raw: JSON.stringify(obj, null, 2), options: { raw: { language: 'json' } } });
const test = (lines) => ({ listen: 'test', script: { type: 'text/javascript', exec: (PRELUDIO + '\n' + lines.join('\n')).split('\n') } });
const hAuth = (actor) => [
  { key: 'Authorization', value: 'Bearer {{token_' + actor + '}}' },
  { key: 'Content-Type', value: 'application/json' },
];

// Cuerpo oficial de transferencia: exactamente los 4 campos que declara el contrato.
const cuerpoTransferencia = (fechaVar, motivo) => raw({
  infraestructura_origen_id: '{{origen}}',
  infraestructura_destino_id: '{{destino}}',
  fecha_transferencia: '{{' + fechaVar + '}}',
  motivo_transferencia: motivo,
});
// Los ids deben viajar como enteros, no como cadenas.
const desentrecomillar = (item) => {
  item.request.body.raw = item.request.body.raw.replace(/"(\{\{(?:origen|destino)\}\})"/g, '$1');
  return item;
};

// ──────────────────────── 00-SETUP-LECTURA ────────────────────────
const setup = { name: '00-SETUP-LECTURA', item: [] };

setup.item.push({
  name: 'OpenAPI - contrato de transferencia y GATE CONTRACTUAL de TC-M02-139',
  request: { method: 'GET', header: [], url: BASE + '/openapi.json' },
  event: [test([
    "pm.test('El ambiente TEST HTTPS responde 200', () => pm.response.to.have.status(200));",
    "const spec = pm.response.json();",
    "const ruta = '/activos-biologicos/{id_activo}/transferencias';",
    "pm.test('El contrato declara POST /transferencias', () => pm.expect(spec.paths[ruta]).to.have.property('post'));",
    "const dto = spec.components.schemas.RegistrarTransferenciaDTO;",
    "const campos = Object.keys(dto.properties).sort();",
    // §7 - Gate contractual: sin campo de cantidad no hay forma de expresar "40 de 100".
    "pm.test('GATE TC-M02-139: el DTO declara exactamente 4 campos, ninguno de cantidad', () => {",
    "  pm.expect(campos).to.eql(['fecha_transferencia', 'infraestructura_destino_id', 'infraestructura_origen_id', 'motivo_transferencia']);",
    "});",
    "pm.test('GATE TC-M02-139: no existe ningun campo para expresar transferencia parcial', () => {",
    "  pm.expect(norm(JSON.stringify(dto))).to.not.match(/cantidad|parcial|unidades|subconjunto/);",
    "});",
    "pm.collectionVariables.set('campos_dto', campos.join(','));",
    // Codigos declarados: relevante para TC-M02-140.
    "const resp = Object.keys(spec.paths[ruta].post.responses);",
    "pm.collectionVariables.set('respuestas_declaradas', resp.join(','));",
    "pm.test('El contrato declara 409, exigido por TC-M02-138', () => pm.expect(resp).to.include('409'));",
    "pm.test('El contrato declara 422, exigido por TC-M02-140', () => pm.expect(resp).to.include('422'));",
    "pm.test('El contrato declara 500, exigido por TC-M02-141', () => pm.expect(resp).to.include('500'));",
    "pm.test('DISCREPANCIA DOCUMENTADA: el contrato NO declara 400 para esta ruta', () => {",
    "  pm.expect(resp, 'respuestas: ' + resp.join(',')).to.not.include('400');",
    "});",
  ])],
});

for (const [clave, a] of Object.entries(ACTORES)) {
  setup.item.push({
    name: 'Login ' + a.etiqueta,
    request: {
      method: 'POST', header: [{ key: 'Content-Type', value: 'application/json' }],
      url: BASE + '/sesiones/',
      body: raw({ correo_electronico: a.correo, contrasena: a.pass }),
    },
    event: [test([
      "pm.test('" + a.etiqueta + ": autentica correctamente', () => pm.response.to.have.status(200));",
      "const t = pm.response.json().token;",
      "pm.collectionVariables.set('token_" + clave + "', t);",
      "pm.test('" + a.etiqueta + ": la credencial corresponde al usuario " + a.sub + "', () => {",
      "  pm.expect(String(JSON.parse(atob(t.split('.')[1])).sub)).to.eql('" + a.sub + "');",
      "});",
    ])],
  });
}

// A4/A5 - el destino elegido debe ser realmente valido y compatible antes de usarlo.
setup.item.push({
  name: 'A5 - El destino ' + DESTINO + ' es valido y compatible (C1/C3)',
  request: { method: 'GET', header: hAuth('productor'), url: BASE + '/activos-biologicos/292/transferencias/disponibles' },
  event: [test([
    "pm.test('El listado de destinos disponibles responde 200', () => pm.response.to.have.status(200));",
    "const lista = pm.response.json();",
    "const d = lista.find((x) => x.id_infraestructura === " + DESTINO + ");",
    "pm.test('A5: el destino " + DESTINO + " figura como disponible para el activo', () => pm.expect(d, 'destino ausente del listado').to.not.eql(undefined));",
    "pm.test('A5: el destino es compatible con la especie del activo (C1)', () => pm.expect(d.id_especie).to.eql(40));",
    "pm.test('A5: el destino declara capacidad suficiente (C3)', () => pm.expect(d.capacidad_maxima).to.be.above(1));",
    "pm.collectionVariables.set('destino_ok', 'SI');",
  ])],
});

// Estado de cada activo ANTES de las peticiones oficiales.
for (const id of TODOS) {
  setup.item.push({
    name: 'Estado ANTES - activo ' + id,
    request: { method: 'GET', header: hAuth('productor'), url: BASE + '/activos-biologicos/' + id + '/ficha-integral' },
    event: [test([
      "pm.test('El activo " + id + " existe y es accesible (A3)', () => pm.response.to.have.status(200));",
      "const b = pm.response.json();",
      "pm.collectionVariables.set('estado_antes_" + id + "', String(b.estado_actual));",
      "pm.collectionVariables.set('infra_antes_" + id + "', String(b.infraestructura_asociada || b.infraestructura || ''));",
      "pm.test('Registrado el estado previo del activo " + id + "', () => pm.expect(b.estado_actual).to.be.a('string'));",
    ])],
  });
}

// ──────────────────────── 01-TC-M02-138 ────────────────────────
const c138 = { name: '01-TC-M02-138', item: [] };

for (const f of T138) {
  const a = ACTORES[f.actor];
  c138.item.push(desentrecomillar({
    name: 'TC-M02-138 ' + a.etiqueta + ' - activo ' + f.activo + ' (' + f.estado + ') rechazado',
    request: {
      method: 'POST', header: hAuth(f.actor),
      url: BASE + '/activos-biologicos/' + f.activo + '/transferencias',
      body: cuerpoTransferencia('fecha_hoy', 'QA G81 TC-138 ' + a.etiqueta + ' - verificacion de estado no ACTIVO'),
    },
    event: [test([
      "const code = pm.response.code;",
      "const b = cuerpo();",
      "pm.test('TC-138/" + a.etiqueta + ": el destino era valido (A5 descartado)', () => pm.expect(pm.collectionVariables.get('destino_ok')).to.eql('SI'));",
      "pm.test('TC-138/" + a.etiqueta + ": el activo no estaba ACTIVO antes de la peticion', () => {",
      "  pm.expect(pm.collectionVariables.get('estado_antes_" + f.activo + "')).to.eql('" + f.estado + "');",
      "});",
      // E-03 → ConflictError → 409.
      "pm.test('TC-138/" + a.etiqueta + ": HTTP 409 CONFLICT', () => pm.expect(code, 'obtenido HTTP ' + code).to.eql(409));",
      "pm.test('TC-138/" + a.etiqueta + ": el error_code corresponde a E-03 (estado no ACTIVO)', () => {",
      "  pm.expect(b.error_code).to.eql('ACTIVO_NO_ACTIVO');",
      "});",
      "pm.test('TC-138/" + a.etiqueta + ": el mensaje exige estado ACTIVO', () => {",
      "  pm.expect(norm(String(b.message))).to.include('solo se pueden transferir activos en estado activo');",
      "});",
      // El rechazo debe venir de E-03, no de una causa posterior del encadenamiento.
      "pm.test('TC-138/" + a.etiqueta + ": el rechazo NO proviene de origen, destino ni fecha', () => {",
      "  pm.expect(b.error_code).to.not.be.oneOf(['SIN_INFRAESTRUCTURA_ORIGEN', 'INFRAESTRUCTURA_ORIGEN_INCORRECTA', 'INFRAESTRUCTURA_DESTINO_INVALIDA', 'DESTINO_IGUAL_ORIGEN', 'VAL_ENTRADA']);",
      "});",
      "sinTransferencia('TC-138/" + a.etiqueta + "');",
      "pm.collectionVariables.set('http_138_" + f.actor + "', code);",
    ])],
  }));
}

// ──────────────────────── 02-TC-M02-140 ────────────────────────
const c140 = { name: '02-TC-M02-140', item: [] };

for (const f of T140) {
  const a = ACTORES[f.actor];
  c140.item.push(desentrecomillar({
    name: 'TC-M02-140 ' + a.etiqueta + ' - activo ' + f.activo + ' con fecha futura rechazado',
    request: {
      method: 'POST', header: hAuth(f.actor),
      url: BASE + '/activos-biologicos/' + f.activo + '/transferencias',
      body: cuerpoTransferencia('fecha_futura', 'QA G81 TC-140 ' + a.etiqueta + ' - verificacion de fecha futura'),
    },
    event: [test([
      "const code = pm.response.code;",
      "const b = cuerpo();",
      // §8 - la fecha futura debe ser la unica condicion invalida.
      "pm.test('TC-140/" + a.etiqueta + ": el activo estaba ACTIVO (aislamiento)', () => {",
      "  pm.expect(pm.collectionVariables.get('estado_antes_" + f.activo + "')).to.eql('ACTIVO');",
      "});",
      "pm.test('TC-140/" + a.etiqueta + ": el destino era valido y distinto del origen (A5 descartado)', () => {",
      "  pm.expect(pm.collectionVariables.get('destino_ok')).to.eql('SI');",
      "  pm.expect(pm.collectionVariables.get('destino')).to.not.eql(pm.collectionVariables.get('origen'));",
      "});",
      // Se comparan como fechas, no como cadenas: Chai exige numero o Date en to.be.above.
      "pm.test('TC-140/" + a.etiqueta + ": la fecha enviada es posterior a hoy (A6)', () => {",
      "  const enviada = JSON.parse(pm.request.body.raw).fecha_transferencia;",
      "  pm.expect(enviada).to.eql(pm.collectionVariables.get('fecha_futura'));",
      "  pm.expect(new Date(enviada), 'fecha enviada: ' + enviada).to.be.above(new Date(pm.collectionVariables.get('fecha_hoy')));",
      "});",
      // V - criterio de la ficha: 422 con E-10.
      "pm.test('TC-140/" + a.etiqueta + ": HTTP 422 UNPROCESSABLE ENTITY (ficha E-10)', () => {",
      "  pm.expect(code, 'obtenido HTTP ' + code).to.eql(422);",
      "});",
      "pm.test('TC-140/" + a.etiqueta + ": el codigo declarado esta entre los del contrato', () => {",
      "  pm.expect(String(pm.collectionVariables.get('respuestas_declaradas')).split(','), 'HTTP ' + code + ' no esta declarado').to.include(String(code));",
      "});",
      "pm.test('TC-140/" + a.etiqueta + ": la causa identificada es la fecha futura', () => {",
      "  pm.expect(norm(texto())).to.match(/fecha.*(no puede ser posterior|futur)/);",
      "});",
      "sinTransferencia('TC-140/" + a.etiqueta + "');",
      "pm.collectionVariables.set('http_140_" + f.actor + "', code);",
      "pm.collectionVariables.set('code_140_" + f.actor + "', String(b.error_code));",
    ])],
  }));
}

// ──────────────────────── 03-VERIFICACION-NO-PERSISTENCIA ────────────────────────
const verif = { name: '03-VERIFICACION-NO-PERSISTENCIA', item: [] };

for (const id of TODOS) {
  verif.item.push({
    name: 'Estado DESPUES - activo ' + id + ' sin cambios',
    request: { method: 'GET', header: hAuth('productor'), url: BASE + '/activos-biologicos/' + id + '/ficha-integral' },
    event: [test([
      "pm.test('El activo " + id + " sigue siendo accesible', () => pm.response.to.have.status(200));",
      "const b = pm.response.json();",
      "pm.test('El estado del activo " + id + " no cambio', () => {",
      "  pm.expect(String(b.estado_actual)).to.eql(pm.collectionVariables.get('estado_antes_" + id + "'));",
      "});",
      "pm.test('La infraestructura del activo " + id + " no cambio', () => {",
      "  pm.expect(String(b.infraestructura_asociada || b.infraestructura || '')).to.eql(pm.collectionVariables.get('infra_antes_" + id + "'));",
      "});",
    ])],
  });
}

const coleccion = {
  info: {
    name: 'TC-M02-G81 FASE A (TEST) - RF-48 rechazo de transferencias invalidas',
    description:
      'RF-48 / TC-M02-G81, fase de TEST compartido. TC-M02-138 (activo no ACTIVO -> 409 E-03) y ' +
      'TC-M02-140 (fecha futura -> 422 E-10) se ejecutan con los dos actores de RF-48: Productor ' +
      '(m2m.nuevo@ejemplo.com) y Administrador (admin@pecuaria.co). TC-M02-139 no genera peticion: ' +
      'el contrato no expone ningun campo de cantidad, por lo que la transferencia parcial no es ' +
      'expresable por API y el sub-caso queda BLOQUEADO (el gate contractual se verifica en SETUP). ' +
      'TC-M02-141 se ejecuta aparte en LOCAL AISLADO: exige fault injection, prohibido en TEST. ' +
      'En TEST solo se emiten peticiones de rechazo: ninguna transferencia debe persistir.',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
  },
  event: [{
    listen: 'prerequest',
    script: {
      type: 'text/javascript',
      exec: [
        '// Fechas calculadas en ejecucion: evita que un valor fijo caduque o quede en el pasado.',
        'const hoy = new Date();',
        'const iso = (d) => d.toISOString().slice(0, 10);',
        'const futura = new Date(hoy.getTime() + 5 * 24 * 60 * 60 * 1000);',
        "pm.collectionVariables.set('fecha_hoy', iso(hoy));",
        "pm.collectionVariables.set('fecha_futura', iso(futura));",
      ],
    },
  }],
  item: [setup, c138, c140, verif],
  variable: [
    { key: 'origen', value: String(ORIGEN) },
    { key: 'destino', value: String(DESTINO) },
  ],
};

const destino = path.join(__dirname, 'test_tc_m02_g81.json');
fs.writeFileSync(destino, JSON.stringify(coleccion, null, 2), 'utf8');
console.log('Coleccion escrita en ' + destino);
console.log('Peticiones oficiales en TEST: 4 (TC-138 x2 actores, TC-140 x2 actores)');
console.log('TC-M02-139: BLOQUEADO por gate contractual, lote de referencia ' + LOTE_139);
console.log('TC-M02-141: se ejecuta en LOCAL AISLADO (fault injection)');
