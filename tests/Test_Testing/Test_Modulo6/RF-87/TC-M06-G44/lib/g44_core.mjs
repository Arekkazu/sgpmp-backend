export const CASOS=['TC-M06-028','TC-M06-029','TC-M06-030'];
export const LIMITE={solicitudes_totales:200,segundos:1800};
export const hoyBogota=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
export const porId=(xs,id)=>xs.find(x=>Number(x.id_periodo_contable)===id);
export const ids=xs=>xs.map(x=>Number(x.id_linea_asiento_nic41??x.id_comprobante_nic41??x.id_variacion_valor_razonable??x.id_registro_costo)).sort((a,b)=>a-b);
export const iguales=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export function evaluar(tabla){
  const out={};
  for(const [caso,criterios] of Object.entries(tabla)){
    const comprobaciones=criterios.map(x=>({id:x.id,esperado:x.esperado,observado:x.observado,estado:x.noConcluyente?'NO_CONCLUYENTE':x.cumple?'APROBADO':'RECHAZADO'}));
    const inconcluso=criterios.some(x=>x.noConcluyente);
    const rechazados=comprobaciones.filter(x=>x.estado==='RECHAZADO');
    out[caso]={estado:rechazados.length?'RECHAZADO':inconcluso?'NO_CONCLUYENTE':'APROBADO',motivo:rechazados.length?rechazados.map(x=>x.id).join(', '):inconcluso?criterios.filter(x=>x.noConcluyente).map(x=>`${x.id}: ${x.observado}`).join('; '):'Criterios conformes',comprobaciones};
  }
  return out;
}
export function criterio(id,esperado,cumple,observado,noConcluyente=false){return{id,esperado,cumple:Boolean(cumple),observado:String(observado),noConcluyente};}
export function listaFaltantes(z,patron){const texto=[z?.data?.message,...(z?.data?.fields??[]).map(x=>x?.message??'')].join(' ');return patron.test(texto);}
export const rolEnMensaje=(mensaje,rol)=>new RegExp(`\\b${rol}\\b`,'i').test(String(mensaje??''));
export const fechaEnMensaje=mensaje=>/\b\d{4}-\d{2}-\d{2}\b/.test(String(mensaje??''));
export const horaEnMensaje=mensaje=>/\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(String(mensaje??''));
export const contiene=(mensaje,dato)=>dato!=null&&String(dato).length>0&&String(mensaje??'').toLocaleLowerCase('es').includes(String(dato).toLocaleLowerCase('es'));
export const horaBogota=fecha=>new Intl.DateTimeFormat('es-CO',{timeZone:'America/Bogota',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(fecha));
export const fechaBogota=fecha=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(fecha));
export const fechaUtc=fecha=>new Date(fecha).toISOString().slice(0,10);
export const horaUtc=fecha=>new Date(fecha).toISOString().slice(0,16).replace('T',' ');
export function fechaEnZonas(mensaje,fecha){
  return Boolean(fecha)&&(contiene(mensaje,fechaBogota(fecha))||contiene(mensaje,fechaUtc(fecha)));
}
export function horaEnZonas(mensaje,fecha){
  if(!fecha)return {coincide:false,soloUtc:false};
  const bogota=contiene(mensaje,`${fechaBogota(fecha)} ${horaBogota(fecha)}`);
  const utc=contiene(mensaje,horaUtc(fecha));
  return {coincide:bogota||utc,soloUtc:utc&&!bogota};
}
