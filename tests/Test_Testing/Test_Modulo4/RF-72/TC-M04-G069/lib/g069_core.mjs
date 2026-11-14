export const CASOS=['TC-M04-212','TC-M04-213'];
export const IDS=['API-212-01','API-213-01'];
// 2 logins + 1 activo + 4 páginas de descubrimiento + 8 versiones + 7 POST Newman
// + 2*(3 historial+1 auditoría) + DELETE + 2*3 historial poscierre = 37.
export const PRESUPUESTO=Object.freeze({solicitudes_totales:37,paginas_descubrimiento:4,
  versiones_maximas:8,paginas_verificacion:3,dias_busqueda:88,timeout_login_ms:120000,
  timeout_ms:30000,duracion_segundos:900,reemplazos_por_caso:1});
export const CAPACIDADES=Object.freeze({contrato:'sigab-qa-ejecutor/1',grupo:'G069',casos:CASOS,
  operaciones:['evaluar','reintentar','reevaluar','recuperar'],versiones:{min:1,max:99},
  comprobaciones_obligatorias:Object.fromEntries(CASOS.map((c,i)=>[c,{API:[IDS[i]]}])),
  limite:{solicitudes_totales:PRESUPUESTO.solicitudes_totales,duracion_segundos:900},
  baja_automatizada:false});
export function usuarioDelToken(token){try{const sub=JSON.parse(Buffer.from(String(token).split('.')[1],'base64url')).sub;
  return /^\d+$/.test(String(sub))?String(sub):null;}catch{return null;}}
export const tipoModelo=(e,versiones={})=>e?.payload?.tipo_modelo??versiones[String(e?.payload?.id_version_modelo)]??null;
export function seleccionar(eventos,usuarios,versiones,inicio){
  const previos=new Set(eventos.filter(e=>e.tipo_evento==='RETROALIMENTACION'
    &&usuarios.includes(String(e.payload?.id_usuario_veterinario))).map(e=>String(e.id_resultado_inferencia)));
  return eventos.filter(e=>e.tipo_evento==='INFERENCIA'&&e.id_activo_biologico===885
    &&['MODELO_ESPECIES_MEDIANAS','MODELO_ESPECIES_GRANDES'].includes(tipoModelo(e,versiones))
    &&!previos.has(String(e.id_resultado_inferencia))
    &&Date.parse(e.fecha_evento)>=Date.parse(inicio)&&Date.parse(e.fecha_evento)<=Date.now())
    .sort((a,b)=>Date.parse(b.fecha_evento)-Date.parse(a.fecha_evento));
}
export const retroEventos=(eventos,resultado)=>eventos.filter(e=>e.tipo_evento==='RETROALIMENTACION'
  &&String(e.id_resultado_inferencia)===String(resultado));
export const foto=e=>e?{id:String(e.payload?.id_retroalimentacion??e.id_evento),
  resultado:String(e.id_resultado_inferencia),usuario:String(e.payload?.id_usuario_veterinario),
  estado:e.payload?.estado_retroalimentacion,diagnosticos:e.payload?.diagnosticos_reales??null,
  fecha:e.fecha_evento}:null;
export const igual=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export const duplicado=b=>/ya existe una retroalimentaci[oó]n registrada por este usuario para este resultado\.?/i.test(String(b?.message??''));
