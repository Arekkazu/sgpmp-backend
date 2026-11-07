export const CASOS=['TC-M04-219','TC-M04-220','TC-M04-221','TC-M04-222','TC-M04-246'];
export const IDS=['API-219-01','API-220-01','API-221-01','API-222-01','API-246-01'];
// 1 login + 40 páginas de descubrimiento + 1 catálogo + 1 modelo + 1 OpenAPI
// + 23 peticiones Newman + 40 páginas de verificación + 1 auditoría + 1 DELETE
// + 40 páginas poscierre = 149. El máximo incluye reemplazos del descubrimiento.
export const PRESUPUESTO=Object.freeze({solicitudes_totales:149,paginas_historial:40,
  solicitudes_newman:23,timeout_login_ms:120000,timeout_ms:30000,duracion_segundos:900});
export const CAPACIDADES=Object.freeze({contrato:'sigab-qa-ejecutor/1',grupo:'G071',casos:CASOS,
  operaciones:['evaluar','reintentar','reevaluar','recuperar'],versiones:{min:1,max:99},
  comprobaciones_obligatorias:Object.fromEntries(CASOS.map((c,i)=>[c,{API:[IDS[i]]}])),
  limite:{solicitudes_totales:PRESUPUESTO.solicitudes_totales,duracion_segundos:900},baja_automatizada:false});
export const uuid=x=>typeof x==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(x);
export const iguales=(a,b)=>JSON.stringify(normalizar(a))===JSON.stringify(normalizar(b));
function normalizar(x){if(Array.isArray(x))return x.map(normalizar);if(x&&typeof x==='object')return Object.fromEntries(Object.keys(x).sort().map(k=>[k,normalizar(x[k])]));return x;}
export function snapshot(e){if(!e||e.tipo_evento!=='INFERENCIA')return null;
  const p=e.payload??{};return {id_resultado_inferencia:e.id_resultado_inferencia,fecha_inferencia:e.fecha_evento,
    nivel_riesgo:p.nivel_riesgo,id_patologia:p.id_patologia,nombre_patologia:p.nombre_patologia,
    probabilidad_riesgo:p.probabilidad_riesgo,probabilidad_enfermedad:p.probabilidad_enfermedad,
    confianza_global:p.confianza_global,tipo_modelo:p.tipo_modelo,id_version_modelo:p.id_version_modelo};}
export function seleccionar(eventos,usuario,modelos,ahora=Date.now()){
  const ocupados=new Set(eventos.filter(e=>e.tipo_evento==='RETROALIMENTACION'&&
    String(e.payload?.id_usuario_veterinario)===String(usuario)).map(e=>String(e.id_resultado_inferencia)));
  const libres=eventos.filter(e=>e.tipo_evento==='INFERENCIA'&&e.id_activo_biologico===885&&
    !ocupados.has(String(e.id_resultado_inferencia))&&Number.isFinite(Date.parse(e.fecha_evento))&&
    ahora-Date.parse(e.fecha_evento)>=0&&ahora-Date.parse(e.fecha_evento)<=21*86400000&&
    (e.payload?.tipo_modelo??modelos?.[e.payload?.id_version_modelo])==='MODELO_ESPECIES_MEDIANAS'&&
    Number(e.payload?.id_version_modelo)===43)
    .sort((a,b)=>Date.parse(b.fecha_evento)-Date.parse(a.fecha_evento));
  const ids=new Set(),salida=[];for(const e of libres)if(!ids.has(e.id_resultado_inferencia)){
    ids.add(e.id_resultado_inferencia);salida.push(e);if(salida.length===7)break;}
  return salida;
}
export function patologiaDistinta(items,estimada){return items.find(x=>x.es_activo===true&&x.id_patologia>=8&&x.id_patologia<=14&&x.id_patologia!==estimada)?.id_patologia??null;}
export function eventosDe(eventos,tipo){return eventos.filter(e=>e.tipo_evento===tipo).map(e=>({
  id_evento:e.id_evento,fecha_evento:e.fecha_evento,id_resultado_inferencia:e.id_resultado_inferencia,
  id_activo_biologico:e.id_activo_biologico,payload:e.payload})).sort((a,b)=>String(a.id_evento).localeCompare(String(b.id_evento)));}
export function retro(eventos,id){return eventos.find(e=>e.tipo_evento==='RETROALIMENTACION'&&e.payload?.id_retroalimentacion===id)??null;}
export function decision(condiciones){if(condiciones.some(x=>x===false))return 'RECHAZADO';
  if(condiciones.every(x=>x===true))return 'APROBADO';return 'NO_CONCLUYENTE';}
