import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { CASOS, exportPath, classifyExport, volumePlan, fragmentInfo, volumeCountSql, safeFragmentPath } from './ejecutar_tc_m03_g124.mjs';
import { pdfText, validarPdf, xlsxSheets, validarExcel, dataRows, volumen, RAW_FIELDS } from './validadores.mjs';
import { verdict } from '../TC-M03-G120/rf59_base.mjs';

const meta={granja:'Granja QA',inicio:'2026-10-01',fin:'2026-10-02',filtros:['sensor'],usuario:'Juan'};
test('catálogo y endpoint de exportación oficial',()=>{
  assert.deepEqual(CASOS,['TC-M03-249','TC-M03-250','TC-M03-254']);
  assert.match(exportPath('EXCEL',{fecha_inicio:meta.inicio,fecha_fin:meta.fin,sensor_id:7}),/^\/iot\/monitoreo\/historial\/exportar\?/);
  assert.throws(()=>exportPath('CSV',{}));
});
test('PDF sintético prueba el parser sin declarar cumplimiento del producto',()=>{
  const content='(Granja QA 2026-10-01 2026-10-02 filtros sensor Juan Tendencia Registro Semaforo Resumen estadistico Generado 2026-10-17) Tj 0 0 m 1 1 l 2 2 l 3 3 l S';
  const pdf=Buffer.from(`%PDF-1.4\n1 0 obj << /Type /Page >> endobj\nstream\n${content}\nendstream\n%%EOF`,'latin1');
  assert.equal(pdfText(pdf).verificable,true);
  assert.ok(Object.values(validarPdf(pdf,meta).checks).every(Boolean));
  assert.equal(validarPdf(Buffer.from('bad'),meta).verificable,false);
});
test('XLSX sintético prueba hojas, metadatos y recuento',()=>{
  const code=`from openpyxl import Workbook
from io import BytesIO
import sys
w=Workbook(); a=w.active;a.title='Datos crudos';b=w.create_sheet('Resumen estadistico');c=w.create_sheet('Alertas correlacionadas')
for s in (a,b,c):s.append(['Granja QA 2026-10-01 2026-10-02 Juan filtros sensor'])
a.append(${JSON.stringify(RAW_FIELDS)});a.append([7]*len(${JSON.stringify(RAW_FIELDS)}))
b.append(['variable','resumen','minimo','maximo','promedio','total']);c.append(['alerta','correlacion'])
o=BytesIO();w.save(o);sys.stdout.buffer.write(o.getvalue())`;
  const p=spawnSync('python',['-c',code],{encoding:null,maxBuffer:2_000_000});
  assert.equal(p.status,0,String(p.stderr));
  const sheets=xlsxSheets(p.stdout);
  assert.equal(sheets.length,3);
  assert.equal(dataRows(sheets[0]),1);
  assert.ok(Object.values(validarExcel(p.stdout,meta).checks).every(Boolean));
});
test('umbrales 5000/5001 y 50000/50001 conservan fragmentación y aviso',()=>{
  const plan=volumePlan(Date.UTC(2026,9,17));
  assert.equal(plan.counts.reduce((a,b)=>a+b,0),50001);
  assert.deepEqual(plan.targets.map(x=>plan.counts.slice(0,x.end+1).reduce((a,b)=>a+b,0)),[5000,5001,50000,50001]);
  assert.match(volumeCountSql(7,plan.dates[0],plan.dates[11]),/id_sensor=7/);
  assert.throws(()=>volumeCountSql(7,"x' OR 1=1",plan.dates[11]));
  assert.deepEqual(volumen('PDF',5000,[5000],false),{dentro:true,completo:true,fragmentado:true,aviso:true});
  assert.equal(volumen('PDF',5001,[5000,1],true).fragmentado,true);
  assert.equal(volumen('PDF',5001,[5001],true).fragmentado,false);
  assert.equal(volumen('EXCEL',50000,[50000],false).completo,true);
  assert.equal(volumen('EXCEL',50001,[50000,1],false).aviso,false);
  assert.equal(volumen('EXCEL',50001,[50000,1],true).fragmentado,true);
  assert.deepEqual(fragmentInfo({headers:{'content-type':'application/json'},bytes:Buffer.from(JSON.stringify({fragmentos:[{registros:50000},{registros:1}],aviso:'Volumen supera límite'}))}).sizes,[50000,1]);
  const api='https://www.api.inmero.co/api-sgpmp-test';
  assert.equal(safeFragmentPath(`${api}/export/a.pdf`,api),'/export/a.pdf');
  assert.equal(safeFragmentPath('export/a.pdf',api),'/export/a.pdf');
  assert.equal(safeFragmentPath('https://www.api.inmero.co/sigab/export/a.pdf',api),null);
  assert.equal(safeFragmentPath('https://www.api.inmero.co/api-sgpmp-dev/export/a.pdf',api),null);
});
test('M08 503 bloquea y no se convierte en aprobación',()=>{
  const unavailable={status:503,bytes:Buffer.from('{"detail":{"code":"M08_NO_DISPONIBLE"}}')};
  assert.equal(classifyExport(unavailable,'PDF').kind,'DEPENDENCIA_M08');
  assert.equal(verdict('CONCLUIDA',[{ok:false}],[],true),'BLOQUEADO');
});
