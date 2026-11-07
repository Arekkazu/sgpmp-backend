const fs = require('fs');

const baseUrl = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const fechaEvento = '2026-09-09T23:01:00Z';
const actores = [
  { nombre: 'Productor', correo: 'm2m.nuevo@ejemplo.com', password: '{{password}}', activo: 279, usuario: 35 },
  // La cuenta indicada en la ficha no existe en TEST. Se usa el veterinario activo
  // existente que posee el activo 311, conforme al intento 1 de la sección 11.3.
  { nombre: 'Veterinario', correo: 'juan.carlos.qa133@sgpmp-test.com', password: '{{password}}', activo: 311, usuario: 3 },
  { nombre: 'Ingeniero de campo', correo: 'ingeniero@pecuaria.co', password: '{{engineer_password}}', activo: 312, usuario: 4 },
];

const script = (lines) => [{ listen: 'test', script: { type: 'text/javascript', exec: lines } }];
const auth = (token) => [{ key: 'Authorization', value: `Bearer {{${token}}}` }];
const url = (raw) => raw;

function item(name, method, raw, { headers = [], body, tests = [] } = {}) {
  const request = { method, header: headers, url: url(raw) };
  if (body) request.body = { mode: 'raw', raw: JSON.stringify(body, null, 2), options: { raw: { language: 'json' } } };
  return { name, request, event: script(tests) };
}

function carpetaActor(actor) {
  const key = actor.nombre.toLowerCase().replaceAll(' ', '_');
  const token = `token_${key}`;
  const before = `conteo_antes_${key}`;
  const eventId = `evento_${key}`;
  const descripcion = `TC-M02-G43 ${actor.nombre}: PESO 250 kg`;
  const common = ['pm.test("HTTP 200", function () { pm.response.to.have.status(200); });'];
  return {
    name: actor.nombre,
    item: [
      item(`Login — ${actor.nombre}`, 'POST', `${baseUrl}/sesiones/`, {
        headers: [{ key: 'Content-Type', value: 'application/json' }],
        body: { correo_electronico: actor.correo, contrasena: actor.password },
        tests: [
          'pm.test("Login 200 y JWT presente", function () { pm.response.to.have.status(200); pm.expect(pm.response.json().token).to.be.a("string").and.not.empty; });',
          `pm.environment.set('${token}', pm.response.json().token);`,
        ],
      }),
      item(`Acceso legítimo y estado — ${actor.nombre}`, 'GET', `${baseUrl}/activos-biologicos/${actor.activo}`, {
        headers: auth(token),
        tests: [...common,
          `pm.test("Precondición: activo ${actor.activo} accesible y ACTIVO", function () { const b=pm.response.json(); pm.expect(b.id_activo_biologico).to.eql(${actor.activo}); pm.expect(b.nombre_estado).to.eql('ACTIVO'); pm.expect(b.tipo).to.eql('INDIVIDUAL'); });`,
        ],
      }),
      item(`Fase activa — ${actor.nombre}`, 'GET', `${baseUrl}/activos-biologicos/${actor.activo}/fases`, {
        headers: auth(token),
        tests: [...common,
          'pm.test("Precondición: fase productiva activa", function () { pm.expect(pm.response.json().fases.some(function (f) { return f.es_activa === true; })).to.eql(true); });',
        ],
      }),
      item(`ANTES — historial de crecimiento — ${actor.nombre}`, 'GET', `${baseUrl}/activos-biologicos/${actor.activo}/historial?page_size=100`, {
        headers: auth(token),
        tests: [...common,
          `pm.environment.set('${before}', pm.response.json().registros.filter(function (x) { return x.categoria === 'CRECIMIENTO'; }).length);`,
          `pm.test("ANTES: conteo de crecimiento capturado para activo ${actor.activo}", function () { pm.expect(Number(pm.environment.get('${before}'))).to.be.at.least(0); });`,
        ],
      }),
      item(`POST crecimiento PESO 250 kg — ${actor.nombre}`, 'POST', `${baseUrl}/activos-biologicos/${actor.activo}/eventos/crecimiento`, {
        headers: [...auth(token), { key: 'Content-Type', value: 'application/json' }],
        body: { tipo_medicion: 'PESO', valor_medicion: 250, unidad_medida: 'kg', fecha: fechaEvento, descripcion },
        tests: [
          'pm.test("HTTP 201 definido por OpenAPI", function () { pm.response.to.have.status(201); });',
          `pm.test("V1 — evento creado con identificador", function () { const e=pm.response.json().evento; pm.expect(e.id_eventos).to.be.a('number'); pm.expect(e.id_activo_biologico).to.eql(${actor.activo}); });`,
          `pm.test("V2 — respuesta conserva PESO, 250, kg y fecha", function () { const e=pm.response.json().evento; pm.expect(e.fecha).to.eql('${fechaEvento}'); pm.expect(e.crecimiento.tipo_medicion).to.eql('PESO'); pm.expect(Number(e.crecimiento.valor_medicion)).to.eql(250); pm.expect(e.crecimiento.unidad_medida).to.eql('kg'); });`,
          `pm.test("V5 — respuesta asocia al actor correcto", function () { pm.expect(pm.response.json().evento.id_usuario).to.eql(${actor.usuario}); });`,
          `pm.environment.set('${eventId}', pm.response.json().evento.id_eventos);`,
        ],
      }),
      item(`DESPUÉS — persistencia e historial por API — ${actor.nombre}`, 'GET', `${baseUrl}/activos-biologicos/${actor.activo}/historial?page_size=100`, {
        headers: auth(token),
        tests: [...common,
          `pm.test("V2 y V3 — historial contiene PESO 250 kg persistido", function () { const e=pm.response.json().registros.find(function (x) { return x.categoria === 'CRECIMIENTO' && x.fecha_evento === '${fechaEvento}' && x.descripcion === '${descripcion}'; }); pm.expect(e).to.exist; pm.expect(e.detalle_especifico.detalle_1).to.eql('PESO'); pm.expect(e.detalle_especifico.detalle_2).to.eql('250.00 kg'); });`,
          `pm.test("V4 — historial ordenado cronológicamente", function () { const fechas=pm.response.json().registros.map(function (x) { return new Date(x.fecha_evento).getTime(); }); const asc=fechas.slice().sort(function(a,b){return a-b;}); const desc=fechas.slice().sort(function(a,b){return b-a;}); pm.expect(fechas.join(",")==asc.join(",") || fechas.join(",")==desc.join(",")).to.eql(true); });`,
          `pm.test("V7 — API muestra incremento individual +1", function () { const despues=pm.response.json().registros.filter(function (x) { return x.categoria === 'CRECIMIENTO'; }).length; pm.expect(despues).to.eql(Number(pm.environment.get('${before}')) + 1); });`,
        ],
      }),
      item(`Historial cronológico — ${actor.nombre}`, 'GET', `${baseUrl}/activos-biologicos/${actor.activo}/historial?page_size=100`, {
        headers: auth(token),
        tests: [...common,
          `pm.test("V3 — evento de crecimiento aparece en historial", function () { const r=pm.response.json().registros; pm.expect(r.some(function (x) { return x.fecha_evento === '${fechaEvento}' && x.categoria === 'CRECIMIENTO'; })).to.eql(true); });`,
          'pm.test("V4 — historial ordenado cronológicamente", function () { const fechas=pm.response.json().registros.map(function (x) { return new Date(x.fecha_evento).getTime(); }); const asc=fechas.slice().sort(function(a,b){return a-b;}); const desc=fechas.slice().sort(function(a,b){return b-a;}); pm.expect(fechas.join(",")==asc.join(",") || fechas.join(",")==desc.join(",")).to.eql(true); });',
        ],
      }),
      item(`Auditoría RF-40 — ${actor.nombre}`, 'GET', `${baseUrl}/activos-biologicos/auditoria?rf_origen=RF40&id_activo_biologico=${actor.activo}&resultado=EXITOSO&page_size=100`, {
        headers: auth(token),
        tests: actor.nombre === 'Ingeniero de campo'
          ? ['pm.test("RF-52: la bitácora se protege con permiso independiente", function () { pm.response.to.have.status(403); });']
          : [...common,
            `pm.test("V6 — auditoría registra el crecimiento y actor", function () { const r=pm.response.json().registros; pm.expect(r.some(function (x) { return x.tipo_evento === 'EVENTO_CRECIMIENTO_REGISTRADO' && x.id_usuario_responsable === ${actor.usuario}; })).to.eql(true); });`,
          ],
      }),
    ],
  };
}

const collection = {
  info: {
    name: 'TC-M02-G43 — RF-40 Registro exitoso de crecimiento',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
    description: 'Ejecución HTTPS. SETUP solo consulta OpenAPI; el caso principal autentica y registra exactamente PESO=250 kg en activos existentes 279, 311 y 312.',
  },
  variable: [{ key: 'password', value: '' }, { key: 'engineer_password', value: '' }],
  item: [
    { name: '00-SETUP', item: [item('Contrato vivo OpenAPI por HTTPS', 'GET', `${baseUrl}/openapi.json`, { tests: ['pm.test("OpenAPI HTTPS 200", function () { pm.response.to.have.status(200); });'] })] },
    { name: '01-CASO-PRINCIPAL', item: actores.map(carpetaActor) },
    { name: '02-DIAGNOSTICO', description: 'Vacía salvo desviaciones que requieran investigación.', item: [
      item('Login observador de auditoría — Administrador', 'POST', `${baseUrl}/sesiones/`, {
        headers: [{ key: 'Content-Type', value: 'application/json' }],
        body: { correo_electronico: 'admin@pecuaria.co', contrasena: '{{password}}' },
        tests: ['pm.test("Login observador 200", function () { pm.response.to.have.status(200); });', 'pm.environment.set("token_observador", pm.response.json().token);'],
      }),
      item('Diagnóstico V6 — bitácora del Ingeniero', 'GET', `${baseUrl}/activos-biologicos/auditoria?rf_origen=RF40&id_activo_biologico=312&resultado=EXITOSO&page_size=100`, {
        headers: auth('token_observador'),
        tests: ['pm.test("Bitácora 200", function () { pm.response.to.have.status(200); });', 'pm.test("Evento del Ingeniero auditado", function () { pm.expect(pm.response.json().registros.some(function (x) { return x.tipo_evento === "EVENTO_CRECIMIENTO_REGISTRADO" && x.id_usuario_responsable === 4; })).to.eql(true); });'],
      }),
    ] },
  ],
};

fs.writeFileSync('test_tc_m02_g43.json', JSON.stringify(collection, null, 2) + '\n', 'utf8');
