export const CASOS=['TC-M04-214','TC-M04-215','TC-M04-216','TC-M04-217','TC-M04-218'];
export const IDS=CASOS.map((_,i)=>`API-${214+i}-01`);
// 2 sesiones + activo + 40 páginas iniciales + 8 modelos + 2 superficies + 7 POST
// + 40 páginas de verificación + auditoría + DELETE + 40 páginas poscierre = 142.
export const PRESUPUESTO=Object.freeze({solicitudes_totales:142,paginas_historial:40,
  versiones_maximas:8,posts_maximos:7,dias_busqueda:125,timeout_login_ms:120000,
  timeout_ms:30000,duracion_segundos:900});
export const CAPACIDADES=Object.freeze({contrato:'sigab-qa-ejecutor/1',grupo:'G070',casos:CASOS,
  operaciones:['evaluar','reintentar','reevaluar','recuperar'],versiones:{min:1,max:99},
  comprobaciones_obligatorias:Object.fromEntries(CASOS.map((c,i)=>[c,{API:[IDS[i]]}])),
  limite:{solicitudes_totales:PRESUPUESTO.solicitudes_totales,duracion_segundos:900},
  baja_automatizada:false});
export const DIAS=86400000;
export function antiguedad(fecha,ahora=Date.now()){
  const ms=ahora-Date.parse(fecha);
  return Number.isFinite(ms)?{dias_backend:Math.floor(ms/DIAS),horas:Number((ms/3600000).toFixed(3)),ms}:null;
}
export function tramo(clave,a){
  if(!a||a.ms<0)return false;
  if(clave==='reciente')return a.dias_backend>=1&&a.dias_backend<=21;
  if(clave==='d89')return a.dias_backend===89;
  if(clave==='d90')return a.dias_backend===90&&a.horas<90*24+12;
  if(clave==='d90h')return a.dias_backend===90&&a.horas>=90*24+12;
  if(clave==='d91')return a.dias_backend===91;
  return clave.startsWith('d120')&&a.dias_backend===120;
}
export function elegir(eventos,usuario,modelos,ahora=Date.now()){
  const ocupados=new Set(eventos.filter(e=>e.tipo_evento==='RETROALIMENTACION'
    &&String(e.payload?.id_usuario_veterinario)===String(usuario)).map(e=>String(e.id_resultado_inferencia)));
  const resultados=eventos.filter(e=>e.tipo_evento==='INFERENCIA'&&e.id_activo_biologico===885
    &&!ocupados.has(String(e.id_resultado_inferencia))
    &&['MODELO_ESPECIES_MEDIANAS','MODELO_ESPECIES_GRANDES'].includes(
      e.payload?.tipo_modelo??modelos[String(e.payload?.id_version_modelo)]))
    .map(e=>({...e,antiguedad:antiguedad(e.fecha_evento,ahora)})).filter(e=>e.antiguedad);
  const seleccion={};const usados=new Set();
  for(const clave of ['reciente','d89','d90','d90h','d91','d120a','d120b']){
    const x=resultados.filter(e=>!usados.has(String(e.id_resultado_inferencia))&&tramo(clave,e.antiguedad))
      .sort((a,b)=>Math.abs(a.antiguedad.horas-({reciente:24,d89:89*24+1,d90:90*24+1,d90h:90*24+12,d91:91*24+1,d120a:120*24,d120b:120*24}[clave]))-
        Math.abs(b.antiguedad.horas-({reciente:24,d89:89*24+1,d90:90*24+1,d90h:90*24+12,d91:91*24+1,d120a:120*24,d120b:120*24}[clave])))[0];
    if(x){seleccion[clave]=x;usados.add(String(x.id_resultado_inferencia));}
  }
  return seleccion;
}
export function superficie(openapi,config){
  const ops=[];for(const [ruta,metodos] of Object.entries(openapi?.paths??{}))
    for(const [metodo,op] of Object.entries(metodos??{}))if(['get','post','put','patch','delete'].includes(metodo))
      ops.push({ruta,metodo,op});
  const parametro='ventana_retroalimentacion_dias';
  const expandir=(v,vistos=new Set())=>{
    if(!v||typeof v!=='object')return v;
    if(Array.isArray(v))return v.map(x=>expandir(x,vistos));
    if(typeof v.$ref==='string'&&v.$ref.startsWith('#/')){
      if(vistos.has(v.$ref))return null;
      const siguiente=new Set(vistos);siguiente.add(v.$ref);
      const destino=v.$ref.slice(2).split('/').reduce((o,k)=>o?.[k.replace(/~1/g,'/').replace(/~0/g,'~')],openapi);
      return expandir(destino,siguiente);
    }
    return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,expandir(x,vistos)]));};
  const refTexto=v=>JSON.stringify(expandir(v??{}));
  const lectura=ops.some(x=>x.metodo==='get'&&
    (x.ruta.includes(parametro)||refTexto(x.op.responses).includes(parametro)));
  const escritura=ops.some(x=>['post','put','patch'].includes(x.metodo)&&
    (x.ruta.includes(parametro)||refTexto(x.op.requestBody).includes(parametro)));
  const configLee=refTexto(config).includes(parametro);
  const ampliacion=ops.some(x=>/ampli|exten|excepci[oó]n.{0,30}ventana/i.test(
    `${x.ruta} ${x.op?.operationId??''} ${x.op?.summary??''}`));
  return {lectura:lectura||configLee,escritura,ampliacion,
    operaciones_ventana:ops.filter(x=>x.ruta.includes(parametro)).map(x=>`${x.metodo.toUpperCase()} ${x.ruta}`),
    operaciones_ampliacion:ops.filter(x=>/ampli|exten|excepci[oó]n.{0,30}ventana/i.test(
      `${x.ruta} ${x.op?.operationId??''} ${x.op?.summary??''}`)).map(x=>`${x.metodo.toUpperCase()} ${x.ruta}`)};
}
export function e9(post,id,fecha,ventana=90){
  const msg=String(post?.cuerpo?.message??'');
  const limite=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'})
    .format(new Date(Date.parse(fecha)+ventana*DIAS));
  return {http:post?.http===422,codigo:post?.cuerpo?.error_code==='FUERA_DE_VENTANA_TEMPORAL',
    dias:new RegExp(`\\b${ventana}\\s+d[ií]as\\b`,'i').test(msg),id:msg.includes(String(id)),
    fecha:msg.includes(limite),contacto:/contacte al administrador/i.test(msg),limite};
}
