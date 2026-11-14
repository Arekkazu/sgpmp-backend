import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { generarInforme, problemaCypress, validarIncidencia, asignarAtencion } from '../lib/g87_informe.mjs';
import { estadoMarcador } from '../lib/g87_cierre.mjs';
import { regenerarInforme } from '../g87.mjs';

const grupo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const run = 'RUN-G87-V1-20261023-145303';
const dir = path.join(grupo, 'Resultados', run);
const r5 = JSON.parse(fs.readFileSync(path.join(dir, 'resultado.json'), 'utf8'));
const defs = Object.fromEntries(Object.keys(r5.casos).map((id) => [id, { titulo: id }]));

test('11 pruebas Cypress no crean un problema QA falso', () => {
  assert.equal(problemaCypress({ status: 'failed', total_pruebas: 11, motivo: null }), null);
  assert.equal(problemaCypress({ status: 'failed', total_pruebas: 0, motivo: null }), '0 comprobaciones');
  const md = generarInforme(r5, defs);
  const seccion = md.split('## Problemas de automatización QA\n')[1].split('## Análisis de fallos')[0];
  assert.match(seccion, /Ninguno\./);
  assert.doesNotMatch(md, /ERROR_QA: Cypress: 0 comprobaciones/);
});

test('API y UI quedan en dos incidencias por defecto funcional', () => {
  const md = generarInforme(r5, defs);
  assert.match(md, /Incidencias funcionales observadas: 2/);
  assert.equal((md.match(/^### REF-G87-\d+/gm) ?? []).length, 2);
  assert.match(md, /REF-G87-01[\s\S]*API: valor 25\.0000[\s\S]*UI: tarjeta verde/);
  assert.match(md, /REF-G87-02[\s\S]*batería 77\.00 %[\s\S]*UI: tarjeta verde/);
});

test('la clasificación de ingestas concuerda en singular y plural', () => {
  const md = generarInforme(r5, defs);
  assert.match(md, /telemetría 116855 FUERA_DE_RANGO/);
  assert.match(md, /telemetría 116856 ERROR_CALIBRACION, 116857 ERROR_CALIBRACION/);
  assert.match(md, /TC-M03-177: ingesta 116855 clasificada FUERA_DE_RANGO/);
  assert.match(md, /TC-M03-178: ingestas 116856 y 116857 clasificadas ERROR_CALIBRACION/);
});

test('resumen y narrativas coinciden; mensajes crudos solo en anexo', () => {
  const md = generarInforme(r5, defs);
  const cuerpo = md.split('## Anexo técnico')[0];
  assert.match(cuerpo, /TC-M03-168 \| APROBADO/);
  assert.match(cuerpo, /TC-M03-177 \| RECHAZADO/);
  assert.match(cuerpo, /TC-M03-178 \| RECHAZADO/);
  assert.equal((cuerpo.match(/\*\*Qué se quería comprobar\.\*\*/g) ?? []).length, 3);
  assert.doesNotMatch(cuerpo, /expected .* to (deeply )?equal|AssertionError|\{\"ultimo_valor\"/);
  assert.match(md.split('## Anexo técnico')[1], /expected false to deeply equal true/);
  assert.doesNotMatch(cuerpo, /\.\./);
});

test('marcador cerrado solo con cierre y rollback comprobado', () => {
  assert.equal(estadoMarcador(r5.cierre), 'CERRADO');
  assert.equal(estadoMarcador({ run: { cierre_http: 200 }, rollback: { verificado: false } }), 'CIERRE_INTENTADO');
  assert.equal(estadoMarcador({ run: { cierre_http: null } }), 'PENDIENTE');
});

test('regeneración se niega a escribir dentro de Resultados', () => {
  const salida = path.join(grupo, 'Resultados', 'prohibido.md');
  assert.throws(() => regenerarInforme(run, salida), /fuera de Resultados/);
  assert.equal(fs.existsSync(salida), false);
});

test('incidencia confirmada exige responsable o escalamiento documentado', () => {
  assert.match(validarIncidencia({ confirmada: true }).join(' '), /sin responsable/);
  assert.match(validarIncidencia({ confirmada: true, responsable: 'POR DETERMINAR' }).join(' '), /escalamiento/);
  assert.deepEqual(validarIncidencia({ confirmada: true, responsable: 'POR DETERMINAR', escalamiento: { responsable_qa: 'responsable QA', evidencia_requerida: 'E1: IDs', faltantes: ['E1: IDs'] } }), []);
});

test('equipo ajeno e hipótesis sin rótulo se rechazan', () => {
  assert.match(validarIncidencia({ confirmada: true, responsable: 'Backend' }).join(' '), /equipo no permitido/);
  const asignacion = asignarAtencion(r5, 'TC-M03-177');
  const incidencia = { confirmada: true, responsable: 'Desarrollo', fundamento: asignacion.fundamento,
    evidencia_asignacion: asignacion.evidencia, verificacion: 'contrastar',
    contexto: { resultado: r5, caso: 'TC-M03-177' } };
  assert.match(validarIncidencia({ ...incidencia, hipotesis: 'quizás' }).join(' '), /hipótesis sin rótulo/);
  assert.deepEqual(validarIncidencia({ ...incidencia, hipotesis: 'HIPÓTESIS: pendiente' }), []);
});

test('E1–E3 reales permiten asignar la frontera API y citar sus datos', () => {
  for (const [caso, id] of [['TC-M03-177', '116855'], ['TC-M03-178', '116856']]) {
    const a = asignarAtencion(r5, caso);
    assert.equal(a.equipo, 'Desarrollo');
    assert.match(a.fundamento, /E1:.*E2:.*E3:/);
    assert.match(a.fundamento, new RegExp(id));
    assert.match(a.fundamento, /estado_calidad="LECTURA_VALIDA"/);
    assert.match(a.fundamento, /resultado\.json; newman\/newman-TC-M03-G87\.json/);
  }
});

test('API rechazada sin IDs o con PRE no aprobados exige escalamiento', () => {
  const sinIds = structuredClone(r5);
  sinIds.bitacora = [];
  const a = asignarAtencion(sinIds, 'TC-M03-177');
  assert.equal(a.equipo, 'POR DETERMINAR');
  assert.match(a.escalamiento.evidencia_requerida, /E1: IDs/);
  const fueraRun = structuredClone(r5);
  fueraRun.bitacora.forEach((x) => { x.en_run = false; });
  assert.match(asignarAtencion(fueraRun, 'TC-M03-177').escalamiento.evidencia_requerida, /E1: IDs/);
  const preFallido = structuredClone(r5);
  preFallido.comprobaciones.find((x) => x.id === 'PRE-177-02').estado = 'RECHAZADO';
  assert.match(asignarAtencion(preFallido, 'TC-M03-177').escalamiento.evidencia_requerida, /E1: PRE/);
});

test('API aprobada y UI rechazada con captura asigna interfaz', () => {
  const soloUi = structuredClone(r5);
  soloUi.comprobaciones.find((x) => x.id === 'API-177-03').estado = 'APROBADO';
  assert.match(asignarAtencion(soloUi, 'TC-M03-177').escalamiento.evidencia_requerida, /UI: observado concreto/);
  soloUi.comprobaciones.find((x) => x.id === 'UI-177-03').observado_pantalla = 'tarjeta verde Normal, sin indicador de anomalía';
  const a = asignarAtencion(soloUi, 'TC-M03-177');
  assert.equal(a.equipo, 'Desarrollo');
  assert.match(a.fundamento, /^UI: API API-177/);
  assert.match(a.fundamento, /cypress\/.*\.png/);
});

test('UI rechazada sin captura ni detalle exige escalamiento', () => {
  const soloUi = structuredClone(r5);
  soloUi.comprobaciones.find((x) => x.id === 'API-177-03').estado = 'APROBADO';
  soloUi.comprobaciones.find((x) => x.id === 'UI-177-03').obtenido = 'pantalla Normal';
  soloUi.comprobaciones.find((x) => x.id === 'UI-177-03').observado_pantalla = 'pantalla Normal';
  soloUi.evidencias = soloUi.evidencias.filter((x) => !x.startsWith('cypress/'));
  const a = asignarAtencion(soloUi, 'TC-M03-177');
  assert.equal(a.equipo, 'POR DETERMINAR');
  assert.match(a.escalamiento.evidencia_requerida, /UI: captura real o detalle/);
});

test('componente DBA necesita verificación y evidencia existente', () => {
  const base = { casos: { 'TC-M03-177': { estadoIngesta: 'FUERA_DE_RANGO', componente_confirmado: 'DBA', estado_verificacion: 'VERIFICADO' } } };
  assert.notEqual(asignarAtencion(r5, 'TC-M03-177', { triaje: base }).equipo, 'DBA');
  const temporal = fs.mkdtempSync(path.join(grupo, 'pruebas', '.evidencia-'));
  try {
    const registro = 'Registro sintético: defecto SQL confirmado';
    fs.writeFileSync(path.join(temporal, 'registro.txt'), registro);
    base.casos['TC-M03-177'].evidencia_componente = { ruta: 'registro.txt', registro };
    assert.equal(asignarAtencion(r5, 'TC-M03-177', { triaje: base, baseDir: temporal }).equipo, 'DBA');
  } finally {
    fs.rmSync(path.join(temporal, 'registro.txt'));
    fs.rmdirSync(temporal);
  }
});

test('validarIncidencia rechaza equipo sin fundamento verificable', () => {
  const a = asignarAtencion(r5, 'TC-M03-177');
  const x = { confirmada: true, responsable: 'Desarrollo', fundamento: a.fundamento, evidencia_asignacion: a.evidencia,
    verificacion: 'contrastar', contexto: { resultado: r5, caso: 'TC-M03-177' } };
  assert.deepEqual(validarIncidencia(x), []);
  assert.match(validarIncidencia({ ...x, fundamento: 'API rechazada' }).join(' '), /sin fundamento verificable/);
  assert.match(validarIncidencia({ ...x, contexto: undefined }).join(' '), /sin fundamento verificable/);
});

test('sin datos de triaje no se inventan hipótesis', () => {
  const md = generarInforme(r5, defs, { triaje: { casos: {} } });
  assert.doesNotMatch(md, /\*\*Causa probable — HIPÓTESIS:/);
  assert.match(md, /causa raíz NO CONFIRMADA/);
});
