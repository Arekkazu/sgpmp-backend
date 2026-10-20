/**
 * Script de validación estática contra hardcodeo en TC-M03-G164 (Cumplimiento L2 / M2 / M7 / M8)
 *
 * Revisa el archivo especificado por argumento (o test_tc_m03_g164.json por defecto)
 * y falla (exit 1) ante:
 * 1. Cualquier comparación contra enteros literales con cualquier operador (==, ===, equal, eql,
 *    >=, >, <=, <, at.least, at.most, above, below, within) que no estén en constantes_especificacion.
 * 2. Literales de fecha tipo 20xx-xx-xx en URLs, queries, bodies o scripts.
 * 3. IDs fijos en URLs o queries (id_sensor=<n>, id_telemetria=<n>, /iot/calidad/<n>).
 * 4. Patrones JWT (eyJ...).
 * 5. "Bearer " seguido de texto literal (no token variable {{...}}).
 * 6. Los valores de las variables sensibles leídas del entorno (TEST_SANDBOX_SECRET, TEST_ADMIN_PASSWORD, etc.).
 * 7. Claves de query param en URLs que no pertenezcan a la lista oficial del router GET /iot/calidad.
 */

const fs = require('fs');
const path = require('path');

const targetFile = process.argv[2] 
    ? path.resolve(process.argv[2]) 
    : path.join(__dirname, 'test_tc_m03_g164.json');

if (!fs.existsSync(targetFile)) {
    console.error('[ERROR] No se encontró el archivo a validar:', targetFile);
    process.exit(1);
}

const rawContent = fs.readFileSync(targetFile, 'utf8');
let collection;
try {
    collection = JSON.parse(rawContent);
} catch (e) {
    console.error('[ERROR] El archivo no es un JSON válido:', e.message);
    process.exit(1);
}

let violations = [];

// 1. Escaneo de variables sensibles dinámicas desde process.env (M7)
const sensitiveEnvVars = [
    'TEST_SANDBOX_SECRET',
    'TEST_ADMIN_PASSWORD',
    'TEST_PRODUCER_PASSWORD',
    'TEST_FIELD_ENGINEER_PASSWORD'
];

sensitiveEnvVars.forEach(envName => {
    const val = process.env[envName];
    if (val && val.trim().length >= 4) {
        if (rawContent.toLowerCase().includes(val.toLowerCase())) {
            violations.push(`Valor de variable sensible [${envName}] detectado en texto plano en la colección.`);
        }
    } else {
        // Aviso no bloqueante si la variable no está seteada en el host
        // (el escaneo se omite para esa variable sin fallar)
    }
});

// 2. Patrón JWT (eyJ...)
const jwtRegex = /eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}/g;
if (jwtRegex.test(rawContent)) {
    violations.push('Patrón JWT hardcodeado (eyJ...) detectado.');
}

// 3. Patrón "Bearer " seguido de texto literal (sin {{...}})
const bearerLiteralRegex = /Bearer\s+(?!\{\{[a-zA-Z0-9_]+\}\})[a-zA-Z0-9_\-\.]{5,}/g;
if (bearerLiteralRegex.test(rawContent)) {
    violations.push('Patrón "Bearer " con token literal (no variable) detectado.');
}

// 4. Parámetros de Query válidos extraídos de la firma de calidad_router.py (M2)
const routerPath = path.resolve(__dirname, '../../../../../src/telemetry/infrastructure/routers/calidad_router.py');
let validQueryParams = new Set(['id_sensor', 'clasificacion', 'fecha_desde', 'fecha_hasta', 'estado_evaluacion', 'pagina', 'por_pagina']);

if (fs.existsSync(routerPath)) {
    try {
        const routerCode = fs.readFileSync(routerPath, 'utf8');
        const matchFn = routerCode.match(/def listar_calidad\(([\s\S]*?)\)\s*->\s*ListaCalidadSchema:/);
        if (matchFn) {
            const paramsBlock = matchFn[1];
            const parsedParams = [];
            paramsBlock.split('\n').forEach(line => {
                const pMatch = line.match(/^\s*([a-zA-Z0-9_]+)\s*:\s*.*Query/);
                if (pMatch) parsedParams.push(pMatch[1]);
            });
            if (parsedParams.length > 0) {
                validQueryParams = new Set(parsedParams);
            }
        }
    } catch (e) {
        console.warn('[AVISO] No se pudo parsear calidad_router.py dinámicamente, usando lista base.');
    }
}

// 5. Lista permitida de enteros según constantes_especificacion (RF-62 / HTTP / Paginación) (M8)
const allowedIntegers = new Set([
    0, 1, 2, 3, 5, 10, 20, 40, 50, 79, 80, 100, 150, 200, 201, 204, 400, 401, 403, 404, 422, 500
]);

// Inspección recursiva de items
function inspectItems(items) {
    items.forEach(it => {
        if (it.request) {
            const req = it.request;
            const urlRaw = req.url ? (typeof req.url === 'string' ? req.url : req.url.raw || '') : '';

            // IDs fijos en URLs o queries: /iot/calidad/<n>
            if (/\/iot\/calidad\/\d+/.test(urlRaw)) {
                violations.push(`[${it.name}] URL con id_telemetria hardcodeado literal: ${urlRaw}`);
            }

            // id_sensor=<n> o id_telemetria=<n> fijos
            if (/id_sensor=\d+/.test(urlRaw)) {
                violations.push(`[${it.name}] Query param con id_sensor hardcodeado literal: ${urlRaw}`);
            }
            if (/id_telemetria=\d+/.test(urlRaw)) {
                violations.push(`[${it.name}] Query param con id_telemetria hardcodeado literal: ${urlRaw}`);
            }

            // Fechas fijas 20xx-xx-xx en URLs o queries
            if (/20\d\d-\d\d-\d\d/.test(urlRaw)) {
                violations.push(`[${it.name}] URL/Query con fecha literal tipo 20xx-xx-xx: ${urlRaw}`);
            }

            // M2: Validación de query params contra la lista oficial de calidad_router.py
            if (urlRaw.includes('/iot/calidad?') || urlRaw.includes('/iot/calidad/?')) {
                const queryString = urlRaw.split('?')[1] || '';
                const queryParts = queryString.split('&');
                queryParts.forEach(qp => {
                    const key = qp.split('=')[0];
                    if (key && !validQueryParams.has(key)) {
                        violations.push(`[${it.name}] Query param no permitido en GET /iot/calidad: "${key}"`);
                    }
                });
            }

            // Bodies con credenciales literales sin template variable {{...}}
            if (req.body && req.body.raw) {
                if (req.body.raw.includes('"password":') && !req.body.raw.includes('{{')) {
                    violations.push(`[${it.name}] Body con contraseña literal sin variable.`);
                }
                if (req.body.raw.includes('"contrasena":') && !req.body.raw.includes('{{')) {
                    violations.push(`[${it.name}] Body con contraseña literal sin variable.`);
                }
                if (/20\d\d-\d\d-\d\d/.test(req.body.raw)) {
                    violations.push(`[${it.name}] Body con fecha literal tipo 20xx-xx-xx.`);
                }
            }
        }

        // Inspeccionar scripts de prerequest y test (M8)
        if (it.event) {
            it.event.forEach(ev => {
                if (ev.script && ev.script.exec) {
                    const lines = Array.isArray(ev.script.exec) ? ev.script.exec : [ev.script.exec];
                    lines.forEach((line, idx) => {
                        // Limpiar comentarios reales al inicio o al final sin romper URLs tipo http://
                        let cleanLine = line.replace(/^\s*\/\/.*$/, ''); // comentario completo de línea
                        cleanLine = cleanLine.replace(/\s+\/\/.*$/, ''); // comentario al final de sentencia

                        if (!cleanLine.trim()) return;

                        // Fechas fijas 20xx-xx-xx
                        if (/20\d\d-\d\d-\d\d/.test(cleanLine)) {
                            violations.push(`[${it.name}] Línea ${idx + 1} de script con fecha literal: ${cleanLine.trim()}`);
                        }

                        // M8: Detección estricta de enteros literales con cualquier operador de Chai / JS:
                        // .to.equal, .to.eql, .at.least, .at.most, .above, .below, ==, ===, >=, <=, >, <, .within(a, b)
                        const chaiRegex = /\.(?:equal|eql|at\.least|at\.most|above|below)\s*\(\s*(\d+)\s*\)/g;
                        let m;
                        while ((m = chaiRegex.exec(cleanLine)) !== null) {
                            const val = parseInt(m[1], 10);
                            if (!allowedIntegers.has(val)) {
                                violations.push(`[${it.name}] Aserción contra entero literal no autorizado (${val}) en: "${cleanLine.trim()}"`);
                            }
                        }

                        const withinRegex = /\.within\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)/g;
                        while ((m = withinRegex.exec(cleanLine)) !== null) {
                            const v1 = parseInt(m[1], 10);
                            const v2 = parseInt(m[2], 10);
                            if (!allowedIntegers.has(v1)) violations.push(`[${it.name}] Rango within no autorizado (${v1}) en: "${cleanLine.trim()}"`);
                            if (!allowedIntegers.has(v2)) violations.push(`[${it.name}] Rango within no autorizado (${v2}) en: "${cleanLine.trim()}"`);
                        }

                        const jsOpRegex = /(?:===|==|>=|<=|>|<)\s*(\d+)/g;
                        while ((m = jsOpRegex.exec(cleanLine)) !== null) {
                            const val = parseInt(m[1], 10);
                            if (!allowedIntegers.has(val)) {
                                violations.push(`[${it.name}] Comparación JS contra entero literal no autorizado (${val}) en: "${cleanLine.trim()}"`);
                            }
                        }
                    });
                }
            });
        }

        if (it.item) {
            inspectItems(it.item);
        }
    });
}

inspectItems(collection.item || []);

if (violations.length > 0) {
    console.error('====================================================');
    console.error('FALLO DE VALIDACIÓN ESTÁTICA (HARDCODEOS O PARÁMETROS INVÁLIDOS):');
    violations.forEach(v => console.error(' - ' + v));
    console.error('====================================================');
    process.exit(1);
} else {
    console.log('====================================================');
    console.log('[VALIDACIÓN ESTÁTICA OK] Cero hardcodeos, secretos, fechas fijas ni parámetros inválidos.');
    console.log(`Parámetros de consulta validados contra router: [${Array.from(validQueryParams).join(', ')}]`);
    console.log('====================================================');
    process.exit(0);
}
