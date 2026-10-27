#!/usr/bin/env node
// Uso: node generar_json_resultado.cjs <junit_xml_path> <json_out_path> <tc_name>
// Parsea el XML JUnit de newman y produce el JSON de checkpoints para el scanner.

const fs = require('fs');
const path = require('path');

const [, , xmlPath, jsonPath, tcName] = process.argv;

if (!xmlPath || !jsonPath || !tcName) {
  console.error('Uso: node generar_json_resultado.cjs <junit_xml> <json_out> <tc>');
  process.exit(2);
}

function extractTestCases(xml) {
  const cases = [];
  // <testcase name="..." time="...">  ...  </testcase>  OR  <testcase ... />
  const re = /<testcase\b([^>]*?)(\/>|>([\s\S]*?)<\/testcase>)/g;
  let m;
  while ((m = re.exec(xml)) !== null) {
    const attrs = m[1];
    const body  = m[3] || '';
    const nameM = attrs.match(/name="([^"]*)"/);
    const name  = nameM ? nameM[1].replace(/&quot;/g,'"').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>') : '(sin nombre)';
    const hasFailure = /<failure\b/.test(body);
    const hasError   = /<error\b/.test(body);
    const hasSkipped = /<skipped\b/.test(body);
    const estado = (hasFailure || hasError) ? 'FALLA' : (hasSkipped ? 'FALLA' : 'OK');
    cases.push({ paso: name, estado });
  }
  return cases;
}

try {
  if (!fs.existsSync(xmlPath)) {
    console.error(`[FATAL] no existe ${xmlPath}`);
    process.exit(1);
  }
  const xml = fs.readFileSync(xmlPath, 'utf8');
  const testcases = extractTestCases(xml);
  const checkpoints = testcases.map(tc => ({
    paso: tc.paso,
    esperado: 'PASSED',
    obtenido: tc.estado === 'OK' ? 'PASSED' : 'FAILED',
    estado: tc.estado
  }));
  const total = checkpoints.length;
  const ok    = checkpoints.filter(c => c.estado === 'OK').length;
  const falla = checkpoints.filter(c => c.estado === 'FALLA').length;
  const veredicto = total === 0 ? 'PENDIENTE' : (falla === 0 ? 'APROBADO' : 'RECHAZADO');
  const payload = {
    tc: tcName,
    summary: { total, ok, falla, veredicto },
    checkpoints
  };
  fs.mkdirSync(path.dirname(jsonPath), { recursive: true });
  fs.writeFileSync(jsonPath, JSON.stringify(payload, null, 2), 'utf8');
  console.log(`[OK] ${jsonPath} → total=${total} ok=${ok} falla=${falla} veredicto=${veredicto}`);
  process.exit(falla === 0 && total > 0 ? 0 : 1);
} catch (e) {
  console.error('[FATAL]', e.message);
  process.exit(1);
}
