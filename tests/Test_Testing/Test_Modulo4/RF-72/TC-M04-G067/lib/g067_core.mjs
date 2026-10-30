export const CASOS = [205,206,207,208,209].map(n => `TC-M04-${n}`);
export const IDS = CASOS.map(c => `API-${c.slice(-3)}-01`);
export const REGISTROS = [
  ['209-correcto-sin',4,'CORRECTO','omitido',true],
  ['209-correcto-con',4,'CORRECTO','uno',true],
  ['209-sin-evento-sin',4,'SIN_EVENTO','omitido',true],
  ['209-sin-evento-con',4,'SIN_EVENTO','otro',true],
  ['207-omitido',2,'PARCIAL','omitido',false],
  ['207-vacio',2,'PARCIAL','vacio',false],
  ['208-omitido',3,'INCORRECTO','omitido',false],
  ['208-vacio',3,'INCORRECTO','vacio',false],
  ['206-ausente',1,null,'uno',false],
  ['205-inexistente',0,'DESCONOCIDO','uno',false],
  ['205-vacio',0,'','uno',false],
  ['205-numerico',0,123,'uno',false],
  ['205-minusculas',0,'correcto','uno',false]
].map(([clave,i,estado,diagnostico,valido]) => ({clave,caso:CASOS[i],estado,diagnostico,valido}));
// 1 login + 4 activos + 128 páginas de descubrimiento + 8 versiones + 1 catálogo
// + 26 POST (13 originales + 13 reemplazos) + 39 páginas de historial de verificación
// + 13 auditorías + 1 DELETE + 39 páginas de historial poscierre = 260.
export const PRESUPUESTO = Object.freeze({solicitudes_totales:260,paginas_activos:4,activos_maximos:32,
  paginas_historial_descubrimiento:4,versiones_maximas:8,paginas_historial_verificacion:3,
  reemplazos_por_registro:1,dias_busqueda:88,timeout_login_ms:120000,timeout_ms:30000,duracion_segundos:900});
export const CAPACIDADES = Object.freeze({contrato:'sigab-qa-ejecutor/1',grupo:'G067',casos:CASOS,
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
const texto = b => `${b?.message??''} ${(b?.fields??[]).map(f=>`${f.field??''} ${f.message??''}`).join(' ')}`.toLowerCase();
const eventosDe = (h, reg, usuarioId) => (h?.eventos??[]).filter(e=>e.tipo_evento==='RETROALIMENTACION'
  && String(e.id_resultado_inferencia)===String(reg.dato.id_resultado_inferencia)
  && String(e.payload?.id_usuario_veterinario)===String(usuarioId));
export function verificarRegistro(reg,post,h,a,usuarioId) {
  if(post?.http==null)return {estado:'NO_CONCLUYENTE',motivo:'POST sin respuesta; conciliación requerida'};
  if(post.http===403)return {estado:'BLOQUEADO',motivo:'HTTP 403 de clave o permiso'};
  if([409,422].includes(post.http)&&['RETROALIMENTACION_DUPLICADA','FUERA_DE_VENTANA_TEMPORAL'].includes(post.cuerpo?.error_code))
    return {estado:'NO_CONCLUYENTE',motivo:'Resultado no apto'};
  const fallos=[],dudas=[],b=post.cuerpo??{},t=texto(b);
  if(post.eco!==true)dudas.push('POST sin eco del RUN');
  if(reg.valido){
    if(post.http!==201)fallos.push(`HTTP ${post.http}; esperado 201`);
    else if(!b.id_retroalimentacion||String(b.id_resultado_inferencia)!==String(reg.dato.id_resultado_inferencia))
      fallos.push('identidad de registro incorrecta');
  } else if(reg.caso===CASOS[0]) {
    if(post.http!==422)fallos.push(`HTTP ${post.http}; E3 exige 422`);
    if(!/estado.*(no es v[aá]lid|inv[aá]lid)/.test(t))fallos.push('mensaje sin estado no válido');
  } else if(reg.caso===CASOS[1]) {
    if(![400,422].includes(post.http))fallos.push(`HTTP ${post.http}; esperado rechazo`);
    if(!t.includes('estado_retroalimentacion')||!/obligatori|requerid/.test(t))
      fallos.push('rechazo sin campo estado_retroalimentacion requerido');
  } else {
    if(post.http!==422)fallos.push(`HTTP ${post.http}; E4 exige 422`);
    if(!/diagn[oó]stico.*obligatori/.test(t))fallos.push('mensaje sin diagnóstico obligatorio');
  }
  const eventos=eventosDe(h,reg,usuarioId);
  const audits=(a?.items??[]).filter(e=>e.tipo_evento==='RETROALIMENTACION_REGISTRADA'
    && String(e.payload_evento?.id_resultado_inferencia)===String(reg.dato.id_resultado_inferencia));
  if(h?.http!==200||h.eco!==true||!h.completo)dudas.push('historial incompleto');
  if(a?.http!==200||a.eco!==true||!a.completo)dudas.push('auditoría incompleta');
  if(reg.valido&&post.http===201){
    if(h?.completo&&!eventos.some(e=>String(e.id_evento)===String(b.id_retroalimentacion)))fallos.push('registro ausente de historial');
    if(a?.completo&&!audits.some(e=>String(e.id_referencia)===String(b.id_retroalimentacion)))fallos.push('registro ausente de auditoría');
  } else if(!reg.valido){
    if(h?.completo&&eventos.length)fallos.push('persistió registro inválido');
    if(a?.completo&&audits.length)fallos.push('se auditó registro inválido');
  }
  return {estado:fallos.length?'RECHAZADO':dudas.length?'NO_CONCLUYENTE':'APROBADO',
    motivo:fallos.join('; ')||dudas.join('; ')||(reg.caso===CASOS[1]&&post.http===400
      ?'Rechazo completo sin persistencia; observación HTTP 400 en lugar del 422 recomendado'
      :'HTTP, mensaje, historial y auditoría concordantes')};
}
