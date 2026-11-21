import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {contexto,CAPACIDADES} from '../g43.mjs';
import {informe} from '../lib/informe.mjs';
import {esquema,instrumentar} from '../lib/contrato.mjs';

const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g43-v2-local-'));
const runId='RUN-G43-V2-20261112-000000',dir=path.join(tmp,runId);
fs.mkdirSync(dir);
const archivo=path.join(dir,'contexto_operacion.json');
const base={grupo:'G43',run_id:runId,version:2,intento:1,operacion:'REEVALUAR',referencia:'LOCAL',version_anterior:1,casos:CAPACIDADES.casos,alcance_reevaluacion:{casos:CAPACIDADES.casos}};
const args=operacion=>['--operacion',operacion.toLowerCase(),'--version','2','--intento','1','--run-id',runId,'--autorizacion','LOCAL','--contexto',archivo];
function validarCapacidades(cap){
  assert.deepEqual(Object.keys(cap.comprobaciones_obligatorias).sort(),[...cap.casos].sort());
  for(const fuentes of Object.values(cap.comprobaciones_obligatorias)){
    assert.deepEqual(Object.keys(fuentes).sort(),['API','UI']);
    for(const [fuente,ids] of Object.entries(fuentes)){
      assert(Array.isArray(ids)&&ids.length>0,`${fuente}: lista obligatoria vacía`);
      for(const id of ids)assert(new RegExp(`^G43-${fuente}-\\d{3}-\\d{2}$`).test(id),`${fuente}: ID inválido ${id}`);
    }
  }
}
try{
  const cli=spawnSync(process.execPath,[path.resolve('g43.mjs'),'--capacidades'],{encoding:'utf8',windowsHide:true});
  if(cli.error?.code!=='EPERM'){
    assert.ifError(cli.error);
    assert.equal(cli.status,0,cli.stderr);
    validarCapacidades(JSON.parse(cli.stdout));
  }else validarCapacidades(CAPACIDADES);
  assert.deepEqual(CAPACIDADES.comprobaciones_obligatorias['TC-M06-024'].UI,['G43-UI-027-01']);
  const invalido=structuredClone(CAPACIDADES);
  invalido.comprobaciones_obligatorias['TC-M06-024'].UI=[];
  assert.throws(()=>validarCapacidades(invalido),/lista obligatoria vacía/);
  invalido.comprobaciones_obligatorias['TC-M06-024'].UI=['G43-UI-27-01'];
  assert.throws(()=>validarCapacidades(invalido),/ID inválido/);
  fs.writeFileSync(archivo,JSON.stringify(base));
  assert.equal(contexto(args('REEVALUAR'),true).version,2);
  fs.writeFileSync(archivo,JSON.stringify({...base,operacion:'REINTENTAR'}));
  assert.equal(contexto(args('REINTENTAR'),true).version,2);
  fs.writeFileSync(archivo,JSON.stringify({...base,operacion:'REINTENTAR',alcance_reevaluacion:{casos:CAPACIDADES.casos.slice(0,3)}}));
  assert.throws(()=>contexto(args('REINTENTAR'),true),/ALCANCE_REEVALUACION/);
  assert(esquema('POST','/finanzas/periodos/8/cierre/cancelacion'));
  assert(esquema('GET','/notificaciones?pagina=1&tamano=50'));
  assert.deepEqual(esquema('POST','/finanzas/periodos/266/cierre').cuerpo.activos_estimados,['integer']);
  const congelado={id_especie:[39,false],id_precio_mercado:100,precio_unitario:'10000',fuente:'MERCADO_ACTIVO',fecha_vigencia:'2026-11-09'};
  const def=esquema('GET','/finanzas/periodos');
  assert.equal(def.respuesta[0].ultimo_cierre.precios_congelados[0].id_especie,'integer|especie_estimacion');
  const forma=def.respuesta[0].ultimo_cierre.precios_congelados[0];
  assert.deepEqual(instrumentar(congelado,forma).id_especie,[39,false]);
  assert.equal(instrumentar({...congelado,id_especie:39},forma).id_especie,39);
  assert.throws(()=>instrumentar({...congelado,id_especie:[39,'false']},forma).id_especie,/TIPO_INVALIDO/);
  const casos=Object.fromEntries(CAPACIDADES.casos.map(x=>[x,{estado:'APROBADO',motivo:'Criterios conformes',comprobaciones:[]}]));
  const r={grupo:'G43',run_id:runId,version:2,rf:'RF-87 v1.2',autorizacion_referencia:'LOCAL',casos,precios:[],activos:[],lineas:[],cypress:{paneles:{}},incidencias:[],herramientas:{node:process.version},evidencias:[],problemas_tecnicos:[],rollback:{verificado:true},oficial:true,condiciones_oficialidad:{cuatro_casos:true}};
  assert(informe(r).startsWith('# TC-M06-G43 — reevaluación V2 oficial - APROBADO'));
  assert(informe({...r,casos:{...casos,'TC-M06-026':{...casos['TC-M06-026'],estado:'RECHAZADO'} }}).startsWith('# TC-M06-G43 — reevaluación V2 oficial - RECHAZADO'));
  assert(informe({...r,oficial:false}).startsWith('# TC-M06-G43 — reevaluación V2 NO OFICIAL'));
  console.log('OK g43_v2_local: alcance, rutas, contrato y títulos');
}finally{assert(path.resolve(tmp).startsWith(path.resolve(os.tmpdir())+path.sep));fs.rmSync(tmp,{recursive:true,force:true});}
