import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const {evaluarSeleccionPeriodo,requiereCambioExplicito,mesPeriodo,opcionTitular,opcionPeriodo,selectorPorEtiqueta}=createRequire(import.meta.url)('../lib/intercepcion.cjs');
const {simuladorBase}=await import('./simulador_base.mjs');

const escenario=JSON.parse(fs.readFileSync(new URL('./escenarios_g43.json',import.meta.url),'utf8'));
const {inspeccionarVista,elementosVista}=createRequire(import.meta.url)('../lib/vista_cierre.cjs');
const el=(textContent,extra={})=>({textContent,getClientRects:()=>[1],getAttribute:()=>null,querySelector:()=>null,querySelectorAll:()=>[],closest:()=>null,...extra});
const vista=(panel,pausa=false,quitar='',filas027=['Línea 17 · A-944 · Lecturas IoT aptas'])=>{
 const fila=el('A-1644 Bovino Sin precio de mercado vigente para su especie');
 const tabla=el('',{querySelector:s=>s==='caption'?panel==='027'?el('1 línea con la cadena de trazabilidad incompleta'):null:s==='thead'?el('Activo Especie Motivo Decisión'):null,querySelectorAll:s=>s.startsWith('th')?panel==='027'?[el('Asiento'),el('Activo'),el('Qué falta')]:[el('Activo'),el('Especie'),el('Motivo'),el('Decisión')]:quitar==='fila'?[]:panel==='027'?filas027.map(x=>el(x)):[fila]});
 const boton=el('Cerrar período',{type:'button',disabled:true});
 const cancelar=el(pausa?'Cancelar el cierre':'Cancelar cierre (No)',{type:'button'});
 const casilla=el('',{type:'checkbox',closest:()=>el('Autorizo excluir del comprobante las líneas con trazabilidad incompleta')});
 const excluir=el('',{type:'radio',name:'sin-precio-1644',closest:()=>el('Excluir de este cierre (pasa al período siguiente)')});
 const estimar=el('',{type:'radio',name:'sin-precio-1644',closest:()=>el('Medir con el último precio conocido, como estimación')});
 const controles=pausa?[cancelar]:panel==='027'?[boton,cancelar,casilla]:[boton,cancelar,excluir,...(quitar==='estimar'?[]:[estimar])];
 return {textContent:pausa?'El cierre espera tu decisión':'Precondiciones para cerrar 1 activo sin precio A-1644 (Bovino)',querySelectorAll:s=>s.startsWith('button,input')?controles:s.startsWith('table,input')?pausa?controles:[tabla,...controles]:s.startsWith('h1')?[el('Precondiciones para cerrar')]:s.startsWith('table')?pausa?[]:[tabla]:[]};
};
const esperadoVista=escenario.paneles['8'].esperado;
assert.equal(inspeccionarVista(vista('027'),'027',esperadoVista).lista_completa,true);
assert.equal(inspeccionarVista(vista('027'),'027',esperadoVista).casilla_autorizacion,true);
assert.equal(inspeccionarVista(vista('027',true),'027',esperadoVista).pausa,true);
assert.equal(inspeccionarVista(vista('026'),'026',escenario.paneles['267'].esperado).decision_por_activo,true);
assert.equal(inspeccionarVista(vista('026',false,'estimar'),'026',escenario.paneles['267'].esperado).decision_por_activo,false);
assert.match(inspeccionarVista(vista('026',false,'fila'),'026',escenario.paneles['267'].esperado).diagnostico,/fila del activo 1644/);
assert.equal(inspeccionarVista(vista('025'),'025',escenario.paneles['267'].esperado).resumen_dom.encabezados.length,1);
assert.equal(inspeccionarVista(vista('025'),'025',escenario.paneles['266'].esperado).faltas.length,0,'025 cumple con advertencia y decisión');
assert.equal(inspeccionarVista(vista('026'),'026',escenario.paneles['267'].esperado).faltas.length,0,'026 cumple con dos radios');
assert.equal(inspeccionarVista(vista('027'),'027',esperadoVista).faltas.length,0,'027 cumple con trazabilidad y casilla');
assert.match(inspeccionarVista(vista('027',false,'fila'),'027',esperadoVista).diagnostico,/Línea 17/);
const varias=vista('027',false,'',['Línea 4 · Otro activo','Línea 17 · QA-M06-BOV-02 · Lecturas IoT aptas, Otro registro de origen','Línea 18 · Otro activo']);
const esperadoReal={linea:17,identificador:'QA-M06-BOV-02',eslabones:['lecturas_nic41','auditoria_m03']};
assert.equal(inspeccionarVista(varias,'027',esperadoReal).faltas.length,0);
assert.deepEqual(inspeccionarVista(varias,'027',esperadoReal).etiquetas_genericas,['auditoria_m03']);
assert.match(inspeccionarVista(vista('027',false,'',['Línea 4 · QA-M06-BOV-02 · Lecturas IoT aptas']),'027',esperadoReal).diagnostico,/Línea 17 ausente/);
assert.match(inspeccionarVista(vista('027',false,'',['Línea 17 · 944 · Lecturas IoT aptas, Otro registro de origen']),'027',esperadoReal).diagnostico,/identificador/);
assert.equal(inspeccionarVista(vista('026',true),'026',escenario.paneles['267'].esperado).resumen_dom.tablas.length,0,'pausa sin tablas es no concluyente');
assert.equal(elementosVista(vista('027'),'027').length>0,true);const ids=Object.keys(escenario.paneles).map(Number);
const api=ids.map(id_periodo_contable=>({id_periodo_contable}));
const opciones=ids=>ids.map(value=>({value:String(value)}));
const casos=[
  {nombre:'opción presente al inicio',eventos:[{api,opciones:opciones(ids)}],esperado:['SELECCIONAR']},
  {nombre:'opción tras demora',eventos:[{api,opciones:opciones([])},{api,opciones:opciones(ids)}],esperado:['ESPERAR_OPCION','SELECCIONAR']},
  {nombre:'opción ausente con período en API',eventos:[{api,opciones:opciones(ids.filter(x=>x!==8))},{api,opciones:opciones(ids.filter(x=>x!==8)),vencido:true}],esperado:['ESPERAR_OPCION','AUSENTE_SELECTOR']},
  {nombre:'período ausente en API',eventos:[{api:api.filter(x=>x.id_periodo_contable!==8),opciones:opciones(ids.filter(x=>x!==8))}],esperado:['AUSENTE_API']},
  {nombre:'proveedor sin segunda petición tras recargar',eventos:[{api,opciones:opciones([])},{api,opciones:opciones(ids)}],esperado:['ESPERAR_OPCION','SELECCIONAR']},
];
for(const {nombre,eventos,esperado} of casos){
  const observado=eventos.map(x=>evaluarSeleccionPeriodo(8,x.api,x.opciones,x.vencido));
  assert.deepEqual(observado,esperado,nombre);
}
assert.equal(requiereCambioExplicito(8,'8',true),true,'el simulador requiere change al seleccionar el valor inicial');
assert.equal(requiereCambioExplicito(8,'266',true),false);
assert.equal(requiereCambioExplicito(8,'8',false),false,'la UI real inicia la prevalidación al montar el panel');
const titulares=[{value:'444444444',texto:'Agropecuaria El Rosal S.A.S. · NIT 444444444'},{value:'111111111',texto:'Titular A S.A.S. · NIT 111111111'}];
assert.notEqual(titulares[0].value,'111111111','titular inicial distinto');
assert.equal(opcionTitular('111111111',titulares)?.value,'111111111','titular objetivo presente');
assert.equal(opcionTitular('777777777',titulares),null,'titular objetivo ausente');
assert.equal(mesPeriodo('2026-11-01'),'Noviembre de 2026');
assert.equal(opcionPeriodo(8,'2026-11-01',[{value:'periodo-8',texto:'Noviembre de 2026 · ABIERTO'}])?.value,'periodo-8','value no numérico');
const control=(atributos={})=>({getAttribute:nombre=>atributos[nombre]??null});
const titular=control({id:'titular'});
const periodoControl=control();
const combo=control({'aria-label':'Periodo contable'});
const etiquetaFor={textContent:' Titular ',getAttribute:nombre=>nombre==='for'?'titular':null,querySelector:()=>null};
const etiquetaEnvolvente={textContent:' Periodo ',getAttribute:()=>null,querySelector:()=>periodoControl};
const documento={querySelectorAll:selector=>selector==='label'?[etiquetaFor,etiquetaEnvolvente]:[titular,periodoControl,combo],getElementById:id=>id==='titular'?titular:null};
const cuerpo={ownerDocument:documento,querySelectorAll:documento.querySelectorAll};
assert.equal(typeof cuerpo.getElementById,'undefined','Element no ofrece getElementById');
assert.equal(selectorPorEtiqueta(cuerpo,'Titular'),titular,'etiqueta for desde Element');
assert.equal(selectorPorEtiqueta(documento,'Titular'),titular,'etiqueta for desde Document');
assert.equal(selectorPorEtiqueta(cuerpo,'Periodo'),periodoControl,'etiqueta envolvente');
assert.equal(selectorPorEtiqueta(cuerpo,'Periodo contable'),combo,'combobox con aria-label');
assert.equal(selectorPorEtiqueta(cuerpo,'Etiqueta ausente'),null,'etiqueta y control ausentes');
const spec=fs.readFileSync(new URL('../g43.cy.js',import.meta.url),'utf8');
assert.match(spec,/post_prohibidos\.push\(ruta\)/,'POST de cierre y cancelación queda registrado como ERROR_QA');
assert.match(spec,/ERROR_QA_RESUMEN_DOM_VACIO/,'DOM vacío queda NO_CONCLUYENTE');
assert.match(spec,/cy\.wait\('@prevalidacion'/,'espera la respuesta de prevalidación');
const diferidas=[...spec.matchAll(/^    let\s+([^;]+);/gm)]
  .flatMap(([,declaraciones])=>declaraciones.split(',').map(x=>x.match(/^\s*([A-Za-z_$][\w$]*)/)?.[1]).filter(Boolean))
  .filter(nombre=>new RegExp(`^ {6,}${nombre}\\s*=`, 'm').test(spec));
assert(diferidas.includes('fechaInicio'),'fechaInicio debe seguir asignándose en el callback de cy.wait');
for(const [indice,linea] of spec.split(/\r?\n/).entries()){
  if(!/^ {4}cy\.(?!then\b)[A-Za-z_$][\w$]*\(/.test(linea))continue;
  for(const nombre of diferidas){
    assert(!new RegExp(`\\b${nombre}\\b`).test(linea),`g43.cy.js:${indice+1}: ${nombre} se lee al encolar un comando antes de ejecutarse su callback`);
  }
}
const sim=await simuladorBase(escenario,{valueNoNumerico:[8]});
try{
  const frontal=await (await fetch(sim.url)).text();
  new vm.Script(frontal.match(/<script>([\s\S]*?)<\/script>/)?.[1]||'');
  assert.match(frontal,/Agropecuaria El Rosal S\.A\.S\./);
  assert.match(frontal,/Precondiciones para cerrar/);
  const defecto=await (await fetch(sim.url+'finanzas/periodos?numero_id_tributaria=444444444')).json();
  const objetivo=await (await fetch(sim.url+'finanzas/periodos?numero_id_tributaria=111111111')).json();
  assert.equal(defecto.length,0,'el período no aparece para el titular por defecto');
  assert(objetivo.some(x=>x.id_periodo_contable===8),'el período aparece tras cambiar de titular');
}finally{await sim.cerrar();}
for(const solo of [false,true]){
  const pausa=await simuladorBase(escenario,{pausa:true,pausaSoloCancelar:solo});
  try{
    const frontal=await (await fetch(pausa.url)).text();
    assert.match(frontal,/El cierre espera tu decisión/);
    assert.match(frontal,/Cancelar el cierre/);
    assert.match(frontal,/document.querySelector\('#decision-pausa'\).innerHTML=pausa\?tarjeta:''/);
    assert.match(frontal,/decision-pausa/);
    assert.match(frontal,/pausaSoloCancelar/);
    assert.match(frontal,/main\{height:360px;overflow-y:auto\}/,'frontal falso con contenedor desplazable');
  }finally{await pausa.cerrar();}
}
console.log('OK selección de titular y período: secuencias iniciales, ausencias, filtro y value no numérico');


