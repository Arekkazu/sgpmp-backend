import { inflateRawSync, inflateSync } from 'node:zlib';

const normal = x => String(x ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[_\s]+/g, ' ');
const contiene = (texto, partes) => partes.every(x => normal(texto).includes(normal(x)));
const xmlTexto = x => String(x).replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<')
  .replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)));

export function pdfText(bytes) {
  const b = Buffer.from(bytes);
  if (!b.subarray(0, 5).equals(Buffer.from('%PDF-')) || !b.toString('latin1').includes('%%EOF'))
    return { verificable: false, motivo: 'PDF inválido o incompleto' };
  const raw = b.toString('latin1');
  const streams = [...raw.matchAll(/stream\r?\n([\s\S]*?)\r?\nendstream/g)].map(m => {
    try { return inflateSync(Buffer.from(m[1], 'latin1')).toString('latin1'); } catch { return m[1]; }
  });
  const cadenas = [raw, ...streams].flatMap(s => [...s.matchAll(/\((?:\\.|[^\\)])*\)/g)]
    .map(m => m[0].slice(1, -1).replace(/\\([()\\])/g, '$1')));
  const texto = cadenas.join(' ');
  const grafica = streams.some(s => /tendencia/i.test(s) &&
    (/(?:[-\d.]+\s+[-\d.]+\s+l\s*){3,}/.test(s) || /\/\w+\s+Do\b/.test(s)));
  return { verificable: texto.trim().length > 0, motivo: texto.trim() ? null : 'Texto PDF no extraíble',
    texto, paginas: (raw.match(/\/Type\s*\/Page\b/g) ?? []).length, grafica };
}

export function validarPdf(bytes, { inicio, fin, sensorId, muestra = {} }) {
  const p = pdfText(bytes);
  if (!p.verificable) return { verificable: false, motivo: p.motivo };
  const granja = /granja\s*:\s*(\S[^:]*?)\s+usuario\s*:/i.exec(p.texto)?.[1]?.trim();
  const usuario = /usuario\s*:\s*(\S[^:]*?)\s+filtros\s*:/i.exec(p.texto)?.[1]?.trim();
  const checks = {
    encabezado_metadatos: !!granja && !!usuario && contiene(p.texto, ['filtros', inicio, fin, String(sensorId)]),
    grafica_tendencia: contiene(p.texto, ['tendencia']) && p.grafica,
    tabla_semaforo: contiene(p.texto, ['registro', 'semaforo', String(muestra.valor ?? ''), String(sensorId)])
      && /semaforo\s*:\s*(?:verde|amarillo|rojo|gris|sin datos)/i.test(p.texto),
    resumen_estadistico: contiene(p.texto, ['resumen', 'estad']),
    pie_timestamp: /generad[^\d]{0,30}\d{4}[-/]\d{2}[-/]\d{2}/i.test(p.texto),
    paginas: p.paginas > 0,
  };
  return { verificable: true, checks, paginas: p.paginas };
}

export function zipEntries(bytes) {
  const b = Buffer.from(bytes);
  const end = b.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  if (end < 0 || end + 22 > b.length) throw Error('XLSX sin directorio ZIP completo');
  const cantidad = b.readUInt16LE(end + 10), offset = b.readUInt32LE(end + 16);
  if (cantidad > 200 || offset >= b.length) throw Error('XLSX fuera de límites QA');
  const entries = new Map(); let p = offset;
  for (let i = 0; i < cantidad; i++) {
    if (p + 46 > b.length || b.readUInt32LE(p) !== 0x02014b50) throw Error('Directorio ZIP inválido');
    const method = b.readUInt16LE(p + 10), compressed = b.readUInt32LE(p + 20), plain = b.readUInt32LE(p + 24);
    const length = b.readUInt16LE(p + 28), extra = b.readUInt16LE(p + 30), comment = b.readUInt16LE(p + 32);
    const local = b.readUInt32LE(p + 42), name = b.subarray(p + 46, p + 46 + length).toString('utf8');
    if (local + 30 > b.length || b.readUInt32LE(local) !== 0x04034b50) throw Error('Entrada ZIP inválida');
    const start = local + 30 + b.readUInt16LE(local + 26) + b.readUInt16LE(local + 28);
    if (start + compressed > b.length || plain > 100_000_000) throw Error('Entrada XLSX excede límite QA');
    const chunk = b.subarray(start, start + compressed);
    const data = method === 8 ? inflateRawSync(chunk) : method === 0 ? chunk : null;
    if (!data || data.length > 100_000_000) throw Error('Compresión XLSX no admitida');
    entries.set(name, data.toString('utf8'));
    p += 46 + length + extra + comment;
  }
  return entries;
}

export function xlsxSheets(bytes) {
  const entries = zipEntries(bytes), workbook = entries.get('xl/workbook.xml');
  const rels = entries.get('xl/_rels/workbook.xml.rels');
  if (!workbook || !rels) throw Error('Libro XLSX incompleto');
  const attr = (s, n) => new RegExp(`\\b${n}="([^"]+)"`).exec(s)?.[1];
  const links = Object.fromEntries([...rels.matchAll(/<Relationship\b[^>]*\/?\s*>/g)]
    .map(m => [attr(m[0], 'Id'), attr(m[0], 'Target')]).filter(([id, target]) => id && target));
  const shared = [...(entries.get('xl/sharedStrings.xml') ?? '').matchAll(/<si\b[^>]*>([\s\S]*?)<\/si>/g)]
    .map(m => xmlTexto(m[1]).trim());
  return [...workbook.matchAll(/<sheet\b[^>]*\/?\s*>/g)].map(m => {
    const name = attr(m[0], 'name'), target = links[attr(m[0], 'r:id')];
    if (!target) throw Error('Relación de hoja ausente');
    const file = target.startsWith('/') ? target.slice(1) : `xl/${target.replace(/^\.\//, '')}`;
    const xml = entries.get(file);
    if (!xml) throw Error('Hoja XLSX ausente');
    const filas = [...xml.matchAll(/<row\b[^>]*>([\s\S]*?)<\/row>/g)].map(row =>
      [...row[1].matchAll(/<c\b([^>]*)>([\s\S]*?)<\/c>/g)].map(cell => {
        const n = /<v>([\s\S]*?)<\/v>/.exec(cell[2])?.[1];
        return /\bt="s"/.test(cell[1]) ? shared[Number(n)] ?? '' : xmlTexto(n ?? cell[2]).trim();
      }));
    return { name, filas, texto: filas.flat().join(' '), filas_datos: Math.max(0, filas.length - 2) };
  });
}

export function validarExcel(bytes, { inicio, fin, sensorId, campos = [] }) {
  let sheets;
  try { sheets = xlsxSheets(bytes); } catch (e) { return { verificable: false, motivo: e.message }; }
  const [raw, summary, alerts] = sheets;
  const metadatos = sheets.slice(0, 3).every(s => contiene(s?.texto, ['granja', 'usuario', 'filtros', inicio, fin, String(sensorId)]));
  const indice = raw?.filas?.findIndex(f => contiene(f.join(' '), ['sensor', 'timestamp'])) ?? -1;
  const headers = indice >= 0 ? raw.filas[indice] : [];
  const checks = {
    tres_hojas: sheets.length >= 3,
    datos_crudos: !!raw && headers.length > 0 && raw.filas.length > indice + 1
      && campos.every(c => contiene(headers.join(' '), [c])),
    resumen_por_variable: !!summary && contiene(`${summary.name} ${summary.texto}`, ['resumen', 'variable', 'min', 'max', 'promedio']),
    alertas_correlacionadas: !!alerts && contiene(`${alerts.name} ${alerts.texto}`, ['alerta', 'correlacion']),
    metadatos,
  };
  return { verificable: true, checks, hojas: sheets.length, filas_datos: raw?.filas_datos ?? 0 };
}
