import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {CAPACIDADES,contexto} from '../g43.mjs';
import {esquema,instrumentar} from '../lib/contrato.mjs';
import {evaluarEstimacion1644} from '../lib/evidencia_estimacion.mjs';
import {informe} from '../lib/informe.mjs';
import {clasificarFallo} from '../lib/infra.mjs';

const runId='RUN-G43-V3-20261113-000000';
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g43-v3-'));
try{
  const dir=path.join(tmp,runId);fs.mkdirSync(dir);
  const archivo=path.join(dir,'contexto_operacion.json');
  const base={grupo:'G43',run_id:runId,version:3,intento:1,operacion:'REEVALUAR',referencia:'LOCAL',version_anterior:2,casos:CAPACIDADES.casos,alcance_reevaluacion:{casos:CAPACIDADES.casos}};
  const args=op=>['--operacion',op,'--version','3','--intento','1','--run-id',runId,'--autorizacion','LOCAL','--contexto',archivo];
  fs.writeFileSync(archivo,JSON.stringify(base));assert.equal(contexto(args('reevaluar'),true).version,3);
  fs.writeFileSync(archivo,JSON.stringify({...base,operacion:'REINTENTAR'}));assert.equal(contexto(args('reintentar'),true).version,3);
  fs.writeFileSync(archivo,JSON.stringify({...base,version_anterior:1}));assert.throws(()=>contexto(args('reevaluar'),true),/ALCANCE_REEVALUACION/);

  const forma=esquema('GET','/finanzas/periodos').respuesta[0].ultimo_cierre.precios_congelados[0];
  const viejo={id_especie:[39,false],id_precio_mercado:18,precio_unitario:'9600',fuente:'MERCADO_ACTIVO',fecha_vigencia:'2026-11-07'};
  const nuevo={...viejo,id_especie:39,estimacion:false,categoria:'PESO_KG',unidad_medida:'KG',fecha_vencimiento:null,id_metrica_produccion:null};
  assert.equal(instrumentar(viejo,forma).id_precio_mercado,18);
  assert.equal(instrumentar(nuevo,forma).estimacion,false);
  assert.equal(instrumentar(null,esquema('GET','/finanzas/periodos').respuesta[0].ultimo_cierre.precios_congelados,[],'respuesta[0].ultimo_cierre.precios_congelados'),null);
  assert.equal(nuevo.id_precio_mercado===18&&nuevo.id_precio_mercado!==900,true,'024: congelado inicial tras precio nuevo');
  assert.equal({...nuevo,id_precio_mercado:900}.id_precio_mercado===18,false,'024: recongelado antiguo incumple');

  const cierreForma=esquema('POST','/finanzas/periodos/267/cierre').respuesta.activos_estimados;
  const objeto={id_activo_biologico:1644,identificador:'A-1644',id_medicion:791,id_precio_mercado:492,precio_unitario:'1000000',fecha_vigencia:'2026-10-01'};
  assert.equal(instrumentar([objeto],cierreForma)[0].id_medicion,791);
  assert.equal(instrumentar([1644],cierreForma)[0],1644);
  assert.throws(()=>instrumentar([{...objeto,id_precio_mercado:'492'}],cierreForma)[0],/TIPO_INVALIDO/);
  const congelado={id_especie:544,estimacion:true,id_precio_mercado:492,precio_unitario:'1000000'};
  const comun={precio492:'1000000',congelados:[congelado],cierre:{id_cierre:267,activos_procesados:1,activos_estimados:[]},calculos:[],auditoria:[],avisos:[]};
  const respuesta=evaluarEstimacion1644({...comun,cierre:{...comun.cierre,activos_estimados:[objeto]}});
  assert.equal(respuesta.vias.respuesta,true);assert.deepEqual(respuesta.evidencia_vias.respuesta,{id_cierre:267,id_activo_biologico:1644,id_medicion:791,id_precio_mercado:492});
  const auditoria=evaluarEstimacion1644({...comun,auditoria:[{tipo_evento:'MEDICION_CON_ESTIMACION',id_activo_biologico:1644,id_referencia:791,payload_evento:{precio_usado:{id_precio_mercado:492,precio_unitario:'1000000'}}}]});
  assert.equal(auditoria.vias.auditoria,true);assert.equal(auditoria.evidencia_vias.auditoria.id_referencia,791);
  const calculo=evaluarEstimacion1644({...comun,calculos:[{id_calculo_valor_razonable:991,id_activo_biologico:1644,tiene_valor_estimado:true,precio_unitario:'1000000'}]});
  assert.equal(calculo.vias.calculo,true);assert.equal(calculo.evidencia_vias.calculo.id_calculo,991);
  const alerta=evaluarEstimacion1644({...comun,avisos:[{id:17,texto:'PRECIO_ESTIMADO activo A-1644'}]});assert.equal(alerta.vias.alerta,true);assert.equal(alerta.evidencia_vias.alerta.id_aviso,17);
  const formaVieja=evaluarEstimacion1644({...comun,congelados:[{...congelado,id_especie:[544,true],estimacion:undefined}],cierre:{...comun.cierre,activos_estimados:[1644]}});assert.equal(formaVieja.vias.respuesta,true);
  assert.equal(evaluarEstimacion1644({...comun,congelados:[{...congelado,id_precio_mercado:900}]}).acreditada,false);
  const casos=Object.fromEntries(CAPACIDADES.casos.map(c=>[c,{estado:'APROBADO',motivo:'Criterios conformes',comprobaciones:[]}]));
  const r={grupo:'G43',version:3,rf:'RF-87',run_id:runId,autorizacion_referencia:'LOCAL',casos,precios:[],activos:[],lineas:[],cypress:{paneles:{}},incidencias:[],herramientas:{node:process.version},evidencias:[],problemas_tecnicos:[],rollback:{verificado:true},oficial:true,seguimiento:{'INC-M06-G43-03':'CORREGIDA','INC-M06-G43-05':'CORREGIDA'}};
  assert(informe(r).startsWith('# TC-M06-G43 — reevaluación V3 oficial - APROBADO'));
  assert(informe({...r,casos:{...casos,'TC-M06-024':{...casos['TC-M06-024'],estado:'RECHAZADO'}}}).startsWith('# TC-M06-G43 — reevaluación V3 oficial - RECHAZADO'));
  assert(informe({...r,oficial:false}).startsWith('# TC-M06-G43 — reevaluación V3 NO OFICIAL'));
  assert(informe(r).includes('INC-M06-G43-05: CORREGIDA'));
  assert.equal(clasificarFallo({consume_version:false,cierre:{run:{cierre_http:200},rollback:{verificado:true}},problemas_tecnicos:['PREFLIGHT_DATOS_NO_CONCLUYENTE']}),'DATOS_PRECONDICION');
  console.log('OK g43_v3_local: contexto, contrato, 024 y cuatro vías 026');
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
