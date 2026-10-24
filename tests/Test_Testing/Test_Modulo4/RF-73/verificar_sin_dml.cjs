const fs = require('fs');
const path = require('path');

// Validador estricto de CERO DML en colecciones Postman / Newman de RF-73
// Prohíbe terminantemente: INSERT, UPDATE, DELETE, TRUNCATE, ALTER, DROP, CREATE
// dentro del cuerpo de peticiones hacia /test-control/query

const filesToInspect = [
    'TC-M04-G081/test_tc_m04_g081.json',
    'TC-M04-G082/test_tc_m04_g082.json',
    'TC-M04-G083/test_tc_m04_g083.json',
    'TC-M04-G084/test_tc_m04_g084.json',
    'TC-M04-G085/test_tc_m04_g085.json',
    'TC-M04-G086/test_tc_m04_g086.json',
    'TC-M04-G087/test_tc_m04_g087.json',
    'TC-M04-G088/test_tc_m04_g088.json',
    'TC-M04-G089/test_tc_m04_g089.json',
    'TC-M04-G090/test_tc_m04_g090.json',
    'TC-M04-G091/test_tc_m04_g091.json',
    'TC-M04-G092/test_tc_m04_g092.json',
    'TC-M04-G094/test_tc_m04_g094.json',
    'TC-M04-G095/test_tc_m04_g095.json',
    'TC-M04-G096/test_tc_m04_g096.json',
    'TC-M04-G097/test_tc_m04_g097.json',
    'TC-M04-G099/test_tc_m04_g099.json',
    'TC-M04-G100/test_tc_m04_g100.json',
    'TC-M04-G101/test_tc_m04_g101.json'
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

console.log('--- Iniciando chequeo de CERO DML en colecciones RF-73 ---');

filesToInspect.forEach(relPath => {
    const fullPath = path.join(__dirname, relPath);
    if (!fs.existsSync(fullPath)) {
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
