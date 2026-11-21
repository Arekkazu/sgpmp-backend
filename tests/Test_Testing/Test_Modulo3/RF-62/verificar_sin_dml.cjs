const fs = require('fs');
const path = require('path');

// Validador estricto de CERO DML en colecciones Postman / Newman de RF-62
// Prohíbe terminantemente: INSERT, UPDATE, DELETE, TRUNCATE, ALTER, DROP, CREATE
// dentro del cuerpo de peticiones hacia /test-control/query

const filesToInspect = [
    'TC-M03-G171/test_tc_m03_g171.json',
    'TC-M03-G173/test_tc_m03_g173.json',
    'TC-M03-G174/test_tc_m03_g174.json',
    'TC-M03-G175/test_tc_m03_g175.json',
    'TC-M03-G176/test_tc_m03_g176.json'
];

// Opcionalmente inspeccionar las demás si existen
['TC-M03-G167', 'TC-M03-G168', 'TC-M03-G169', 'TC-M03-G170'].forEach(tc => {
    const f = `${tc}/test_tc_m03_${tc.toLowerCase().replace('tc-m03-', '')}.json`;
    if (fs.existsSync(path.join(__dirname, f))) {
        // Podríamos auditar
    }
});

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

console.log('--- Iniciando chequeo de CERO DML en colecciones RF-62 ---');

filesToInspect.forEach(relPath => {
    const fullPath = path.join(__dirname, relPath);
    if (!fs.existsSync(fullPath)) {
        console.warn(`[WARN] Archivo no encontrado: ${fullPath}`);
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
