import assert from 'node:assert/strict';
import {evaluar,preInicial,precioVigente,sinCambios,cierre8CoincideG32,paresMatrizFaltantes,cuerpoParMatriz,numeroAislado,calculosUsanPrecio} from '../lib/g43_core.mjs';
import {clasificarRegistro} from '../lib/infra.mjs';
import {CAPACIDADES,permitidos} from '../g43.mjs';
import {esquema} from '../lib/contrato.mjs';
const conforme={pausaEstado:'EN_CIERRE',pIni:{id_precio_mercado:17,fecha_vigencia:'2026-11-07'},pNuevo:{id_precio_mercado:999},congelado:{id_precio_mercado:17,fecha_vigencia:'2026-11-07'},cierre8:{http:200},medicionesIni:true,aviso25:true,no25:true,si25:true,ui25:true,confirmacion26:true,costo26:true,sinEstimacion26:true,ui26:true,lista27:true,no27:true,si27:true,ui27:true};
const status=(x,c)=>evaluar(x)[c].estado;
const p={puede_cerrar:true,bloqueos:[],activos_sin_precio:[],lineas_sin_trazabilidad:[]};
const old={id_precio_mercado:435,id_especie:422,categoria:'POR_CABEZA',id_metrica_produccion:null,fuente:'MERCADO_ACTIVO',fecha_vigencia:'2026-11-01',fecha_vencimiento:null};
const vencido={...old,id_precio_mercado:999,fecha_vigencia:'2026-11-02',fecha_vencimiento:'2026-11-08'};
const base={periodo:{estado:'ABIERTO'},lineas:[{id_linea_asiento_nic41:17,estado:'REGISTRADA',estado_trazabilidad:'VERIFICACION_PENDIENTE',id_periodo_contable:8}],comprobantes:[],variaciones:[]};
const matrizBase=[{tipo_hecho:'OTRO',sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito:'516005',cuenta_credito:'159205'},{tipo_hecho:'OTRO',sentido:'GANANCIA',id_especie:null,subtipo_costo:null,cuenta_debito:'516005',cuenta_credito:'159205'},{tipo_hecho:'OTRO',sentido:'PERDIDA',id_especie:null,subtipo_costo:null,cuenta_debito:'516005',cuenta_credito:'159205'}];
const artefactos=new Set(['resultado.json','TC-M06-G43_resultado.md','newman/newman-G43.json','newman/newman-G43.html',...['025','026','027'].flatMap(n=>[`cypress/${n}/G43-UI-${n}.json`,`cypress/${n}/screenshots/g43.cy.js/G43-UI-${n}.png`])]);
const registro={grupo:'G43',run_id:'RUN-G43-V1-20261109-223000',autorizacion_referencia:'QA-LOCAL',version:1,oficial:true,consume_version:true,rollback:{verificado:true},herramientas:{newman:{codigo:0,fallos:0,reportes:true}},total_solicitudes_api:100,casos:Object.fromEntries(CAPACIDADES.casos.map(c=>[c,{estado:'APROBADO',comprobaciones:[{id:'local'}]}])),cypress:{paneles:Object.fromEntries(['025','026','027'].map(n=>[n,{codigo:0,totalTests:1,estado:'APROBADO',evidencia:`cypress/${n}/G43-UI-${n}.json`}]))},evidencias:[...artefactos]};
registro.comprobaciones=CAPACIDADES.casos.flatMap(c=>[{caso:c,id:`G43-API-${c.slice(-3)}-01`,fuente:'API',tipo:'ASSERT',estado:'APROBADO',evidencia:'resultado.json'},{caso:c,id:`G43-UI-${c==='TC-M06-024'?'027':c.slice(-3)}-01`,fuente:'UI',tipo:'ASSERT',estado:'APROBADO',evidencia:`cypress/${c==='TC-M06-024'?'027':c.slice(-3)}/G43-UI-${c==='TC-M06-024'?'027':c.slice(-3)}.json`}]);
const ctx={runId:registro.run_id,version:1,referencia:'QA-LOCAL'};
registro.cierre={run:{cierre_http:200},rollback:{verificado:true}};
const filas=[
 ['matriz_completa',()=>assert.equal(paresMatrizFaltantes([...matrizBase,...paresMatrizFaltantes(matrizBase).map(([tipo_hecho,sentido])=>({tipo_hecho,sentido,id_especie:null,subtipo_costo:null}))]).length,0)],
 ['matriz_par_faltante_creado',()=>assert.equal(cuerpoParMatriz(matrizBase,['DEPRECIACION_ACTIVO_COSTO','UNICO']).cuenta_debito,'516005')],
 ['matriz_sin_par_origen',()=>assert.equal(cuerpoParMatriz([],['DEPRECIACION_ACTIVO_COSTO','UNICO']),null)],
 ['calculo_precio_P_ini',()=>assert.equal(calculosUsanPrecio([{id_activo_biologico:945,precio_unitario:'9300'},{id_activo_biologico:947,precio_unitario:'9300'}],[945,947],9300,9765),true)],
 ['calculo_precio_P_nuevo',()=>assert.equal(calculosUsanPrecio([{id_activo_biologico:945,precio_unitario:'9765'},{id_activo_biologico:947,precio_unitario:'9765'}],[945,947],9300,9765),false)],
 ['mensaje_409_N_aislado',()=>{assert.equal(numeroAislado('1 activo',1),true);assert.equal(numeroAislado('10 activos',1),false);}],
 ['500_sin_auditoria_preimpedido',()=>assert.ok(permitidos.some(([recurso,accion])=>recurso==='auditoria_financiera'&&accion===2))],
 ['confirmacion_por_evidencia_observada',()=>assert.equal(status({...conforme,confirmacion26:false},'026'),'RECHAZADO')],
 ['prevalidacion_inicial_distinta',()=>assert.equal(preInicial(p,p,p),false)],
 ['expiracion_no_deja_sin_precio',()=>assert.ok(precioVigente([old,vencido,{...old,id_precio_mercado:600,fuente:'UPRA'}],422,'POR_CABEZA','2026-11-09'))],
 ['409_esperado_ausente',()=>assert.equal(status({...conforme,pausaEstado:'CERRADO'},'024'),'RECHAZADO')],
 ['pausa_ABIERTO',()=>assert.equal(status({...conforme,pausaEstado:'ABIERTO'},'027'),'RECHAZADO')],
 ['pausa_EN_CIERRE',()=>assert.equal(status(conforme,'024'),'APROBADO')],
 ['no_sin_cambios',()=>assert.equal(sinCambios(base,base),true)],
 ['no_con_linea_M02_nueva',()=>assert.equal(sinCambios(base,{...base,lineas:[...base.lineas,{id_linea_asiento_nic41:22,estado:'REGISTRADA',estado_trazabilidad:'VERIFICADO',id_periodo_contable:8,tipo_evidencia:'REGISTRO_MANUAL'}]}),true)],
 ['no_con_linea_cierre_nueva',()=>assert.equal(sinCambios(base,{...base,lineas:[...base.lineas,{id_linea_asiento_nic41:22,estado:'REGISTRADA',estado_trazabilidad:'VERIFICADO',id_periodo_contable:8,tipo_evidencia:'CIERRE_PERIODO'}]}),false)],
 ['precio_nuevo_no_elegido',()=>assert.equal(precioVigente([old,{...old,id_precio_mercado:2,fecha_vigencia:'2026-12-01'}],422,'POR_CABEZA','2026-11-09')?.id_precio_mercado,435)],
 ['congelado_P_ini',()=>assert.equal(status(conforme,'024'),'APROBADO')],
 ['congelado_P_nuevo',()=>assert.equal(status({...conforme,congelado:{id_precio_mercado:999,fecha_vigencia:'2026-11-09'}},'024'),'RECHAZADO')],
 ['cierre8_500_paso3_generico',()=>assert.equal(cierre8CoincideG32({http:500},[{tipo_evento:'CIERRE_PERIODO_FALLIDO',timestamp_evento:'2026-11-09T21:24:36Z',payload_evento:{paso:3,error:'Error interno'}}],'2026-11-09T21:24:20Z'),true)],
 ['cierre8_500_otro_paso',()=>assert.equal(cierre8CoincideG32({http:500},[{tipo_evento:'CIERRE_PERIODO_FALLIDO',timestamp_evento:'2026-11-09T21:24:36Z',payload_evento:{paso:2,error:'Error interno'}}],'2026-11-09T21:24:20Z'),false)],
 ['cierre8_500_evento_anterior',()=>assert.equal(cierre8CoincideG32({http:500},[{tipo_evento:'CIERRE_PERIODO_FALLIDO',timestamp_evento:'2026-11-09T21:24:10Z',payload_evento:{paso:3}}],'2026-11-09T21:24:20Z'),false)],
 ['1568_excluido',()=>assert.equal(status(conforme,'025'),'APROBADO')],
 ['1568_no_excluido',()=>assert.equal(status({...conforme,si25:false},'025'),'RECHAZADO')],
 ['caprinos_estimados',()=>assert.equal(status({...conforme,sinEstimacion26:false},'026'),'RECHAZADO')],
 ['caprinos_pendientes',()=>assert.equal(status(conforme,'026'),'APROBADO')],
 ['equino_costo_confirmado',()=>assert.equal(status(conforme,'026'),'APROBADO')],
 ['equino_sin_confirmacion',()=>assert.equal(status({...conforme,confirmacion26:false},'026'),'RECHAZADO')],
 ['sin_confirmacion_en_contrato',()=>assert.ok(!('confirmaciones_parrafo30' in esquema('POST','/finanzas/periodos/220/cierre').cuerpo))],
 ['ui_lista_completa',()=>assert.equal(status(conforme,'027'),'APROBADO')],
 ['ui_lista_incompleta',()=>assert.equal(status({...conforme,ui27:false},'027'),'RECHAZADO')],
 ['rollback_fallido',()=>assert.equal(clasificarRegistro(CAPACIDADES,{...registro,rollback:{verificado:false}},artefactos,ctx),false)],
 ['newman_fallido',()=>assert.equal(clasificarRegistro(CAPACIDADES,{...registro,herramientas:{newman:{codigo:2,fallos:1,reportes:true}}},artefactos,ctx),false)],
 ['cypress_cero',()=>assert.equal(clasificarRegistro(CAPACIDADES,{...registro,cypress:{paneles:{...registro.cypress.paneles,'025':{codigo:0,totalTests:0,evidencia:'cypress/025/G43-UI-025.json'}}}},artefactos,ctx),false)],
];
for(const [nombre,fn] of filas){fn();console.log(`OK decision_${nombre}`);}
assert.equal(clasificarRegistro(CAPACIDADES,registro,artefactos,ctx),true);
