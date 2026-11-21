/**
 * Script para generar la vista desescapada y estructurada de test_tc_m03_g164.json
 * Requisito M0
 */

const fs = require('fs');
const path = require('path');

const jsonPath = path.join(__dirname, 'test_tc_m03_g164.json');
if (!fs.existsSync(jsonPath)) {
    console.error('No se encontró test_tc_m03_g164.json');
    process.exit(1);
}

const collection = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));

console.log('================================================================================');
console.log('VISTA GENERADA POR vista_coleccion_tc_m03_g164.cjs');
console.log('================================================================================\n');

console.log('--- A. VARIABLES DE COLECCIÓN ---');
(collection.variable || []).forEach(v => {
    const isSensitive = ['sandbox_secret', 'admin_password', 'productor_password', 'ingeniero_password'].includes(v.key);
    console.log(`- ${v.key}: ${isSensitive ? '<ENV>' : JSON.stringify(v.value)}`);
});

console.log('\n--- B. SCRIPTS DE COLECCIÓN ---');
(collection.event || []).forEach(ev => {
    console.log(`[Evento Colección: ${ev.listen}]`);
    if (ev.script && ev.script.exec) {
        const code = Array.isArray(ev.script.exec) ? ev.script.exec.join('\n') : ev.script.exec;
        console.log(code);
    }
});

console.log('\n--- C. ITEMS EN ORDEN DE EJECUCIÓN ---');

function printItems(items) {
    items.forEach(it => {
        if (it.request) {
            console.log(`\n================================================================================`);
            console.log(`ITEM: ${it.name}`);
            console.log(`MÉTODO: ${it.request.method}`);
            const urlRaw = it.request.url ? (typeof it.request.url === 'string' ? it.request.url : it.request.url.raw || '') : '';
            console.log(`URL: ${urlRaw}`);
            console.log(`HEADERS:`);
            (it.request.header || []).forEach(h => {
                const isSecret = h.key.toLowerCase().includes('secret');
                console.log(`  ${h.key}: ${isSecret ? '<ENV>' : h.value}`);
            });
            if (it.request.body && it.request.body.raw) {
                console.log(`BODY:`);
                let bodyClean = it.request.body.raw;
                bodyClean = bodyClean.replace(/\"(password|contrasena)\":\s*\"[^\"]+\"/g, '"$1": "<ENV>"');
                console.log(bodyClean);
            }
            if (it.event) {
                it.event.forEach(ev => {
                    console.log(`--- Script (${ev.listen}) ---`);
                    if (ev.script && ev.script.exec) {
                        const code = Array.isArray(ev.script.exec) ? ev.script.exec.join('\n') : ev.script.exec;
                        console.log(code);
                    }
                });
            }
        }
        if (it.item) {
            printItems(it.item);
        }
    });
}

printItems(collection.item || []);
