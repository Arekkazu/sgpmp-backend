import { inflateRawSync, inflateSync } from 'node:zlib';

const norm = x => String(x).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/_/g,' ');
const has = (s, words) => words.every(w => norm(s).includes(norm(w)));
export const RAW_FIELDS=['id_telemetria','id_sensor','id_variable','tipo_variable','categoria_variable','valor','valor_ajustado','unidad_medida','timestamp_captura','estado_calidad','estado_semaforo_historico','origen_dato','id_infraestructura','infraestructura','finca','id_activo_biologico','especie','id_especie','id_alerta','nivel_bateria_pct','calidad_senal_rssi','calidad_senal_snr','id_umbral_ambiental','valor_min_umbral','valor_max_umbral','version_umbral'];
export function pdfText(bytes) {
  const b = Buffer.from(bytes);
  if (!b.subarray(0,5).equals(Buffer.from('%PDF-')) || !b.toString('latin1').includes('%%EOF')) return { verificable:false, motivo:'PDF inválido o incompleto' };
  const raw = b.toString('latin1'), streams = [];
  const re = /stream\r?\n([\s\S]*?)\r?\nendstream/g;
  for (const m of raw.matchAll(re)) {
    const data = Buffer.from(m[1], 'latin1');
    try { streams.push(inflateSync(data).toString('latin1')); }
    catch { streams.push(m[1]); }
  }
  const objects = [raw,...streams].join('\n');
  const strings = [...objects.matchAll(/\((?:\\.|[^\\)])*\)/g)].map(m => m[0].slice(1,-1).replace(/\\([()\\])/g,'$1')).join(' ');
  const text = strings || objects;
  const chartStream=streams.some(s=>/tendencia/i.test(s)&&(/\b(?:[-\d.]+\s+){6,}c\b/.test(s)||/(?:[-\d.]+\s+[-\d.]+\s+l\s*){3,}/.test(s)||(/\/\w+\s+Do\b/.test(s)&&/\/Subtype\s*\/Image\b/.test(raw))));
  return { verificable: strings.length > 0, texto:text, paginas:(raw.match(/\/Type\s*\/Page\b/g)||[]).length,
    grafica:chartStream };
}
export function validarPdf(bytes, meta) {
  const p = pdfText(bytes);
  if (!p.verificable) return { verificable:false, motivo:p.motivo || 'texto PDF no extraíble con el validador local' };
  return { verificable:true, checks:{
    granja:has(p.texto,[meta.granja]), periodo:has(p.texto,[meta.inicio,meta.fin]),
    filtros:has(p.texto,['filtros',...meta.filtros]), usuario:has(p.texto,[meta.usuario]),
    tendencia:!has(p.texto,['tendencia'])?false:p.grafica?true:null,
    tabla:has(p.texto,['registro','semaforo']), resumen:has(p.texto,['resumen','estad']),
    generado:has(p.texto,['generad']) && /\d{4}[-/]\d{2}[-/]\d{2}/.test(p.texto),
    paginas:p.paginas > 0,
  }, paginas:p.paginas };
}
export function zipEntries(bytes) {
  const b = Buffer.from(bytes), end = b.lastIndexOf(Buffer.from([0x50,0x4b,0x05,0x06]));
  if (end < 0 || end + 22 > b.length) throw Error('XLSX sin directorio ZIP completo');
  const n = b.readUInt16LE(end+10), offset = b.readUInt32LE(end+16);
  if (n > 200 || offset >= b.length) throw Error('XLSX fuera de límites QA');
  const result = new Map(); let p = offset;
  for (let i=0;i<n;i++) {
    if (b.readUInt32LE(p) !== 0x02014b50) throw Error('Directorio ZIP inválido');
    const method=b.readUInt16LE(p+10), comp=b.readUInt32LE(p+20), plainSize=b.readUInt32LE(p+24), length=b.readUInt16LE(p+28), extra=b.readUInt16LE(p+30), comment=b.readUInt16LE(p+32), local=b.readUInt32LE(p+42);
    const name=b.subarray(p+46,p+46+length).toString('utf8');
    if (local+30>b.length || b.readUInt32LE(local)!==0x04034b50) throw Error('Entrada ZIP inválida');
    const start=local+30+b.readUInt16LE(local+26)+b.readUInt16LE(local+28);
    if (start+comp>b.length) throw Error('Entrada ZIP truncada');
    if(plainSize>100_000_000)throw Error('Entrada XLSX excede memoria QA');
    const data=b.subarray(start,start+comp);
    const plain=method===8?inflateRawSync(data):method===0?data:null;
    if (!plain || plain.length>100_000_000) throw Error('Compresión XLSX no admitida');
    result.set(name,plain.toString('utf8'));
    p+=46+length+extra+comment;
  }
  return result;
}
export function xlsxSheets(bytes) {
  const entries=zipEntries(bytes), workbook=entries.get('xl/workbook.xml'), rels=entries.get('xl/_rels/workbook.xml.rels');
  if (!workbook || !rels) throw Error('Libro XLSX incompleto');
  const attr=(tag,name)=>new RegExp(`\\b${name}="([^"]+)"`).exec(tag)?.[1];
  const links=Object.fromEntries([...rels.matchAll(/<Relationship\b[^>]*\/>/g)].map(m=>[attr(m[0],'Id'),attr(m[0],'Target')]).filter(([id,target])=>id&&target));
  const shared=[...(entries.get('xl/sharedStrings.xml')||'').matchAll(/<si\b[^>]*>([\s\S]*?)<\/si>/g)].map(m=>m[1].replace(/<[^>]+>/g,' '));
  return [...workbook.matchAll(/<sheet\b[^>]*\/>/g)].map(m=>{
    const name=attr(m[0],'name'), rid=attr(m[0],'r:id');
    const target=links[rid]; if(!target) throw Error('Relación de hoja ausente');
    const file=target.startsWith('/')?target.slice(1):'xl/'+target.replace(/^\.\//,'');
    const xml=entries.get(file); if(!xml) throw Error('Hoja XLSX ausente');
    const text=xml.replace(/<c\b([^>]*)>\s*<v>(\d+)<\/v>\s*<\/c>/g,(all,attrs,n)=>/\bt="s"/.test(attrs)?shared[Number(n)]??'':all).replace(/<[^>]+>/g,' ');
    return { name, xml, text, shared, rows:(xml.match(/<row\b/g)||[]).length };
  });
}
function tableParts(sheet) {
  const rows=[...sheet.xml.matchAll(/<row\b[^>]*>([\s\S]*?)<\/row>/g)].map(m=>m[1]);
  const text=row=>row.replace(/<c\b([^>]*)>\s*<v>(\d+)<\/v>\s*<\/c>/g,(all,attrs,n)=>/\bt="s"/.test(attrs)?sheet.shared[Number(n)]??'':all).replace(/<[^>]+>/g,' ');
  const header=rows.findIndex(row=>has(text(row),['sensor','timestamp']));
  return {rows,text,header};
}
export function dataRows(sheet) {
  const {rows,header}=tableParts(sheet);
  if(header<0)return null;
  return rows.slice(header+1).filter(row=>(row.match(/<c\b/g)||[]).length>=2).length;
}
export function metadataText(sheet) {
  const {rows,text,header}=tableParts(sheet);
  return header<0?null:rows.slice(0,header).map(text).join(' ');
}
export function validarExcel(bytes, meta) {
  let sheets;try{sheets=xlsxSheets(bytes);}catch(e){return { verificable:false, motivo:e.message };}
  if(sheets.length!==3)return { verificable:true,checks:{tres_hojas:false},hojas:sheets.map(x=>x.name)};
  const [raw,summary,alerts]=sheets, text=s=>s.name+' '+s.text;
  return { verificable:true,hojas:sheets.map(x=>x.name),checks:{
    tres_hojas:sheets.length===3, datos_crudos:has(text(raw),RAW_FIELDS),
    resumen:has(text(summary),['resumen','variable','minimo','maximo','promedio','total']),
    alertas:has(text(alerts),['alerta','correlacion']),
    metadatos:sheets.every(s=>has(text(s),[meta.granja,meta.inicio,meta.fin,meta.usuario,'filtros',...meta.filtros])),
  }, filas_datos:raw.rows };
}
export function volumen(format, requested, chunks, aviso) {
  const limit=format==='PDF'?5000:format==='EXCEL'?50000:NaN;
  if(!Number.isFinite(limit)||!Number.isSafeInteger(requested))throw Error('Volumen inválido');
  const total=chunks.reduce((n,x)=>n+x,0);
  return { dentro:requested<=limit, completo:total===requested,
    fragmentado:requested<=limit?chunks.length===1:chunks.length>1&&chunks.every(x=>x<=limit),
    aviso:requested<=limit?true:!!aviso };
}
