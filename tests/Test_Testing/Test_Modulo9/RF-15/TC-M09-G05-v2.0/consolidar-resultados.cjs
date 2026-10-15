/**
 * Consolidador de resultados oficial para TC-M09-G05-v2.0.
 *
 * Lee la salida de Newman (consola/HTML) y los resultados de auditoría y base de datos,
 * valida los 11 checkpoints estrictos (NW-01 a NW-11), aborta si falta cualquiera,
 * y genera 'resultados/resultado_TC-M09-G05-v2.0.json'.
 */
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const BASE_DIR = __dirname;
const RESULTADOS_DIR = path.join(BASE_DIR, 'resultados');
const EVIDENCIAS_DIR = path.join(BASE_DIR, 'evidencias');

const HTML_FILE = path.join(RESULTADOS_DIR, 'resultado_TC-M09-G05-v2.0.html');
const CONSOLA_FILE = path.join(EVIDENCIAS_DIR, 'consola_TC-M09-G05-v2.0.txt');
const AUDITORIA_SCRIPT = path.join(BASE_DIR, 'auditoria-seguridad.cjs');
const VERIFICAR_BD_SCRIPT = path.join(BASE_DIR, 'verificar-bd.py');
const JSON_OUT = path.join(RESULTADOS_DIR, 'resultado_TC-M09-G05-v2.0.json');

// Definición estricta de los 11 checkpoints requeridos
const DEFINICION_CHECKPOINTS = [
    {
        paso: 'NW-01',
        regex: /NW-01: Autenticación exitosa del Administrador/,
        esperado: 'HTTP 200 OK con token JWT administrativo válido',
        obtenidoOk: 'HTTP 200 recibido con token JWT emitido'
    },
    {
        paso: 'NW-02',
        regex: /NW-02: Preflight de solo lectura y verificación de fixture F-04/,
        esperado: 'HTTP 200 OK; Fixture F-04 activo, estado capturado y ausencia previa de Alpaca QA2',
        obtenidoOk: 'HTTP 200 recibido; F-04 verificado activo y datos originales capturados'
    },
    {
        paso: 'NW-03',
        regex: /NW-03: Autenticación exitosa del Ingeniero de Campo/,
        esperado: 'HTTP 200 OK con token JWT de Ingeniero válido',
        obtenidoOk: 'HTTP 200 recibido con token de Ingeniero emitido'
    },
    {
        paso: 'NW-04',
        regex: /NW-04: Verificación de matriz de permisos RBAC del Ingeniero/,
        esperado: 'HTTP 200 OK; Rol tiene (8,2) y (8,3), sin permisos (8,1) ni (8,4)',
        obtenidoOk: 'HTTP 200 recibido; matriz RBAC confirmada (sin permisos de creación ni desactivación)'
    },
    {
        paso: 'NW-05',
        regex: /NW-05: SC-1 Rechazo de creación por Ingeniero con HTTP 403 y sin persistencia/,
        esperado: 'HTTP 403 Forbidden con error_code ACCESO_DENEGADO; sin persistencia en BD',
        obtenidoOk: 'HTTP 403 recibido con error_code ACCESO_DENEGADO; creación rechazada por RBAC'
    },
    {
        paso: 'NW-06',
        regex: /NW-06: SC-2 Rechazo de desactivación de F-04 con HTTP 403 e inmutabilidad/,
        esperado: 'HTTP 403 Forbidden con error_code ACCESO_DENEGADO; es_activo permanece inmutable',
        obtenidoOk: 'HTTP 403 recibido con error_code ACCESO_DENEGADO; estado es_activo inalterado'
    },
    {
        paso: 'NW-07',
        regex: /NW-07: SC-3 Edición autorizada de descripción de F-04 por Ingeniero con HTTP 200/,
        esperado: 'HTTP 200 OK con descripción actualizada por Ingeniero',
        obtenidoOk: 'HTTP 200 recibido; descripción de especie modificada exitosamente'
    },
    {
        paso: 'NW-08',
        esScript: true,
        esperado: 'Registro de auditoría UPDATE persistido en modulo9.auditorias_especies con id_usuario=4',
        obtenidoOk: 'Registro de auditoría UPDATE confirmado en BD con id_usuario=4 e id_especie=4'
    },
    {
        paso: 'NW-09',
        regex: /NW-09: Teardown administrativo y restauración de descripción original/,
        esperado: 'HTTP 200 OK; descripción original restaurada en fixture F-04 con token Admin',
        obtenidoOk: 'HTTP 200 recibido; descripción original restaurada exitosamente'
    },
    {
        paso: 'NW-10',
        esScript: true,
        esperado: 'Cero fugas de credenciales, contraseñas o tokens JWT en resultados/ y evidencias/',
        obtenidoOk: 'Auditoría superada: cero secretos expuestos en evidencias y reportes'
    },
    {
        paso: 'NW-11',
        esScript: true,
        esperado: 'Integridad final en BD: F-04 activo con descripción original y cero residuales de Alpaca QA2',
        obtenidoOk: 'Integridad en BD confirmada: F-04 restaurado activo y cero registros residuales'
    }
];

function extraerTextoNewman() {
    let texto = '';
    if (fs.existsSync(CONSOLA_FILE)) {
        texto += fs.readFileSync(CONSOLA_FILE, 'utf8') + '\n';
    }
    if (fs.existsSync(HTML_FILE)) {
        texto += fs.readFileSync(HTML_FILE, 'utf8') + '\n';
    }
    return texto;
}

function evaluarCheckpointNewman(chk, textoCompleto) {
    if (!chk.regex) return null;

    if (!chk.regex.test(textoCompleto)) {
        return null; // No apareció en la salida
    }

    // Buscar si falló la aserción
    const regexFalla = new RegExp(`AssertionError.*?${chk.paso}`, 'i');
    const regexFailText = new RegExp(`FAIL.*?${chk.paso}`, 'i');
    const regexError = new RegExp(`${chk.paso}.*?(failed|error)`, 'i');

    const hayFalla = regexFalla.test(textoCompleto) || regexFailText.test(textoCompleto) || regexError.test(textoCompleto);

    return {
        paso: chk.paso,
        esperado: chk.esperado,
        obtenido: hayFalla ? 'Aserción fallida en ejecución Newman' : chk.obtenidoOk,
        estado: hayFalla ? 'FALLA' : 'OK'
    };
}

function ejecutarAuditoriaSeguridad() {
    console.log('[CONSOLIDADOR] Ejecutando auditoría de seguridad (NW-10)...');
    const res = spawnSync('node', [AUDITORIA_SCRIPT], { encoding: 'utf8' });
    const salida = (res.stdout || '') + '\n' + (res.stderr || '');

    const evidenciasDir = path.join(BASE_DIR, 'evidencias');
    if (!fs.existsSync(evidenciasDir)) fs.mkdirSync(evidenciasDir, { recursive: true });
    fs.writeFileSync(path.join(evidenciasDir, 'auditoria_fuga.txt'), salida, 'utf8');

    return {
        paso: 'NW-10',
        esperado: DEFINICION_CHECKPOINTS.find(c => c.paso === 'NW-10').esperado,
        obtenido: res.status === 0 ? DEFINICION_CHECKPOINTS.find(c => c.paso === 'NW-10').obtenidoOk : `Falla en auditoría: ${salida.trim()}`,
        estado: res.status === 0 ? 'OK' : 'FALLA'
    };
}

function ejecutarVerificacionBD(modo, pasoId) {
    console.log(`[CONSOLIDADOR] Ejecutando verificación de base de datos (${pasoId} - modo: ${modo})...`);
    
    // Buscar python en el venv del repositorio
    const repoRoot = path.resolve(BASE_DIR, '../../../../..');
    const pythonVenv = path.join(repoRoot, '.venv', 'Scripts', 'python.exe');
    const pythonExe = fs.existsSync(pythonVenv) ? pythonVenv : 'python';

    const res = spawnSync(pythonExe, [VERIFICAR_BD_SCRIPT, '--modo', modo], { encoding: 'utf8' });
    const salida = (res.stdout || '') + '\n' + (res.stderr || '');

    const evidenciasDir = path.join(BASE_DIR, 'evidencias');
    if (!fs.existsSync(evidenciasDir)) fs.mkdirSync(evidenciasDir, { recursive: true });
    fs.writeFileSync(path.join(evidenciasDir, `verificacion_bd_${pasoId.toLowerCase()}.txt`), salida, 'utf8');

    const def = DEFINICION_CHECKPOINTS.find(c => c.paso === pasoId);
    return {
        paso: pasoId,
        esperado: def.esperado,
        obtenido: res.status === 0 ? def.obtenidoOk : `Falla en BD: ${salida.trim()}`,
        estado: res.status === 0 ? 'OK' : 'FALLA'
    };
}

function main() {
    console.log('[CONSOLIDADOR] Iniciando consolidación para TC-M09-G05-v2.0...');

    const textoNewman = extraerTextoNewman();
    const checkpointsProcesados = [];

    // 1. Procesar checkpoints Newman
    for (const chk of DEFINICION_CHECKPOINTS) {
        if (!chk.esScript) {
            const res = evaluarCheckpointNewman(chk, textoNewman);
            if (res) {
                checkpointsProcesados.push(res);
            }
        }
    }

    // 2. Procesar scripts externos (NW-08, NW-10, NW-11)
    const resNW08 = ejecutarVerificacionBD('nw08', 'NW-08');
    checkpointsProcesados.push(resNW08);

    const resNW10 = ejecutarAuditoriaSeguridad();
    checkpointsProcesados.push(resNW10);

    const resNW11 = ejecutarVerificacionBD('nw11', 'NW-11');
    checkpointsProcesados.push(resNW11);

    // 3. Ordenar checkpoints por paso NW-xx
    checkpointsProcesados.sort((a, b) => a.paso.localeCompare(b.paso, undefined, { numeric: true }));

    // 4. Validar que estén los 11 checkpoints exactos
    const pasosPresentes = new Set(checkpointsProcesados.map(c => c.paso));
    const faltantes = DEFINICION_CHECKPOINTS.map(c => c.paso).filter(p => !pasosPresentes.has(p));

    if (faltantes.length > 0) {
        console.error(`[CONSOLIDADOR] ERROR CRÍTICO: Faltan los siguientes checkpoints en la consolidación: ${faltantes.join(', ')}`);
        console.error('[CONSOLIDADOR] Abortando sin generar archivo de resultados JSON.');
        process.exit(1);
    }

    // 5. Construir objeto final
    const resultadoFinal = {
        tc: 'TC-M09-G05-v2.0',
        ambiente: 'TEST',
        fecha: new Date().toISOString(),
        checkpoints: checkpointsProcesados,
        checkpoints_no_contabilizados: [
            {
                paso: 'G05-v2.0-4',
                motivo: 'Subcaso 4 excluido: edición de grupo_manejo pendiente de definición funcional'
            }
        ]
    };

    // 6. Escribir archivo de resultados computable
    if (!fs.existsSync(RESULTADOS_DIR)) {
        fs.mkdirSync(RESULTADOS_DIR, { recursive: true });
    }
    fs.writeFileSync(JSON_OUT, JSON.stringify(resultadoFinal, null, 2), 'utf8');
    console.log(`[CONSOLIDADOR] ÉXITO: Reporte computable generado en ${JSON_OUT}`);
    console.log(`[CONSOLIDADOR] Total checkpoints procesados: ${checkpointsProcesados.length}/11`);
    
    const totalOk = checkpointsProcesados.filter(c => c.estado === 'OK').length;
    const totalFalla = checkpointsProcesados.filter(c => c.estado === 'FALLA').length;
    console.log(`[CONSOLIDADOR] Resumen: ${totalOk} OK, ${totalFalla} FALLA`);

    if (totalFalla > 0) {
        process.exit(1);
    } else {
        process.exit(0);
    }
}

main();
