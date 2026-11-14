// Genera test_tc_m02_g44.json - TC-M02-G44 (RF-40): validacion de formato, signo y unidad.
// SETUP de solo lectura; el caso principal envia 12 POST negativos que el sistema debe rechazar.
const fs = require('fs');
const path = require('path');

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const FECHA = '2026-09-10T08:30:00Z';

const ACTORES = [
  { key: 'productor',   nombre: 'Productor',          correo: 'm2m.nuevo@ejemplo.com',            pwdVar: 'password',          activo: 279, usuario: 35 },
  { key: 'veterinario', nombre: 'Veterinario',        correo: 'juan.carlos.qa133@sgpmp-test.com', pwdVar: 'password',          activo: 311, usuario: 3  },
  { key: 'ingeniero',   nombre: 'Ingeniero de campo', correo: 'ingeniero@pecuaria.co',            pwdVar: 'engineer_password', activo: 312, usuario: 4  }
];

// Helpers inyectados al inicio de cada script de test.
const PRELUDIO = [
  "const norm = (s) => String(s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();",
  "const cuerpo = () => { try { return JSON.stringify(pm.response.json()); } catch (e) { return pm.response.text(); } };"
].join('\n');

const VARIANTES = [
  {
    id: 'TC-M02-082', slug: 'abc', titulo: 'TC-M02-082 abc',
    body: (a) => ({ tipo_medicion: 'PESO', valor_medicion: 'abc', unidad_medida: 'kg', fecha: FECHA,
                    descripcion: 'TC-M02-082 ' + a.nombre + ': valor_medicion no numerico' }),
    fichaHttp: 400,
    // La ficha enuncia "Los datos ingresados no son de caracter numerico". El criterio verificable de la
    // seccion 13 es que el mensaje corresponda a un valor no numerico, no que el texto sea identico.
    fichaMensaje: null,
    campoEsperado: 'valor_medicion',
    regexMensaje: 'numeric|decimal|number|numero',
    etiquetaMensaje: 'el mensaje corresponde a valor no numerico'
  },
  {
    id: 'TC-M02-083-A', slug: 'cero', titulo: 'TC-M02-083-A cero',
    body: (a) => ({ tipo_medicion: 'PESO', valor_medicion: 0, unidad_medida: 'kg', fecha: FECHA,
                    descripcion: 'TC-M02-083-A ' + a.nombre + ': valor_medicion = 0' }),
    fichaHttp: null,
    fichaMensaje: null,
    regexMensaje: 'mayor a 0|mayor que 0|mayor a cero|positiv|no puede ser cero|debe ser mayor',
    etiquetaMensaje: 'el mensaje identifica un valor no positivo'
  },
  {
    id: 'TC-M02-083-B', slug: 'negativo', titulo: 'TC-M02-083-B negativo',
    body: (a) => ({ tipo_medicion: 'PESO', valor_medicion: -5, unidad_medida: 'kg', fecha: FECHA,
                    descripcion: 'TC-M02-083-B ' + a.nombre + ': valor_medicion = -5' }),
    fichaHttp: null,
    fichaMensaje: null,
    regexMensaje: 'mayor a 0|mayor que 0|mayor a cero|positiv|no puede ser negativ|debe ser mayor',
    etiquetaMensaje: 'el mensaje identifica un valor no positivo'
  },
  {
    id: 'TC-M02-084', slug: 'unidad', titulo: 'TC-M02-084 unidad incompatible',
    body: (a) => ({ tipo_medicion: 'PESO', valor_medicion: 250, unidad_medida: 'cm', fecha: FECHA,
                    descripcion: 'TC-M02-084 ' + a.nombre + ': PESO con unidad cm' }),
    fichaHttp: 400,
    // Clausula sustantiva de la ficha: "...no corresponde al tipo de medicion...". Se verifica esa
    // clausula y no el texto literal completo, que la ficha enuncia de forma generica.
    fichaMensaje: 'no corresponde al tipo de medicion',
    regexMensaje: 'unidad de medida',
    etiquetaMensaje: 'el mensaje corresponde a incompatibilidad entre unidad y tipo de medicion'
  }
];

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
    "pm.test('tipo_medicion, valor_medicion y unidad_medida son obligatorios', () => pm.expect(dto.required).to.have.members(['tipo_medicion', 'valor_medicion', 'unidad_medida']));",
    "pm.collectionVariables.set('respuestas_declaradas', Object.keys(spec.paths[ruta].post.responses).join(','));"
  ])]
});

for (const a of ACTORES) {
  setup.item.push({
    name: 'Login (lectura de sesion) - ' + a.nombre,
    request: {
      method: 'POST', header: [{ key: 'Content-Type', value: 'application/json' }],
      url: BASE + '/sesiones/',
      body: raw({ correo_electronico: a.correo, contrasena: '{{' + a.pwdVar + '}}' })
    },
    event: [test([
      "pm.test('Login exitoso - " + a.nombre + "', () => pm.response.to.have.status(200));",
      "const t = pm.response.json().token;",
      "pm.collectionVariables.set('token_" + a.key + "', t);",
      "const sub = JSON.parse(atob(t.split('.')[1])).sub;",
      "pm.test('El token pertenece al usuario " + a.usuario + "', () => pm.expect(String(sub)).to.eql('" + a.usuario + "'));"
    ])]
  });

  setup.item.push({
    name: 'Acceso legitimo y estado del activo - ' + a.nombre,
    request: { method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
               url: BASE + '/activos-biologicos/' + a.activo },
    event: [test([
      "pm.test('Acceso legitimo al activo " + a.activo + " - " + a.nombre + " (no 403 ni 404)', () => pm.response.to.have.status(200));",
      "const b = pm.response.json();",
      "pm.test('El activo " + a.activo + " esta ACTIVO', () => pm.expect(norm(cuerpo())).to.include('activo'));",
      "pm.test('El activo es INDIVIDUAL, por lo que no exige tipo_agregacion', () => pm.expect(norm(b.tipo || b.tipo_activo || '')).to.eql('individual'));"
    ])]
  });

  setup.item.push({
    name: 'Conteo base de eventos de crecimiento - ' + a.nombre,
    request: { method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
               url: BASE + '/activos-biologicos/' + a.activo + '/historial?page_size=100' },
    event: [test([
      "pm.test('Historial legible - " + a.nombre + "', () => pm.response.to.have.status(200));",
      "const n = pm.response.json().registros.filter(r => r.categoria === 'CRECIMIENTO').length;",
      "pm.collectionVariables.set('base_" + a.key + "', n);",
      "pm.test('Conteo base de " + a.nombre + " registrado: ' + n, () => pm.expect(n).to.be.a('number'));"
    ])]
  });
}

// ---------- 01-CASO-PRINCIPAL ----------
const principal = { name: '01-CASO-PRINCIPAL', item: [] };

for (const a of ACTORES) {
  const carpeta = { name: a.nombre, item: [] };

  for (const v of VARIANTES) {
    const lines = [
      "const code = pm.response.code;",
      "const txt = norm(cuerpo());",
      "pm.test('" + v.id + " / " + a.nombre + ": la peticion es rechazada, no se crea el evento', () => pm.expect(code).to.not.eql(201));",
      "pm.test('" + v.id + " / " + a.nombre + ": el rechazo es controlado (4xx, sin error de servidor)', () => { pm.expect(code, 'HTTP ' + code).to.be.at.least(400); pm.expect(code, 'HTTP ' + code).to.be.below(500); });"
    ];
    if (v.fichaHttp) {
      lines.push("pm.test('" + v.id + " / " + a.nombre + ": HTTP " + v.fichaHttp + " segun la ficha del caso', () => pm.expect(code).to.eql(" + v.fichaHttp + "));");
    }
    lines.push("pm.test('" + v.id + " / " + a.nombre + ": " + v.etiquetaMensaje + "', () => pm.expect(txt).to.match(/" + v.regexMensaje + "/i));");
    if (v.fichaMensaje) {
      lines.push("pm.test('" + v.id + " / " + a.nombre + ": el mensaje contiene la clausula sustantiva de la ficha', () => pm.expect(txt).to.include(norm('" + v.fichaMensaje + "')));");
    }
    if (v.campoEsperado) {
      lines.push("pm.test('" + v.id + " / " + a.nombre + ": el error se atribuye al campo " + v.campoEsperado + "', () => { const f = (pm.response.json().fields || []).map((x) => x.field); pm.expect(f).to.include('" + v.campoEsperado + "'); });");
    }
    lines.push("pm.collectionVariables.set('http_" + a.key + "_" + v.slug + "', code);");
    lines.push("pm.collectionVariables.set('body_" + a.key + "_" + v.slug + "', pm.response.text().slice(0, 600));");

    carpeta.item.push({
      name: v.titulo + ' - ' + a.nombre,
      request: {
        method: 'POST',
        header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }, { key: 'Content-Type', value: 'application/json' }],
        url: BASE + '/activos-biologicos/' + a.activo + '/eventos/crecimiento',
        body: raw(v.body(a))
      },
      event: [test(lines)]
    });

    carpeta.item.push({
      name: 'Verificacion de no persistencia tras ' + v.id + ' - ' + a.nombre,
      request: { method: 'GET', header: [{ key: 'Authorization', value: 'Bearer {{token_' + a.key + '}}' }],
                 url: BASE + '/activos-biologicos/' + a.activo + '/historial?page_size=100' },
      event: [test([
        "pm.test('Historial legible', () => pm.response.to.have.status(200));",
        "const n = pm.response.json().registros.filter(r => r.categoria === 'CRECIMIENTO').length;",
        "const base = Number(pm.collectionVariables.get('base_" + a.key + "'));",
        "pm.test('" + v.id + " / " + a.nombre + ": el rechazo no persistio ningun evento (' + base + ' -> ' + n + ', delta 0)', () => pm.expect(n).to.eql(base));",
        "pm.collectionVariables.set('post_" + a.key + "_" + v.slug + "', n);"
      ])]
    });
  }

  principal.item.push(carpeta);
}

const coleccion = {
  info: {
    name: 'TC-M02-G44 - RF-40 validacion de formato, signo y unidad',
    description: 'RF-40 / TC-M02-G44. Sub-casos TC-M02-082, TC-M02-083 y TC-M02-084 sobre POST /activos-biologicos/{id_activo}/eventos/crecimiento, ejecutados con Productor, Veterinario e Ingeniero de campo. Cada peticion introduce una unica condicion invalida sobre un payload base valido. El SETUP es de solo lectura.',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'
  },
  item: [setup, principal, { name: '02-DIAGNOSTICO', item: [] }],
  variable: [
    { key: 'password', value: 'Test1234!' },
    { key: 'engineer_password', value: 'Pruebas12#' }
  ]
};

const destino = path.join(__dirname, 'test_tc_m02_g44.json');
fs.writeFileSync(destino, JSON.stringify(coleccion, null, 2), 'utf8');

const posts = principal.item.reduce((acc, f) => acc + f.item.filter((i) => i.request.method === 'POST').length, 0);
console.log('Coleccion escrita en ' + destino);
console.log('POST oficiales del caso principal: ' + posts);
