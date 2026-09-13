// Genera test_tc_m02_g45.json - TC-M02-G45 (RF-40): coherencia entre tipo de activo y tipo_agregacion.
// TC-M02-085: activo INDIVIDUAL + tipo_agregacion='PROMEDIO'  -> debe rechazarse.
// TC-M02-086: activo POBLACIONAL sin tipo_agregacion          -> debe rechazarse.
// SETUP de solo lectura; las 6 peticiones oficiales son negativas y no deben crear eventos.
const fs = require('fs');
const path = require('path');

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

const ACTORES = [
  {
    key: 'productor', nombre: 'Productor',
    correo: 'm2m.nuevo@ejemplo.com', pwdVar: 'password', usuario: 35,
    individual: 279, lote: 281,
  },
  {
    key: 'veterinario', nombre: 'Veterinario',
    correo: 'juan.carlos.qa133@sgpmp-test.com', pwdVar: 'password', usuario: 3,
    individual: 311, lote: 328,
  },
  {
    key: 'ingeniero', nombre: 'Ingeniero de campo',
    correo: 'ingeniero@pecuaria.co', pwdVar: 'engineer_password', usuario: 4,
    individual: 312, lote: 334,
  },
];

// Helpers inyectados al inicio de cada script de test.
const PRELUDIO = [
  "const norm = (s) => String(s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();",
  "const cuerpo = () => { try { return JSON.stringify(pm.response.json()); } catch (e) { return pm.response.text(); } };",
].join('\n');

// --- Payloads base validos -------------------------------------------------------------
// La ficha de G45 no fija medicion, valor ni unidad: se usa una combinacion valida y se
// documenta. PESO/kg esta configurado en modulo9.metricas_produccion para la especie 40
// (aplica_a_tipo_activo = AMBOS, rango 0.1 - 2000), que es la especie de los seis activos.

// INDIVIDUAL: base valida SIN tipo_agregacion. TC-M02-085 solo anade ese campo.
const baseIndividual = (a) => ({
  tipo_medicion: 'PESO',
  valor_medicion: 250,
  unidad_medida: 'kg',
  fecha: '{{fecha_evento}}',
  descripcion: 'TC-M02-085 ' + a.nombre + ': INDIVIDUAL con tipo_agregacion',
});

// POBLACIONAL: base valida CON tipo_agregacion. TC-M02-086 solo elimina ese campo.
// nuevo_peso_promedio y cantidad_medida son obligatorios para POBLACIONAL y el backend los
// valida ANTES que tipo_agregacion; omitirlos desplazaria el rechazo a otra regla.
const baseLote = (a) => ({
  tipo_medicion: 'PESO',
  valor_medicion: 26,
  unidad_medida: 'kg',
  fecha: '{{fecha_evento}}',
  nuevo_peso_promedio: 26,
  cantidad_medida: 100,
  tipo_agregacion: 'PROMEDIO',
  descripcion: 'TC-M02-086 ' + a.nombre + ': POBLACIONAL sin tipo_agregacion',
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
    "pm.test('El contrato declara POST ' + ruta, () => pm.expect(spec.paths).to.have.property(ruta));",
    "const dto = spec.components.schemas.RegistrarEventoCrecimientoDTO;",
    "pm.test('tipo_agregacion existe en el contrato y es opcional a nivel de esquema', () => {",
    "  pm.expect(dto.properties).to.have.property('tipo_agregacion');",
    "  pm.expect(dto.required).to.not.include('tipo_agregacion');",
    "});",
    "pm.test('El contrato no restringe tipo_agregacion con un enum: PROMEDIO es sintacticamente valido', () => {",
    "  pm.expect(JSON.stringify(dto.properties.tipo_agregacion)).to.not.include('enum');",
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
      "pm.test('El token pertenece al usuario " + a.usuario + "', () => pm.expect(String(sub)).to.eql('" + a.usuario + "'));",
    ])],
  });

  for (const rec of [
    { slug: 'individual', tipo: 'INDIVIDUAL', id: a.individual },
    { slug: 'lote', tipo: 'POBLACIONAL', id: a.lote },
  ]) {
    setup.item.push({
      name: 'Recurso ' + rec.tipo + ' ' + rec.id + ' - ' + a.nombre,
      request: {
        method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
        url: BASE + '/activos-biologicos/' + rec.id,
      },
      event: [test([
        "pm.test('Acceso legitimo al activo " + rec.id + " - " + a.nombre + " (no 403 ni 404)', () => pm.response.to.have.status(200));",
        "const b = pm.response.json();",
        "pm.test('El activo " + rec.id + " es de tipo " + rec.tipo + "', () => pm.expect(b.tipo).to.eql('" + rec.tipo + "'));",
        "pm.test('El activo " + rec.id + " esta ACTIVO', () => pm.expect(norm(cuerpo())).to.include('activo'));",
        "pm.collectionVariables.set('tipo_" + a.key + "_" + rec.slug + "', b.tipo);",
      ])],
    });

    setup.item.push({
      name: 'Fase productiva activa de ' + rec.id + ' - ' + a.nombre,
      request: {
        method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
        url: BASE + '/activos-biologicos/' + rec.id + '/fases',
      },
      event: [test([
        "pm.test('Fases legibles del activo " + rec.id + "', () => pm.response.to.have.status(200));",
        "const b = pm.response.json();",
        "const lista = Array.isArray(b) ? b : (b.fases || b.registros || []);",
        "const activas = lista.filter((f) => f.es_activa === true);",
        "pm.test('El activo " + rec.id + " tiene una fase productiva activa', () => pm.expect(activas.length).to.eql(1));",
      ])],
    });

    setup.item.push({
      name: 'Conteo ANTES de ' + rec.id + ' - ' + a.nombre,
      request: {
        method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
        url: BASE + '/activos-biologicos/' + rec.id + '/historial?page_size=100',
      },
      event: [test([
        "pm.test('Historial legible del activo " + rec.id + "', () => pm.response.to.have.status(200));",
        "const n = pm.response.json().registros.filter((r) => r.categoria === 'CRECIMIENTO').length;",
        "pm.collectionVariables.set('base_" + a.key + "_" + rec.slug + "', n);",
        "pm.test('Conteo ANTES del activo " + rec.id + " (" + a.nombre + "): ' + n, () => pm.expect(n).to.be.a('number'));",
      ])],
    });
  }
}

// ---------- 01-CASO-PRINCIPAL ----------
const principal = { name: '01-CASO-PRINCIPAL', item: [] };

for (const a of ACTORES) {
  const carpeta = { name: a.nombre, item: [] };

  // --- TC-M02-085: INDIVIDUAL + tipo_agregacion ---
  const cuerpo085 = Object.assign({}, baseIndividual(a), { tipo_agregacion: 'PROMEDIO' });
  carpeta.item.push({
    name: 'TC-M02-085 - INDIVIDUAL con tipo_agregacion - ' + a.nombre,
    request: {
      method: 'POST',
      header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }, { key: 'Content-Type', value: 'application/json' }],
      url: BASE + '/activos-biologicos/' + a.individual + '/eventos/crecimiento',
      body: raw(cuerpo085),
    },
    event: [test([
      "const enviado = JSON.parse(pm.request.body.raw);",
      "const code = pm.response.code;",
      "const txt = norm(cuerpo());",
      // 1 - el activo es realmente INDIVIDUAL
      "pm.test('TC-M02-085 / " + a.nombre + ": el activo " + a.individual + " es INDIVIDUAL', () => pm.expect(pm.collectionVariables.get('tipo_" + a.key + "_individual')).to.eql('INDIVIDUAL'));",
      // 2 - la peticion lleva tipo_agregacion = PROMEDIO
      "pm.test('TC-M02-085 / " + a.nombre + ": la peticion envia tipo_agregacion PROMEDIO', () => pm.expect(enviado.tipo_agregacion).to.eql('PROMEDIO'));",
      // 3 - los demas campos son validos (una sola condicion invalida)
      "pm.test('TC-M02-085 / " + a.nombre + ": los demas campos son validos, unica condicion invalida', () => {",
      "  pm.expect(enviado.tipo_medicion).to.eql('PESO');",
      "  pm.expect(enviado.valor_medicion).to.be.above(0);",
      "  pm.expect(enviado.unidad_medida).to.eql('kg');",
      "  pm.expect(enviado.fecha).to.match(/^\\d{4}-\\d{2}-\\d{2}T/);",
      "});",
      // 4 - rechazo controlado
      "pm.test('TC-M02-085 / " + a.nombre + ": la peticion es rechazada, no se crea el evento', () => pm.expect(code).to.not.eql(201));",
      "pm.test('TC-M02-085 / " + a.nombre + ": el rechazo es controlado (4xx, sin error de servidor)', () => { pm.expect(code, 'HTTP ' + code).to.be.at.least(400); pm.expect(code, 'HTTP ' + code).to.be.below(500); });",
      // 5 - el rechazo corresponde a la regla evaluada, no a cualquier otra
      "pm.test('TC-M02-085 / " + a.nombre + ": el rechazo senala tipo_agregacion como no aplicable a INDIVIDUAL', () => {",
      "  pm.expect(txt).to.include('tipo_agregacion');",
      "  pm.expect(txt).to.include('individual');",
      "});",
      // El rechazo NO puede deberse a otra precondicion (seccion 16.3).
      "pm.test('TC-M02-085 / " + a.nombre + ": el rechazo no se debe a otra regla de RF-40', () => {",
      "  ['sin_fase_activa', 'fecha_futura', 'fecha_anterior', 'tipo_medicion_no_configurado', 'valor_fuera_de_rango'].forEach((otro) => {",
      "    pm.expect(txt, 'rechazo atribuido a ' + otro).to.not.include(otro);",
      "  });",
      "});",
      "pm.collectionVariables.set('http_" + a.key + "_085', code);",
      "pm.collectionVariables.set('body_" + a.key + "_085', pm.response.text().slice(0, 600));",
    ])],
  });

  carpeta.item.push({
    name: 'Verificacion de no persistencia tras TC-M02-085 - ' + a.nombre,
    request: {
      method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
      url: BASE + '/activos-biologicos/' + a.individual + '/historial?page_size=100',
    },
    event: [test([
      "pm.test('Historial legible', () => pm.response.to.have.status(200));",
      "const n = pm.response.json().registros.filter((r) => r.categoria === 'CRECIMIENTO').length;",
      "const base = Number(pm.collectionVariables.get('base_" + a.key + "_individual'));",
      "pm.test('TC-M02-085 / " + a.nombre + ": el rechazo no persistio ningun evento (' + base + ' -> ' + n + ', delta 0)', () => pm.expect(n).to.eql(base));",
      "pm.collectionVariables.set('post_" + a.key + "_085', n);",
    ])],
  });

  // --- TC-M02-086: POBLACIONAL sin tipo_agregacion ---
  const cuerpo086 = baseLote(a);
  delete cuerpo086.tipo_agregacion;
  carpeta.item.push({
    name: 'TC-M02-086 - LOTE sin tipo_agregacion - ' + a.nombre,
    request: {
      method: 'POST',
      header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }, { key: 'Content-Type', value: 'application/json' }],
      url: BASE + '/activos-biologicos/' + a.lote + '/eventos/crecimiento',
      body: raw(cuerpo086),
    },
    event: [test([
      "const enviado = JSON.parse(pm.request.body.raw);",
      "const code = pm.response.code;",
      "const txt = norm(cuerpo());",
      // 1 - el activo es realmente POBLACIONAL
      "pm.test('TC-M02-086 / " + a.nombre + ": el activo " + a.lote + " es POBLACIONAL', () => pm.expect(pm.collectionVariables.get('tipo_" + a.key + "_lote')).to.eql('POBLACIONAL'));",
      // 2 - tipo_agregacion esta efectivamente ausente del request
      "pm.test('TC-M02-086 / " + a.nombre + ": el request omite tipo_agregacion', () => pm.expect(enviado).to.not.have.property('tipo_agregacion'));",
      // 3 - los demas campos obligatorios de POBLACIONAL si estan presentes y son validos
      "pm.test('TC-M02-086 / " + a.nombre + ": los demas campos son validos (unica condicion invalida)', () => {",
      "  pm.expect(enviado.tipo_medicion).to.eql('PESO');",
      "  pm.expect(enviado.valor_medicion).to.be.above(0);",
      "  pm.expect(enviado.unidad_medida).to.eql('kg');",
      "  pm.expect(enviado.nuevo_peso_promedio).to.be.above(0);",
      "  pm.expect(enviado.cantidad_medida).to.be.above(0);",
      "  pm.expect(enviado.fecha).to.match(/^\\d{4}-\\d{2}-\\d{2}T/);",
      "});",
      // 4 - rechazo controlado
      "pm.test('TC-M02-086 / " + a.nombre + ": la peticion es rechazada, no se crea el evento', () => pm.expect(code).to.not.eql(201));",
      "pm.test('TC-M02-086 / " + a.nombre + ": el rechazo es controlado (4xx, sin error de servidor)', () => { pm.expect(code, 'HTTP ' + code).to.be.at.least(400); pm.expect(code, 'HTTP ' + code).to.be.below(500); });",
      // 5 - el rechazo corresponde a la regla evaluada: campo obligatorio ausente
      "pm.test('TC-M02-086 / " + a.nombre + ": el rechazo senala tipo_agregacion como obligatorio para POBLACIONAL', () => {",
      "  pm.expect(txt).to.include('tipo_agregacion');",
      "  pm.expect(txt).to.match(/obligatorio|requerid|falta|required/);",
      "});",
      // El rechazo NO puede deberse a otra precondicion (seccion 16.3).
      "pm.test('TC-M02-086 / " + a.nombre + ": el rechazo no se debe a otra regla de RF-40', () => {",
      "  ['sin_fase_activa', 'fecha_futura', 'fecha_anterior', 'tipo_medicion_no_configurado', 'valor_fuera_de_rango', 'nuevo_peso_requerido', 'cantidad_medida_requerida'].forEach((otro) => {",
      "    pm.expect(txt, 'rechazo atribuido a ' + otro).to.not.include(otro);",
      "  });",
      "});",
      "pm.collectionVariables.set('http_" + a.key + "_086', code);",
      "pm.collectionVariables.set('body_" + a.key + "_086', pm.response.text().slice(0, 600));",
    ])],
  });

  carpeta.item.push({
    name: 'Verificacion de no persistencia tras TC-M02-086 - ' + a.nombre,
    request: {
      method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
      url: BASE + '/activos-biologicos/' + a.lote + '/historial?page_size=100',
    },
    event: [test([
      "pm.test('Historial legible', () => pm.response.to.have.status(200));",
      "const n = pm.response.json().registros.filter((r) => r.categoria === 'CRECIMIENTO').length;",
      "const base = Number(pm.collectionVariables.get('base_" + a.key + "_lote'));",
      "pm.test('TC-M02-086 / " + a.nombre + ": el rechazo no persistio ningun evento (' + base + ' -> ' + n + ', delta 0)', () => pm.expect(n).to.eql(base));",
      "pm.collectionVariables.set('post_" + a.key + "_086', n);",
    ])],
  });

  principal.item.push(carpeta);
}

const coleccion = {
  info: {
    name: 'TC-M02-G45 - RF-40 coherencia entre tipo de activo y tipo_agregacion',
    description:
      'RF-40 / TC-M02-G45. Sub-casos TC-M02-085 (activo INDIVIDUAL con tipo_agregacion) y TC-M02-086 ' +
      '(activo POBLACIONAL sin tipo_agregacion) sobre POST /activos-biologicos/{id_activo}/eventos/crecimiento, ' +
      'ejecutados con Productor, Veterinario e Ingeniero de campo sobre recursos de acceso legitimo. ' +
      'Cada peticion introduce una unica condicion invalida sobre un payload base valido. El SETUP es de solo lectura.',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
  },
  item: [setup, principal, { name: '02-DIAGNOSTICO', item: [] }],
  event: [{
    listen: 'prerequest',
    script: {
      type: 'text/javascript',
      exec: [
        '// Fecha valida para todas las peticiones: posterior al ultimo evento de los activos',
        '// INDIVIDUAL (2026-09-10T08:33:36Z) y no futura, que el backend rechaza con FECHA_FUTURA.',
        "pm.collectionVariables.set('fecha_evento', new Date(Date.now() - 120000).toISOString().replace(/\\.\\d{3}Z$/, 'Z'));",
      ],
    },
  }],
  variable: [
    { key: 'password', value: 'Test1234!' },
    { key: 'engineer_password', value: 'Pruebas12#' },
  ],
};

const destino = path.join(__dirname, 'test_tc_m02_g45.json');
fs.writeFileSync(destino, JSON.stringify(coleccion, null, 2), 'utf8');

const posts = principal.item.reduce((acc, f) => acc + f.item.filter((i) => i.request.method === 'POST').length, 0);
console.log('Coleccion escrita en ' + destino);
console.log('POST oficiales del caso principal: ' + posts);
