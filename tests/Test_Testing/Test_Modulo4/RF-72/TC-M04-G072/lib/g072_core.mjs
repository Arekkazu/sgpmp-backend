export const CASOS=['TC-M04-226','TC-M04-227','TC-M04-230'];
export const IDS=['API-226-01','API-227-01','API-230-01'];
// 3 logins + 40 páginas + catálogo + modelo + 4 auditorías iniciales
// + 9 POST y hasta 5*40 páginas Newman + 4 auditorías por resultado + 9 por registro
// + DELETE + 40 páginas poscierre. Los reemplazos salen del descubrimiento.
export const PRESUPUESTO=Object.freeze({solicitudes_totales:312,paginas_historial:40,solicitudes_newman:209,
  timeout_login_ms:120000,timeout_ms:30000,duracion_segundos:900});
export const CAPACIDADES=Object.freeze({contrato:'sigab-qa-ejecutor/1',grupo:'G072',casos:CASOS,
  operaciones:['evaluar','reintentar','reevaluar','recuperar'],versiones:{min:1,max:99},
  comprobaciones_obligatorias:Object.fromEntries(CASOS.map((x,i)=>[x,{API:[IDS[i]]}])),
  limite:{solicitudes_totales:312,duracion_segundos:900},baja_automatizada:false});
export const iguales=(a,b)=>JSON.stringify(normal(a))===JSON.stringify(normal(b));
function normal(x){if(Array.isArray(x))return x.map(normal);if(x&&typeof x==='object')return Object.fromEntries(Object.keys(x).sort().map(k=>[k,normal(x[k])]));return x;}
export function seleccionar(eventos,ahora=Date.now()){
  const ocupados=new Set(eventos.filter(x=>x.tipo_evento==='RETROALIMENTACION').map(x=>String(x.id_resultado_inferencia)));
  const ids=new Set(),salida=[];
  for(const x of eventos.filter(x=>x.tipo_evento==='INFERENCIA'&&x.id_activo_biologico===885&&
    !ocupados.has(String(x.id_resultado_inferencia))&&Number.isFinite(Date.parse(x.fecha_evento))&&
    ahora-Date.parse(x.fecha_evento)>=0&&ahora-Date.parse(x.fecha_evento)<=21*86400000&&
    x.payload?.tipo_modelo==='MODELO_ESPECIES_MEDIANAS'&&Number(x.payload?.id_version_modelo)===43)
    .sort((a,b)=>Date.parse(b.fecha_evento)-Date.parse(a.fecha_evento))){
      if(!ids.has(String(x.id_resultado_inferencia))){ids.add(String(x.id_resultado_inferencia));salida.push(x);}
      if(salida.length===8)break;
    }return salida;
}
export const retro=(eventos,id)=>eventos.find(e=>e.tipo_evento==='RETROALIMENTACION'&&String(e.payload?.id_retroalimentacion)===String(id));
export const retrosDe=(eventos,id)=>eventos.filter(e=>e.tipo_evento==='RETROALIMENTACION'&&String(e.id_resultado_inferencia)===String(id));
export function decision(condiciones){return condiciones.some(x=>x===false)?'RECHAZADO':condiciones.every(x=>x===true)?'APROBADO':'NO_CONCLUYENTE';}
