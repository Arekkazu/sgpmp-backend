// Genera test_tc_m02_g96.json - TC-M02-G96 (RF-51): rechazo de indicadores no calculables.
// Sub-casos: TC-M02-160 (muestra insuficiente), TC-M02-161 (incompatibilidad biologica),
// TC-M02-162 (division por cero - BLOQUEADO, precondicion inexistente), TC-M02-163 (outlier critico).
// Caso completamente de lectura: 0 escrituras de QA (solo GET).
const fs = require('fs');
const path = require('path');

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

// ── Fixtures preexistentes en TEST, verificados por SELECT antes de cualquier request ──
// Ninguno fue creado ni modificado por QA.
const F160 = { activo: 285, ident: 'QAJE-IND-1MED', fi: '2026-07-01', ff: '2026-07-31', mediciones: 1 };
const F161 = { activo: 299, ident: 'QAJE-IND-MACHO', especie: 'Bovino Qa Je', sexo: 'Macho' };
const F163 = {
  activo: 280, ident: 'QAJE-IND-OUTLIER', fi: '2026-08-01', ff: '2026-08-02',
  peso_inicial: 10.0, peso_final: 510.0, dias: 1, gdp_qa: 500,
};
const CONTROL = 279; // QAJE-CREC-OK: activo con datos normales, para el control positivo.

const RUTA = (id) => '/activos-biologicos/' + id + '/indicadores';

// Patrones definidos como cadenas para evitar ambiguedades de escape al serializar.
const RE_TECNICO = "/Traceback|site-packages|sqlalchemy|psycopg2|SELECT .*FROM/i";
const RE_INVALIDO = "/\\bInfinity\\b|\\bNaN\\b/";

const PRELUDIO = [
  "const norm = (s) => String(s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();",
  "const bodyTexto = () => pm.response.text();",
  "const json = () => { try { return pm.response.json(); } catch (e) { return null; } };",
  // Localiza un indicador por tipo dentro de la respuesta de exito.
  "const indicadorDe = (tipo) => { const b = json(); if (!b || !Array.isArray(b.indicadores)) return null;",
  "  return b.indicadores.find((i) => i.tipo === tipo) || null; };",
  "const advertencias = () => { const b = json(); return (b && Array.isArray(b.advertencias)) ? b.advertencias.join(' | ') : ''; };",
  // §8.6 / §14: ninguna respuesta puede exponer NaN, Infinity ni detalles tecnicos.
  "const sinValoresInvalidos = (etiqueta) => {",
  "  pm.test(etiqueta + ': la respuesta no contiene Infinity ni NaN', () => {",
  "    pm.expect(bodyTexto()).to.not.match(" + RE_INVALIDO + ");",
  "  });",
  "};",
  "const sinDetallesTecnicos = (etiqueta) => {",
  "  pm.test(etiqueta + ': la respuesta no expone stack trace, SQL ni rutas internas', () => {",
  "    const t = bodyTexto();",
  "    pm.expect(t).to.not.match(" + RE_TECNICO + ");",
  "    pm.expect(t).to.not.include('/src/');",
  "  });",
  "};",
].join('\n');

const raw = (obj) => ({ mode: 'raw', raw: JSON.stringify(obj, null, 2), options: { raw: { language: 'json' } } });
const test = (lines) => ({ listen: 'test', script: { type: 'text/javascript', exec: (PRELUDIO + '\n' + lines.join('\n')).split('\n') } });
const authH = [{ key: 'Authorization', value: 'Bearer {{token_consumidor}}' }];

const url = (id, tipo, fi, ff) => {
  let u = BASE + RUTA(id) + '?tipo_indicador=' + tipo;
  if (fi) u += '&fecha_inicio=' + fi + '&fecha_fin=' + ff;
  return u;
};

// ──────────────────────── 00-SETUP-LECTURA ────────────────────────
const setup = { name: '00-SETUP-LECTURA', item: [] };

setup.item.push({
  name: 'OpenAPI - contrato de /indicadores',
  request: { method: 'GET', header: [], url: BASE + '/openapi.json' },
  event: [test([
    "pm.test('El ambiente TEST HTTPS responde 200', () => pm.response.to.have.status(200));",
    "const spec = pm.response.json();",
    "const ruta = '/activos-biologicos/{id_activo}/indicadores';",
    "pm.test('El contrato declara la ruta de indicadores', () => pm.expect(spec.paths).to.have.property(ruta));",
    "const get = spec.paths[ruta].get;",
    // A7 / D12: el valor del indicador debe salir del contrato, no inventarse.
    "const p = get.parameters.find((x) => x.name === 'tipo_indicador');",
    "pm.test('D12: el contrato expone tipo_indicador con sus valores admitidos', () => {",
    "  pm.expect(p, 'no existe el parametro tipo_indicador').to.not.eql(undefined);",
    "  ['CRECIMIENTO', 'PRODUCCION', 'SANITARIO', 'EFICIENCIA', 'TODOS'].forEach((v) => {",
    "    pm.expect(p.schema.description, 'falta ' + v).to.include(v);",
    "  });",
    "});",
    "pm.test('A7: el contrato NO expone un enum por indicador individual (leche, GDP, conversion)', () => {",
    "  pm.expect(norm(JSON.stringify(p.schema))).to.not.match(/leche|ganancia_diaria|conversion_alimenticia/);",
    "});",
    "const resp = Object.keys(get.responses);",
    "pm.collectionVariables.set('respuestas_declaradas', resp.join(','));",
    // Discrepancias de contrato relevantes para TC-162 y TC-163.
    "pm.test('DISCREPANCIA DOCUMENTADA: el contrato no declara 409, exigido por TC-M02-162', () => {",
    "  pm.expect(resp, 'respuestas declaradas: ' + resp.join(',')).to.not.include('409');",
    "});",
    "pm.test('DISCREPANCIA DOCUMENTADA: el contrato no declara 500, exigido por TC-M02-163', () => {",
    "  pm.expect(resp, 'respuestas declaradas: ' + resp.join(',')).to.not.include('500');",
    "});",
    "pm.test('El contrato declara un unico metodo GET (caso de solo lectura)', () => {",
    "  pm.expect(Object.keys(spec.paths[ruta])).to.eql(['get']);",
    "});",
  ])],
});

setup.item.push({
  name: 'Login del consumidor autorizado RF-51',
  request: {
    method: 'POST', header: [{ key: 'Content-Type', value: 'application/json' }],
    url: BASE + '/sesiones/',
    body: raw({ correo_electronico: 'm2m.nuevo@ejemplo.com', contrasena: '{{password}}' }),
  },
  event: [test([
    "pm.test('D1: el consumidor autentica correctamente', () => pm.response.to.have.status(200));",
    "const t = pm.response.json().token;",
    "pm.collectionVariables.set('token_consumidor', t);",
    // Propietario de la finca 57, donde residen los tres fixtures: alcance de finca valido.
    "pm.test('D1: la credencial corresponde al usuario 35, propietario de la finca 57', () => {",
    "  pm.expect(String(JSON.parse(atob(t.split('.')[1])).sub)).to.eql('35');",
    "});",
  ])],
});

setup.item.push({
  name: 'A1 - El consumidor esta autorizado para leer indicadores (control positivo)',
  request: { method: 'GET', header: authH, url: url(CONTROL, 'CRECIMIENTO') },
  event: [test([
    // Sin este 200, un rechazo posterior podria confundirse con falta de permiso (A1).
    "pm.test('A1: el consumidor obtiene 200 en /indicadores de un activo accesible', () => pm.response.to.have.status(200));",
    "pm.test('A1: la respuesta corresponde al activo consultado', () => pm.expect(pm.response.json().id_activo_biologico).to.eql(" + CONTROL + "));",
    "pm.collectionVariables.set('autorizacion_ok', 'SI');",
  ])],
});

setup.item.push({
  name: 'Datos TC-M02-160 - activo ' + F160.activo + ' existe y esta activo',
  request: { method: 'GET', header: authH, url: BASE + '/activos-biologicos/' + F160.activo + '/ficha-integral' },
  event: [test([
    "pm.test('A2: el activo " + F160.activo + " existe y es accesible', () => pm.response.to.have.status(200));",
    "const b = pm.response.json();",
    "pm.test('El activo es " + F160.ident + " y esta ACTIVO', () => {",
    "  pm.expect(b.identificador).to.eql('" + F160.ident + "');",
    "  pm.expect(b.estado_actual).to.eql('ACTIVO');",
    "});",
  ])],
});

setup.item.push({
  name: 'Datos TC-M02-160 - historial confirma 1 medicion en el rango',
  request: { method: 'GET', header: authH, url: BASE + '/activos-biologicos/' + F160.activo + '/historial' },
  event: [test([
    "pm.test('El historial del activo " + F160.activo + " es accesible', () => pm.response.to.have.status(200));",
    "const regs = pm.response.json().registros || [];",
    "const enRango = regs.filter((r) => r.categoria === 'CRECIMIENTO' && r.fecha_evento >= '" + F160.fi + "' && r.fecha_evento <= '" + F160.ff + "T23:59:59Z');",
    // A3/A4: la precondicion es exactamente UNA medicion dentro del rango solicitado.
    "pm.test('A3/A4: exactamente 1 evento de crecimiento entre " + F160.fi + " y " + F160.ff + "', () => {",
    "  pm.expect(enRango.length, 'eventos en rango: ' + enRango.length).to.eql(" + F160.mediciones + ");",
    "});",
  ])],
});

setup.item.push({
  name: 'Datos TC-M02-161 - activo ' + F161.activo + ' bovino macho',
  request: { method: 'GET', header: authH, url: BASE + '/activos-biologicos/' + F161.activo + '/ficha-integral' },
  event: [test([
    "pm.test('A2: el activo " + F161.activo + " existe y es accesible', () => pm.response.to.have.status(200));",
    "const b = pm.response.json();",
    // A5/A6: la precondicion biologica se confirma antes de solicitar el indicador.
    "pm.test('A6: la especie del activo es bovina', () => pm.expect(norm(b.especie)).to.include('bovino'));",
    "pm.test('A5: el sexo del activo es Macho', () => pm.expect(norm(String(b.sexo))).to.eql('macho'));",
    "pm.test('El activo esta ACTIVO (ninguna otra condicion invalida)', () => pm.expect(b.estado_actual).to.eql('ACTIVO'));",
  ])],
});

setup.item.push({
  name: 'Datos TC-M02-163 - activo ' + F163.activo + ' con crecimiento atipico',
  request: { method: 'GET', header: authH, url: BASE + '/activos-biologicos/' + F163.activo + '/historial' },
  event: [test([
    "pm.test('A2: el activo " + F163.activo + " existe y su historial es accesible', () => pm.response.to.have.status(200));",
    "const regs = pm.response.json().registros || [];",
    "const crec = regs.filter((r) => r.categoria === 'CRECIMIENTO' && r.fecha_evento >= '" + F163.fi + "' && r.fecha_evento <= '" + F163.ff + "T23:59:59Z');",
    "pm.test('El rango contiene las 2 mediciones que generan el outlier', () => pm.expect(crec.length).to.eql(2));",
    // §8.3: el calculo independiente de QA parte de los valores leidos por SELECT en BD.
    "const gdp = (" + F163.peso_final + " - " + F163.peso_inicial + ") / " + F163.dias + ";",
    "pm.test('8.3: el calculo independiente de QA da +" + F163.gdp_qa + " kg/dia (outlier critico)', () => {",
    "  pm.expect(gdp).to.eql(" + F163.gdp_qa + ");",
    "  pm.expect(gdp, 'el escenario del caso exige una ganancia biologicamente imposible').to.be.at.least(500);",
    "});",
    "pm.collectionVariables.set('gdp_qa', String(gdp));",
  ])],
});

// ──────────────────────── 01-CASO-PRINCIPAL ────────────────────────
const principal = { name: '01-CASO-PRINCIPAL', item: [] };

// TC-M02-160 — muestra insuficiente → 422 esperado por la ficha (§5.5).
principal.item.push({
  name: 'TC-M02-160 - muestra insuficiente (activo ' + F160.activo + ', Ganancia Diaria de Peso)',
  request: { method: 'GET', header: authH, url: url(F160.activo, 'CRECIMIENTO', F160.fi, F160.ff) },
  event: [test([
    "const code = pm.response.code;",
    "pm.test('TC-M02-160: el consumidor esta autorizado (A1 descartado)', () => pm.expect(pm.collectionVariables.get('autorizacion_ok')).to.eql('SI'));",
    "pm.test('TC-M02-160: la solicitud pide crecimiento en el rango aislado (A15)', () => {",
    "  const u = pm.request.url.toString();",
    "  pm.expect(u).to.include('tipo_indicador=CRECIMIENTO');",
    "  pm.expect(u).to.include('fecha_inicio=" + F160.fi + "');",
    "  pm.expect(u).to.include('fecha_fin=" + F160.ff + "');",
    "});",
    // V3 - criterio de la ficha.
    "pm.test('V3: HTTP 422 por muestra insuficiente (5.5)', () => pm.expect(code, 'obtenido HTTP ' + code).to.eql(422));",
    // V4 - la causa debe identificarse como muestra insuficiente.
    "pm.test('V4: la respuesta identifica la muestra insuficiente', () => {",
    "  pm.expect(norm(bodyTexto())).to.match(/insuficiente|al menos (2|dos) medicion/);",
    "});",
    // §5.6.8 - lo critico para integridad: no debe publicarse un GDP como valido.
    "const ind = indicadorDe('ganancia_peso');",
    "pm.test('5.6.8: no se retorna un valor de GDP como valido', () => {",
    "  if (ind) { pm.expect(ind.valor, 'valor publicado: ' + ind.valor).to.eql(null);",
    "             pm.expect(ind.disponible, 'el indicador se marca disponible').to.eql(false); }",
    "});",
    "sinValoresInvalidos('TC-M02-160');",
    "sinDetallesTecnicos('TC-M02-160');",
    "pm.collectionVariables.set('http_160', code);",
    "pm.collectionVariables.set('adv_160', advertencias());",
  ])],
});

// TC-M02-161 — incompatibilidad biologica → 400 esperado por la ficha (§6.4).
principal.item.push({
  name: 'TC-M02-161 - incompatibilidad biologica (activo ' + F161.activo + ' macho, Produccion de leche)',
  request: { method: 'GET', header: authH, url: url(F161.activo, 'PRODUCCION') },
  event: [test([
    "const code = pm.response.code;",
    "pm.test('TC-M02-161: el consumidor esta autorizado (A1 descartado)', () => pm.expect(pm.collectionVariables.get('autorizacion_ok')).to.eql('SI'));",
    // A7: el contrato no expone un enum 'Produccion de leche'; PRODUCCION es su unica via de solicitud.
    "pm.test('A7: se solicita produccion por la unica via que expone el contrato', () => {",
    "  pm.expect(pm.request.url.toString()).to.include('tipo_indicador=PRODUCCION');",
    "});",
    // V7 - criterio de la ficha.
    "pm.test('V7: HTTP 400 por incompatibilidad biologica (6.4)', () => pm.expect(code, 'obtenido HTTP ' + code).to.eql(400));",
    // V8 - la causa debe ser la incompatibilidad especie/sexo, no otra.
    "pm.test('V8: la respuesta identifica la incompatibilidad biologica especie/genero', () => {",
    "  pm.expect(norm(bodyTexto()), 'la respuesta no menciona incompatibilidad biologica').to.match(/incompatibilidad|no es aplicable|especie|genero|sexo/);",
    "});",
    // §6.5.8 - no debe calcularse ni exponerse el indicador.
    "const ind = indicadorDe('produccion_promedio');",
    "pm.test('6.5.8: no se calcula ni expone el indicador de produccion', () => {",
    "  if (ind) { pm.expect(ind.valor, 'valor publicado: ' + ind.valor).to.eql(null);",
    "             pm.expect(ind.disponible).to.eql(false); }",
    "});",
    "sinValoresInvalidos('TC-M02-161');",
    "sinDetallesTecnicos('TC-M02-161');",
    "pm.collectionVariables.set('http_161', code);",
    "pm.collectionVariables.set('adv_161', advertencias());",
  ])],
});

// TC-M02-163 — outlier critico → 500 controlado esperado por la ficha (§8.5).
principal.item.push({
  name: 'TC-M02-163 - outlier critico (activo ' + F163.activo + ', +' + F163.gdp_qa + ' kg/dia)',
  request: { method: 'GET', header: authH, url: url(F163.activo, 'CRECIMIENTO', F163.fi, F163.ff) },
  event: [test([
    "const code = pm.response.code;",
    "pm.test('TC-M02-163: el consumidor esta autorizado (A1 descartado)', () => pm.expect(pm.collectionVariables.get('autorizacion_ok')).to.eql('SI'));",
    "pm.test('TC-M02-163: la solicitud cubre el periodo del crecimiento atipico (A15)', () => {",
    "  const u = pm.request.url.toString();",
    "  pm.expect(u).to.include('fecha_inicio=" + F163.fi + "');",
    "  pm.expect(u).to.include('fecha_fin=" + F163.ff + "');",
    "});",
    // A11/A12/A13: el outlier se corrobora con las variables que el propio producto reporta.
    "const ind = indicadorDe('ganancia_peso');",
    "pm.test('A11/A12: el producto usa los mismos pesos y dias que QA leyo en BD', () => {",
    "  pm.expect(ind, 'no se devolvio el indicador ganancia_peso').to.not.eql(null);",
    "  pm.expect(ind.variables_usadas.peso_inicial_kg).to.eql(" + F163.peso_inicial + ");",
    "  pm.expect(ind.variables_usadas.peso_final_kg).to.eql(" + F163.peso_final + ");",
    "  pm.expect(ind.variables_usadas.dias).to.eql(" + F163.dias + ");",
    "});",
    // V14 - el calculo independiente de QA confirma el outlier.
    "pm.test('V14: el calculo independiente de QA confirma +" + F163.gdp_qa + " kg/dia', () => {",
    "  pm.expect(Number(pm.collectionVariables.get('gdp_qa'))).to.eql(" + F163.gdp_qa + ");",
    "});",
    // V15 - criterio de la ficha.
    "pm.test('V15: HTTP 500 controlado por outlier critico (8.5)', () => pm.expect(code, 'obtenido HTTP ' + code).to.eql(500));",
    // V16 - el mensaje debe identificar el valor atipico.
    "pm.test('V16: la respuesta identifica valores atipicos / resultado biologicamente imposible', () => {",
    "  pm.expect(norm(bodyTexto()), 'la respuesta no menciona outlier ni imposibilidad biologica').to.match(/atipic|outlier|biologicamente imposible/);",
    "});",
    // V17 - lo critico: el indicador imposible no debe publicarse como valido.
    "pm.test('V17: no se expone el indicador atipico como valido', () => {",
    "  if (ind) { pm.expect(ind.disponible, 'el indicador se publica como disponible').to.eql(false);",
    "             pm.expect(ind.valor, 'valor publicado: ' + ind.valor).to.eql(null); }",
    "});",
    "sinValoresInvalidos('TC-M02-163');",
    "sinDetallesTecnicos('TC-M02-163');",
    "pm.collectionVariables.set('http_163', code);",
    "pm.collectionVariables.set('valor_163', ind ? String(ind.valor) : 'sin indicador');",
  ])],
});

// ──────────────────────── 02-DIAGNOSTICO ────────────────────────
// Solo se ejecuta porque hubo desviacion (§13). Ninguna peticion de esta carpeta
// cuenta como solicitud oficial.
const diagnostico = { name: '02-DIAGNOSTICO', item: [] };

diagnostico.item.push({
  name: 'DIAG TC-M02-162 - estado real de conversion_alimenticia (NO es la solicitud oficial)',
  request: { method: 'GET', header: authH, url: url(F160.activo, 'EFICIENCIA') },
  event: [test([
    // TC-M02-162 quedo BLOQUEADO: no existe ningun registro de consumo = 0 en TEST.
    // Esta peticion documenta que, ademas, el indicador nunca llega a calcularse.
    "pm.test('DIAG: la solicitud de EFICIENCIA responde 200', () => pm.response.to.have.status(200));",
    "const ind = indicadorDe('conversion_alimenticia');",
    "pm.test('DIAG: conversion_alimenticia se devuelve siempre como NO disponible', () => {",
    "  pm.expect(ind).to.not.eql(null);",
    "  pm.expect(ind.disponible).to.eql(false);",
    "  pm.expect(ind.valor).to.eql(null);",
    "});",
    "pm.test('DIAG: el motivo declarado es la ausencia del modulo M05, no el consumo cero', () => {",
    "  pm.expect(advertencias()).to.include('REQUIERE_M05');",
    "});",
    "sinValoresInvalidos('DIAG-162');",
    "pm.collectionVariables.set('adv_162_diag', advertencias());",
  ])],
});

diagnostico.item.push({
  name: 'DIAG - control positivo: el calculo si funciona con datos normales (activo ' + CONTROL + ')',
  request: { method: 'GET', header: authH, url: url(CONTROL, 'CRECIMIENTO') },
  event: [test([
    // Descarta que los 200 anteriores vengan de un endpoint inerte: con datos normales
    // el indicador se calcula y se publica.
    "pm.test('DIAG: el endpoint calcula normalmente con datos validos', () => pm.response.to.have.status(200));",
    "const ind = indicadorDe('ganancia_peso');",
    "pm.test('DIAG: con 2+ mediciones normales el indicador se publica como disponible', () => {",
    "  pm.expect(ind).to.not.eql(null);",
    "  pm.expect(ind.disponible).to.eql(true);",
    "});",
    "pm.collectionVariables.set('valor_control_" + CONTROL + "', ind ? String(ind.valor) : 'n/d');",
  ])],
});

const coleccion = {
  info: {
    name: 'TC-M02-G96 - RF-51 rechazo de indicadores no calculables',
    description:
      'RF-51 / TC-M02-G96. TC-M02-160 (muestra insuficiente -> 422), TC-M02-161 (incompatibilidad ' +
      'biologica -> 400) y TC-M02-163 (outlier critico -> 500 controlado) se ejecutan sobre fixtures ' +
      'preexistentes verificados por SELECT: 285 (QAJE-IND-1MED), 299 (QAJE-IND-MACHO) y 280 ' +
      '(QAJE-IND-OUTLIER). TC-M02-162 queda BLOQUEADO: no existe en TEST ningun registro de consumo ' +
      'de alimento igual a 0 y QA no puede fabricarlo. Caso completamente de lectura: solo GET, ' +
      'cero escrituras de QA.',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
  },
  item: [setup, principal, diagnostico],
  variable: [{ key: 'password', value: 'Test1234!' }],
};

const destino = path.join(__dirname, 'test_tc_m02_g96.json');
fs.writeFileSync(destino, JSON.stringify(coleccion, null, 2), 'utf8');
console.log('Coleccion escrita en ' + destino);
console.log('Solicitudes oficiales ejecutables: 3 de 4 (TC-M02-162 BLOQUEADO por falta de fixture)');
