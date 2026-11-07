/**
 * Script de auditoría de seguridad y fuga de secretos (NW-14) para TC-M09-G08-v2.0.
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
        console.error(`[AUDITORÍA SEGURIDAD] ALERTA: Posible JWT detectado en ${path.relative(__dirname, filePath)}`);
        hallazgos++;
    }

    if (RE_BEARER.test(content)) {
        console.error(`[AUDITORÍA SEGURIDAD] ALERTA: Cabecera Bearer con token crudo detectada en ${path.relative(__dirname, filePath)}`);
        hallazgos++;
    }

    for (const pwd of passwordsSensibles) {
        if (pwd && pwd.length >= 6 && content.includes(pwd)) {
            console.error(`[AUDITORÍA SEGURIDAD] ALERTA: Contraseña de entorno detectada en ${path.relative(__dirname, filePath)}`);
            hallazgos++;
        }
    }
}

for (const dir of directorios) {
    if (fs.existsSync(dir)) {
        escanearArchivo(dir);
    }
}

if (hallazgos > 0) {
    console.error(`[AUDITORÍA SEGURIDAD] FALLA: Se encontraron ${hallazgos} posibles fugas de secretos.`);
    process.exit(1);
} else {
    console.log('[AUDITORÍA SEGURIDAD] OK: Cero fugas de credenciales o tokens detectadas.');
    process.exit(0);
}
