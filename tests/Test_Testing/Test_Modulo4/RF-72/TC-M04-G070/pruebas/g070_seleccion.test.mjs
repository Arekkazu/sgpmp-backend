import assert from 'node:assert/strict';
import fs from 'node:fs';
import {elegir,PRESUPUESTO} from '../lib/g070_core.mjs';

const fixture=JSON.parse(fs.readFileSync(new URL('./semilla_observada_G070_V2.json',import.meta.url),'utf8'));
const ahora=Date.parse(fixture.hora_descubrimiento);
const inferencias=fixture.semilla_observada.map(x=>({tipo_evento:'INFERENCIA',
  id_activo_biologico:885,id_resultado_inferencia:x.id,fecha_evento:x.fecha,
  payload:{tipo_modelo:'MODELO_ESPECIES_MEDIANAS'}}));
const id=x=>x?.id_resultado_inferencia;
const seleccionado=elegir(inferencias,91,{},ahora);
const de215=new Set(['d89','d90','d90h','d91'].map(k=>id(seleccionado[k])));
const candidatos=new Set(fixture.semilla_observada.filter(x=>x.dias_backend>91).map(x=>x.id));
assert.equal(PRESUPUESTO.dias_busqueda>=125,true);
assert.equal(seleccionado.d91.antiguedad.dias_backend,91);
assert.equal(seleccionado.d120a.antiguedad.dias_backend,93);
assert.equal(seleccionado.d120b.antiguedad.dias_backend,93);
for(const k of ['d120a','d120b']){
  assert.ok(candidatos.has(id(seleccionado[k])),`${k} vencido de la semilla real`);
  assert.ok(!de215.has(id(seleccionado[k])),`${k} distinto de 215`);
}
assert.notEqual(id(seleccionado.d120a),id(seleccionado.d120b));
assert.equal(id(seleccionado.d120a),'7d597a54-2d05-43d6-a12b-ad8a7c8ac4ff');
assert.equal(id(seleccionado.d120b),'fb07d478-2993-45a0-8636-02e62fd22c82');

const antiguo={tipo_evento:'INFERENCIA',id_activo_biologico:885,id_resultado_inferencia:'local-122',
  fecha_evento:new Date(ahora-122*86400000).toISOString(),payload:{tipo_modelo:'MODELO_ESPECIES_MEDIANAS'}};
const conAntiguo=elegir([...inferencias,antiguo],91,{},ahora);
assert.equal(id(conAntiguo.d120a),antiguo.id_resultado_inferencia);
assert.equal(id(conAntiguo.d120b),id(seleccionado.d120a));

const ocupado={tipo_evento:'RETROALIMENTACION',id_resultado_inferencia:id(seleccionado.d120a)};
const alternativa=elegir([...inferencias,ocupado],91,{},ahora);
assert.equal(id(alternativa.d120a),id(seleccionado.d120b));
assert.equal(id(alternativa.d120b),'ac952c1d-5574-4223-92ab-2df8a8ac9e32');
const sinDos=elegir([...inferencias,ocupado,
  {tipo_evento:'RETROALIMENTACION',id_resultado_inferencia:id(seleccionado.d120b)}],91,{},ahora);
assert.ok(sinDos.d120a);
assert.equal(sinDos.d120b,undefined);
console.log('OK G070 selección: semilla observada, vencidos libres, exclusión de 215 y faltante técnico');
