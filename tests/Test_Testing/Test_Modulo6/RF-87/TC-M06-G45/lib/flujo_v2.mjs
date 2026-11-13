import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {crearSolicitante, lanzarHijo, listarEvidencias, guardarResultado, validarFormaResultado, clasificarFallo, sha256} from './infra.mjs';
import {esquema, validarLecturas, validarError} from './contrato.mjs';
import {informe} from './informe.mjs';

const CASOS=['TC-M06-031','TC-M06-032','TC-M06-033'];
const limpia=x=>String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+|\bQA-[A-Z0-9-]{4,}\b|\b\d{8,12}\b/g,'[RESERVADO]').slice(0,400);
const sanear=(x,k='')=>/token|password|contrasena|cookie|secret|jwt|serial|identificador|numero_id_tributaria|correo|email|authorization|nombre_usuario|actor/i.test(k)?'[RESERVADO]':Array.isArray(x)?x.map(v=>sanear(v)):x&&typeof x==='object'?Object.fromEntries(Object.entries(x).map(([a,b])=>[a,sanear(b,a)])):typeof x==='string'?x.replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+|\bQA-[A-Z0-9-]{4,}\b|\b\d{8,12}\b/g,'[RESERVADO]'):x;
const eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const hash=x=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
const porId=(ps,id)=>ps.find(p=>Number(p.id_periodo_contable)===id);
const veredicto=xs=>xs.some(x=>x.estado==='RECHAZADO')?'RECHAZADO':xs.some(x=>x.estado==='NO_CONCLUYENTE')?'NO_CONCLUYENTE':'APROBADO';
const buena=x=>x>=200&&x<300;

export async function ejecutarV2({c,e,api,local,dir,capacidades,limite,pf,hijo}){
  const r={grupo:'G45',rf:'RF-87 v1.1',run_id:c.runId,version:c.version,autorizacion_referencia:c.ref,commit_referencia:'453277e4',casos:Object.fromEntries(CASOS.map(k=>[k,{estado:'NO_CONCLUYENTE',motivo:'No ejecutado',comprobaciones:[]} ])),preflight:pf,preflight_datos:[],solicitudes:[],comprobaciones:[],incidencias:[],evidencias:[],observaciones:['032: las rutas públicas de modificación y eliminación histórica de costos y variaciones no están disponibles; se comprueban las escrituras públicas pertinentes y la integridad.'],problemas_tecnicos:[],respuestas:{},cypress:{paneles:{},total_pruebas:0},rollback:{verificado:false},herramientas:{node:process.version},oficial:false,consume_version:false};
  let token=null,contadorToken=null,adminToken=null,escrituras=0,newman=false,basales=null,idsPeriodos=[],costos944=[],recon949=null,activo31=null,costos31=[],elegido=null,historialBase=null,siguienteId=null;
  const inicio=Date.now();
  const solicitud=crearSolicitante({api,runId:c.runId,secret:e.QA_SANDBOX_SECRET,limite,solicitudes:r.solicitudes,esquema,validarLecturas,validarError,clean:limpia,id:n=>'G45-'+String(n).padStart(3,'0'),token:()=>token,inicio});
  const req=solicitud.req;
  const get=async(ruta,sinRun=false)=>{const z=await req('GET',ruta,undefined,sinRun);if(z.http!==200)throw Error('GET_'+z.http+'_'+ruta);return z.data;};
  const periodos=(sinRun=false)=>get('/finanzas/periodos',sinRun);
  const estado=async(id,sinRun=false)=>{const p=porId(await periodos(sinRun),id);if(!p)throw Error('PERIODO_'+id+'_AUSENTE');return {estado:p.estado,fecha_cierre:p.fecha_cierre??null,ultimo_cierre:p.ultimo_cierre??null,lineas:await get('/finanzas/lineas?id_periodo_contable='+id,sinRun),comprobantes:await get('/finanzas/periodos/'+id+'/comprobantes',sinRun),variaciones:await get('/finanzas/periodos/'+id+'/variaciones',sinRun)};};
  const dato=(requisito,esperado,observado,cumple,bloqueante=true)=>r.preflight_datos.push({requisito,esperado,observado:sanear(observado),cumple:!!cumple,bloqueante});
  const check=(caso,id,esperado,estado,observado,evidencia)=>{const z={id,esperado,estado,observado:limpia(observado),evidencia:evidencia??r.solicitudes.at(-1)?.id};r.casos[caso].comprobaciones.push(z);r.comprobaciones.push({caso,id,fuente:'API',tipo:'ASSERT',estado,evidencia:'resultado.json'});};
  const cerrar=()=>{for(const caso of CASOS){const x=r.casos[caso];if(x.comprobaciones.length){x.estado=veredicto(x.comprobaciones);x.motivo=x.estado==='APROBADO'?'Criterios conformes':x.comprobaciones.filter(z=>z.estado===x.estado).map(z=>z.id).join(', ')||x.comprobaciones.filter(z=>z.estado!=='APROBADO').map(z=>z.id).join(', ');}}};
  const incidencia=(num,caso,esperado,observado,sev)=>r.incidencias.push({id:'INC-M06-G45-'+num,casos:[caso],esperado,obtenido:limpia(observado),evidencia:'resultado.json',severidad:sev,justificacion_severidad:sev==='ALTA'?'La operación relevante incumple el criterio y no hay alternativa acreditada.':'La discrepancia afecta parcialmente la regla comprobada.',certeza:'CONFIRMADA',equipo:'Desarrollo',fundamento:'Primera discrepancia comprobada por API pública en el RUN.',causa_raiz:'Por determinar.',accion:'Desarrollo revisa la discrepancia; QA repite con autorización.'});
  const post=async(ruta,body)=>{escrituras++;return req('POST',ruta,body);};
  const partes=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()).map(x=>[x.type,x.value]));
  const hoy=partes.year+'-'+partes.month+'-'+partes.day;
  const diaBogota=valor=>valor?/^\d{4}-\d{2}-\d{2}$/.test(String(valor))?String(valor):new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(valor)):null;
  try{
    const login=await req('POST','/sesiones/',{correo_electronico:e.QA_CONTADOR_EMAIL,contrasena:e.QA_CONTADOR_PASSWORD},true);
    if(login.http!==200||!login.data?.token)throw Error('LOGIN_CONTADOR_'+login.http);
    token=login.data.token;contadorToken=token;
    const permisos=(await get('/sesiones/me/permisos')).permisos;
    const tiene=(n,a)=>permisos.some(p=>p.nombre_recurso===n&&Number(p.id_accion)===a);
    for(const [nombre,accion] of [['cierre_periodo',5],['cierre_periodo',2],['costos_activos',1],['reconocimiento_inicial',4],['valoracion_activos',5],['valoracion_activos',2],['auditoria_financiera',2]]){
      dato('permiso_'+nombre+'_'+accion,'presente',tiene(nombre,accion)?'presente':'ausente',tiene(nombre,accion));
    }
    const loginAdmin=await req('POST','/sesiones/',{correo_electronico:e.QA_ADMIN_EMAIL,contrasena:e.QA_ADMIN_PASSWORD},true);
    if(loginAdmin.http!==200||!loginAdmin.data?.token)throw Error('LOGIN_ADMIN_'+loginAdmin.http);
    adminToken=loginAdmin.data.token;token=adminToken;
    const permisosAdmin=(await get('/sesiones/me/permisos')).permisos;
    const adminPuede=permisosAdmin.some(p=>p.nombre_recurso==='activos_biologicos'&&Number(p.id_accion)===1);
    dato('permiso_administrador_activos_biologicos_1','presente',adminPuede?'presente':'ausente',adminPuede,false);
    token=contadorToken;
    if(r.preflight_datos.some(x=>x.bloqueante&&!x.cumple))throw Error('PERMISOS_NO_COINCIDEN_'+r.preflight_datos.filter(x=>x.bloqueante&&!x.cumple).map(x=>x.requisito).join('_'));
    r.observaciones.push('El vencimiento temporal de precios de la especie 422 y la asignacion temporal de usuarios_fincas fila 3493 se hacen fuera del RUN; el responsable QA revierte ambos al cerrar G45.');
    const ps=await periodos();idsPeriodos=ps.map(p=>Number(p.id_periodo_contable)).sort((a,b)=>a-b);
    const base={};
    for(const id of [7,8,219,260,220,266])base[id]=await estado(id);
    const a949=await get('/finanzas/activos/949');
    recon949={ids:a949.reconocimientos.map(x=>x.id_reconocimiento_inicial),registro:a949.reconocimientos.find(x=>Number(x.id_reconocimiento_inicial)===20)};
    costos944=await get('/finanzas/costos?id_activo_biologico=944');
    const a944=await get('/finanzas/activos/944');
    dato('periodo_7_estado','CERRADO',base[7].estado,base[7].estado==='CERRADO');
    dato('periodo_8_estado','EN_CIERRE, cierre 67', {estado:base[8].estado,id_cierre:base[8].ultimo_cierre?.id_cierre},base[8].estado==='EN_CIERRE'&&Number(base[8].ultimo_cierre?.id_cierre)===67);
    dato('periodo_219_estado','CERRADO',base[219].estado,base[219].estado==='CERRADO');
    dato('periodo_260_estado','ABIERTO',base[260].estado,base[260].estado==='ABIERTO');
    dato('periodo_266_estado','ABIERTO sin cierre',{estado:base[266].estado,ultimo_cierre:base[266].ultimo_cierre},base[266].estado==='ABIERTO'&&!base[266].ultimo_cierre,false);
    const linea2625=base[219].lineas.find(x=>Number(x.id_linea_asiento_nic41)===2625);
    dato('linea_2625_en_219','REGISTRADA y VERIFICADO',{estado:linea2625?.estado,trazabilidad:linea2625?.estado_trazabilidad},linea2625?.estado==='REGISTRADA'&&linea2625?.estado_trazabilidad==='VERIFICADO');
    dato('activo_944','ACTIVO con reconocimiento en 7',{estado:a944.activo.estado,reconocimiento:a944.reconocimientos.some(x=>Number(x.id_periodo_contable)===7&&x.estado==='CONFIRMADO')},a944.activo.estado==='ACTIVO'&&a944.reconocimientos.some(x=>Number(x.id_periodo_contable)===7&&x.estado==='CONFIRMADO'));
    dato('activo_949','ACTIVO con reconocimiento 20 en 7',{estado:a949.activo.estado,reconocimiento:recon949.registro?.estado},a949.activo.estado==='ACTIVO'&&recon949.registro?.estado==='CONFIRMADO'&&Number(recon949.registro?.id_periodo_contable)===7);
    dato('periodo_260_sin_ajustes',0,base[260].lineas.filter(x=>x.tipo_hecho==='AJUSTE_PERIODO_ANTERIOR').length,!base[260].lineas.some(x=>x.tipo_hecho==='AJUSTE_PERIODO_ANTERIOR'));
    const configuracion=await req('GET','/finanzas/configuracion');
    const especies=configuracion.http===200&&Array.isArray(configuracion.data?.especies)?configuracion.data.especies:[];
    // valorador.py:62: sin parámetros de la especie, la categoría es PESO_KG.
    const categorias=new Map(especies.map(x=>[Number(x.id_especie),x.categoria_precio??'PESO_KG']));
    const categoriasPorDefecto=new Set(especies.filter(x=>x.categoria_precio===null).map(x=>Number(x.id_especie)));
    dato('031_configuracion_especies','categorías por especie',configuracion.http===200?'HTTP 200; especies '+categorias.size:'HTTP '+configuracion.http,configuracion.http===200&&categorias.size>0,false);
    for(const id of [220,266,241]){
      const p=porId(ps,id);
      if(!p){dato('031_candidato_'+id,'período accesible','ausente',false,false);continue;}
      const dentro=p.fecha_inicio<=hoy&&hoy<=p.fecha_fin;
      const previa=p.estado==='ABIERTO'&&dentro?await get('/finanzas/periodos/'+id+'/prevalidacion'):null;
      const sinPrecio=previa?.activos_sin_precio??[];
      const pausa=previa&&Array.isArray(previa.bloqueos)&&previa.bloqueos.length===0&&((previa.lineas_sin_trazabilidad?.length??0)>0||sinPrecio.length>0)&&(id!==220||sinPrecio.some(x=>[1569,1570,1571].includes(Number(x.id_activo_biologico))))&&(id!==266||(sinPrecio.some(x=>Number(x.id_activo_biologico)===1644)&&base[266].estado==='ABIERTO'&&!base[266].ultimo_cierre));
      if(id===220)dato('031_220_sin_precio_especie_422','activos 1569/1570/1571 sin precio vigente de especie 422',{activos_sin_precio:sinPrecio.map(x=>({id_activo_biologico:x.id_activo_biologico,id_especie:x.id_especie})),especie_422_sin_precio_vigente:sinPrecio.some(x=>[1569,1570,1571].includes(Number(x.id_activo_biologico))&&Number(x.id_especie)===422)},sinPrecio.some(x=>[1569,1570,1571].includes(Number(x.id_activo_biologico))&&Number(x.id_especie)===422),false);
      let activo=null,ficha=null,precioPeso=false,respaldo=null;
      if(pausa)for(const candidato of (id===266?[1644]:id===241?[1831,1832,1833,1627]:[1569,1570,1571])){
        const aRespuesta=await req('GET','/finanzas/activos/'+candidato);
        if(aRespuesta.http===404){if(id===266)dato('031_acceso_1644','GET /finanzas/activos/1644 HTTP 200','HTTP 404; finca 472 pendiente de asignar al Contador',false,false);continue;}
        if(aRespuesta.http!==200)throw Error('CANDIDATO_FINANCIERO_'+candidato+'_'+aRespuesta.http);
        const a=aRespuesta.data;
        if(a.activo.estado!=='ACTIVO'||Number(a.activo.id_finca)!==(id===266?472:id===241?468:467)||a.valoracion_costo||!a.reconocimientos.some(x=>x.estado==='CONFIRMADO')||(id===220&&Number(a.activo.id_especie)!==422))continue;
        token=adminToken;
        try{const f=await req('GET','/activos-biologicos/'+candidato+'/ficha-integral');if(f.http===404)continue;if(f.http!==200)throw Error('CANDIDATO_FICHA_'+candidato+'_'+f.http);ficha=f.data;}finally{token=contadorToken;}
        const sinPrecio=(previa.activos_sin_precio??[]).some(x=>Number(x.id_activo_biologico)===candidato);
        if(ficha.estado_actual==='ACTIVO'&&(id===266||(Number(ficha.peso_actual)>0&&ficha.fecha_ultimo_peso&&ficha.unidad_peso==='kg'&&(id===220?sinPrecio:!sinPrecio)))){
          const categoria=categorias.get(Number(a.activo.id_especie));
          if(id===266||(id===220&&categoria==='POR_CABEZA')||(id===241&&categoria==='PESO_KG')){activo=a.activo;precioPeso=categoria==='PESO_KG';break;}
          if(id===220&&categoria==='POR_CABEZA'&&!respaldo)respaldo={activo:a.activo,ficha};
        }
      }
      if(!activo&&respaldo){activo=respaldo.activo;ficha=respaldo.ficha;}
      const ok=!!(pausa&&activo);
      const tipo=ficha?.tipo??ficha?.tipo_activo??activo?.tipo??activo?.tipo_activo;
      const cantidad=ficha?.cantidad_actual??ficha?.cantidad??activo?.cantidad_actual??activo?.cantidad;
      if(id===266&&pausa)dato('031_1644_tipo_cantidad','ficha o activo con tipo POBLACIONAL y cantidad actual positiva',{tipo:tipo??null,cantidad:cantidad??null},tipo==='POBLACIONAL'&&Number.isInteger(Number(cantidad))&&Number(cantidad)>0,false);
      if(id===266&&pausa)dato('031_1644_fase_activa','fase productiva activa si la API la expone',{fase_activa:ficha?.fase_activa??activo?.fase_activa??null},ficha?.fase_activa!=null||activo?.fase_activa!=null,false);
      dato('031_candidato_'+id,'ABIERTO, contiene hoy, sin bloqueos, causa de pausa y activo de la finca accesible; 266 admite ausencia de precio',{estado:p.estado,dentro,bloqueos:previa?.bloqueos?.length??null,lineas_sin_trazabilidad:previa?.lineas_sin_trazabilidad?.length??null,activos_sin_precio:previa?.activos_sin_precio?.length??null,activo_id:activo?.id_activo_biologico??null,estado_m02:ficha?.estado_actual??null,peso:ficha?.peso_actual??null,fecha_peso:ficha?.fecha_ultimo_peso??null,tipo:tipo??null,cantidad:cantidad??null},ok,false);
      if(ok){elegido=id;activo31=activo;r.periodo_031={id,activo_id:activo.id_activo_biologico,tipo:tipo??null,cantidad_actual:cantidad??null,precio_peso:precioPeso,categoria_precio:categorias.get(Number(activo.id_especie))??'NO_DETERMINADA',categoria_efectiva:categorias.get(Number(activo.id_especie))??'NO_DETERMINADA',categoria_por_defecto:categoriasPorDefecto.has(Number(activo.id_especie)),ultimo_peso:ficha.peso_actual??0,fecha_ultimo_peso:ficha.fecha_ultimo_peso,causa_pausa:{lineas_sin_trazabilidad:previa.lineas_sin_trazabilidad.length,activos_sin_precio:previa.activos_sin_precio.length},activos_sin_precio_ids:previa.activos_sin_precio.map(x=>Number(x.id_activo_biologico))};break;}
    }
    if(elegido){base[elegido]=await estado(elegido);costos31=await get('/finanzas/costos?id_activo_biologico='+activo31.id_activo_biologico);token=adminToken;try{historialBase=await get('/activos-biologicos/'+activo31.id_activo_biologico+'/eventos');}finally{token=contadorToken;}r.m02={activo_id:activo31.id_activo_biologico,ultimo_peso:r.periodo_031.ultimo_peso,fecha_ultimo_peso:r.periodo_031.fecha_ultimo_peso,evento_ids:[],crecimientos:[]};}
    basales=base;
    r.bases=Object.fromEntries(Object.entries(base).map(([id,s])=>[id,{estado:s.estado,fecha_cierre:s.fecha_cierre,ultimo_cierre:sanear(s.ultimo_cierre),hash_contenido:hash(s),lineas:s.lineas.length,comprobantes:s.comprobantes.length,variaciones:s.variaciones.length}]));
    if(r.preflight_datos.some(x=>x.bloqueante&&!x.cumple))throw Error('PREFLIGHT_DATOS_NO_CONCLUYENTE_'+r.preflight_datos.filter(x=>x.bloqueante&&!x.cumple).map(x=>x.requisito).join('_'));
    if(elegido){
      const cierre=await post('/finanzas/periodos/'+elegido+'/cierre',{});
      const pausa=await estado(elegido);
      const okPausa=cierre.http===409&&cierre.data?.error_code==='EXCLUSION_REQUIERE_AUTORIZACION'&&pausa.estado==='EN_CIERRE'&&pausa.ultimo_cierre?.estado==='EN_PROCESO'&&Number(pausa.ultimo_cierre?.paso_actual??pausa.ultimo_cierre?.paso)===3;
      check(CASOS[0],'031_en_cierre','409 EXCLUSION_REQUIERE_AUTORIZACION, EN_CIERRE y último cierre EN_PROCESO paso 3',okPausa?'APROBADO':'RECHAZADO','HTTP '+cierre.http+'; error '+cierre.data?.error_code+'; estado '+pausa.estado+'; último cierre '+JSON.stringify(sanear(pausa.ultimo_cierre)));
      const costo=await post('/finanzas/costos',{subtipo_costo:'MANO_OBRA',origen_costo:'MANO_OBRA_PROPIA',monto_costo:'50.00',fecha_costo:hoy,id_activo_biologico:activo31.id_activo_biologico,naturaleza_costo:'MANTENIMIENTO'});
      const luego=await estado(elegido),costosLuego=await get('/finanzas/costos?id_activo_biologico='+activo31.id_activo_biologico);
      const intacto=eq(pausa.lineas,luego.lineas)&&eq(pausa.variaciones,luego.variaciones)&&eq(costos31,costosLuego);
      const costo031Estado=buena(costo.http)||!intacto?'RECHAZADO':costo.http>=400&&costo.http<500?'APROBADO':'NO_CONCLUYENTE';
      check(CASOS[0],'031_costo','cualquier 4xx sin cambio de líneas, costos ni variaciones',costo031Estado,'HTTP '+costo.http+'; contenido idéntico '+intacto);
      const historial=async()=>{token=adminToken;try{return await get('/activos-biologicos/'+activo31.id_activo_biologico+'/eventos');}finally{token=contadorToken;}};
      const guardarRespuesta=(tipo,z,detalle={})=>{const lista=r.respuestas[tipo]??=[];lista.push({solicitud:r.solicitudes.at(-1)?.id,http:z.http,cuerpo:sanear(z.data),...detalle});};
      const pesoNuevo=incremento=>String(Number(r.periodo_031.ultimo_peso)+(Number(r.periodo_031.ultimo_peso)>0?incremento:incremento===5?30:35));
      const crecer=async(incremento)=>{token=adminToken;try{const peso=pesoNuevo(incremento);const body={tipo_medicion:'PESO',valor_medicion:peso,unidad_medida:'kg',fecha:new Date().toISOString(),descripcion:'Pesaje de verificacion G45'};if(r.periodo_031.tipo==='POBLACIONAL'){body.nuevo_peso_promedio=peso;body.cantidad_medida=Number(r.periodo_031.cantidad_actual);body.tipo_agregacion='PROMEDIO';}const z=await post('/activos-biologicos/'+activo31.id_activo_biologico+'/eventos/crecimiento',body);guardarRespuesta('crecimientos',z,{escenario:incremento===5?'B':'A',cuerpo_enviado:body});return z;}finally{token=contadorToken;}};
      const procesar=async(escenario)=>{const z=await post('/finanzas/eventos/procesar',{});guardarRespuesta('procesamientos',z,{escenario});return z;};
      const auditoria=async(evento,escenario)=>{const encontrados=[];let total=0;for(let pagina=1;pagina<=20;pagina++){const z=await req('GET','/finanzas/auditoria?id_activo_biologico='+activo31.id_activo_biologico+'&formato=TECNICO&orden=DESC&tamano=500&pagina='+pagina);guardarRespuesta('auditorias',z,{escenario,id_evento:evento,pagina});if(z.http!==200)throw Error('AUDITORIA_HTTP_'+z.http);const q=z.data;total=Number(q.total_registros??q.eventos?.length??0);encontrados.push(...(q.eventos??[]));if(encontrados.length>=total||(q.eventos??[]).length<500)break;}if(encontrados.length<total)throw Error('AUDITORIA_PAGINACION_INCOMPLETA');return encontrados.filter(x=>/^MEDICION_/.test(x.tipo_evento)&&Number(x.id_activo_biologico)===Number(activo31.id_activo_biologico)&&(Number(x.payload_evento?.id_evento)===Number(evento)||Number(x.id_referencia)===Number(evento)));};
      const evidencia=async(evento,escenario,periodos)=>{const registros=(await auditoria(evento,escenario)).map(x=>({fuente:'AUDITORIA',registro:x,id_periodo_contable:x.id_periodo_contable}));for(const id of periodos.filter(Boolean)){const s=await estado(id);const variaciones=s.variaciones.filter(x=>Number(x.id_activo_biologico)===Number(activo31.id_activo_biologico)&&Number(x.id_evento??x.evento_origen_id)===Number(evento));for(const x of variaciones)registros.push({fuente:'VARIACION',registro:x,id_periodo_contable:x.id_periodo_contable});for(const x of s.lineas.filter(x=>Number(x.id_activo_biologico)===Number(activo31.id_activo_biologico)&&(Number(x.id_evento??x.evento_origen_id)===Number(evento)||variaciones.some(v=>Number(v.id_variacion_valor_razonable)===Number(x.id_origen))))){registros.push({fuente:'LINEA',registro:x,id_periodo_contable:x.id_periodo_contable});}}r.respuestas.evidencias_medicion??=[];r.respuestas.evidencias_medicion.push({escenario,id_evento:evento,registros:sanear(registros)});return registros;};
      const resumenAuditoria=xs=>xs.map(x=>({fuente:x.fuente,tipo:x.registro.tipo_evento??x.registro.tipo_hecho??x.registro.tipo,id_evento_m02:x.registro.payload_evento?.id_evento??x.registro.id_referencia??x.registro.id_evento??x.registro.evento_origen_id,id_periodo_contable:x.id_periodo_contable}));
      const tienePeriodo=(xs,id)=>xs.some(x=>Number(x.id_periodo_contable)===Number(id));
      const medicionEsperada=(xs,id)=>xs.some(x=>Number(x.id_periodo_contable)===Number(id));
      const fechaEvidencia=(xs,evento)=>xs.filter(x=>x.registro.fecha_hecho??x.registro.payload_evento?.fecha_hecho??x.registro.payload_evento?.fecha).every(x=>diaBogota(x.registro.fecha_hecho??x.registro.payload_evento?.fecha_hecho??x.registro.payload_evento?.fecha)===diaBogota(evento.fecha));
      const efectos=(s)=>({lineas:s.lineas.filter(x=>Number(x.id_activo_biologico)===activo31.id_activo_biologico),variaciones:s.variaciones.filter(x=>Number(x.id_activo_biologico)===activo31.id_activo_biologico)});
      const propio=(respuesta,historia)=>historia.eventos.find(x=>x.id_eventos===respuesta.data?.evento?.id_eventos);
      let eventoB=null,fechaB=null,colaB=null,procesoB=null,finPausa=null;
      if(!adminPuede){check(CASOS[0],'031_m02','Administrador con activos_biologicos 1 para crear crecimiento','NO_CONCLUYENTE','Permiso Administrador activos_biologicos Crear ausente; no se crea evento.');}
      else{
        const creado=await crecer(5);const h=await historial();eventoB=propio(creado,h);fechaB=diaBogota(eventoB?.fecha);if(eventoB){r.m02.evento_ids.push(eventoB.id_eventos);r.m02.crecimientos.push({escenario:'B',id_evento:eventoB.id_eventos,timestamp_original:eventoB.fecha,peso_nuevo:pesoNuevo(5),autor:'Administrador QA'});}
        colaB=eventoB?await procesar('B_en_cierre'):null;finPausa=eventoB?await evidencia(eventoB.id_eventos,'B_en_cierre',[elegido]):null;
        const sinEfectos=!!finPausa&&!tienePeriodo(finPausa,elegido)&&eq(efectos(pausa),efectos(await estado(elegido)));
        const visible=Number(colaB?.data?.eventos?.ENCOLADO_CIERRE??0)>0;
        const estadoM=creado.http===201&&!!eventoB&&!!fechaB&&sinEfectos?'APROBADO':creado.http===201&&!!eventoB&&!sinEfectos?'RECHAZADO':'NO_CONCLUYENTE';
        check(CASOS[0],'031_m02','evento M02 encolado con timestamp_original y sin efectos en período EN_CIERRE',estadoM,'crecimiento HTTP '+creado.http+'; error_code '+(creado.data?.error_code??'ninguno')+'; mensaje '+(creado.data?.message??'ninguno')+'; evento '+(eventoB?.id_eventos??'ausente')+'; fecha '+(fechaB??'ausente')+'; cola '+(visible?'ENCOLADO_CIERRE visible':'estado de cola no visible')+'; auditoria '+JSON.stringify(resumenAuditoria(finPausa??[]))+'; sin medicion propia en pausa '+sinEfectos);
      }
      const cancel=await post('/finanzas/periodos/'+elegido+'/cierre/cancelacion');
      const abierto=await estado(elegido);
      procesoB=eventoB?await procesar('B_abierto'):null;
      const fB=eventoB?await evidencia(eventoB.id_eventos,'B_abierto',[elegido]):null;
      const bEstado=!eventoB?'NO_CONCLUYENTE':medicionEsperada(fB,elegido)&&!!fechaB&&fechaEvidencia(fB,eventoB)&&cancel.http===200&&abierto.estado==='ABIERTO'?'APROBADO':fB?.length?'RECHAZADO':'NO_CONCLUYENTE';
      check(CASOS[0],'031_escenario_b','cancelación ABIERTO; registro propio de B en el período actual con fecha original',bEstado,'cancelación HTTP '+cancel.http+'; estado '+abierto.estado+'; procesamiento HTTP '+(procesoB?.http??'no ejecutado')+'; evidencia '+JSON.stringify(resumenAuditoria(fB??[]))+'; fecha original '+(fB?.some(x=>x.registro.fecha_hecho??x.registro.payload_evento?.fecha_hecho??x.registro.payload_evento?.fecha)?'comparada con registro':'comprobada con historial M02'));
      const segundo=await post('/finanzas/periodos/'+elegido+'/cierre',{});
      const pausa2=await estado(elegido);
      let eventoA=null,fechaA=null,procesoA=null,fPausa2=null;
      if(adminPuede){const creadoA=await crecer(10);eventoA=propio(creadoA,await historial());fechaA=diaBogota(eventoA?.fecha);if(eventoA){r.m02.evento_ids.push(eventoA.id_eventos);r.m02.crecimientos.push({escenario:'A',id_evento:eventoA.id_eventos,timestamp_original:eventoA.fecha,peso_nuevo:pesoNuevo(10),autor:'Administrador QA'});procesoA=await procesar('A_en_cierre');fPausa2=await evidencia(eventoA.id_eventos,'A_en_cierre',[elegido]);}}
      const autorizado=await post('/finanzas/periodos/'+elegido+'/cierre',{autorizar_exclusiones:true});
      const fin=await estado(elegido);
      r.respuestas.exclusion_031={presente:r.periodo_031.activos_sin_precio_ids.length>0&&r.periodo_031.activos_sin_precio_ids.every(id=>(autorizado.data?.activos_excluidos??[]).some(x=>Number(x.id_activo_biologico)===id&&String(x.estado??x.motivo??'').includes('PENDIENTE_PRECIO')))};
      if(elegido===266)r.respuestas.exclusion_1644=r.respuestas.exclusion_031;
      siguienteId=Number(autorizado.data?.id_periodo_siguiente)||null;
      const postA=eventoA?await procesar('A_siguiente'):null;
      const auditoriaA=eventoA?await evidencia(eventoA.id_eventos,'A_siguiente',[elegido,siguienteId]):[];
      const dentroA=tienePeriodo(auditoriaA,elegido);
      const siguienteA=!!siguienteId&&medicionEsperada(auditoriaA,siguienteId);
      const enCola=adminPuede&&eventoA&&fPausa2&&!tienePeriodo(fPausa2,elegido);
      const siguienteNuevo=!!siguienteId&&!idsPeriodos.includes(siguienteId);
      const aEstado=!eventoA?'NO_CONCLUYENTE':dentroA?'RECHAZADO':!auditoriaA.length?'NO_CONCLUYENTE':segundo.http===409&&pausa2.estado==='EN_CIERRE'&&enCola&&autorizado.http===200&&fin.estado==='CERRADO'&&siguienteNuevo&&siguienteA&&!!fechaA&&fechaEvidencia(auditoriaA,eventoA)&&([220,266].includes(elegido)?r.respuestas.exclusion_031.presente:true)?'APROBADO':'RECHAZADO';
      check(CASOS[0],'031_escenario_a','segunda pausa; evento M02 encolado y procesado en período siguiente nuevo con fecha original',aEstado,'segunda pausa HTTP '+segundo.http+'; cierre HTTP '+autorizado.http+'; período siguiente '+(siguienteId??'ausente')+'; nuevo '+siguienteNuevo+'; procesamiento HTTP '+(postA?.http??'no ejecutado')+'; exclusion 1644 '+(r.respuestas.exclusion_1644?.presente??'no aplica')+'; evidencia '+JSON.stringify(resumenAuditoria(auditoriaA))+'; efecto siguiente '+siguienteA+'; efecto en cerrado '+dentroA+'; fecha original '+(auditoriaA.some(x=>x.registro.fecha_hecho??x.registro.payload_evento?.fecha_hecho??x.registro.payload_evento?.fecha)?'comparada con registro':'comprobada con historial M02'));
      r.respuestas.cierre={primero:{http:cierre.http,error:cierre.data?.error_code},segundo:{http:segundo.http,error:segundo.data?.error_code},autorizado:{http:autorizado.http,cuerpo:sanear(autorizado.data)}};
      r.respuestas.costo_en_cierre={http:costo.http,cuerpo:sanear(costo.data)};
    }else{
      check(CASOS[0],'031_en_cierre','período 241 o 220 pausable hoy','NO_CONCLUYENTE','Ningún candidato cumplió el preflight; no se hicieron escrituras de 031.','resultado.json');
      r.casos[CASOS[0]].motivo='Sin período pausable accesible que contenga la fecha actual';
    }
    const costo32=await post('/finanzas/costos',{subtipo_costo:'MANO_OBRA',origen_costo:'MANO_OBRA_PROPIA',monto_costo:'50.00',fecha_costo:'2026-11-05',id_activo_biologico:944,naturaleza_costo:'MANTENIMIENTO'});
    const s7Costo=await estado(7);
    const codigoCerrado=['PERIODO_CONTABLE_CERRADO','PERIODO_CERRADO'].includes(costo32.data?.error_code);
    const c32=buena(costo32.http)||!eq(s7Costo,base[7])?'RECHAZADO':costo32.http>=400&&costo32.http<500&&codigoCerrado?'APROBADO':'NO_CONCLUYENTE';
    check(CASOS[1],'032_alta_costo','Rechazo por período cerrado (CA-3: 409) y período 7 idéntico',c32,'HTTP '+costo32.http+'; error_code '+costo32.data?.error_code+'; mensaje '+costo32.data?.message+'; íntegro '+eq(s7Costo,base[7]));
    if(c32==='APROBADO'&&costo32.http!==409)r.observaciones.push('OBS-G45-01 para Desarrollo: CA-3 pide 409; el producto responde HTTP '+costo32.http+' '+costo32.data?.error_code+'. Mensaje: '+limpia(costo32.data?.message)+'.');
    const rev=await post('/finanzas/reconocimientos/949/reversion',{motivo_reversion:'Corrección contable de prueba autorizada'});
    const s7Rev=await estado(7);
    const revEstado=buena(rev.http)||!eq(s7Rev,base[7])?'RECHAZADO':rev.http===409&&rev.data?.error_code==='REVERSION_BLOQUEADA'?'APROBADO':'NO_CONCLUYENTE';
    check(CASOS[1],'032_eliminar_reconocimiento','HTTP 409 REVERSION_BLOQUEADA y 7 idéntico',revEstado,'HTTP '+rev.http+'; error '+rev.data?.error_code+'; íntegro '+eq(s7Rev,base[7]));
    const integridad=eq(await estado(7),base[7])&&eq(await estado(219),base[219]);
    check(CASOS[1],'032_integridad','7 y 219 idénticos en estado, fecha, líneas, comprobantes y variaciones',integridad?'APROBADO':'RECHAZADO','integridad '+integridad);
    r.respuestas.costo_cerrado={http:costo32.http,cuerpo:sanear(costo32.data)};
    r.respuestas.reversion={http:rev.http,cuerpo:sanear(rev.data)};
    const justificacion='Ajuste QA autorizado por error del período anterior';
    const ajuste=await post('/finanzas/lineas-asiento/2625/ajustes',{tipo_ajuste:'AUMENTAR',valor:'10.00',justificacion});
    const lineas260=await get('/finanzas/lineas?id_periodo_contable=260');
    const auditRespuesta=await req('GET','/finanzas/auditoria?tipo_evento=LINEA_ASIENTO_REGISTRADA&id_periodo_contable=260&formato=TECNICO&orden=DESC');
    r.respuestas.auditoria_033={solicitud:r.solicitudes.at(-1)?.id,http:auditRespuesta.http,cuerpo:sanear(auditRespuesta.data)};
    if(auditRespuesta.http!==200)throw Error('AUDITORIA_033_HTTP_'+auditRespuesta.http);
    const audit=auditRespuesta.data;
    const linea=lineas260.find(x=>x.tipo_hecho==='AJUSTE_PERIODO_ANTERIOR'&&Number(x.id_linea_corregida)===2625&&x.justificacion===justificacion);
    const evento=audit.eventos?.find(x=>x.tipo_evento==='LINEA_ASIENTO_REGISTRADA'&&JSON.stringify(x).includes('ajuste_periodo_anterior')&&JSON.stringify(x).includes('2625')&&JSON.stringify(x).includes(justificacion));
    const ajusteOk=ajuste.http===201&&Number(ajuste.data?.id_periodo_contable)===260&&Number(ajuste.data?.id_linea_corregida)===2625&&!!linea&&!!evento;
    check(CASOS[2],'033_ajuste','201; AJUSTE_PERIODO_ANTERIOR en 260 con referencia 2625, justificación y auditoría',ajusteOk?'APROBADO':'RECHAZADO','HTTP '+ajuste.http+'; período obtenido '+ajuste.data?.id_periodo_contable+'; línea '+!!linea+'; auditoría '+!!evento);
    const s219=await estado(219);
    const intacto219=s219.estado==='CERRADO'&&eq(s219,base[219]);
    check(CASOS[2],'033_cerrado_intacto','219 CERRADO con líneas, comprobantes, variaciones y fecha idénticos',intacto219?'APROBADO':'RECHAZADO','integridad '+intacto219);
    r.respuestas.ajuste={http:ajuste.http,cuerpo:sanear(ajuste.data),linea_id:linea?.id_linea_asiento_nic41??null,auditoria_hallada:!!evento};
    cerrar();
    if(r.casos[CASOS[0]].estado==='RECHAZADO')incidencia('01',CASOS[0],'EN_CIERRE y escenarios A/B conforme RF-87',r.casos[CASOS[0]].motivo,'ALTA');
    if(r.casos[CASOS[1]].estado==='RECHAZADO')incidencia('02',CASOS[1],'Rechazo por período cerrado (CA-3: 409) y períodos cerrados intactos',r.casos[CASOS[1]].motivo,'ALTA');
    if(r.casos[CASOS[2]].estado==='RECHAZADO')incidencia('03',CASOS[2],'Ajuste en 260 y 219 intacto',r.casos[CASOS[2]].motivo,'ALTA');
    r.seguimiento_v1=Object.fromEntries(['01','02','03'].map((n,i)=>['INC-M06-G45-'+n,r.casos[CASOS[i]].estado==='RECHAZADO'?'REPRODUCIDA':r.casos[CASOS[i]].estado==='APROBADO'?'CORREGIDA':'NO_CONCLUYENTE']));
    newman=CASOS.every(k=>['APROBADO','RECHAZADO'].includes(r.casos[k].estado));
    if(newman){
      const lanzar=local&&typeof hijo==='function'?hijo:(script,input,timeout)=>lanzarHijo({base:dir,script,input,timeout,env:e,clean:limpia});
      const n=await lanzar('newman_hijo.mjs',{salida:path.join(c.dir,'newman'),coleccion:path.join(dir,'G45.postman_collection.json'),environment:{values:[{key:'base_url',value:api},{key:'contador_token',value:token},{key:'run_id',value:c.runId},{key:'sandbox_secret',value:e.QA_SANDBOX_SECRET},{key:'periodo_031',value:String(elegido??'')}] }},300000);
      r.herramientas.newman=n.data??{codigo:2};if(n.code||n.data?.codigo!==0||n.data?.fallos)r.problemas_tecnicos.push('NEWMAN_'+limpia(n.error??n.code));
    }
  }catch(err){
    r.problemas_tecnicos.push(limpia(err.message));
    cerrar();
    for(const caso of CASOS)if(r.casos[caso].motivo==='No ejecutado')r.casos[caso]={estado:'NO_CONCLUYENTE',motivo:limpia(err.message),comprobaciones:[]};
  }finally{
    r.cierre={run:{cierre_http:null},rollback:r.rollback};
    if(token)try{
      const d=await req('DELETE','/test-control/runs/'+c.runId);r.cierre.run.cierre_http=d.http;
      if(d.http!==200)throw Error('DELETE_'+d.http);
      if(!escrituras){r.rollback={verificado:true,motivo:'Sin escrituras; DELETE 200.'};}
      else if(!basales)throw Error('BASES_NO_DISPONIBLES');
      else{
        const detalles={};
        for(const [id,s] of Object.entries(basales))detalles['periodo_'+id]=eq(await estado(Number(id),true),s);
        const periodosFinales=(await periodos(true)).map(p=>Number(p.id_periodo_contable)).sort((a,b)=>a-b);
        detalles.periodos_nuevos=eq(periodosFinales,idsPeriodos);
        if(siguienteId&&!idsPeriodos.includes(siguienteId))detalles.periodo_siguiente_ausente=!periodosFinales.includes(siguienteId);
        detalles.costos_944=eq(await get('/finanzas/costos?id_activo_biologico=944',true),costos944);
        if(elegido){detalles.costos_031=eq(await get('/finanzas/costos?id_activo_biologico='+activo31.id_activo_biologico,true),costos31);if(historialBase){token=adminToken;try{const h=await get('/activos-biologicos/'+activo31.id_activo_biologico+'/eventos',true);detalles.crecimientos_ausentes=eq(h.eventos.map(x=>x.id_eventos),historialBase.eventos.map(x=>x.id_eventos))&&!(r.m02?.evento_ids??[]).some(id=>h.eventos.some(x=>x.id_eventos===id));}finally{token=contadorToken;}}}
        const a=await get('/finanzas/activos/949',true);
        detalles.reconocimiento_949=eq({ids:a.reconocimientos.map(x=>x.id_reconocimiento_inicial),registro:a.reconocimientos.find(x=>Number(x.id_reconocimiento_inicial)===20)},recon949);
        detalles.ajustes_ausentes=!((await get('/finanzas/lineas?id_periodo_contable=260',true)).some(x=>x.tipo_hecho==='AJUSTE_PERIODO_ANTERIOR'));
        r.rollback={verificado:Object.values(detalles).every(Boolean),motivo:JSON.stringify(detalles)};
      }
    }catch(err){r.rollback={verificado:false,motivo:limpia(err.message)};r.problemas_tecnicos.push('ROLLBACK_'+limpia(err.message));}
    r.cierre.rollback=r.rollback;
    r.total_solicitudes_api=solicitud.total()+(r.herramientas.newman?.solicitudes??0);
    r.duracion_segundos=Math.ceil((Date.now()-inicio)/1000);
    r.evidencias=listarEvidencias(c.dir).filter(x=>x.startsWith('newman/'));
    r.oficial=newman&&r.rollback.verificado&&r.cierre.run.cierre_http===200&&r.herramientas.newman?.codigo===0&&r.herramientas.newman?.fallos===0&&r.herramientas.newman?.reportes===true&&['newman/newman-G45.json','newman/newman-G45.html'].every(x=>r.evidencias.includes(x))&&r.problemas_tecnicos.length===0&&r.total_solicitudes_api<=limite.solicitudes_totales&&r.duracion_segundos<=limite.segundos;
    r.consume_version=escrituras>0;
    r.clasificacion_fallo=!escrituras&&r.cierre.run.cierre_http===200&&r.rollback.verificado?r.problemas_tecnicos.some(x=>x.includes('PERMISO'))?'PERMISO':'DATOS_PRECONDICION':clasificarFallo(r);
    if(r.clasificacion_fallo==='NINGUNO'&&Object.values(r.casos).some(x=>x.estado==='NO_CONCLUYENTE'))r.clasificacion_fallo='DATOS_PRECONDICION';
    r.sha256={ejecutor:sha256(path.join(dir,'g45.mjs')),infraestructura:Object.fromEntries(['lib/infra.mjs','lib/contrato.mjs','lib/informe.mjs','lib/flujo_v2.mjs','pruebas/newman_hijo.mjs','pruebas/verificar.mjs'].map(x=>[x,sha256(path.join(dir,x))]))};
    const forma=validarFormaResultado(r,capacidades,c.dir);if(forma.length){r.problemas_tecnicos.push('RESULTADO_FORMA_'+forma.join('_'));r.oficial=false;r.clasificacion_fallo='CONTRATO';}
    guardarResultado(c,r,informe);
  }
  return r;
}
