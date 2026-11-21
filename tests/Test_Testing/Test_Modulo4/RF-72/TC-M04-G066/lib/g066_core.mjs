export const CASOS = [200,201,202,203,204].map(n => `TC-M04-${n}`);
export const IDS = [200,201,202,203,204].map(n => `API-${n}-01`);
export const REGISTROS = [
  ['200-una',0,1,true], ['201-tres',1,3,true],
  ['202-una',2,1,true], ['202-dos',2,2,true], ['202-tres',2,3,true], ['202-cuatro',2,4,false],
  ['203-inexistente',3,1,false], ['203-mixta',3,3,false], ['204-inactiva',4,1,false]
].map(([clave,i,lista,valido]) => ({clave,caso:CASOS[i],lista,valido}));
// 1 login + 4 activos + 128 historial descubrimiento + 8 versiones + 1 catálogo
// + 18 POST + 27 historial + 9 auditoría + 1 login admin + 9 auditoría
// + 1 PATCH contingente + 1 DELETE + 27 historial poscierre + 1 catálogo poscierre = 236.
export const PRESUPUESTO = Object.freeze({solicitudes_totales:236,paginas_activos:4,activos_maximos:32,
  paginas_historial_descubrimiento:4,versiones_maximas:8,paginas_historial_verificacion:3,
  reemplazos_por_registro:1,dias_busqueda:88,timeout_login_ms:120000,timeout_ms:30000,duracion_segundos:900});
export const CAPACIDADES = Object.freeze({contrato:'sigab-qa-ejecutor/1',grupo:'G066',casos:CASOS,
  operaciones:['evaluar','reintentar','reevaluar','recuperar'],versiones:{min:1,max:99},
  comprobaciones_obligatorias:Object.fromEntries(CASOS.map((c,i)=>[c,{API:[IDS[i]]}])),
  limite:{solicitudes_totales:PRESUPUESTO.solicitudes_totales,duracion_segundos:900}});
export function usuarioDelToken(token) { try { const sub=JSON.parse(Buffer.from(String(token).split('.')[1],'base64url')).sub;
  return /^\d+$/.test(String(sub))?String(sub):null; } catch { return null; } }
export const tipoModelo=(e,v={})=>e?.payload?.tipo_modelo??v[String(e?.payload?.id_version_modelo)]??null;
export function patologiasActivasPara(patologias, especie) {
  return patologias.filter(p => p.es_activo && Number(p.id_patologia) !== 7
    && ['TODAS', String(especie)].includes(String(p.especie_aplicable)))
    .sort((a,b) => (Number(String(b.especie_aplicable) === 'TODAS' && b.id_patologia >= 8 && b.id_patologia <= 14)
      - Number(String(a.especie_aplicable) === 'TODAS' && a.id_patologia >= 8 && a.id_patologia <= 14))
      || Number(a.id_patologia) - Number(b.id_patologia));
}
export function diagnosticar(eventos,usuarioId,versiones={}) {
  const por_modelo={};for(const e of eventos.filter(x=>x.tipo_evento==='INFERENCIA')) {
    const tipo=tipoModelo(e,versiones)??'sin_tipo';por_modelo[tipo]=(por_modelo[tipo]??0)+1;}
  return {eventos:eventos.length,por_modelo,usuario_id_presente:usuarioId!=null};
}
export function seleccionar(eventos,usados,usuarioId,versiones,inicio,fin) {
  const propias=new Set(eventos.filter(e=>e.tipo_evento==='RETROALIMENTACION'
    && String(e.payload?.id_usuario_veterinario)===String(usuarioId)).map(e=>String(e.id_resultado_inferencia)));
  return eventos.filter(e=>e.tipo_evento==='INFERENCIA'
    && ['MODELO_ESPECIES_MEDIANAS','MODELO_ESPECIES_GRANDES'].includes(tipoModelo(e,versiones))
    && !propias.has(String(e.id_resultado_inferencia))&&!usados.has(String(e.id_resultado_inferencia))
    && Date.parse(e.fecha_evento)>=Date.parse(inicio)&&Date.parse(e.fecha_evento)<=Date.now()
    && Date.parse(e.fecha_evento)<=Date.parse(fin+'T23:59:59.999Z'))
    .sort((a,b)=>Date.parse(b.fecha_evento)-Date.parse(a.fecha_evento));
}
export const iguales=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export function verificarRegistro(reg,post,h,a,usuarioId) {
  if(post?.http==null)return {estado:'NO_CONCLUYENTE',motivo:'POST sin respuesta; conciliar'};
  if(post.http===403)return {estado:'BLOQUEADO',motivo:'HTTP 403 de clave o permiso'};
  if([409,422].includes(post.http)&&['RETROALIMENTACION_DUPLICADA','FUERA_DE_VENTANA_TEMPORAL'].includes(post.cuerpo?.error_code))
    return {estado:'NO_CONCLUYENTE',motivo:'Resultado no apto'};
  const fallos=[],dudas=[],b=post.cuerpo??{};
  if(post.eco!==true)dudas.push('POST sin eco del RUN');
  if(reg.valido){
    if(post.http!==201)fallos.push(`HTTP ${post.http}; esperado 201`);
    else {if(!b.id_retroalimentacion||String(b.id_resultado_inferencia)!==String(reg.dato.id_resultado_inferencia))fallos.push('identidad incorrecta');
      if(!iguales(b.diagnosticos_reales,reg.enviada))fallos.push('lista u orden distintos en respuesta');}
  } else {
    const e5=reg.caso===CASOS[3]||reg.caso===CASOS[4];
    if(e5?post.http!==422:![400,422].includes(post.http))fallos.push(`HTTP ${post.http}; esperado ${e5?'422':'rechazo 400 o 422'}`);
    const texto=`${b.message??''} ${JSON.stringify(b.fields??[])}`.toLowerCase();
    if(reg.caso===CASOS[2]){if(!/3|tres/.test(texto)||!/max|long|m[aá]s de|at most/.test(texto)||!texto.includes('diagnosticos_reales'))
      fallos.push('rechazo sin campo y máximo 3');}
    else if(!/patolog[ií]a|diagn[oó]stico/.test(texto)||!/no es v[aá]lida|no est[aá] activa|no v[aá]lid/.test(texto))
      fallos.push('mensaje sin patología no válida o inactiva');
  }
  const eventos=(h?.eventos??[]).filter(e=>e.tipo_evento==='RETROALIMENTACION'
    && String(e.id_resultado_inferencia)===String(reg.dato.id_resultado_inferencia)
    && String(e.payload?.id_usuario_veterinario)===String(usuarioId));
  const audits=(a?.items??[]).filter(e=>e.tipo_evento==='RETROALIMENTACION_REGISTRADA'
    && String(e.payload_evento?.id_resultado_inferencia)===String(reg.dato.id_resultado_inferencia));
  if(h?.http!==200||h.eco!==true||!h.completo)dudas.push('historial incompleto');
  if(a?.http!==200||a.eco!==true||!a.completo)dudas.push('auditoría incompleta');
  if(reg.valido&&post.http===201){
    const evento=eventos.find(e=>String(e.id_evento)===String(b.id_retroalimentacion));
    const audit=audits.find(e=>String(e.id_referencia)===String(b.id_retroalimentacion));
    if(h?.completo&&!evento)fallos.push('retroalimentación ausente de historial');
    if(a?.completo&&!audit)fallos.push('retroalimentación ausente de auditoría');
    if(evento&&!iguales(evento.payload?.diagnosticos_reales,reg.enviada))fallos.push('lista u orden distintos en historial');
    if(audit&&!iguales(audit.payload_evento?.diagnosticos_reales,reg.enviada))fallos.push('lista u orden distintos en auditoría');
  } else if(!reg.valido){
    if(h?.completo&&eventos.length)fallos.push('persistió registro inválido');
    if(a?.completo&&audits.length)fallos.push('se auditó registro inválido');
  }
  return {estado:fallos.length?'RECHAZADO':dudas.length?'NO_CONCLUYENTE':'APROBADO',
    motivo:fallos.join('; ')||dudas.join('; ')||(!reg.valido&&reg.caso===CASOS[2]&&post.http===400
      ?'Rechazo completo sin persistencia; observación HTTP 400 en lugar del 422 recomendado'
      :'HTTP, lista, historial y auditoría concordantes')};
}
