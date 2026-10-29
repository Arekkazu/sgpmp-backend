const fs = require('fs');
const path = require('path');

const dirResultados = path.join(__dirname, 'resultados');
const xmlPath = path.join(dirResultados, 'resultado_TC-M03-G165.xml');

let total = 0, failed = 0;
try {
  const xml = fs.readFileSync(xmlPath, 'utf8');
  const totalMatch = xml.match(/tests="(\d+)"/);
  const failMatch = xml.match(/failures="(\d+)"/);
  if (totalMatch) total = parseInt(totalMatch[1]);
  if (failMatch) failed = parseInt(failMatch[1]);
} catch (e) {
  console.error('No se pudo leer el XML:', e.message);
  process.exit(1);
}

const passed = total - failed;

const checkpoints = [
  { paso: "TC-M03-303 happy path (POST /evaluar, serie 20+1, índice 100)", esperado: "201 Created, indice_calidad=100, APTO", obtenido: "500 ERROR_INTERNO (DEF-08)", estado: "FALLA" },
  { paso: "TC-M03-318(a) outlier+drift7%+gap (índice 60)", esperado: "201 Created, indice_calidad=60, APTO_CON_RESERVA", obtenido: "500 ERROR_INTERNO (DEF-08)", estado: "FALLA" },
  { paso: "TC-M03-318(b) congelado MODERADO+drift15% (índice 40)", esperado: "201 Created, indice_calidad=40, APTO_CON_RESERVA", obtenido: "500 ERROR_INTERNO (DEF-08)", estado: "FALLA" },
  { paso: "TC-M03-318(c) sigma=0 + outlier (índice 0)", esperado: "201 Created, indice_calidad=0, NO_APTO", obtenido: "500 ERROR_INTERNO (DEF-08)", estado: "FALLA" },
  { paso: "TC-M03-318(c)bis limite fisico 65C (índice 0)", esperado: "201 Created, indice_calidad=0, NO_APTO", obtenido: "500 ERROR_INTERNO (DEF-08)", estado: "FALLA" },
  { paso: "TC-M03-319 serie nominal limpia (índice 100)", esperado: "201 Created, indice_calidad=100, APTO", obtenido: "500 ERROR_INTERNO (DEF-08)", estado: "FALLA" },
  { paso: "TC-M03-320 congelado+outlier+gap (índice 35)", esperado: "201 Created, indice_calidad=35, NO_APTO", obtenido: "500 ERROR_INTERNO (DEF-08)", estado: "FALLA" },
  { paso: "Invariante D7: 1 sola VIGENTE tras evaluar", esperado: "1 fila VIGENTE por lectura", obtenido: "No verificable (500 previo)", estado: "FALLA" },
  { paso: "Side effects RF-53/RF-63: flags + bitácora", esperado: "apto_para_ia/nic41 actualizados + evento bitácora", obtenido: "No verificable (500 previo)", estado: "FALLA" }
];

const resultado = {
  tc: "TC-M03-G165",
  titulo: "Disparo de evaluación puntual y cálculo/clasificación del índice de calidad",
  rf: "RF-62",
  ambiente: "TEST",
  fecha: new Date().toISOString().slice(0, 10),
  corrida: "V1",
  veredicto: "Rechazado",
  total: checkpoints.length,
  passed: checkpoints.filter(c => c.estado === "OK").length,
  failed: checkpoints.filter(c => c.estado === "FALLA").length,
  pytest_total: total,
  pytest_passed: passed,
  pytest_failed: failed,
  bloqueo: "DEF-08 (backend 500 en POST /evaluar con serie histórica N≥20)",
  checkpoints
};

const outPath = path.join(dirResultados, 'resultado_TC-M03-G165.json');
fs.writeFileSync(outPath, JSON.stringify(resultado, null, 2));

console.log('Generado:', outPath);
console.log('Veredicto:', resultado.veredicto);
console.log('Checkpoints:', resultado.total, `(${resultado.passed} OK, ${resultado.failed} FALLA)`);
console.log('Pytest original:', total, 'tests,', passed, 'passed,', failed, 'failed');
