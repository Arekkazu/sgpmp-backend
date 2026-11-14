import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {CAPACIDADES,contexto,ejecutar} from '../g45.mjs';
import {validarFormaResultado} from '../lib/infra.mjs';
import {simuladorG45} from './simulador_g45.mjs';
import {ejecutar as ejecutarNewman} from './newman_hijo.mjs';

const base=path.dirname(fileURLToPath(import.meta.url));
const config=JSON.parse(fs.readFileSync(path.join(base,'escenarios_g45.json'),'utf8'));
const salidas=process.env.QA_VERIFICAR_SALIDAS??fs.mkdtempSync(path.join(os.tmpdir(),'g45-escenarios-'));
fs.mkdirSync(salidas,{recursive:true});
let total=0;
{
  const sim=await simuladorG45('266_pausable');
  try{
    const z=await fetch(sim.url+'/activos-biologicos/1644/eventos/crecimiento',{method:'POST',headers:{authorization:'Bearer ADMIN_LOCAL','content-type':'application/json'},body:JSON.stringify({tipo_medicion:'PESO',valor_medicion:'30',unidad_medida:'kg',fecha:new Date().toISOString()})});
    assert.equal(z.status,422,'Un lote sin campos poblacionales debe recibir 422');
    assert.equal((await z.json()).error_code,'LOTE_INCOMPLETO');
  }finally{await sim.cerrar();}
}
for(const modo of config.escenarios)for(const variante of config.variantes){
  const nombre=modo+'_'+variante;
  const dir=path.join(salidas,nombre,'RUN-G45-V2-20261113-000000');
  fs.mkdirSync(dir,{recursive:true});
  const sim=await simuladorG45(modo,variante==='campos_inyectados');
  try{
    let c={dir,runId:path.basename(dir),version:2,operacion:'reevaluar',ref:'LOCAL_SIMULADO'};
    if(modo==='conforme'&&variante==='normal'){
      const archivo=path.join(dir,'contexto_operacion.json');
      fs.writeFileSync(archivo,JSON.stringify({grupo:'G45',run_id:c.runId,version:2,intento:2,operacion:'REINTENTAR',referencia:c.ref,casos:CAPACIDADES.casos,version_anterior:null}));
      c=contexto(['--operacion','reintentar','--version','2','--intento','2','--run-id',c.runId,'--autorizacion',c.ref,'--contexto',archivo],true);
    }
    const hijo=async(_script,input)=>{const data=await ejecutarNewman(input);return{code:data.codigo||data.fallos?2:0,data};};
    const r=await ejecutar(c,{QA_SANDBOX_SECRET:'LOCAL',QA_CONTADOR_EMAIL:'local@example.invalid',QA_CONTADOR_PASSWORD:'LOCAL',QA_ADMIN_EMAIL:'admin@example.invalid',QA_ADMIN_PASSWORD:'LOCAL'},{ensayo:true,api:sim.url,hijo});
    const s=k=>r.casos['TC-M06-'+k].estado;
    assert.equal(sim.peticiones.filter(x=>x.metodo==='DELETE').length,1,nombre);
    assert(sim.peticiones.filter(x=>x.metodo==='POST'&&x.ruta.includes('/eventos/crecimiento')).every(x=>x.actor==='ADMIN'),nombre);
    assert(sim.peticiones.filter(x=>x.metodo==='POST'&&x.ruta!=='/sesiones/'&&!x.ruta.includes('/eventos/crecimiento')).every(x=>x.actor==='CONTADOR'),nombre);
    assert.equal(r.cierre.run.cierre_http,modo==='delete_fallido'?500:200,nombre);
    assert(!/identificador|numero_id_tributaria|razon_social/i.test(JSON.stringify({preflight_datos:r.preflight_datos,bases:r.bases})),nombre);
    if(modo==='permisos'){
      assert.equal(sim.peticiones.filter(x=>x.metodo==='POST'&&x.ruta!=='/sesiones/').length,0,nombre);
      assert.equal(r.rollback.verificado,true,nombre);
      assert.notEqual(r.clasificacion_fallo,'ROLLBACK',nombre);
      assert(r.preflight_datos.some(x=>x.requisito.startsWith('permiso_')&&!x.cumple),nombre);
    }else{
      assert.equal(r.rollback.verificado,modo!=='delete_fallido',nombre);
      if(['sin_pausa','266_no_access'].includes(modo)){
        assert.equal(s('031'),'NO_CONCLUYENTE',nombre);
        if(modo==='266_no_access'){assert(r.preflight_datos.some(x=>x.requisito==='031_acceso_1644'&&!x.cumple&&String(x.observado).includes('404')),nombre);assert.equal(sim.peticiones.some(x=>x.metodo==='POST'&&x.ruta.includes('/266/cierre')),false,nombre);}
        assert.equal(sim.peticiones.some(x=>x.metodo==='POST'&&x.ruta.includes('/241/cierre')),false,nombre);
      }else{
        assert(r.periodo_031,nombre+' sin periodo 031: '+JSON.stringify(r.problemas_tecnicos));
        assert.equal(r.periodo_031.id,modo.startsWith('266_')||modo==='220_no_price'?266:['241_no_pausable','220_solo_por_cabeza'].includes(modo)||modo.startsWith('220_')?220:241,nombre);
        if(modo==='categorias_null'){
          assert.equal(r.periodo_031.categoria_efectiva,'PESO_KG',nombre);
          assert.equal(r.periodo_031.categoria_por_defecto,true,nombre);
          assert.equal(r.periodo_031.precio_peso,true,nombre);
          for(const id of ['031_m02','031_escenario_a','031_escenario_b'])assert.equal(r.casos['TC-M06-031'].comprobaciones.find(x=>x.id===id).estado,'APROBADO',nombre);
        }
        if(modo==='1831_no_apto')assert.equal(r.periodo_031.activo_id,1832,nombre);
        assert.equal(r.casos['TC-M06-031'].comprobaciones.find(x=>x.id==='031_m02').estado,['admin_sin_permiso','220_growth_422'].includes(modo)?'NO_CONCLUYENTE':['m02_durante_cierre','266_pause_med','220_pause_med','costo_pausa_201'].includes(modo)?'RECHAZADO':'APROBADO',nombre);
        assert.equal(s('031'),['admin_sin_permiso','266_no_audit','a_no_cerrado','220_growth_422'].includes(modo)?'NO_CONCLUYENTE':['costo_pausa_201','m02_durante_cierre','a_mismo_periodo','b_otro_periodo','266_pause_med','266_a_closed','220_pause_med'].includes(modo)?'RECHAZADO':'APROBADO',nombre+' '+JSON.stringify(r.casos['TC-M06-031'].comprobaciones));
        if(['241_no_pausable','220_solo_por_cabeza'].includes(modo)){
          assert.equal(r.periodo_031.categoria_precio,'POR_CABEZA',nombre);
          for(const id of ['031_en_cierre','031_costo','031_m02','031_escenario_a','031_escenario_b'])assert.equal(r.casos['TC-M06-031'].comprobaciones.find(x=>x.id===id).estado,'APROBADO',nombre);
        }
        if(modo==='220_pausable'){assert.equal(r.periodo_031.activo_id,1569,nombre);assert.equal(r.respuestas.exclusion_031.presente,true,nombre);assert.equal(r.respuestas.crecimientos.length,2,nombre);assert.equal(r.respuestas.procesamientos.length,4,nombre);assert(r.respuestas.auditorias.length>=4,nombre);assert(r.preflight_datos.some(x=>x.requisito==='031_220_sin_precio_especie_422'&&x.cumple),nombre);assert.equal(JSON.parse(r.rollback.motivo).periodo_220,true,nombre);}
        if(r.periodo_031.tipo==='INDIVIDUAL')assert((r.respuestas.crecimientos??[]).every(x=>!Object.hasOwn(x.cuerpo_enviado,'tipo_agregacion')),nombre);
        if(modo==='220_growth_422'){assert.equal(r.respuestas.crecimientos[0].http,422,nombre);assert.equal(r.respuestas.crecimientos[0].cuerpo.error_code,'SIN_FASE_ACTIVA',nombre);assert(r.casos['TC-M06-031'].comprobaciones.find(x=>x.id==='031_m02').observado.includes('SIN_FASE_ACTIVA'),nombre);}
        if(modo==='220_no_price')assert.equal(r.preflight_datos.find(x=>x.requisito==='031_220_sin_precio_especie_422').cumple,false,nombre);
        if(['266_pausable','266_lineas'].includes(modo)){
          assert.equal(r.periodo_031.activo_id,1644,nombre);
          assert.equal(r.periodo_031.precio_peso,false,nombre);
          assert.equal(r.periodo_031.ultimo_peso,0,nombre);
          assert.equal(r.periodo_031.tipo,'POBLACIONAL',nombre);
          assert.equal(r.periodo_031.cantidad_actual,1,nombre);
          assert(r.preflight_datos.some(x=>x.requisito==='031_1644_tipo_cantidad'&&x.cumple),nombre);
          assert(r.preflight_datos.some(x=>x.requisito==='031_1644_fase_activa'&&x.cumple),nombre);
          assert.deepEqual(r.respuestas.crecimientos.map(x=>x.cuerpo_enviado.valor_medicion),['30','35'],nombre);
          assert(r.respuestas.crecimientos.every(x=>x.cuerpo_enviado.nuevo_peso_promedio===x.cuerpo_enviado.valor_medicion&&x.cuerpo_enviado.cantidad_medida===1&&x.cuerpo_enviado.tipo_agregacion==='PROMEDIO'),nombre);
          assert.equal(r.respuestas.exclusion_1644.presente,true,nombre);
          for(const id of ['031_m02','031_escenario_a','031_escenario_b'])assert.equal(r.casos['TC-M06-031'].comprobaciones.find(x=>x.id===id).estado,'APROBADO',nombre);
          assert(r.respuestas.evidencias_medicion.some(x=>x.escenario==='B_abierto'&&x.registros.some(y=>y.fuente===(modo==='266_lineas'?'LINEA':'AUDITORIA')&&y.id_periodo_contable===266)),nombre);
          assert(r.respuestas.evidencias_medicion.some(x=>x.escenario==='A_siguiente'&&x.registros.some(y=>y.fuente===(modo==='266_lineas'?'LINEA':'AUDITORIA')&&y.id_periodo_contable===270)),nombre);
          assert(r.rollback.verificado,nombre);
        }
        if(modo==='266_pause_med')assert.equal(r.casos['TC-M06-031'].comprobaciones.find(x=>x.id==='031_m02').estado,'RECHAZADO',nombre);
        if(modo==='266_a_closed')assert.equal(r.casos['TC-M06-031'].comprobaciones.find(x=>x.id==='031_escenario_a').estado,'RECHAZADO',nombre);
        if(modo==='266_no_audit')for(const id of ['031_escenario_a','031_escenario_b'])assert.equal(r.casos['TC-M06-031'].comprobaciones.find(x=>x.id===id).estado,'NO_CONCLUYENTE',nombre);
        if(modo==='b_otro_periodo')assert.equal(r.casos['TC-M06-031'].comprobaciones.find(x=>x.id==='031_escenario_b').estado,'RECHAZADO',nombre);
        if(modo==='a_mismo_periodo')assert.equal(r.casos['TC-M06-031'].comprobaciones.find(x=>x.id==='031_escenario_a').estado,'RECHAZADO',nombre);
        if(modo==='cola_no_visible')assert(r.casos['TC-M06-031'].comprobaciones.find(x=>x.id==='031_m02').observado.includes('estado de cola no visible'),nombre);
        if(modo==='admin_sin_permiso')assert(r.preflight_datos.some(x=>x.requisito==='permiso_administrador_activos_biologicos_1'&&!x.cumple),nombre);
      }
      assert.equal(s('032'),modo==='costo_cerrado_201'?'RECHAZADO':'APROBADO',nombre);
      if(modo==='costo_422'){
        assert(r.observaciones.some(x=>x.includes('OBS-G45-01')&&x.includes('HTTP 422')&&x.includes('PERIODO_CONTABLE_CERRADO')&&x.includes('Mensaje:')),nombre);
        assert.equal(r.incidencias.some(x=>x.id==='INC-M06-G45-02'),false,nombre);
        assert.equal(r.seguimiento_v1['INC-M06-G45-02'],'CORREGIDA',nombre);
      }
      if(modo==='conforme')assert.equal(r.observaciones.some(x=>x.includes('OBS-G45-01')),false,nombre);
      if(modo==='costo_cerrado_201')assert.equal(r.seguimiento_v1['INC-M06-G45-02'],'REPRODUCIDA',nombre);
      assert.equal(s('033'),modo==='ajuste_nuevo_periodo'?'RECHAZADO':'APROBADO',nombre);
      if(modo==='ajuste_nuevo_periodo')assert(r.casos['TC-M06-033'].comprobaciones.find(x=>x.id==='033_ajuste').observado.includes('261'),nombre);
      if(modo==='conforme'){
        assert.equal(r.oficial,true,JSON.stringify(r.problemas_tecnicos));
        assert.deepEqual(r.seguimiento_v1,{'INC-M06-G45-01':'CORREGIDA','INC-M06-G45-02':'CORREGIDA','INC-M06-G45-03':'CORREGIDA'},nombre);
        assert.deepEqual(validarFormaResultado(r,CAPACIDADES,dir),[],nombre);
      }
    }
    assert(fs.existsSync(path.join(dir,'resultado.json')),nombre);
    assert(fs.existsSync(path.join(dir,'TC-M06-G45_reevaluacion_V2.md')),nombre);
    assert.equal(fs.readdirSync(dir).filter(x=>x.endsWith('.md')).length,1,nombre);
    const informe=fs.readFileSync(path.join(dir,'TC-M06-G45_reevaluacion_V2.md'),'utf8');
    if(modo==='costo_422')assert(informe.includes('OBS-G45-01')&&informe.includes('HTTP 422')&&informe.includes('PERIODO_CONTABLE_CERRADO'),nombre);
    if(modo==='conforme')assert.equal(informe.includes('OBS-G45-01'),false,nombre);
    assert(informe.startsWith('# TC-M06-G45 — reevaluación V2 '+(r.oficial?'oficial - '+(Object.values(r.casos).some(x=>x.estado==='RECHAZADO')?'RECHAZADO':'APROBADO'):'NO OFICIAL')),nombre);
    assert(informe.includes(r.run_id),nombre);
    if(process.env.QA_VERIFICAR_SALIDAS)for(const entrada of fs.readdirSync(dir))fs.cpSync(path.join(dir,entrada),path.join(salidas,nombre,entrada),{recursive:true});
    total++;
  }finally{await sim.cerrar();}
}
assert.equal(total,config.integrales);
console.log(JSON.stringify({escenarios:total,estado:'OK',salidas}));
