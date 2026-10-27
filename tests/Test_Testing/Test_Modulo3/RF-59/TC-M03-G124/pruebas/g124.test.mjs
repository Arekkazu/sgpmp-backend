import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { CASOS, CAPACIDADES, clasificarExportacion, clasificarVolumen, ruta } from '../lib/g124_escenario.mjs';
import { validarPdf, validarExcel, xlsxSheets } from '../validadores.mjs';
import { validarObligatorias } from './registro_qa.mjs';
import { pdfSintetico, excelSintetico } from './fixtures.mjs';
import { seleccionarConsulta } from '../g124.mjs';

const meta = { inicio: '2026-10-25', fin: '2026-10-26', sensorId: 73,
  campos: ['id_sensor', 'timestamp_captura', 'valor'] };
test('catálogo, capacidades y rutas solo GET con filtros', () => {
  assert.deepEqual(CASOS, ['TC-M03-249', 'TC-M03-250', 'TC-M03-254']);
  assert.deepEqual(validarObligatorias(CAPACIDADES), CAPACIDADES.comprobaciones_obligatorias);
  assert.match(ruta('PDF', meta), /formato=PDF.*sensor_id=73/);
  assert.match(ruta('EXCEL', meta), /incluir_alertas=true/);
  const col = JSON.parse(fs.readFileSync(new URL('../G124.postman_collection.json', import.meta.url)));
  assert.equal(col.item.length, 3);
  assert.ok(col.item.every(x => x.request.method === 'GET'));
});
test('PDF y Excel sintéticos se inspeccionan y sus defectos se distinguen', () => {
  assert.ok(Object.values(validarPdf(pdfSintetico(), meta).checks).every(Boolean));
  assert.equal(validarPdf(pdfSintetico({ incompleto: true }), meta).checks.grafica_tendencia, false);
  assert.equal(validarPdf(Buffer.from('sin PDF'), meta).verificable, false);
  assert.equal(xlsxSheets(excelSintetico()).length, 3);
  assert.ok(Object.values(validarExcel(excelSintetico(), meta).checks).every(Boolean));
  assert.equal(validarExcel(excelSintetico({ sinHojas: true }), meta).checks.tres_hojas, false);
});
test('503 M08 bloquea; 200 exige archivo y estructura; 500 genérico contradice E5', () => {
  const dep = clasificarExportacion({ http: 503, eco: true,
    error: { codigo: 'M08_NO_DISPONIBLE', mensaje: 'No disponible' } }, 'PDF');
  assert.equal(dep.estado, 'BLOQUEADO');
  assert.equal(dep.subtipo, 'REQUISITO_DEPENDIENTE');
  assert.equal(clasificarVolumen(dep, dep, 1).estado, 'BLOQUEADO');
  assert.equal(clasificarExportacion({ http: 200, eco: true, bytes: pdfSintetico(),
    validacion: validarPdf(pdfSintetico(), meta) }, 'PDF').estado, 'APROBADO');
  assert.equal(clasificarExportacion({ http: 200, eco: true, bytes: Buffer.alloc(0) }, 'PDF').estado, 'RECHAZADO');
  assert.equal(clasificarExportacion({ http: 200, eco: true, bytes: Buffer.from('error'),
    validacion: { verificable: false, motivo: 'PDF inválido o incompleto' } }, 'PDF').estado, 'RECHAZADO');
  assert.equal(clasificarExportacion({ http: 400, eco: true,
    error: { codigo: 'EXPORTAR_SIN_FILTROS', mensaje: 'Falta filtro' } }, 'PDF').estado, 'RECHAZADO');
  assert.equal(clasificarExportacion({ http: 500, eco: true,
    error: { codigo: 'ERROR_INTERNO', mensaje: 'Error interno' } }, 'PDF').estado, 'RECHAZADO');
  assert.equal(clasificarExportacion({ http: null, eco: false }, 'EXCEL').estado, 'NO_CONCLUYENTE');
  assert.equal(clasificarVolumen({ estado: 'APROBADO' }, { estado: 'APROBADO' }, 1).estado, 'NO_CONCLUYENTE');
});
test('selección sin datos agota el alcance acotado sin semilla manual', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async url => {
    const path = new URL(url).pathname;
    const body = path.endsWith('/historial') ? { total: 0, items: [] }
      : path.endsWith('/dashboard') ? { total: 0, sensores: [], resumen_unidades: [] }
        : { total: 0, sensores: [] };
    return new Response(JSON.stringify(body), { status: 200, headers: { 'x-test-run-id': 'LOCAL' } });
  };
  try {
    const r = { bitacora: [] }, presupuesto = { directas: 0, inicio: Date.now() };
    const s = await seleccionarConsulta('http://127.0.0.1:1', 'TOKEN_SINTETICO',
      { QA_SANDBOX_SECRET: 'SINTETICO' }, { runId: 'LOCAL' }, r, presupuesto);
    assert.equal(s, null);
    assert.deepEqual(r.diagnostico_seleccion.intentos.map(x => x.total), [0, 0]);
    assert.deepEqual(r.diagnostico_seleccion.unidades.map(x => x.id_infraestructura), [1, 268, 337]);
    assert.equal(presupuesto.directas, 6);
    assert.ok(r.bitacora.every(x => x.en_run && x.eco));
  } finally { globalThis.fetch = original; }
});
