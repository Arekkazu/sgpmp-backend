import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
export const contrato=JSON.parse(fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../pruebas/contrato_g037.json'),'utf8'));
export const esquema=(metodo,ruta)=>contrato.rutas.find(x=>x.metodo===metodo&&x.ruta===(ruta.split('?')[0].replace(/^\/integracion\/contratos\/\d+\/deprecar$/,'/integracion/contratos/{id}/deprecar')));
const tipo=(v,t)=>t==='null'?v===null:t==='integer'?Number.isInteger(v):t==='date'?typeof v==='string'&&/^\d{4}-\d\d-\d\d$/.test(v):t==='datetime'?typeof v==='string'&&/^\d{4}-\d\d-\d\d[T ]/.test(v):t==='object'?v!==null&&typeof v==='object'&&!Array.isArray(v):t==='array'?Array.isArray(v):typeof v===t;
function revisar(v,m,p){if(typeof m==='string'){if(!m.split('|').some(t=>tipo(v,t)))throw Error(`TIPO_INVALIDO_${p}`);}else if(Array.isArray(m)){if(!Array.isArray(v))throw Error(`TIPO_INVALIDO_${p}`);}else if(v===null&&m._nullable===true)return;else if(!v||typeof v!=='object'||Array.isArray(v))throw Error(`TIPO_INVALIDO_${p}`);}
export function instrumentar(v,m,lecturas=[],p='respuesta',{estricto=false,extras=new Set()}={}){
  revisar(v,m,p);
  if(v===null||typeof v!=='object')return v;
  if(Array.isArray(v))return new Proxy(v,{get(o,k){if(typeof k==='string'&&/^\d+$/.test(k)){const q=`${p}[${k}]`;lecturas.push(q);return instrumentar(o[k],m[0],lecturas,q,{estricto,extras});}return Reflect.get(o,k);}});
  for(const k of Object.keys(v))if(!Object.hasOwn(m,k))extras.add(`${p}.${k}`);
  return new Proxy(v,{get(o,k){if(typeof k==='symbol'||k==='then'||k==='inspect'||k==='toJSON')return Reflect.get(o,k);if(!Object.hasOwn(m,k)){if(estricto)throw Error(`LECTURA_FUERA_CONTRATO_${p}.${String(k)}`);return Reflect.get(o,k);}const q=`${p}.${String(k)}`;lecturas.push(q);if(!Object.hasOwn(o,k))throw Error(`CAMPO_AUSENTE_${q}`);return instrumentar(o[k],m[k],lecturas,q,{estricto,extras});}});
}
export function validarLecturas(v,metodo,ruta,opciones={}){const e=esquema(metodo,ruta);if(!e)throw Error(`RUTA_FUERA_CONTRATO_${metodo}_${ruta}`);return instrumentar(v,e.respuesta,[], 'respuesta',opciones);}
function forma(v,m){if(typeof m==='string')return m.split('|').some(t=>tipo(v,t));if(Array.isArray(m))return Array.isArray(v)&&v.every(x=>forma(x,m[0]));return !!v&&typeof v==='object'&&!Array.isArray(v)&&Object.entries(m).every(([k,t])=>k.endsWith('?')?!Object.hasOwn(v,k.slice(0,-1))||forma(v[k.slice(0,-1)],t):typeof t==='string'&&t.endsWith('?')?!Object.hasOwn(v,k)||forma(v[k],t.slice(0,-1)):Object.hasOwn(v,k)&&forma(v[k],t));}
function sinExtras(v,m){if(Array.isArray(m))return Array.isArray(v)&&v.every(x=>sinExtras(x,m[0]));if(!m||typeof m!=='object')return true;if(!v||typeof v!=='object'||Array.isArray(v))return false;return Object.keys(v).every(k=>Object.hasOwn(m,k)&&sinExtras(v[k],m[k]));}
export function validarSolicitud(metodo,ruta,cuerpo){const e=esquema(metodo,ruta);if(!e)throw Error(`RUTA_FUERA_CONTRATO_${metodo}_${ruta}`);if(!e.solicitud){if(cuerpo!==undefined)throw Error('CUERPO_INESPERADO');return true;}if(!forma(cuerpo,e.solicitud)||!sinExtras(cuerpo,e.solicitud))throw Error(`SOLICITUD_FUERA_CONTRATO_${metodo}_${ruta}`);return true;}
export function validarError(v){return forma(v,contrato.error_respuesta.cuerpo);}
