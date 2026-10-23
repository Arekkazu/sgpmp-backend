const fs = require('fs');
const path = require('path');

// Validador estricto de CERO DML en colecciones Postman / Newman de RF-63
// Prohíbe terminantemente: INSERT, UPDATE, DELETE, TRUNCATE, ALTER, DROP, CREATE
// dentro del cuerpo de peticiones hacia /test-control/query

const filesToInspect = [
    'TC-M03-G177/test_tc_m03_g177.json',
    'TC-M03-G178/test_tc_m03_g178.json',
    'TC-M03-G179/test_tc_m03_g179.json',
    'TC-M03-G180/test_tc_m03_g180.json',
    'TC-M03-G181/test_tc_m03_g181.json',
    'TC-M03-G182/test_tc_m03_g182.json',
    'TC-M03-G183/test_tc_m03_g183.json',
    'TC-M03-G184/test_tc_m03_g184.json',
    'TC-M03-G185/test_tc_m03_g185.json',
    'TC-M03-G186/test_tc_m03_g186.json',
    'TC-M03-G187/test_tc_m03_g187.json',
    'TC-M03-G190/test_tc_m03_g190.json',
    'TC-M03-G191/test_tc_m03_g191.json'
];

const dmlPattern = /\b(INSERT|UPDATE|DELETE|TRUNCATE|ALTER|DROP|CREATE)\b/i;

let hasViolations = false;

function scanItem(item, fileName, folderPath) {
    if (item.item && Array.isArray(item.item)) {
        item.item.forEach(sub => scanItem(sub, fileName, `${folderPath} > ${item.name}`));
        return;
    }

    if (item.request && item.request.url) {
        const rawUrl = typeof item.request.url === 'string' ? item.request.url : (item.request.url.raw || '');
        if (rawUrl.includes('/test-control/query') && item.request.body && item.request.body.raw) {
            let bodyText = item.request.body.raw;
            try {
                const parsed = JSON.parse(bodyText);
                if (parsed.query) bodyText = parsed.query;
            } catch (e) {
                // raw text
            }

            const match = dmlPattern.exec(bodyText);
            if (match) {
                console.error(`[ERROR CERO DML] Violación detectada en ${fileName}:`);
                console.error(`  Ruta: ${folderPath} > ${item.name}`);
                console.error(`  Palabra prohibida: ${match[1].toUpperCase()}`);
                console.error(`  Query: ${bodyText.substring(0, 120)}...`);
                hasViolations = true;
            }
        }
    }
}

console.log('--- Iniciando chequeo de CERO DML en colecciones RF-63 ---');

filesToInspect.forEach(relPath => {
    const fullPath = path.join(__dirname, relPath);
    if (!fs.existsSync(fullPath)) {
        console.warn(`[WARN] Archivo no encontrado todavía: ${fullPath}`);
        return;
    }
    const collection = JSON.parse(fs.readFileSync(fullPath, 'utf8'));
    (collection.item || []).forEach(it => scanItem(it, relPath, collection.info.name || 'Root'));
});

if (hasViolations) {
    console.error('\nChequeo CERO DML FALLIDO: Se encontraron sentencias DML prohibidas.');
    process.exit(1);
} else {
    console.log('Chequeo CERO DML EXITOSO: Ninguna petición a /test-control/query contiene DML.');
    process.exit(0);
}
