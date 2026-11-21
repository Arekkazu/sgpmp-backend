export const CASOS=['TC-M06-021','TC-M06-022','TC-M06-023'];
export const LIMITE={solicitudes_totales:300,duracion_segundos:1800};
const d=x=>{if(!/^-?\d+(?:\.\d+)?$/.test(String(x)))throw Error('DECIMAL_INVALIDO');const [a,b='']=String(x).replace('-','').split('.');return{n:BigInt(a+b)*(String(x).startsWith('-')?-1n:1n),e:b.length};};
const esc=(x,e)=>x.n*10n**BigInt(e-x.e);
export function sumar(...valores){const a=valores.map(d),e=Math.max(0,...a.map(x=>x.e)),n=a.reduce((s,x)=>s+esc(x,e),0n);return `${n<0n?'-':''}${(n<0n?-n:n)/10n**BigInt(e)}${e?'.'+String((n<0n?-n:n)%10n**BigInt(e)).padStart(e,'0'):''}`;}
export const igual=(a,b)=>{try{return sumar(a)===sumar(b)||(()=>{const x=d(a),y=d(b),e=Math.max(x.e,y.e);return esc(x,e)===esc(y,e);})();}catch{return false;}};
export const pre8=(p,preexistentes)=>p?.puede_cerrar===true&&Array.isArray(p.bloqueos)&&p.bloqueos.length===0&&Array.isArray(p.activos_sin_precio)&&p.activos_sin_precio.length===0&&Array.isArray(p.lineas_sin_trazabilidad)&&preexistentes instanceof Set&&p.lineas_sin_trazabilidad.every(x=>Number.isInteger(Number(x?.id_linea))&&preexistentes.has(Number(x.id_linea)));
export const lineasRunExcluidas=(excluidas,preexistentes)=>!Array.isArray(excluidas)||excluidas.some(x=>!Number.isInteger(Number(x?.id_linea))||!preexistentes.has(Number(x.id_linea)));
export const preLimpia=p=>p?.puede_cerrar===true&&p.requiere_autorizacion===false&&['bloqueos','activos_sin_precio','lineas_sin_trazabilidad'].every(k=>Array.isArray(p[k])&&p[k].length===0);
export const fechaValida=(fecha,periodos)=>/^\d{4}-\d{2}-\d{2}$/.test(fecha)&&fecha<'2026-12-01'&&[241,220].every(id=>{const p=periodos.find(x=>Number(x.id_periodo_contable)===id);return p&&fecha>=String(p.fecha_inicio).slice(0,10)&&fecha<=String(p.fecha_fin).slice(0,10);});
export function cierre8CoincideG32(respuesta,auditoria,logBackend=''){return respuesta?.http===500&&(auditoria?.some(x=>x.tipo_evento==='CIERRE_PERIODO_FALLIDO'&&Number(x.payload_evento?.paso)===3&&/TGR-M06-26/i.test(String(x.payload_evento?.error??'')))||/TGR-M06-26/i.test(String(logBackend))&&auditoria?.some(x=>x.tipo_evento==='CIERRE_PERIODO_FALLIDO'&&Number(x.payload_evento?.paso)===3));}
const key=x=>[x.numero_id_tributaria,x.tipo_hecho,x.id_especie].join('|');
const par=x=>[x.cuenta_debito,x.cuenta_credito].join('|');
const fail=(out,c,m)=>{if(!c)out.push(m);};
export function evaluar021(x){const f=[];if(x.cierreHttp!==200){f.push('cierre_8_fallido');return f;}
  const {variaciones=[],lineas=[],comprobantes=[],cierre={},ultimo_cierre={},auditoria=[]}=x;
  const excluidas=new Set((x.lineasExcluidas??[]).map(v=>Number(v.id_linea)));
  const grupos=[['VARIACION_VR_TB','GANANCIA'],['VARIACION_VR_TB','PERDIDA'],['VARIACION_VR_PM','GANANCIA'],['VARIACION_VR_PM','PERDIDA']];
  for(const [tipo,sentido] of grupos){const ls=lineas.filter(l=>l.tipo_hecho===tipo&&l.sentido===sentido&&l.estado==='REGISTRADA'),vt=`${sentido}_${tipo.endsWith('_TB')?'TRANSFORMACION_BIOLOGICA':'PRECIO_MERCADO'}`,vs=variaciones.filter(v=>v.tipo===vt&&!excluidas.has(Number(v.id_linea))),especies=new Set(ls.map(l=>Number(l.id_especie)));
    fail(f,ls.length>0&&vs.length>0,`variacion_ausente_${tipo}_${sentido}`);
    for(const especie of especies){const gl=ls.filter(l=>Number(l.id_especie)===especie),gv=vs.filter(v=>gl.some(l=>Number(l.id_linea_asiento_nic41)===Number(v.id_linea))),ids=new Set(gl.map(l=>Number(l.id_linea_asiento_nic41))),cuentas=new Map();
      fail(f,ids.size===gl.length&&gv.length===gl.length&&new Set(gv.map(v=>Number(v.id_linea))).size===gv.length,`doble_conteo_${tipo}_${sentido}_${especie}`);
      for(const l of gl){const p=par(l);cuentas.set(p,sumar(cuentas.get(p)??'0',l.valor));}
      const cs=comprobantes.filter(c=>c.tipo_hecho===tipo&&Number(c.id_especie)===especie);fail(f,cs.length===1,`comprobante_ausente_${tipo}_${especie}`);if(cs.length!==1)continue;
      for(const [p,total] of cuentas){const filas=cs[0].lineas?.filter(z=>par(z)===p)??[];fail(f,filas.length===1&&igual(filas[0].valor,total),`suma_${tipo}_${sentido}_${especie}`);}
    }
    fail(f,vs.every(v=>ls.some(l=>Number(l.id_linea_asiento_nic41)===Number(v.id_linea))),`variacion_sin_linea_${tipo}_${sentido}`);
  }
  fail(f,Number(ultimo_cierre.id_cierre)===Number(cierre.id_cierre)&&Number(ultimo_cierre.id_usuario_ejecutor)===Number(x.usuario)&&!!ultimo_cierre.fecha_fin,'ejecutor_o_timestamp_ausente');
  const generadas=x.variacionesCierre??[];fail(f,generadas.length>0,'variacion_cierre_ausente');for(const v of generadas){const evento=auditoria.find(a=>a.tipo_evento==='VARIACION_REGISTRADA'&&Number(a.id_referencia)===Number(v.id_variacion_valor_razonable));fail(f,!!evento&&Number(evento.payload_evento?.id_cierre)===Number(cierre.id_cierre),`evento_origen_id_${v.id_variacion_valor_razonable}`);}return f;
}
export function evaluar022(x){const f=[];const {lineas=[],comprobantes=[],nit,fecha='2026-11-30',descargas={}}=x;
  const registradas=lineas.filter(l=>l.estado==='REGISTRADA');const grupos=new Map();for(const l of registradas){const k=[nit,l.tipo_hecho,l.id_especie].join('|');if(!grupos.has(k))grupos.set(k,[]);grupos.get(k).push(l);}
  for(const [k,ls] of grupos){const [n,t,e]=k.split('|'),cs=comprobantes.filter(c=>key(c)===k);fail(f,cs.length===1,`comprobante_cantidad_${k}`);if(cs.length!==1)continue;const c=cs[0];fail(f,c.codigo===`NIC-${n}-${fecha.slice(0,7).replace('-','')}-${t}-${e}`,`codigo_${k}`);fail(f,String(c.fecha_comprobante).slice(0,10)===fecha,`fecha_${k}`);const pares=new Map();for(const l of ls){const p=par(l);if(!pares.has(p))pares.set(p,[]);pares.get(p).push(l.valor);}fail(f,c.lineas?.length===pares.size,`pares_cantidad_${k}`);for(const [p,valores] of pares){const fila=c.lineas?.filter(z=>par(z)===p)??[];fail(f,fila.length===1&&igual(fila[0].valor,sumar(...valores)),`suma_par_${k}_${p}`);}}
  fail(f,comprobantes.length===grupos.size,'comprobante_extra_o_duplicado');fail(f,descargas.csv?.http===200&&descargas.csv?.tipo?.includes('csv')&&[...grupos.keys()].every(k=>descargas.csv.texto?.includes(comprobantes.find(c=>key(c)===k)?.codigo)),'descarga_csv');fail(f,descargas.pdf?.http===200&&descargas.pdf?.tipo?.includes('pdf')&&descargas.pdf?.cabecera==='%PDF','descarga_pdf');fail(f,[descargas.put?.http,descargas.delete?.http].every(h=>h===404||h===405)&&descargas.hashesIguales===true,'inmutabilidad');return f;
}
export function buscarDesglose(publicos,costos){
  const tipos=['ALIMENTO','MEDICAMENTO','MANO_OBRA','VETERINARIO'];
  const esperado=Object.fromEntries(tipos.map(t=>[t,sumar(...costos.filter(c=>c.subtipo_costo===t).map(c=>c.monto_costo))]));
  const visitar=(o,ruta)=>{if(!o||typeof o!=='object')return null;
    const entradas=Object.entries(o),valores={};
    for(const t of tipos){const candidatos=entradas.filter(([k,v])=>typeof v!=='object'&&new RegExp(`(?:^|_)${t}(?:_|$)`,'i').test(k)&&igual(v,esperado[t]));if(candidatos.length)valores[t]=candidatos[0][1];}
    if(tipos.every(t=>Object.hasOwn(valores,t)))return{ruta,valores};
    for(const [k,v] of entradas){const hallado=visitar(v,`${ruta}.${k}`);if(hallado)return hallado;}return null;
  };return visitar(publicos,'RF93');
}
export function evaluar023(x){const f=[],costos=x.costosRun??[],previos=x.costosPrevios??[],comp=x.estadoNoviembre?.componentes??{},dic=x.estadoDiciembre?.componentes??{},tipos=['ALIMENTO','MEDICAMENTO','MANO_OBRA','VETERINARIO'];fail(f,costos.length===4&&tipos.every(t=>costos.some(c=>c.subtipo_costo===t&&c.naturaleza_costo==='MANTENIMIENTO')),'costos_incompletos');
  const todos=[...previos,...costos].filter(c=>c.naturaleza_costo==='MANTENIMIENTO'),esperado=Object.fromEntries(tipos.map(t=>[t,sumar(...todos.filter(c=>c.subtipo_costo===t).map(c=>c.es_reverso?`-${c.monto_costo}`:c.monto_costo))]));
  fail(f,igual(comp.costos_mantenimiento,sumar(...Object.values(esperado))),'costos_no_incluidos');const desglose=comp.desglose_costos_mantenimiento??x.estadoNoviembre?.desglose_costos_mantenimiento;fail(f,desglose&&tipos.every(t=>igual(desglose[t],esperado[t])),'sin_desglose_por_tipo');fail(f,desglose&&tipos.every(t=>desglose[t]!=null)&&igual(sumar(...tipos.map(t=>desglose[t])),comp.costos_mantenimiento),'desglose_suma_incorrecta');fail(f,igual(dic.costos_mantenimiento,x.baseDiciembre??'0'),'costo_noviembre_en_diciembre');fail(f,igual(x.medConCostos?.valor_razonable_actual,x.medSinCostos?.valor_razonable_actual),'valor_razonable_aumentado');fail(f,x.calculosPorCostos===0&&x.variacionesPorCostos===0,'costos_generan_valor');return f;}
