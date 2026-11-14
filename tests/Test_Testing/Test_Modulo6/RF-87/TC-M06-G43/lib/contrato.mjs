import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {grupoDesdeCarpeta} from './infra.mjs';
const base=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const grupo=grupoDesdeCarpeta(base);
if(!grupo)throw Error('GRUPO_NO_DEDUCIBLE');
const archivo=path.join(base,'pruebas',`contrato_${grupo.toLowerCase()}.json`);
export const contrato=JSON.parse(fs.readFileSync(archivo,'utf8'));
export function validarError(dato){const forma=contrato.error_respuesta?.cuerpo;if(!forma||!dato||typeof dato!=='object'||Array.isArray(dato))return false;return Object.entries(forma).every(([campo,tipo])=>Object.hasOwn(dato,campo)&&(tipo==='array'?Array.isArray(dato[campo]):typeof dato[campo]===tipo));}
export function rutaCanonica(ruta){return ruta.replace(/\/RUN-G\d+-V\d+-\d{8}-\d{6}(?=\/|$)/g,'/{id}').replace(/\/\d+(?=\/|$)/g,'/{id}').replace(/\?.*$/,'');}
export function esquema(metodo,ruta){const canonical=rutaCanonica(ruta);return contrato.rutas.find(x=>x.metodo===metodo&&rutaCanonica(x.ruta)===canonical);}
function tipoValido(valor,tipo){
  if(tipo==='integer')return Number.isInteger(valor);
  if(tipo==='especie_estimacion')return Array.isArray(valor)&&valor.length===2&&Number.isInteger(valor[0])&&typeof valor[1]==='boolean';
  if(tipo==='decimal')return (typeof valor==='string'&&/^-?\d+(\.\d+)?$/.test(valor))||(typeof valor==='number'&&Number.isFinite(valor));
  if(tipo==='date')return typeof valor==='string'&&/^\d{4}-\d\d-\d\d$/.test(valor);
  if(tipo==='datetime')return typeof valor==='string'&&/^\d{4}-\d\d-\d\d[T ]/.test(valor);
  if(tipo==='array')return Array.isArray(valor);
  if(tipo==='object')return valor!==null&&typeof valor==='object'&&!Array.isArray(valor);
  return typeof valor===tipo;
}
function revisar(dato,forma,prefijo){
  if(Array.isArray(forma)){
    if(dato===null&&prefijo.endsWith('.precios_congelados'))return;
    if(!Array.isArray(dato))throw Error(`TIPO_INVALIDO_${prefijo}`);
    return;
  }
  if(typeof forma==='string'){
    const opcional=forma.endsWith('?'),tipos=forma.replace(/\?$/,'').split('|');
    if(dato===undefined&&opcional)return;
    if(!tipos.some(t=>t==='null'?dato===null:tipoValido(dato,t)))throw Error(`TIPO_INVALIDO_${prefijo}`);
    return;
  }
  if(dato===null&&forma._nullable===true)return;
  if(!dato||typeof dato!=='object'||Array.isArray(dato))throw Error(`TIPO_INVALIDO_${prefijo}`);
}
export function instrumentar(dato,forma,lecturas=[],prefijo='respuesta',opciones={estricto:true}){
  revisar(dato,forma,prefijo);
  const envolver=(valor,modelo,ruta)=>{
    if(typeof modelo==='string')return valor;
    if(Array.isArray(valor))return new Proxy(valor,{get(o,k){if(typeof k==='string'&&/^\d+$/.test(k)){
      const hijo=`${ruta}[${k}]`;lecturas.push(hijo);revisar(o[k],modelo[0]??{},hijo);
      return envolver(o[k],modelo[0]??{},hijo);
    }return Reflect.get(o,k);}});
    if(valor===null||typeof valor!=='object'||!modelo||typeof modelo!=='object')return valor;
    for(const clave of Object.keys(valor))if(!Object.hasOwn(modelo,clave))opciones.camposExtra?.add(`${ruta}.${clave}`);
    return new Proxy(valor,{get(o,k){
      if(typeof k==='symbol'||k==='toJSON'||k==='inspect'||k==='then')return Reflect.get(o,k);
      if(!Object.hasOwn(modelo,k)){
        if(opciones.estricto)throw Error(`LECTURA_FUERA_CONTRATO_${ruta}.${String(k)}`);
        return Reflect.get(o,k);
      }
      lecturas.push(`${ruta}.${String(k)}`);
      if(!Object.hasOwn(o,k)&&!(typeof modelo[k]==='string'&&modelo[k].endsWith('?'))&&modelo[k]?._optional!==true)throw Error(`CAMPO_AUSENTE_${ruta}.${String(k)}`);
      revisar(o[k],modelo[k],`${ruta}.${String(k)}`);
      return envolver(o[k],modelo[k],`${ruta}.${String(k)}`);
    }});
  };
  return envolver(dato,forma,prefijo);
}
export function validarLecturas(dato,metodo,ruta,opciones={estricto:true}){const def=esquema(metodo,ruta);if(!def)throw Error(`RUTA_FUERA_CONTRATO_${metodo}_${ruta}`);return instrumentar(dato,def.respuesta,[], 'respuesta',opciones);}

