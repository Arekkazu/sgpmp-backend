// Archivos sintéticos locales para probar los parsers; nunca se presentan como evidencia de TEST.
import { deflateRawSync } from 'node:zlib';

export function pdfSintetico({ incompleto = false, sensorId = 73,
  inicio = '2026-10-25', fin = '2026-10-26' } = {}) {
  const texto = `Granja: Granja QA Usuario: Productor QA Filtros: sensor ${sensorId} Periodo ${inicio} ${fin} `;
  const resto = incompleto ? `Registro ${sensorId} valor 25 Semaforo: VERDE Generado ${fin}`
    : `Tendencia Registro ${sensorId} valor 25 Semaforo: VERDE Resumen estadistico por variable Generado ${fin}`;
  const stream = `BT /F1 12 Tf 30 760 Td (${texto}${resto}) Tj ET\n${incompleto ? '' : '0 0 m 1 1 l 2 2 l 3 3 l S\n'}`;
  const obj = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}endstream`,
  ];
  let doc = '%PDF-1.4\n'; const offsets = [0];
  for (let i = 0; i < obj.length; i++) { offsets.push(Buffer.byteLength(doc)); doc += `${i + 1} 0 obj\n${obj[i]}\nendobj\n`; }
  const start = Buffer.byteLength(doc);
  doc += `xref\n0 ${obj.length + 1}\n0000000000 65535 f \n`;
  for (const off of offsets.slice(1)) doc += `${String(off).padStart(10, '0')} 00000 n \n`;
  doc += `trailer\n<< /Size ${obj.length + 1} /Root 1 0 R >>\nstartxref\n${start}\n%%EOF\n`;
  return Buffer.from(doc, 'latin1');
}

function crc32(bytes) {
  let c = 0xffffffff;
  for (const b of bytes) { c ^= b; for (let i = 0; i < 8; i++) c = (c >>> 1) ^ ((c & 1) ? 0xedb88320 : 0); }
  return (c ^ 0xffffffff) >>> 0;
}
const u16 = n => { const b = Buffer.alloc(2); b.writeUInt16LE(n); return b; };
const u32 = n => { const b = Buffer.alloc(4); b.writeUInt32LE(n); return b; };
function zip(entries) {
  const locales = [], centrales = []; let offset = 0;
  for (const [name, xml] of entries) {
    const archivo = Buffer.from(name), data = Buffer.from(xml), compressed = deflateRawSync(data), crc = crc32(data);
    const local = Buffer.concat([u32(0x04034b50), u16(20), u16(0), u16(8), u16(0), u16(0),
      u32(crc), u32(compressed.length), u32(data.length), u16(archivo.length), u16(0), archivo, compressed]);
    const central = Buffer.concat([u32(0x02014b50), u16(20), u16(20), u16(0), u16(8), u16(0), u16(0),
      u32(crc), u32(compressed.length), u32(data.length), u16(archivo.length), u16(0), u16(0),
      u16(0), u16(0), u32(0), u32(offset), archivo]);
    locales.push(local); centrales.push(central); offset += local.length;
  }
  const center = Buffer.concat(centrales);
  const end = Buffer.concat([u32(0x06054b50), u16(0), u16(0), u16(entries.length), u16(entries.length),
    u32(center.length), u32(offset), u16(0)]);
  return Buffer.concat([...locales, center, end]);
}
const esc = x => String(x).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const hoja = rows => `<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${rows.map((r, i) =>
  `<row r="${i + 1}">${r.map((v, j) => `<c r="${String.fromCharCode(65 + j)}${i + 1}" t="inlineStr"><is><t>${esc(v)}</t></is></c>`).join('')}</row>`).join('')}</sheetData></worksheet>`;
export function excelSintetico({ sinHojas = false, sensorId = 73,
  inicio = '2026-10-25', fin = '2026-10-26' } = {}) {
  const meta = `Granja Granja QA Usuario Productor QA filtros sensor ${sensorId} ${inicio} ${fin}`;
  const hojas = sinHojas ? [
    ['Datos crudos', [[meta], ['id_sensor', 'timestamp_captura', 'valor'], [String(sensorId), `${fin}T10:00:00Z`, '25']]],
  ] : [
    ['Datos crudos', [[meta], ['id_sensor', 'timestamp_captura', 'valor'], [String(sensorId), `${fin}T10:00:00Z`, '25']]],
    ['Resumen estadistico', [[meta], ['variable', 'minimo', 'maximo', 'promedio'], ['temperatura', '25', '25', '25']]],
    ['Alertas correlacionadas', [[meta], ['alerta', 'correlacion'], ['ninguna', 'ninguna']]],
  ];
  const workbook = `<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${hojas.map(([name], i) => `<sheet name="${name}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('')}</sheets></workbook>`;
  const rels = `<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${hojas.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join('')}</Relationships>`;
  const tipos = `<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>${hojas.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}</Types>`;
  const raiz = '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>';
  return zip([['[Content_Types].xml', tipos], ['_rels/.rels', raiz],
    ['xl/workbook.xml', workbook], ['xl/_rels/workbook.xml.rels', rels],
    ...hojas.map(([_, rows], i) => [`xl/worksheets/sheet${i + 1}.xml`, hoja(rows)])]);
}
