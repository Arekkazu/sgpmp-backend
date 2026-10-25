/**
 * Script de auditoría de seguridad y fuga de secretos (NW-19) para TC-M09-G14-v2.0.
 *
 * Analiza todos los archivos bajo resultados/ y evidencias/
 * buscando tokens JWT, Bearer crudos o contraseñas en texto plano.
 * No imprime los valores de secretos encontrados para evitar fugas en logs.
 */
const fs = require('fs');
const path = require('path');

const directorios = [
    path.join(__dirname, 'resultados'),
    path.join(__dirname, 'evidencias')
];

// Patrones de secretos sensibles
const RE_JWT = /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/;
const RE_BEARER = /Bearer\s+(?!\{\{)[A-Za-z0-9._-]{20,}/;

// Lectura de passwords desde .env.test si existe, para verificar que no estén filtradas
const passwordsSensibles = [];
const repoRoot = path.resolve(__dirname, '../../../../..');
const envTestPath = path.join(repoRoot, '.env.test');
if (fs.existsSync(envTestPath)) {
    const envContent = fs.readFileSync(envTestPath, 'utf8');
    const matchAdmin = envContent.match(/TEST_ADMIN_PASSWORD=(.+)/);
    if (matchAdmin && matchAdmin[1].trim()) {
        passwordsSensibles.push(matchAdmin[1].trim());
    }
}

let hallazgos = 0;
const detallesHallazgos = [];

function escanearArchivo(filePath) {
    if (!fs.existsSync(filePath)) return;
    const stat = fs.statSync(filePath);
    if (stat.isDirectory()) {
        const files = fs.readdirSync(filePath);
        for (const file of files) {
            escanearArchivo(path.join(filePath, file));
        }
        return;
    }

    const ext = path.extname(filePath).toLowerCase();
    if (!['.json', '.html', '.txt', '.log', '.xml', '.md'].includes(ext)) {
        return;
    }

    // Ignorar scripts fuente
    if (filePath.endsWith('.cjs') || filePath.endsWith('.py')) {
        return;
    }

    const content = fs.readFileSync(filePath, 'utf8');

    if (RE_JWT.test(content)) {
        const msg = `[AUDITORÍA SEGURIDAD] ALERTA: Posible JWT detectado en ${path.relative(__dirname, filePath)}`;
        console.error(msg);
        detallesHallazgos.push(msg);
        hallazgos++;
    }

    if (RE_BEARER.test(content)) {
        const msg = `[AUDITORÍA SEGURIDAD] ALERTA: Token Bearer expuesto detectado en ${path.relative(__dirname, filePath)}`;
        console.error(msg);
        detallesHallazgos.push(msg);
        hallazgos++;
    }

    for (const pwd of passwordsSensibles) {
        if (pwd && content.includes(pwd)) {
            const msg = `[AUDITORÍA SEGURIDAD] ALERTA CRÍTICA: Contraseña de test en texto plano detectada en ${path.relative(__dirname, filePath)}`;
            console.error(msg);
            detallesHallazgos.push(msg);
            hallazgos++;
        }
    }
}

for (const dir of directorios) {
    if (fs.existsSync(dir)) {
        const files = fs.readdirSync(dir);
        for (const file of files) {
            escanearArchivo(path.join(dir, file));
        }
    }
}

const outputFile = path.join(__dirname, 'evidencias', 'auditoria_fuga.txt');
const resultadoTexto = [
    `AUDITORÍA DE FUGA DE SECRETOS — TC-M09-G14-v2.0`,
    `Fecha: ${new Date().toISOString()}`,
    `Total archivos analizados en resultados/ y evidencias/`,
    `Hallazgos detectados: ${hallazgos}`,
    ``,
    hallazgos === 0 ? 'ESTADO: LIMPIO (Sin fugas de tokens ni credenciales)' : 'ESTADO: VULNERABLE\n' + detallesHallazgos.join('\n')
].join('\n');

fs.writeFileSync(outputFile, resultadoTexto, 'utf8');

if (hallazgos > 0) {
    console.error(`Auditoría fallida: ${hallazgos} secretos expuestos.`);
    process.exit(1);
} else {
    console.log(`Auditoría de seguridad exitosa: 0 secretos expuestos.`);
    process.exit(0);
}
