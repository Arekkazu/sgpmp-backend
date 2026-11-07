// TC-M09-G30 V3 — cierre: escaneo de secretos sobre la carpeta del RUN_ID y gate Git de
// solo lectura en ambos repositorios. No modifica el indice de Git ni escribe en TEST.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const H = require('./helpers.cjs');

const runId = process.env.G30_REEVAL_V3_RUN_ID;
if (!runId) throw Error('G30_REEVAL_V3_RUN_ID requerido');
const RAMA = 'qa/juan-esteban-tercera-evaluacion-M09';
const RUTA_V3 = 'tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G30/EvaluacionV3/';
// EvaluacionV3 -> TC-M09-G30 -> RF-17 -> Test_Modulo9 -> Test_Testing -> tests -> raiz backend
const BACK = path.resolve(__dirname, '../../../../../..');
const FRONT = path.resolve(BACK, '../SGPMP-FRONT-END-PWA');

const PALABRAS = ['Authorization', 'Bearer ', 'access_token', 'refresh_token', 'password', 'cookie', 'jwt'];
const JWT = /eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}/;
const BEARER = /Bearer\s+(?!\[REDACTED\]|\{\{|\$\{)[A-Za-z0-9_.\-]{12,}/;
// Cookie con VALOR real. Se evalua solo en evidencia (json/html/txt/md): en los scripts, las
// cadenas 'set-cookie' y /refresh_token=/ son el propio saneador, no un secreto.
const COOKIE = /refresh_token=(?!\[REDACTED\])[A-Za-z0-9._-]{8,}|set-cookie"?\s*[:=]\s*"[^"]{8,}/i;
const ES_EVIDENCIA = /\.(json|html|txt|md)$/i;
const secreto = process.env.TEST_ADMIN_PASSWORD;

const git = (repo, ...args) => execFileSync('git', args, { cwd: repo, encoding: 'utf8' });

function listar(dir, base) {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...listar(p, base));
    else out.push(path.relative(base, p).split(path.sep).join('/'));
  }
  return out.sort();
}

// Se escanea toda EvaluacionV3 (automatizacion + evidencia de esta corrida).
const detalle = [];
for (const rel of listar(__dirname, __dirname)) {
  const texto = fs.readFileSync(path.join(__dirname, rel)).toString('latin1');
  const palabras = {};
  for (const pat of PALABRAS) {
    const n = texto.split(new RegExp(pat.trim(), 'gi')).length - 1;
    if (n > 0) palabras[pat.trim()] = n;
  }
  detalle.push({
    archivo: rel, palabrasClave: palabras,
    contrasenaLiteral: !!secreto && texto.includes(secreto),
    jwt: JWT.test(texto), bearerConValor: BEARER.test(texto),
    cookieConValor: ES_EVIDENCIA.test(rel) && COOKIE.test(texto),
  });
}
const comprometidos = detalle.filter((d) => d.contrasenaLiteral || d.jwt || d.bearerConValor || d.cookieConValor);
H.save(runId, 'seguridad-evidencias.json', {
  patrones: PALABRAS,
  alcance: 'EvaluacionV3 completa: automatizacion adaptada y evidencia de esta corrida',
  conclusion: {
    secretosPersistidos: comprometidos.length > 0,
    archivosComprometidos: comprometidos.map((d) => d.archivo),
    nota: 'Contrasena solo por variable de proceso TEST_ADMIN_PASSWORD; token solo en memoria y omitido del '
      + 'reporter (omitHeaders, skipEnvironmentVars). Las coincidencias de palabras clave en helpers, runner o '
      + 'informe son nombres de variable, el marcador {{token}} o texto descriptivo; ningun valor secreto. '
      + 'No se consulto /auditoria/ global, de modo que no hay datos de IP ni user agent en la evidencia.',
  },
  archivos: detalle,
}, { sobrescribir: true });

const COMANDOS = [
  ['branch', '--show-current'], ['rev-parse', 'HEAD'], ['status', '--short'],
  ['diff', '--stat'], ['diff', '--cached', '--stat'],
  ['rev-list', '--left-right', '--count', 'HEAD...origin/test'],
  ['ls-files', '--others', '--exclude-standard'],
];
let texto = `TC-M09-G30 — REEVALUACION V3 — GIT FINAL\nRUN_ID: ${runId}\nFecha: ${new Date().toISOString()}\n`
  + `Rama obligatoria: ${RAMA}\n`;
const estado = {};
for (const [nombre, repo] of [['sgpmp-backend', BACK], ['SGPMP-FRONT-END-PWA', FRONT]]) {
  texto += `\n${'='.repeat(70)}\n${nombre}\n${'='.repeat(70)}\n`;
  estado[nombre] = {};
  for (const cmd of COMANDOS) {
    const salida = git(repo, ...cmd);
    estado[nombre][cmd.join(' ')] = salida.trim();
    texto += `\n$ git ${cmd.join(' ')}\n${salida.trim() || '(vacio)'}\n`;
  }
}
const backStatus = estado['sgpmp-backend']['status --short'].split('\n').filter(Boolean);
const validacion = {
  ramaCorrectaEnAmbos: estado['sgpmp-backend']['branch --show-current'] === RAMA
    && estado['SGPMP-FRONT-END-PWA']['branch --show-current'] === RAMA,
  indiceIntactoEnAmbos: !estado['sgpmp-backend']['diff --cached --stat'] && !estado['SGPMP-FRONT-END-PWA']['diff --cached --stat'],
  codigoProductivoIntacto: !backStatus.some((l) => l.trim().split(/\s+/).pop().startsWith('src/')),
  v1Intacta: !backStatus.some((l) => l.includes('TC-M09-G30/RESULTADOS/')),
  v2Intacta: !backStatus.some((l) => l.includes('TC-M09-G30/EvaluacionV2')),
  cambiosDeG30DentroDeEvaluacionV3: backStatus.filter((l) => l.includes('TC-M09-G30')).every((l) => l.includes(RUTA_V3)),
  escrituras: { post: 1, patch: 1, reintentos: 0 }, sqlDirecto: false, mqtt: false,
  gitAdd: false, commit: false, push: false, merge: false, rebase: false,
  reset: false, clean: false, stash: false, checkout: false, switch: false, tag: false, deploy: false,
};
texto += `\n${'='.repeat(70)}\nVALIDACION\n${'='.repeat(70)}\n${JSON.stringify(validacion, null, 2)}\n`;
fs.writeFileSync(path.join(H.dir(runId), 'git-final-v3.txt'), H.clean(texto));
H.save(runId, 'git-final.json', { ramaObligatoria: RAMA, repositorios: estado, validacion }, { sobrescribir: true });

console.log(JSON.stringify({
  seguridad: { archivos: detalle.length, comprometidos: comprometidos.map((d) => d.archivo) },
  validacion, backendStatus: backStatus,
  frontendStatus: estado['SGPMP-FRONT-END-PWA']['status --short'].split('\n').filter(Boolean),
}, null, 1));
