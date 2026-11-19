import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {CAPACIDADES,principal} from '../g040.mjs';
import {servidorG040} from './simulador_g040.mjs';
import {ejecutar as ejecutarNewman} from './newman_hijo.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url));
const runId='RUN-G040-V2-20261118-000000';
const escenarios=JSON.parse(fs.readFileSync(path.join(DIR,'escenarios_g040.json'),'utf8')).escenarios;
const secretos=['LOCAL_ADMIN_TOKEN','LOCAL_CHANNEL_TOKEN','LOCAL_SECRET','LOCAL_CLIENT','900123456','local@example.invalid'];
export async function ejecutarEscenarios(salida=process.env.QA_VERIFICAR_SALIDAS??fs.mkdtempSync(path.join(os.tmpdir(),'g040-escenarios-'))){
 const resultados=[];
 for(const x of escenarios){
  const sim=await servidorG040(x.opciones);
  try{
   const dir=path.join(salida,x.id,runId);fs.mkdirSync(dir,{recursive:true});
   const archivo=path.join(dir,'contexto_operacion.json');
   fs.writeFileSync(archivo,JSON.stringify({grupo:'G040',version:2,intento:1,run_id:runId,operacion:'REEVALUAR',referencia:'REF-LOCAL',casos:CAPACIDADES.casos,alcance_reevaluacion:{casos:CAPACIDADES.casos,version_anterior:1,motivo:'Reevaluación V2 completa decidida por QA el 2026-11-18',incumplimientos_previos:'V1 oficial: TC-M07-19 RECHAZADO BAJA por VERSION_NO_REGISTRADA',correcciones_informadas:'Líder de análisis cambiará RF-98 FA-7; documento pendiente',resultado_esperado:'Cinco casos según RF-98 y decisión QA: 19 admite ambos códigos con HTTP 404 y mensaje CA-15'},version_anterior:1}));
   const args=['--autorizacion','REF-LOCAL','--operacion','reevaluar','--version','2','--intento','1','--run-id',runId,'--contexto',archivo];
   const e={QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL_PASSWORD',QA_SANDBOX_SECRET:'LOCAL_SANDBOX',SIGAB_API_TEST_BASE:sim.api,AGROFUSION_CLIENT_ID:'LOCAL_CLIENT',AGROFUSION_CLIENT_SECRET:'LOCAL_SECRET',ExternoAgrofusion:'local@example.invalid'};
   const z=await principal(args,{proceso:e,archivo:path.join(os.tmpdir(),'g040-inexistente.env'),prueba:true,dobles:{pausa:async ms=>sim.avanzar(ms),newman:ejecutarNewman}});
   assert.equal(z.codigo,0,x.id);const r=z.resultado,veredictos=['17','18','19','20','21'].map(k=>r.veredictos[k]);
   assert.deepEqual(veredictos,x.esperado,x.id);assert.equal(r.oficial,x.oficial,x.id);
   assert(r.solicitudes_total<=40,x.id);const login=sim.peticiones.find(p=>p.ruta==='/sesiones/');assert(login&&!login.cabecerasSandbox,`${x.id}: login dentro del sandbox`);const abiertas=sim.peticiones.some(p=>p.sandbox);assert.equal(sim.peticiones.filter(p=>p.metodo==='DELETE').length,abiertas?1:0,`${x.id}: DELETE`);assert.equal(r.cierre.fases.length,abiertas?1:0,x.id);
   assert.equal(r.cierre.rollback.verificado,abiertas&&x.id!=='m_rollback_fallido',x.id);
   if(x.id==='p_login_invalido'){assert.equal(r.solicitudes.length,1);assert.equal(r.solicitudes[0].http,400);}
   if(x.id==='q_cierre_tras_bloqueo'){assert(r.preflight_datos.some(v=>v.bloqueante&&!v.cumple));assert.equal(r.cierre.http,200);}
   if(x.id==='k_token_rechazado')assert.equal(r.solicitudes.filter(y=>y.caso).length,0);
   if(x.id==='a_conforme'){assert.equal(r.incidencias.length,0);assert(r.observaciones.includes('Código aceptado por decisión del responsable QA a la espera del cambio de RF-98 FA-7'));assert.equal(r.solicitudes.filter(y=>y.http===429).length,0);} if(x.id==='d_codigo_19_correcto')assert(!r.observaciones.some(y=>y.startsWith('Código aceptado')));if(x.severidad_19)assert(r.incidencias.some(y=>y.caso==='TC-M07-19'&&y.severidad===x.severidad_19));
   if(x.id==='e_sin_advertencia'||x.id==='f_sunset_distinto')assert(r.incidencias.some(i=>i.caso==='TC-M07-18'&&i.severidad==='MEDIA'));
   if(x.id==='g_version_equivocada')assert(r.incidencias.some(i=>i.caso==='TC-M07-17'&&i.severidad==='ALTA'));
   if(x.id==='h_inactiva_atendida')assert(r.incidencias.some(i=>i.caso==='TC-M07-20'&&i.severidad==='ALTA'));
   const entradas={'TC-M07-17':[null],'TC-M07-18':[r.versiones_elegidas.activo?.version??null,r.versiones_elegidas.deprecado?.version??null],'TC-M07-19':['9.9'],'TC-M07-20':[r.versiones_elegidas.inactivo?.version??null],'TC-M07-21':['3','3.0.0','abc']};for(const [caso,values] of Object.entries(entradas)){const filas=r.solicitudes.filter(y=>y.caso===caso);for(let i=0;i<filas.length;i++)assert.equal(filas[i].acceptVersion,values[i],x.id);}if(x.id==='i_formato_aceptado')assert(r.incidencias.some(i=>i.caso==='TC-M07-21'&&i.severidad==='ALTA'));
   for(const file of [path.join(dir,'resultado.json'),path.join(dir,'TC-M07-G040_reevaluacion_V2.md'),...fs.existsSync(path.join(dir,'newman'))?fs.readdirSync(path.join(dir,'newman')).map(f=>path.join(dir,'newman',f)):[]]){
    const content=fs.readFileSync(file,'utf8');for(const secret of secretos)assert(!content.includes(secret),`${x.id} expone secreto en ${file}`);
   }
   const linea=`OK escenario_${x.id}: 17=${veredictos[0]} 18=${veredictos[1]} 19=${veredictos[2]} 20=${veredictos[3]} 21=${veredictos[4]} oficial=${r.oficial} solicitudes=${r.solicitudes_total}/40`;
   console.log(linea);resultados.push({id:x.id,dir,veredictos:r.veredictos,oficial:r.oficial,linea});
  }finally{await sim.cerrar();}
 }
 fs.writeFileSync(path.join(salida,'resumen_escenarios.json'),JSON.stringify(resultados,null,2));return resultados;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))await ejecutarEscenarios();
