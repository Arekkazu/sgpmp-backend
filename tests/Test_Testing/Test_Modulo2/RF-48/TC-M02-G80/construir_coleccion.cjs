// Genera test_tc_m02_g80.json - TC-M02-G80 (RF-48): reglas de compatibilidad de infraestructura destino.
// TC-M02-134 E-06 destino = origen | TC-M02-135 E-07 C1 especie
// TC-M02-136 E-08 C2 tipo         | TC-M02-137 E-09 C3 capacidad
// SETUP de solo lectura; las 8 peticiones oficiales deben ser rechazadas con 422.
const fs = require('fs');
const path = require('path');

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

// --- Infraestructuras de la finca 57, verificadas por SELECT en la Etapa 1 -------------
const INFRA = {
  origenCorral: 48,   // Corral QA JE Origen      · activa · cap 1000 · especie NULL
  destinoOk: 51,      // Corral QA JE Destino OK  · activa · cap  200 · especie 40 (bovino)
  capacidad: 47,      // Corral QA JE Capacidad   · activa · cap   50 · especie 40 · ocupacion 48
  estanque: 52,       // Estanque QA JE Piscicola · activa · cap  100 · especie NULL
  galponAves: 53,     // Galpon QA JE Aves        · activa · cap  100 · especie 41 (ave)
};

// --- Activos de la finca 57, todos bovinos (especie 40) y ACTIVO ----------------------
// 134 y 135 siempre son rechazos, por lo que ambos actores pueden reutilizar el mismo
// activo. 136 se ejecuta con un activo distinto por actor: si el producto no aplicase la
// regla C2, la transferencia se materializaria y el segundo actor ya no encontraria el
// escenario en pie.
const ACTIVOS = {
  reglas: 294,        // QAJE-TRF-REGLAS  · INDIVIDUAL · origen 51
  c2Productor: 280,   // QAJE-IND-OUTLIER · INDIVIDUAL · origen 48
  c2Admin: 285,       // QAJE-IND-1MED    · INDIVIDUAL · origen 48
  lote: 296,          // POBLACIONAL · cantidad 10 · origen 48
};

const ACTORES = [
  { key: 'productor', nombre: 'Productor', correo: 'm2m.nuevo@ejemplo.com', pwdVar: 'password', usuario: 35, activoC2: ACTIVOS.c2Productor },
  { key: 'admin', nombre: 'Administrador', correo: 'admin@pecuaria.co', pwdVar: 'password', usuario: 1, activoC2: ACTIVOS.c2Admin },
];

const PRELUDIO = [
  "const norm = (s) => String(s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();",
  "const cuerpo = () => { try { return JSON.stringify(pm.response.json()); } catch (e) { return pm.response.text(); } };",
].join('\n');

// `infraestructura_*_id` son enteros en el contrato. JSON.stringify entrecomillaria el
// marcador {{origen_N}}, de modo que se le quitan las comillas para que Postman inyecte un
// numero. `fecha_hoy` y el resto de marcadores siguen siendo cadenas.
const raw = (obj) => ({
  mode: 'raw',
  raw: JSON.stringify(obj, null, 2).replace(/"(\{\{origen_\d+\}\})"/g, '$1'),
  options: { raw: { language: 'json' } },
});
const test = (lines) => ({ listen: 'test', script: { type: 'text/javascript', exec: (PRELUDIO + '\n' + lines.join('\n')).split('\n') } });
const auth = (k) => [{ key: 'Authorization', value: 'Bearer {{token_' + k + '}}' }];
const authJson = (k) => auth(k).concat([{ key: 'Content-Type', value: 'application/json' }]);

// Lectura del estado vigente de un activo: guarda su infraestructura origen real, para no
// enviar nunca un origen desactualizado (que dispararia INFRAESTRUCTURA_ORIGEN_INCORRECTA).
const lecturaActivo = (actorKey, actorNombre, idActivo, etiqueta, tipoEsperado, extra) => ({
  name: etiqueta + ' - activo ' + idActivo + ' - ' + actorNombre,
  request: { method: 'GET', header: auth(actorKey), url: BASE + '/activos-biologicos/' + idActivo },
  event: [test([
    "pm.test('Acceso legitimo al activo " + idActivo + " - " + actorNombre + "', () => pm.response.to.have.status(200));",
    "const b = pm.response.json();",
    "pm.test('El activo " + idActivo + " esta ACTIVO', () => pm.expect(b.nombre_estado).to.eql('ACTIVO'));",
    "pm.test('El activo " + idActivo + " es " + tipoEsperado + "', () => pm.expect(b.tipo).to.eql('" + tipoEsperado + "'));",
    "pm.test('El activo " + idActivo + " es de la especie 40 (bovino)', () => pm.expect(b.id_especie).to.eql(40));",
    "pm.collectionVariables.set('origen_" + idActivo + "', b.id_infraestructura);",
    "pm.test('Infraestructura origen vigente del activo " + idActivo + ": ' + b.id_infraestructura, () => pm.expect(b.id_infraestructura).to.be.a('number'));",
  ].concat(extra || []))],
});

// ---------- 00-SETUP-LECTURA ----------
const setup = { name: '00-SETUP-LECTURA', item: [] };

setup.item.push({
  name: 'Contrato vivo OpenAPI por HTTPS',
  request: { method: 'GET', header: [], url: BASE + '/openapi.json' },
  event: [test([
    "pm.test('El ambiente TEST HTTPS responde 200', () => pm.response.to.have.status(200));",
    "const spec = pm.response.json();",
    "const post = '/activos-biologicos/{id_activo}/transferencias';",
    "const get = '/activos-biologicos/{id_activo}/transferencias/disponibles';",
    "pm.test('El contrato declara POST ' + post, () => pm.expect(spec.paths).to.have.property(post));",
    "pm.test('El contrato declara GET ' + get, () => pm.expect(spec.paths).to.have.property(get));",
    "const resp = Object.keys(spec.paths[post].post.responses);",
    "pm.test('El contrato declara 422 para el POST de transferencia', () => pm.expect(resp).to.include('422'));",
    "const dto = spec.components.schemas.RegistrarTransferenciaDTO;",
    "pm.test('El body exige origen, destino, fecha y motivo', () => pm.expect(dto.required).to.have.members(['infraestructura_origen_id', 'infraestructura_destino_id', 'fecha_transferencia', 'motivo_transferencia']));",
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
}

// Lectura de los cuatro activos del caso, con el Productor.
setup.item.push(lecturaActivo('productor', 'Productor', ACTIVOS.reglas, 'Estado inicial', 'INDIVIDUAL'));
setup.item.push(lecturaActivo('productor', 'Productor', ACTIVOS.c2Productor, 'Estado inicial', 'INDIVIDUAL'));
setup.item.push(lecturaActivo('admin', 'Administrador', ACTIVOS.c2Admin, 'Estado inicial', 'INDIVIDUAL'));
setup.item.push(lecturaActivo('productor', 'Productor', ACTIVOS.lote, 'Estado inicial', 'POBLACIONAL', [
  "pm.test('El LOTE " + ACTIVOS.lote + " tiene cantidad actual 10, como exige la ficha', () => {",
  "  const c = (b.detalle_poblacional && b.detalle_poblacional.cantidad_actual) || b.cantidad_actual;",
  "  pm.expect(Number(c)).to.eql(10);",
  "  pm.collectionVariables.set('cantidad_lote', Number(c));",
  "});",
]));

// GET disponibles: evidencia complementaria de la seccion 16 y lectura de los destinos.
for (const [idActivo, etiqueta] of [[ACTIVOS.reglas, 'activo INDIVIDUAL 294'], [ACTIVOS.lote, 'LOTE 296']]) {
  setup.item.push({
    name: 'GET transferencias/disponibles del ' + etiqueta + ' - Productor',
    request: { method: 'GET', header: auth('productor'), url: BASE + '/activos-biologicos/' + idActivo + '/transferencias/disponibles' },
    event: [test([
      "pm.test('El endpoint de destinos disponibles responde 200', () => pm.response.to.have.status(200));",
      "const lista = pm.response.json();",
      "const porId = Object.fromEntries(lista.map((i) => [i.id_infraestructura, i]));",
      "const origen = Number(pm.collectionVariables.get('origen_" + idActivo + "'));",
      // Lo unico que el filtrado hace bien: excluir el origen (coherente con E-06).
      "pm.test('El origen del activo no aparece como destino disponible (coherente con E-06)', () => pm.expect(porId).to.not.have.property(String(origen)));",
      // Lectura de las caracteristicas reales de cada destino del caso.
      "if (porId[" + INFRA.galponAves + "]) {",
      "  pm.test('Destino C1 (" + INFRA.galponAves + "): Galpon habilitado para la especie 41, no la 40 del activo', () => {",
      "    pm.expect(porId[" + INFRA.galponAves + "].id_especie).to.eql(41);",
      "    pm.expect(norm(porId[" + INFRA.galponAves + "].tipo)).to.eql('galpon');",
      "    pm.expect(porId[" + INFRA.galponAves + "].capacidad_maxima).to.eql(100);",
      "  });",
      "}",
      "if (porId[" + INFRA.estanque + "]) {",
      "  pm.test('Destino C2 (" + INFRA.estanque + "): Estanque SIN especie restringida, para que C1 no interfiera', () => {",
      "    pm.expect(porId[" + INFRA.estanque + "].tipo).to.eql('Estanque');",
      "    pm.expect(porId[" + INFRA.estanque + "].id_especie, 'id_especie NULL => C1 no puede fallar').to.eql(null);",
      "    pm.expect(porId[" + INFRA.estanque + "].capacidad_maxima).to.eql(100);",
      "  });",
      "}",
      "if (porId[" + INFRA.capacidad + "]) {",
      "  pm.test('Destino C3 (" + INFRA.capacidad + "): Corral de especie 40 y capacidad maxima 50', () => {",
      "    pm.expect(porId[" + INFRA.capacidad + "].tipo).to.eql('Corral');",
      "    pm.expect(porId[" + INFRA.capacidad + "].id_especie, 'misma especie => C1 no puede fallar').to.eql(40);",
      "    pm.expect(porId[" + INFRA.capacidad + "].capacidad_maxima).to.eql(50);",
      "  });",
      "}",
      // Hallazgo complementario de la seccion 16: el listado no filtra C1, C3 ni finca.
      "pm.collectionVariables.set('disponibles_total_" + idActivo + "', lista.length);",
      "pm.collectionVariables.set('disponibles_incompatibles_" + idActivo + "', [" + INFRA.galponAves + ", " + INFRA.estanque + ", " + INFRA.capacidad + "].filter((i) => porId[i]).join(','));",
    ])],
  });
}

// ---------- 01-CASO-PRINCIPAL ----------
const principal = { name: '01-CASO-PRINCIPAL', item: [] };

// Aserciones comunes a las ocho peticiones oficiales.
const comunes = (id, actor, activo, reglaTexto) => [
  "const enviado = JSON.parse(pm.request.body.raw);",
  "const code = pm.response.code;",
  "const b = (() => { try { return pm.response.json(); } catch (e) { return {}; } })();",
  "const txt = norm(cuerpo());",
  "pm.test('" + id + " / " + actor + ": el origen enviado es la infraestructura vigente del activo " + activo + "', () => pm.expect(enviado.infraestructura_origen_id).to.eql(Number(pm.collectionVariables.get('origen_" + activo + "'))));",
  "pm.test('" + id + " / " + actor + ": el resto del payload es valido (fecha no futura y motivo presente)', () => {",
  "  pm.expect(enviado.fecha_transferencia).to.match(/^\\d{4}-\\d{2}-\\d{2}$/);",
  "  pm.expect(new Date(enviado.fecha_transferencia + 'T00:00:00Z').getTime()).to.be.at.most(Date.now());",
  "  pm.expect(String(enviado.motivo_transferencia).trim()).to.not.eql('');",
  "});",
  "pm.test('" + id + " / " + actor + ": HTTP 422 segun la ficha (" + reglaTexto + ")', () => pm.expect(code).to.eql(422));",
  "pm.test('" + id + " / " + actor + ": el actor autorizado no recibe 403', () => pm.expect(code).to.not.eql(403));",
  "pm.test('" + id + " / " + actor + ": no se produce un error de servidor', () => pm.expect(code).to.be.below(500));",
];

// Verificacion de ausencia de cambios tras un rechazo.
const verificacion = (id, actorKey, actorNombre, activo) => ({
  name: 'Verificacion sin cambios tras ' + id + ' - ' + actorNombre,
  request: { method: 'GET', header: auth(actorKey), url: BASE + '/activos-biologicos/' + activo },
  event: [test([
    "pm.test('Activo legible', () => pm.response.to.have.status(200));",
    "const b = pm.response.json();",
    "const origen = Number(pm.collectionVariables.get('origen_" + activo + "'));",
    "pm.test('" + id + " / " + actorNombre + ": el activo " + activo + " sigue en su infraestructura origen (' + origen + '), delta ubicacion = 0', () => pm.expect(b.id_infraestructura).to.eql(origen));",
    "pm.test('" + id + " / " + actorNombre + ": el activo " + activo + " sigue ACTIVO', () => pm.expect(b.nombre_estado).to.eql('ACTIVO'));",
    "pm.collectionVariables.set('infra_post_" + id + "_" + actorKey + "', b.id_infraestructura);",
  ])],
});

for (const a of ACTORES) {
  const carpeta = { name: a.nombre, item: [] };

  // Paso 8: antes de la segunda tanda se revalida el estado de los recursos compartidos.
  if (a.key === 'admin') {
    carpeta.item.push(lecturaActivo('admin', 'Administrador', ACTIVOS.reglas, 'Revalidacion de precondiciones', 'INDIVIDUAL'));
    carpeta.item.push(lecturaActivo('admin', 'Administrador', ACTIVOS.lote, 'Revalidacion de precondiciones', 'POBLACIONAL', [
      "pm.test('El LOTE " + ACTIVOS.lote + " conserva cantidad actual 10', () => {",
      "  const c = (b.detalle_poblacional && b.detalle_poblacional.cantidad_actual) || b.cantidad_actual;",
      "  pm.expect(Number(c)).to.eql(10);",
      "});",
    ]));
  }

  // ---- TC-M02-134 : E-06 destino igual al origen ----
  carpeta.item.push({
    name: 'TC-M02-134 - destino = origen - ' + a.nombre,
    request: {
      method: 'POST', header: authJson(a.key),
      url: BASE + '/activos-biologicos/' + ACTIVOS.reglas + '/transferencias',
      body: raw({
        infraestructura_origen_id: '{{origen_' + ACTIVOS.reglas + '}}',
        infraestructura_destino_id: '{{origen_' + ACTIVOS.reglas + '}}',
        fecha_transferencia: '{{fecha_hoy}}',
        motivo_transferencia: 'TC-M02-134 ' + a.nombre + ': destino igual al origen',
      }),
    },
    event: [test(comunes('TC-M02-134', a.nombre, ACTIVOS.reglas, 'E-06').concat([
      "pm.test('TC-M02-134 / " + a.nombre + ": el destino enviado es igual al origen', () => pm.expect(enviado.infraestructura_destino_id).to.eql(enviado.infraestructura_origen_id));",
      "pm.test('TC-M02-134 / " + a.nombre + ": el error corresponde a E-06 (DESTINO_IGUAL_ORIGEN)', () => pm.expect(b.error_code).to.eql('DESTINO_IGUAL_ORIGEN'));",
      "pm.test('TC-M02-134 / " + a.nombre + ": el mensaje indica que el destino debe ser diferente al origen', () => {",
      "  pm.expect(txt).to.include('destino');",
      "  pm.expect(txt).to.include('diferente');",
      "});",
      "pm.test('TC-M02-134 / " + a.nombre + ": el rechazo no se debe a otra regla de RF-48', () => {",
      "  ['transferencia_concurrente', 'activo_no_encontrado', 'activo_no_activo', 'sin_infraestructura_origen', 'infraestructura_origen_incorrecta', 'infraestructura_destino_invalida', 'incompatibilidad_especie', 'capacidad_excedida'].forEach((otro) => {",
      "    pm.expect(txt, 'rechazo atribuido a ' + otro).to.not.include(otro);",
      "  });",
      "});",
      "pm.collectionVariables.set('http_" + a.key + "_134', code);",
      "pm.collectionVariables.set('body_" + a.key + "_134', pm.response.text().slice(0, 600));",
    ]))],
  });
  carpeta.item.push(verificacion('TC-M02-134', a.key, a.nombre, ACTIVOS.reglas));

  // ---- TC-M02-135 : E-07 incompatibilidad C1 por especie ----
  carpeta.item.push({
    name: 'TC-M02-135 - C1 especie - ' + a.nombre,
    request: {
      method: 'POST', header: authJson(a.key),
      url: BASE + '/activos-biologicos/' + ACTIVOS.reglas + '/transferencias',
      body: raw({
        infraestructura_origen_id: '{{origen_' + ACTIVOS.reglas + '}}',
        infraestructura_destino_id: INFRA.galponAves,
        fecha_transferencia: '{{fecha_hoy}}',
        motivo_transferencia: 'TC-M02-135 ' + a.nombre + ': destino habilitado solo para aves',
      }),
    },
    event: [test(comunes('TC-M02-135', a.nombre, ACTIVOS.reglas, 'E-07 / C1').concat([
      "pm.test('TC-M02-135 / " + a.nombre + ": el destino " + INFRA.galponAves + " es distinto del origen', () => pm.expect(enviado.infraestructura_destino_id).to.not.eql(enviado.infraestructura_origen_id));",
      "pm.test('TC-M02-135 / " + a.nombre + ": el error corresponde a E-07 (INCOMPATIBILIDAD_ESPECIE)', () => pm.expect(b.error_code).to.eql('INCOMPATIBILIDAD_ESPECIE'));",
      "pm.test('TC-M02-135 / " + a.nombre + ": el mensaje identifica la incompatibilidad de especie', () => pm.expect(txt).to.include('especie'));",
      // C3 no puede haber intervenido: el mensaje no menciona capacidad.
      "pm.test('TC-M02-135 / " + a.nombre + ": el rechazo no se debe a capacidad ni a otra regla de RF-48', () => {",
      "  ['capacidad_excedida', 'destino_igual_origen', 'infraestructura_destino_invalida', 'infraestructura_origen_incorrecta', 'activo_no_activo', 'transferencia_concurrente'].forEach((otro) => {",
      "    pm.expect(txt, 'rechazo atribuido a ' + otro).to.not.include(otro);",
      "  });",
      "});",
      "pm.collectionVariables.set('http_" + a.key + "_135', code);",
      "pm.collectionVariables.set('body_" + a.key + "_135', pm.response.text().slice(0, 600));",
    ]))],
  });
  carpeta.item.push(verificacion('TC-M02-135', a.key, a.nombre, ACTIVOS.reglas));

  // ---- TC-M02-136 : E-08 incompatibilidad C2 por tipo ----
  carpeta.item.push({
    name: 'TC-M02-136 - C2 tipo (Estanque) - ' + a.nombre,
    request: {
      method: 'POST', header: authJson(a.key),
      url: BASE + '/activos-biologicos/' + a.activoC2 + '/transferencias',
      body: raw({
        infraestructura_origen_id: '{{origen_' + a.activoC2 + '}}',
        infraestructura_destino_id: INFRA.estanque,
        fecha_transferencia: '{{fecha_hoy}}',
        motivo_transferencia: 'TC-M02-136 ' + a.nombre + ': bovino INDIVIDUAL hacia Estanque',
      }),
    },
    event: [test(comunes('TC-M02-136', a.nombre, a.activoC2, 'E-08 / C2').concat([
      "pm.test('TC-M02-136 / " + a.nombre + ": el destino " + INFRA.estanque + " es distinto del origen', () => pm.expect(enviado.infraestructura_destino_id).to.not.eql(enviado.infraestructura_origen_id));",
      "pm.test('TC-M02-136 / " + a.nombre + ": el error corresponde a E-08, incompatibilidad de tipo de infraestructura', () => {",
      "  pm.expect(txt, 'la ficha exige rechazo por tipo de infraestructura incompatible').to.match(/tipo|estanque|incompatib/);",
      "});",
      "pm.test('TC-M02-136 / " + a.nombre + ": el rechazo no se debe a C1 ni a C3, que aqui si se cumplen', () => {",
      "  ['incompatibilidad_especie', 'capacidad_excedida', 'destino_igual_origen', 'infraestructura_destino_invalida'].forEach((otro) => {",
      "    pm.expect(txt, 'rechazo atribuido a ' + otro).to.not.include(otro);",
      "  });",
      "});",
      "pm.collectionVariables.set('http_" + a.key + "_136', code);",
      "pm.collectionVariables.set('body_" + a.key + "_136', pm.response.text().slice(0, 600));",
    ]))],
  });
  carpeta.item.push(verificacion('TC-M02-136', a.key, a.nombre, a.activoC2));

  // ---- TC-M02-137 : E-09 capacidad C3 ----
  carpeta.item.push({
    name: 'TC-M02-137 - C3 capacidad - ' + a.nombre,
    request: {
      method: 'POST', header: authJson(a.key),
      url: BASE + '/activos-biologicos/' + ACTIVOS.lote + '/transferencias',
      body: raw({
        infraestructura_origen_id: '{{origen_' + ACTIVOS.lote + '}}',
        infraestructura_destino_id: INFRA.capacidad,
        fecha_transferencia: '{{fecha_hoy}}',
        motivo_transferencia: 'TC-M02-137 ' + a.nombre + ': LOTE de 10 hacia destino con capacidad 50 y ocupacion 48',
      }),
    },
    event: [test(comunes('TC-M02-137', a.nombre, ACTIVOS.lote, 'E-09 / C3').concat([
      "pm.test('TC-M02-137 / " + a.nombre + ": el activo es un LOTE de cantidad 10', () => pm.expect(Number(pm.collectionVariables.get('cantidad_lote'))).to.eql(10));",
      "pm.test('TC-M02-137 / " + a.nombre + ": el destino " + INFRA.capacidad + " es distinto del origen', () => pm.expect(enviado.infraestructura_destino_id).to.not.eql(enviado.infraestructura_origen_id));",
      "pm.test('TC-M02-137 / " + a.nombre + ": el error corresponde a E-09 (CAPACIDAD_EXCEDIDA)', () => pm.expect(b.error_code).to.eql('CAPACIDAD_EXCEDIDA'));",
      // La respuesta debe informar capacidad maxima y ocupacion actual, con los valores de la ficha.
      "pm.test('TC-M02-137 / " + a.nombre + ": la respuesta informa capacidad maxima 50', () => pm.expect(txt).to.match(/capacidad maxima: ?50/));",
      "pm.test('TC-M02-137 / " + a.nombre + ": la respuesta informa ocupacion actual 48', () => pm.expect(txt).to.match(/ocupacion actual: ?48/));",
      "pm.test('TC-M02-137 / " + a.nombre + ": la proyeccion 48 + 10 = 58 supera la capacidad 50', () => pm.expect(48 + Number(pm.collectionVariables.get('cantidad_lote'))).to.be.above(50));",
      "pm.test('TC-M02-137 / " + a.nombre + ": el rechazo no se debe a C1 ni a otra regla de RF-48', () => {",
      "  ['incompatibilidad_especie', 'destino_igual_origen', 'infraestructura_destino_invalida', 'infraestructura_origen_incorrecta', 'activo_no_activo'].forEach((otro) => {",
      "    pm.expect(txt, 'rechazo atribuido a ' + otro).to.not.include(otro);",
      "  });",
      "});",
      "pm.collectionVariables.set('http_" + a.key + "_137', code);",
      "pm.collectionVariables.set('body_" + a.key + "_137', pm.response.text().slice(0, 600));",
    ]))],
  });
  carpeta.item.push(verificacion('TC-M02-137', a.key, a.nombre, ACTIVOS.lote));

  principal.item.push(carpeta);
}

const coleccion = {
  info: {
    name: 'TC-M02-G80 - RF-48 reglas de compatibilidad de infraestructura destino',
    description:
      'RF-48 / TC-M02-G80. Sub-casos TC-M02-134 (E-06 destino igual al origen), TC-M02-135 (E-07 incompatibilidad ' +
      'C1 por especie), TC-M02-136 (E-08 incompatibilidad C2 por tipo) y TC-M02-137 (E-09 capacidad C3 excedida) ' +
      'sobre POST /activos-biologicos/{id_activo}/transferencias, ejecutados con Productor y Administrador. ' +
      'Cada peticion aisla una unica regla sobre recursos de la finca 57. El SETUP es de solo lectura.',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
  },
  item: [setup, principal, { name: '02-DIAGNOSTICO', item: [] }],
  event: [{
    listen: 'prerequest',
    script: {
      type: 'text/javascript',
      exec: [
        '// Fecha de hoy: el DTO rechaza cualquier fecha posterior a la actual (E-10).',
        "pm.collectionVariables.set('fecha_hoy', new Date().toISOString().slice(0, 10));",
      ],
    },
  }],
  variable: [{ key: 'password', value: 'Test1234!' }],
};

const destino = path.join(__dirname, 'test_tc_m02_g80.json');
fs.writeFileSync(destino, JSON.stringify(coleccion, null, 2), 'utf8');

const posts = principal.item.reduce((acc, f) => acc + f.item.filter((i) => i.request.method === 'POST').length, 0);
console.log('Coleccion escrita en ' + destino);
console.log('POST oficiales del caso principal: ' + posts);
