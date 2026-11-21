/**
 * Consolidador de resultados para TC-M09-G02-v2.0.
 *
 * Lee la salida de Newman (consola/HTML) y los resultados de auditoría y base de datos,
 * genera el reporte JSON computable oficial en 'resultados/resultado_TC-M09-G02-v2.0.json'
 * con los 20 checkpoints exactos.
 */
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const BASE_DIR = __dirname;
const RESULTADOS_DIR = path.join(BASE_DIR, 'resultados');
const EVIDENCIAS_DIR = path.join(BASE_DIR, 'evidencias');

const HTML_FILE = path.join(RESULTADOS_DIR, 'resultado_TC-M09-G02-v2.0.html');
const CONSOLA_FILE = path.join(EVIDENCIAS_DIR, 'consola_TC-M09-G02-v2.0.txt');
const AUDITORIA_TXT = path.join(EVIDENCIAS_DIR, 'auditoria_fuga.txt');
const VERIFICACION_BD_TXT = path.join(EVIDENCIAS_DIR, 'verificacion_bd.txt');
const JSON_OUT = path.join(RESULTADOS_DIR, 'resultado_TC-M09-G02-v2.0.json');

// Definición estricta de los 20 checkpoints esperados
const DEFINICION_CHECKPOINTS = [
    {
        paso: 'NW-01',
        regex: /NW-01: Autenticación exitosa del Administrador/,
        esperado: 'HTTP 200 OK con token JWT válido en cuerpo',
        obtenidoOk: 'HTTP 200 recibido con token JWT emitido'
    },
    {
        paso: 'NW-02',
        regex: /NW-02: Preflight exitoso y verificación de fixture/,
        esperado: 'HTTP 200 OK; Cachama Blanca existe y nombres de prueba libres',
        obtenidoOk: 'HTTP 200 recibido; Cachama Blanca verificada y nombres libres'
    },
    {
        paso: 'NW-03',
        regex: /NW-03: Registro exitoso con nombre de 3 caracteres/,
        esperado: 'HTTP 201 Created con entidad de 3 caracteres persistida',
        obtenidoOk: 'HTTP 201 recibido; especie de 3 caracteres registrada'
    },
    {
        paso: 'NW-03b',
        regex: /NW-03b: Confirmación de persistencia de especie de 3 caracteres/,
        esperado: 'HTTP 200 OK; especie de 3 caracteres existe y está activa',
        obtenidoOk: 'HTTP 200 recibido; persistencia y estado activo confirmados'
    },
    {
        paso: 'NW-04',
        regex: /NW-04: Desactivación lógica de especie creada en Subcaso 1/,
        esperado: 'HTTP 200 OK con es_activo=false',
        obtenidoOk: 'HTTP 200 recibido; especie desactivada lógicamente'
    },
    {
        paso: 'NW-05',
        regex: /NW-05: Registro exitoso con nombre límite de 50 caracteres/,
        esperado: 'HTTP 201 Created con entidad de 50 caracteres persistida',
        obtenidoOk: 'HTTP 201 recibido; especie de 50 caracteres registrada'
    },
    {
        paso: 'NW-05b',
        regex: /NW-05b: Confirmación de persistencia de especie de 50 caracteres/,
        esperado: 'HTTP 200 OK; especie de 50 caracteres existe y está activa',
        obtenidoOk: 'HTTP 200 recibido; persistencia y estado activo confirmados'
    },
    {
        paso: 'NW-06',
        regex: /NW-06: Desactivación lógica de especie creada en Subcaso 2/,
        esperado: 'HTTP 200 OK con es_activo=false',
        obtenidoOk: 'HTTP 200 recibido; especie desactivada lógicamente'
    },
    {
        paso: 'NW-07',
        regex: /NW-07: Rechazo de nombre con 2 caracteres por longitud insuficiente/,
        esperado: 'HTTP 400 Bad Request (VAL_ENTRADA) por longitud <3',
        obtenidoOk: 'HTTP 400 recibido; error de longitud en campo nombre'
    },
    {
        paso: 'NW-07b',
        regex: /NW-07b: Confirmación de no-persistencia de nombre rechazado con 2 caracteres/,
        esperado: 'HTTP 200 OK; nombre de 2 caracteres no existe en base de datos',
        obtenidoOk: 'HTTP 200 recibido; ausencia en base de datos confirmada'
    },
    {
        paso: 'NW-08',
        regex: /NW-08: Rechazo de nombre con 51 caracteres por exceso de longitud/,
        esperado: 'HTTP 400 Bad Request (VAL_ENTRADA) por longitud >50',
        obtenidoOk: 'HTTP 400 recibido; error de longitud en campo nombre'
    },
    {
        paso: 'NW-08b',
        regex: /NW-08b: Confirmación de no-persistencia de nombre con 51 caracteres/,
        esperado: 'HTTP 200 OK; nombre de 51 caracteres no existe en base de datos',
        obtenidoOk: 'HTTP 200 recibido; ausencia en base de datos confirmada'
    },
    {
        paso: 'NW-09a',
        regex: /NW-09a: Rechazo de nombre vacío/,
        esperado: 'HTTP 400 Bad Request (VAL_ENTRADA) para nombre vacío',
        obtenidoOk: 'HTTP 400 recibido; error de validación en campo nombre'
    },
    {
        paso: 'NW-09b',
        regex: /NW-09b: Rechazo de nombre nulo/,
        esperado: 'HTTP 400 Bad Request (VAL_ENTRADA) para nombre null',
        obtenidoOk: 'HTTP 400 recibido; error de tipo en campo nombre'
    },
    {
        paso: 'NW-10',
        regex: /NW-10: Rechazo de nombre duplicado case-insensitive/,
        esperado: 'HTTP 409 Conflict (ESPECIE_DUPLICADA)',
        obtenidoOk: 'HTTP 409 recibido; rechazo por unicidad case-insensitive'
    },
    {
        paso: 'NW-10b',
        regex: /NW-10b: Confirmación de unicidad en catálogo/,
        esperado: 'HTTP 200 OK; exactamente 1 instancia de Cachama Blanca',
        obtenidoOk: 'HTTP 200 recibido; catálogo mantiene exactamente 1 registro'
    },
    {
        paso: 'NW-11',
        regex: /NW-11: Rechazo de nombre con caracteres especiales no permitidos/,
        esperado: 'HTTP 400 Bad Request (VAL_ENTRADA) por formato inválido',
        obtenidoOk: 'HTTP 400 recibido; error de caracteres en campo nombre'
    },
    {
        paso: 'NW-11b',
        regex: /NW-11b: Confirmación de no-persistencia de nombre con símbolos/,
        esperado: 'HTTP 200 OK; nombre con símbolos no existe en base de datos',
        obtenidoOk: 'HTTP 200 recibido; ausencia en base de datos confirmada'
    },
    {
        paso: 'NW-12',
        esperado: 'Cero tokens JWT, Bearer crudos o contraseñas en evidencias y resultados',
        obtenidoOk: 'Auditoría completada: Cero fugas de credenciales o tokens detectadas'
    },
    {
        paso: 'NW-13',
        esperado: 'Cero registros de prueba activos en PostgreSQL TEST y teardown completo',
        obtenidoOk: 'Verificación BD completada: Cero especies de prueba activas residuales'
    }
];

function obtenerTextoConsola() {
    if (fs.existsSync(CONSOLA_FILE)) {
        return fs.readFileSync(CONSOLA_FILE, 'utf8');
    }
    if (fs.existsSync(HTML_FILE)) {
        return fs.readFileSync(HTML_FILE, 'utf8');
    }
    throw new Error(`No se encontró ni ${CONSOLA_FILE} ni ${HTML_FILE} para consolidar resultados.`);
}

function evaluarAuditoria() {
    let salida = '';
    if (fs.existsSync(AUDITORIA_TXT)) {
        salida = fs.readFileSync(AUDITORIA_TXT, 'utf8');
    } else {
        const res = spawnSync('node', [path.join(BASE_DIR, 'auditoria-seguridad.cjs')], { encoding: 'utf8' });
        salida = res.stdout + (res.stderr || '');
    }
    const esOk = salida.includes('Cero fugas de credenciales o tokens detectadas');
    return {
        estado: esOk ? 'OK' : 'FALLA',
        obtenido: esOk ? 'Cero fugas de credenciales o tokens detectadas' : `Fuga detectada: ${salida.trim()}`
    };
}

function evaluarVerificacionBD() {
    let salida = '';
    if (fs.existsSync(VERIFICACION_BD_TXT)) {
        salida = fs.readFileSync(VERIFICACION_BD_TXT, 'utf8');
    } else {
        const res = spawnSync('node', [path.join(BASE_DIR, 'verificar-bd.cjs')], { encoding: 'utf8' });
        salida = res.stdout + (res.stderr || '');
    }
    const esOk = salida.includes('Cero especies de prueba permanecen activas en base de datos');
    return {
        estado: esOk ? 'OK' : 'FALLA',
        obtenido: esOk ? 'Cero especies de prueba activas en base de datos tras teardown' : `Inconsistencia en BD: ${salida.trim()}`
    };
}

function consolidar() {
    console.log('[CONSOLIDADOR] Iniciando consolidación de resultados para TC-M09-G02-v2.0...');
    const textoNewman = obtenerTextoConsola();
    const checkpoints = [];
    const checkpointsNoContabilizados = [];

    // Evaluar items NW-01 a NW-11b
    for (const def of DEFINICION_CHECKPOINTS) {
        if (def.paso === 'NW-12') {
            const auditRes = evaluarAuditoria();
            checkpoints.push({
                paso: 'NW-12',
                esperado: def.esperado,
                obtenido: auditRes.obtenido,
                estado: auditRes.estado
            });
            continue;
        }

        if (def.paso === 'NW-13') {
            const bdRes = evaluarVerificacionBD();
            checkpoints.push({
                paso: 'NW-13',
                esperado: def.esperado,
                obtenido: bdRes.obtenido,
                estado: bdRes.estado
            });
            continue;
        }

        // Buscar aserción de Newman
        if (!def.regex) continue;

        // Comprobar si pasó (√ o pase en htmlextra)
        const encontradoEnTexto = def.regex.test(textoNewman);
        if (!encontradoEnTexto) {
            console.error(`[CONSOLIDADOR] ERROR: No se encontró rastro de la aserción ${def.paso} en la salida de Newman.`);
            checkpointsNoContabilizados.push(def.paso);
            continue;
        }

        // En consola de newman, una falla se lista con número al inicio de la aserción o "assertion failed"
        const regexFalla = new RegExp(`(?:[0-9]+\\)\\s+${def.regex.source}|${def.regex.source}.*AssertionError)`, 'i');
        const falloDetectado = regexFalla.test(textoNewman);

        if (falloDetectado) {
            checkpoints.push({
                paso: def.paso,
                esperado: def.esperado,
                obtenido: `Aserción fallida en ejecución Newman`,
                estado: 'FALLA'
            });
        } else {
            checkpoints.push({
                paso: def.paso,
                esperado: def.esperado,
                obtenido: def.obtenidoOk,
                estado: 'OK'
            });
        }
    }

    if (checkpoints.length !== 20) {
        console.error(`[CONSOLIDADOR] ABORTADO: Se esperaban 20 checkpoints pero se computaron ${checkpoints.length}. Faltantes: ${checkpointsNoContabilizados.join(', ')}`);
        process.exit(1);
    }

    const payload = {
        tc: 'TC-M09-G02-v2.0',
        ambiente: 'TEST',
        fecha: new Date().toISOString(),
        checkpoints: checkpoints
    };

    if (checkpointsNoContabilizados.length > 0) {
        payload.checkpoints_no_contabilizados = checkpointsNoContabilizados;
    }

    fs.writeFileSync(JSON_OUT, JSON.stringify(payload, null, 2), 'utf8');
    console.log(`[CONSOLIDADOR] ÉXITO: Reporte computable generado en ${JSON_OUT} con ${checkpoints.length} checkpoints.`);
}

try {
    consolidar();
} catch (err) {
    console.error(`[CONSOLIDADOR] Error fatal: ${err.message}`);
    process.exit(1);
}
