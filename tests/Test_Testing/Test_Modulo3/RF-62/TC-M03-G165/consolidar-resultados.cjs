const fs = require('fs');
const path = require('path');

const TC_ID = 'TC-M03-G165';
const dirResultados = path.join(__dirname, 'resultados');
const v1JsonPath = path.join(dirResultados, `resultado_${TC_ID}.json`);

const ORDEN_CLASES = [
  'TestEscenarioBase',
  'TestEscenario318a',
  'TestEscenario318b',
  'TestEscenario318c',
  'TestEscenario320',
];

function parsearArgumentos(argv) {
  let sufijoArg = '';
  let xmlsArg = '';
  const args = argv.slice(2);
  for (let i = 0; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--sufijo' && args[i + 1]) {
      sufijoArg = args[i + 1].trim();
      i += 1;
    } else if (a.startsWith('--sufijo=')) {
      sufijoArg = a.split('=', 2)[1].trim();
    } else if (a === '--xmls' && args[i + 1]) {
      xmlsArg = args[i + 1].trim();
      i += 1;
    } else if (a.startsWith('--xmls=')) {
      xmlsArg = a.split('=', 2)[1].trim();
    } else if (!a.startsWith('--') && !sufijoArg) {
      sufijoArg = a.trim();
    }
  }
  return { sufijoArg, xmlsArg };
}

function resolverSufijo(sufijoArg) {
  if (sufijoArg) {
    return sufijoArg.startsWith('_') ? sufijoArg : `_${sufijoArg}`;
  }
  if (!fs.existsSync(v1JsonPath)) {
    return '';
  }
  let idx = 1;
  while (fs.existsSync(path.join(dirResultados, `resultado_${TC_ID}_reintento${idx}.json`))) {
    idx += 1;
  }
  return `_reintento${idx}`;
}

function decodificarEntidadesXml(texto) {
  if (!texto) return '';
  return texto
    .replace(/&#10;/g, '\n')
    .replace(/&#13;/g, '\r')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
}

function escaparHtml(texto) {
  return String(texto || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function extraerAtributo(attrsStr, nombre) {
  const regex = new RegExp(`(?:^|\\s)${nombre}="([^"]*)"`);
  const match = attrsStr.match(regex);
  return match ? decodificarEntidadesXml(match[1]) : '';
}

function resolverRutasXml(sufijo, xmlsArg) {
  if (xmlsArg) {
    return xmlsArg
      .split(',')
      .map((p) => p.trim())
      .filter(Boolean)
      .map((p) => (path.isAbsolute(p) ? p : path.resolve(__dirname, p)));
  }
  const splitPaths = ['A', 'B', 'C'].map((letra) =>
    path.join(dirResultados, `resultado_${TC_ID}${sufijo}_${letra}.xml`)
  );
  if (splitPaths.every((p) => fs.existsSync(p))) {
    return splitPaths;
  }
  return [path.join(dirResultados, `resultado_${TC_ID}${sufijo}.xml`)];
}

function parsearXmlTestcases(xmlPath) {
  if (!fs.existsSync(xmlPath)) {
    console.error(`No se encontró el archivo JUnit XML esperado: ${xmlPath}`);
    process.exit(1);
  }
  let xml = '';
  try {
    xml = fs.readFileSync(xmlPath, 'utf8');
  } catch (e) {
    console.error(`No se pudo leer el XML (${xmlPath}):`, e.message);
    process.exit(1);
  }

  const items = [];
  const testcaseRegex = /<testcase\s+([^>]*?)(?:\/>|>([\s\S]*?)<\/testcase>)/g;
  let match;
  let ordenLocal = 0;

  while ((match = testcaseRegex.exec(xml)) !== null) {
    ordenLocal += 1;
    const attrs = match[1] || '';
    const inner = match[2] || '';
    const classname = extraerAtributo(attrs, 'classname');
    const name = extraerAtributo(attrs, 'name');
    const timeStr = extraerAtributo(attrs, 'time') || '0';
    const timeSec = Number.parseFloat(timeStr) || 0;
    const claseCorta = classname ? classname.split('.').pop() : '';
    const paso = claseCorta ? `${claseCorta}::${name}` : name;

    const failMatch = inner.match(/<(?:failure|error)\b([^>]*)>([\s\S]*?)<\/(?:failure|error)>/);
    const failSelfClosing = inner.match(/<(?:failure|error)\b([^>]*)\/>/);

    if (failMatch || failSelfClosing) {
      const failAttrs = (failMatch ? failMatch[1] : failSelfClosing[1]) || '';
      const failBody = failMatch ? decodificarEntidadesXml(failMatch[2]).trim() : '';
      const msgAttr = extraerAtributo(failAttrs, 'message').trim();
      const obtenido = (msgAttr || failBody || 'Fallo en testcase').split('\n')[0].slice(0, 300);
      items.push({
        claseCorta,
        ordenLocal,
        timeSec,
        checkpoint: {
          paso,
          esperado: 'Aserción cumplida',
          obtenido,
          estado: 'FALLA',
        },
      });
    } else {
      items.push({
        claseCorta,
        ordenLocal,
        timeSec,
        checkpoint: {
          paso,
          esperado: 'Aserción cumplida',
          obtenido: 'Aserción cumplida',
          estado: 'OK',
        },
      });
    }
  }
  return items;
}

function generarHtmlConsolidado(resultado, itemsOrdenados, xmlPaths) {
  const filasHtml = itemsOrdenados
    .map((item, idx) => {
      const cp = item.checkpoint;
      const esOk = cp.estado === 'OK';
      const badgeColor = esOk ? '#15803d' : '#b91c1c';
      const bgRow = esOk ? '#f0fdf4' : '#fef2f2';
      return `<tr style="background:${bgRow}">
        <td>${idx + 1}</td>
        <td><code>${escaparHtml( item.claseCorta || '-' )}</code></td>
        <td><code>${escaparHtml(cp.paso)}</code></td>
        <td><strong style="color:${badgeColor}">${escaparHtml(cp.estado)}</strong></td>
        <td>${item.timeSec.toFixed(3)}s</td>
        <td>${escaparHtml(cp.obtenido)}</td>
      </tr>`;
    })
    .join('\n');

  const veredictoColor = resultado.summary.veredicto === 'APROBADO' ? '#15803d' : '#b91c1c';
  const tiempoTotal = itemsOrdenados.reduce((acc, it) => acc + it.timeSec, 0);

  return `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>Reporte Consolidado ${escaparHtml(resultado.tc)} (${escaparHtml(resultado.corrida)})</title>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; margin: 24px; color: #1f2937; }
    h1 { margin-bottom: 4px; }
    .summary { display: flex; gap: 16px; margin: 16px 0; padding: 12px 16px; border: 1px solid #d1d5db; border-radius: 8px; background: #f9fafb; }
    table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }
    th, td { border: 1px solid #e5e7eb; padding: 8px 10px; text-align: left; }
    th { background: #f3f4f6; }
    code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
  </style>
</head>
<body>
  <h1>${escaparHtml(resultado.tc)} — ${escaparHtml(resultado.titulo)}</h1>
  <p><strong>RF:</strong> ${escaparHtml(resultado.rf)} | <strong>Ambiente:</strong> ${escaparHtml(resultado.ambiente)} | <strong>Fecha:</strong> ${escaparHtml(resultado.fecha)} | <strong>Corrida:</strong> ${escaparHtml(resultado.corrida)}</p>
  <div class="summary">
    <div><strong>Veredicto:</strong> <span style="color:${veredictoColor};font-weight:700">${escaparHtml(resultado.summary.veredicto)}</span></div>
    <div><strong>Total:</strong> ${resultado.summary.total}</div>
    <div><strong>OK:</strong> ${resultado.summary.ok}</div>
    <div><strong>FALLA:</strong> ${resultado.summary.falla}</div>
    <div><strong>Tiempo tests:</strong> ${tiempoTotal.toFixed(2)}s</div>
    <div><strong>XMLs fusionados:</strong> ${xmlPaths.length}</div>
  </div>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Clase</th>
        <th>Checkpoint (Paso)</th>
        <th>Estado</th>
        <th>Tiempo</th>
        <th>Resultado Obtenido</th>
      </tr>
    </thead>
    <tbody>
      ${filasHtml}
    </tbody>
  </table>
</body>
</html>`;
}

const { sufijoArg, xmlsArg } = parsearArgumentos(process.argv);
const sufijo = resolverSufijo(sufijoArg);
const outPath = path.join(dirResultados, `resultado_${TC_ID}${sufijo}.json`);
const outHtmlPath = path.join(dirResultados, `resultado_${TC_ID}${sufijo}.html`);

if (path.resolve(outPath) === path.resolve(v1JsonPath) && fs.existsSync(v1JsonPath)) {
  console.error('ERROR: V1 es inmutable (§1.4.4). Prohibido sobrescribir el resultado original sin sufijo.');
  process.exit(1);
}

const xmlPaths = resolverRutasXml(sufijo, xmlsArg);
const todosLosItems = [];
xmlPaths.forEach((xmlPath, fileIdx) => {
  const extraidos = parsearXmlTestcases(xmlPath);
  extraidos.forEach((it) => {
    todosLosItems.push({ ...it, fileIdx });
  });
});

todosLosItems.sort((a, b) => {
  const idxA = ORDEN_CLASES.indexOf(a.claseCorta);
  const idxB = ORDEN_CLASES.indexOf(b.claseCorta);
  const rankA = idxA === -1 ? 999 : idxA;
  const rankB = idxB === -1 ? 999 : idxB;
  if (rankA !== rankB) return rankA - rankB;
  if (a.fileIdx !== b.fileIdx) return a.fileIdx - b.fileIdx;
  return a.ordenLocal - b.ordenLocal;
});

const checkpoints = todosLosItems.map((it) => it.checkpoint);
const passed = checkpoints.filter((c) => c.estado === 'OK').length;
const failed = checkpoints.filter((c) => c.estado === 'FALLA').length;

const resultado = {
  tc: TC_ID,
  titulo: 'Disparo de evaluación puntual y cálculo/clasificación del índice de calidad',
  rf: 'RF-62',
  ambiente: 'TEST',
  fecha: new Date().toISOString().slice(0, 10),
  corrida: sufijo ? sufijo.replace(/^_/, '') : 'V1',
  summary: {
    total: checkpoints.length,
    ok: passed,
    falla: failed,
    veredicto: failed === 0 && checkpoints.length > 0 ? 'APROBADO' : 'RECHAZADO',
    bloqueo_externo: null,
  },
  checkpoints,
};

fs.writeFileSync(outPath, JSON.stringify(resultado, null, 2));
fs.writeFileSync(outHtmlPath, generarHtmlConsolidado(resultado, todosLosItems, xmlPaths));

console.log('Generado JSON:', outPath);
console.log('Generado HTML:', outHtmlPath);
console.log('Corrida:', resultado.corrida);
console.log('Veredicto:', resultado.summary.veredicto);
console.log('Checkpoints:', resultado.summary.total, `(${resultado.summary.ok} OK, ${resultado.summary.falla} FALLA)`);
