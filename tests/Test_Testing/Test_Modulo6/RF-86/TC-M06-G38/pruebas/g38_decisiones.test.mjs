import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import { resolverMatriz, truncar2, redondear2, estructuraLineas, predecirComponentes } from '../lib/g38_core.mjs';
import { oraculo014, oraculo015, predecir, buscarPeso, buscarCombinacion } from '../g38.mjs';

const matriz=[
  {tipo_hecho:'VARIACION_VR_TB',sentido:'GANANCIA',id_especie:null,subtipo_costo:null,cuenta_debito:'158405',cuenta_credito:'424805'},
  {tipo_hecho:'VARIACION_VR_PM',sentido:'PERDIDA',id_especie:null,subtipo_costo:null,cuenta_debito:'539505',cuenta_credito:'158405'}];
const base={fecha_hecho:'2026-11-08',id_periodo_contable:8,id_activo_biologico:944,id_especie:39,id_finca:5,
  numero_id_tributaria:'900000001',es_estimacion:false,estado:'REGISTRADA'};
const v=[{tipo:'GANANCIA_TRANSFORMACION_BIOLOGICA',id_variacion_valor_razonable:256},
  {tipo:'PERDIDA_PRECIO_MERCADO',id_variacion_valor_razonable:257}];
const m={ganancia_perdida_transformacion:'272615.0499',ganancia_perdida_precio_mercado:'-53805.6059'};
const l=[{...base,id_linea_asiento_nic41:903,id_origen:256,tipo_hecho:'VARIACION_VR_TB',sentido:'GANANCIA',valor:272615.04,
  cuenta_debito:'158405',cuenta_credito:'424805'},
  {...base,id_linea_asiento_nic41:904,id_origen:257,tipo_hecho:'VARIACION_VR_PM',sentido:'PERDIDA',valor:53805.60,
    cuenta_debito:'539505',cuenta_credito:'158405'}];
test('matriz por especie precede a genérica y falta par bloquea',()=>{
  assert.equal(resolverMatriz(matriz,'VARIACION_VR_TB','GANANCIA',39).cuenta_debito,'158405');
  assert.equal(resolverMatriz(matriz,'VARIACION_VR_TB','PERDIDA',39),null);
  assert.equal(resolverMatriz([...matriz,{...matriz[0],id_especie:39,cuenta_debito:'150000'}],
    'VARIACION_VR_TB','GANANCIA',39).cuenta_debito,'150000');
});
test('014 reconoce el par y rechaza PM redondeada',()=>{
  assert.equal(oraculo014({variaciones:v,medicion:m,lineas:l,matriz,especie:39}).estado,'APROBADO');
  assert.equal(oraculo014({variaciones:v,medicion:m,lineas:[l[0],{...l[1],valor:53805.61}],matriz,especie:39}).estado,'RECHAZADO');
});
test('015 distingue truncado de redondeo e identidad',()=>{
  assert.equal(truncar2('1234567.899'),'1234567.89');assert.equal(redondear2('1234567.899'),'1234567.90');
  assert.equal(oraculo015({antes:[],despues:[l[0]],nuevas:[l[0]],
    medicion:{ganancia_perdida_transformacion:'272615.0499'},lineaTB:l[0]}).estado,'APROBADO');
  assert.equal(oraculo015({antes:[],despues:[{...l[0],valor:272615.05}],nuevas:[{...l[0],valor:272615.05}],
    medicion:{ganancia_perdida_transformacion:'272615.0499'},lineaTB:{...l[0],valor:272615.05}}).estado,'RECHAZADO');
  assert.ok(estructuraLineas([], [l[0],{...l[0]}],[l[0]]).some(x=>x.includes('duplicado')));
  assert.ok(estructuraLineas([l[0]],[{...l[0],id_linea_asiento_nic41:905}],[]).some(x=>x.includes('desapareció')));
});
test('predictor cuantiza cada costo y busca tercer decimal discriminante',()=>{
  const p=predecir('950.00','110.01',{magnitud:'100.00',valor_neto:'90000.0000'},
    {pct_transporte:'0.01',pct_comisiones:'0.02',pct_impuestos:'0.00'});
  assert.match(p.tb,/^-?\d+\.\d{4}$/);
  const x=buscarPeso('950.00','110.00',{magnitud:'100.00',valor_neto:'90000.0000'},
    {pct_transporte:'0.01',pct_comisiones:'0.02',pct_impuestos:'0.00'});
  assert.ok(x);assert.notEqual(truncar2(x.prediccion.tb),redondear2(x.prediccion.tb));
});
const archivoDatos=new URL('./predictor_datos_reales.json',import.meta.url);
test('predictor_datos_reales',()=>{
  const datos=JSON.parse(fs.readFileSync(archivoDatos,'utf8'));
  assert.equal(datos.calculos.length,10);assert.equal(datos.mediciones.length,5);
  const calculos=new Map(datos.calculos.map(c=>[c.id,c]));
  for(const c of datos.calculos){
    const p=predecirComponentes({magnitud_anterior:c.magnitud,magnitud_actual:c.magnitud,
      precio_unitario:c.precio_unitario,valor_neto_anterior:'0',...datos.parametro_costos_venta});
    for(const [campo,esperado] of Object.entries({bruto:c.bruto,transporte:c.transporte,
      comisiones:c.comisiones,impuestos:c.impuestos,neto:c.valor_neto}))
      assert.equal(p[campo],esperado,`cálculo ${c.id}: ${campo}`);
  }
  for(const m of datos.mediciones){
    const anterior=calculos.get(m.calc_anterior),actual=calculos.get(m.calc_actual);
    assert.equal(anterior.activo,m.activo);assert.equal(actual.activo,m.activo);
    const p=predecirComponentes({magnitud_anterior:anterior.magnitud,magnitud_actual:actual.magnitud,
      precio_unitario:actual.precio_unitario,valor_neto_anterior:anterior.valor_neto,
      hubo_evento:m.hubo_evento,...datos.parametro_costos_venta});
    assert.equal(p.tb,m.tb,`medición ${m.id}: TB`);
    assert.equal(p.pm,m.pm,`medición ${m.id}: PM`);
    assert.equal(p.neto,actual.valor_neto,`medición ${m.id}: neto`);
  }
});
test('ejemplo del orquestador y búsqueda discriminante con datos reales',()=>{
  const datos=JSON.parse(fs.readFileSync(archivoDatos,'utf8'));
  const anterior=datos.calculos.find(c=>c.id===26);
  const p=predecir('9612.37','351.37',{magnitud:anterior.magnitud,valor_neto:anterior.valor_neto},
    datos.parametro_costos_venta);
  assert.equal(p.tb,'57556.9491');assert.equal(p.pm,'101301.5910');
  assert.equal(truncar2(p.tb),'57556.94');assert.equal(redondear2(p.tb),'57556.95');
  const x=buscarCombinacion('9300.00','345.00',
    {magnitud:anterior.magnitud,valor_neto:anterior.valor_neto},datos.parametro_costos_venta);
  assert.ok(x);assert.match(x.precio,/\.\d{2}$/);assert.notEqual(x.precio.split('.')[1],'00');
  assert.ok(Number(x.precio)>=8835&&Number(x.precio)<=9765);
  assert.ok(Number(x.peso)>=348.45&&Number(x.peso)<=362.25);
  assert.ok(BigInt(x.prediccion.tb.replace('.',''))>0n);
  assert.ok(BigInt(x.prediccion.pm.replace('.',''))<0n);
  assert.notEqual(truncar2(x.prediccion.tb),redondear2(x.prediccion.tb));
  assert.equal(buscarCombinacion('1.00','0.01',
    {magnitud:'0.01',valor_neto:'0.0000'},datos.parametro_costos_venta),null);
});
