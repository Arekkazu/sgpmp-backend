/**
 * Consolidador de resultados oficial para TC-M09-G08-v2.0.
 *
 * Lee la salida de Newman (consola/HTML) y los resultados de auditoría y base de datos,
 * valida los 19 checkpoints requeridos (NW-01 a NW-15 incluyendo sub-a/b),
 * aborta sin escribir si falta cualquiera, y genera 'resultados/resultado_TC-M09-G08-v2.0.json'.
 */
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const BASE_DIR = __dirname;
const RESULTADOS_DIR = path.join(BASE_DIR, 'resultados');
const EVIDENCIAS_DIR = path.join(BASE_DIR, 'evidencias');

const HTML_FILE = path.join(RESULTADOS_DIR, 'resultado_TC-M09-G08-v2.0.html');
const CONSOLA_FILE = path.join(EVIDENCIAS_DIR, 'consola_TC-M09-G08-v2.0.txt');
const AUDITORIA_SCRIPT = path.join(BASE_DIR, 'auditoria-seguridad.cjs');
const VERIFICAR_BD_SCRIPT = path.join(BASE_DIR, 'verificar-bd.py');
const JSON_OUT = path.join(RESULTADOS_DIR, 'resultado_TC-M09-G08-v2.0.json');

// Definición estricta de los 19 checkpoints requeridos
const DEFINICION_CHECKPOINTS = [
    {
        paso: 'NW-01',
        regex: /NW-01: Autenticación exitosa del Administrador/,
        esperado: 'HTTP 200 OK con token JWT administrativo válido',
        obtenidoOk: 'HTTP 200 recibido con token JWT emitido'
    },
    {
        paso: 'NW-02',
        regex: /NW-02: Preflight de solo lectura, backend activo y verificación de fixture libre/,
        esperado: 'HTTP 200 OK; backend activo, nombres de prueba libres y captura de run_start_time',
        obtenidoOk: 'HTTP 200 recibido; catálogo libre y timestamp de inicio capturado'
    },
    {
        paso: 'NW-03',
        regex: /NW-03: Subcaso 1 Creación de especie con grupo_manejo/,
        esperado: 'HTTP 201 Created con id_especie y fecha_actualizacion asignadas',
        obtenidoOk: 'HTTP 201 recibido; especie creada exitosamente'
    },
    {
        paso: 'NW-04',
        esBD: true,
        esperado: 'Registro de auditoría CREATE persistido en modulo9.auditorias_especies para especie creada',
        obtenidoOk: 'Registro de auditoría CREATE confirmado en BD con id_usuario=104'
    },
    {
        paso: 'NW-04a',
        esBD: true,
        esperado: 'id_usuario=104, tipo_operacion=\'CREATE\', fecha_gestion >= run_start_time',
        obtenidoOk: 'Metadatos CREATE confirmados: id_usuario=104, tipo_operacion=\'CREATE\', fecha_gestion válida'
    },
    {
        paso: 'NW-04b',
        esBD: true,
        esperado: 'valores_nuevos.grupo_manejo == \'ESPECIES_MEDIANAS\'',
        obtenidoOk: 'valores_nuevos contiene grupo_manejo'
    },
    {
        paso: 'NW-05',
        regex: /NW-05: Subcaso 2 Edición de nombre/,
        esperado: 'HTTP 200 OK con nombre actualizado',
        obtenidoOk: 'HTTP 200 recibido; nombre actualizado conforme'
    },
    {
        paso: 'NW-06',
        esBD: true,
        esperado: 'valores_anteriores.nombre ≈ \'Cabra Qaa\' y valores_nuevos.nombre ≈ \'Cabra Criolla Qaa\' (case-insensitive)',
        obtenidoOk: 'Transición de nombres confirmada en snapshot de auditoría'
    },
    {
        paso: 'NW-07',
        regex: /NW-07: Subcaso 3 Intento de edición de grupo_manejo/,
        esperado: 'HTTP 200 OK (Pydantic ignora campo extra grupo_manejo)',
        obtenidoOk: 'HTTP 200 recibido; petición procesada ignorando campo extra'
    },
    {
        paso: 'NW-08',
        esBD: true,
        esperado: 'Auditoría UPDATE persistida en BD tras intento de edición de grupo_manejo',
        obtenidoOk: 'Registro de auditoría UPDATE confirmado en BD'
    },
    {
        paso: 'NW-08a',
        esBD: true,
        esperado: 'tipo_operacion=\'UPDATE\' y usuario/fecha válidos (id_usuario=104)',
        obtenidoOk: 'Metadatos UPDATE confirmados: id_usuario=104 y fecha válida'
    },
    {
        paso: 'NW-08b',
        esBD: true,
        esperado: 'valores_anteriores.grupo_manejo == \'ESPECIES_MEDIANAS\' AND valores_nuevos.grupo_manejo == \'ESPECIES_GRANDES\'',
        obtenidoOk: 'Transición de grupo_manejo auditada correctamente'
    },
    {
        paso: 'NW-09',
        regex: /NW-09: Subcaso 4 Desactivación de especie/,
        esperado: 'HTTP 200 OK con es_activo=false',
        obtenidoOk: 'HTTP 200 recibido; especie desactivada con es_activo=false'
    },
    {
        paso: 'NW-10',
        esBD: true,
        esperado: 'tipo_operacion=\'DEACTIVATE\', valores_anteriores.es_activo=true, valores_nuevos.es_activo=false',
        obtenidoOk: 'Auditoría DEACTIVATE confirmada: es_activo=true -> es_activo=false'
    },
    {
        paso: 'NW-11',
        regex: /NW-11: Subcaso 5 Reactivación de especie/,
        esperado: 'HTTP 200 OK con es_activo=true',
        obtenidoOk: 'HTTP 200 recibido; especie reactivada con es_activo=true'
    },
    {
        paso: 'NW-12',
        esBD: true,
        esperado: 'tipo_operacion=\'UPDATE\', valores_anteriores.es_activo=false, valores_nuevos.es_activo=true',
        obtenidoOk: 'Auditoría de reactivación confirmada: UPDATE con es_activo=false -> es_activo=true'
    },
    {
        paso: 'NW-13',
        regex: /NW-13: Teardown Desactivación final de especie para limpieza/,
        esperado: 'HTTP 200 OK; especie desactivada en teardown dejando es_activo=false',
        obtenidoOk: 'HTTP 200 recibido; especie desactivada exitosamente en teardown'
    },
    {
        paso: 'NW-14',
        esSeguridad: true,
        esperado: 'Cero fugas de credenciales, contraseñas o tokens JWT en resultados/ y evidencias/',
        obtenidoOk: 'Auditoría superada: cero secretos expuestos en evidencias y reportes'
    },
    {
        paso: 'NW-15',
        esBD: true,
        esperado: 'Especie creada con es_activo=false y cero especies residuales activas de prueba',
        obtenidoOk: 'Integridad final en BD confirmada: especie inactiva y cero residuales activos'
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
    console.log('[CONSOLIDADOR] Ejecutando auditoría de seguridad (NW-14)...');
    const res = spawnSync('node', [AUDITORIA_SCRIPT], { encoding: 'utf8' });
    const salida = (res.stdout || '') + '\n' + (res.stderr || '');

    const evidenciasDir = path.join(BASE_DIR, 'evidencias');
    if (!fs.existsSync(evidenciasDir)) fs.mkdirSync(evidenciasDir, { recursive: true });
    fs.writeFileSync(path.join(evidenciasDir, 'auditoria_fuga.txt'), salida, 'utf8');

    const def = DEFINICION_CHECKPOINTS.find(c => c.paso === 'NW-14');
    return {
        paso: 'NW-14',
        esperado: def.esperado,
        obtenido: res.status === 0 ? def.obtenidoOk : `Falla en auditoría: ${salida.trim()}`,
        estado: res.status === 0 ? 'OK' : 'FALLA'
    };
}

function ejecutarVerificacionBD() {
    console.log('[CONSOLIDADOR] Ejecutando verificación de base de datos...');
    const repoRoot = path.resolve(BASE_DIR, '../../../../..');
    const pythonVenv = path.join(repoRoot, '.venv', 'Scripts', 'python.exe');
    const pythonExe = fs.existsSync(pythonVenv) ? pythonVenv : 'python';

    const res = spawnSync(pythonExe, [VERIFICAR_BD_SCRIPT, '--modo', 'all'], { encoding: 'utf8' });
    const salida = (res.stdout || '') + '\n' + (res.stderr || '');

    const evidenciasDir = path.join(BASE_DIR, 'evidencias');
    if (!fs.existsSync(evidenciasDir)) fs.mkdirSync(evidenciasDir, { recursive: true });
    fs.writeFileSync(path.join(evidenciasDir, 'verificacion_bd_completa.txt'), salida, 'utf8');

    const resBDFile = path.join(evidenciasDir, 'resultados_bd.json');
    if (fs.existsSync(resBDFile)) {
        try {
            return JSON.parse(fs.readFileSync(resBDFile, 'utf8'));
        } catch (e) {
            console.error('[CONSOLIDADOR] Error leyendo resultados_bd.json:', e);
        }
    }
    return {};
}

function main() {
    console.log('[CONSOLIDADOR] Iniciando consolidación para TC-M09-G08-v2.0...');

    const textoNewman = extraerTextoNewman();
    const checkpointsProcesados = [];

    // 1. Procesar checkpoints Newman
    for (const chk of DEFINICION_CHECKPOINTS) {
        if (!chk.esBD && !chk.esSeguridad) {
            const res = evaluarCheckpointNewman(chk, textoNewman);
            if (res) {
                checkpointsProcesados.push(res);
            }
        }
    }

    // 2. Procesar scripts de BD
    const resultadosBD = ejecutarVerificacionBD();
    for (const chk of DEFINICION_CHECKPOINTS) {
        if (chk.esBD) {
            if (resultadosBD[chk.paso]) {
                checkpointsProcesados.push(resultadosBD[chk.paso]);
            } else {
                checkpointsProcesados.push({
                    paso: chk.paso,
                    esperado: chk.esperado,
                    obtenido: 'No se obtuvo resultado desde verificación en BD',
                    estado: 'FALLA'
                });
            }
        }
    }

    // 3. Procesar auditoría de seguridad
    const resSeg = ejecutarAuditoriaSeguridad();
    checkpointsProcesados.push(resSeg);

    // 4. Ordenar checkpoints según orden en DEFINICION_CHECKPOINTS
    const ordenMap = new Map();
    DEFINICION_CHECKPOINTS.forEach((c, idx) => ordenMap.set(c.paso, idx));
    checkpointsProcesados.sort((a, b) => (ordenMap.get(a.paso) ?? 999) - (ordenMap.get(b.paso) ?? 999));

    // 5. Validar que estén los 19 checkpoints exactos
    const pasosPresentes = new Set(checkpointsProcesados.map(c => c.paso));
    const faltantes = DEFINICION_CHECKPOINTS.map(c => c.paso).filter(p => !pasosPresentes.has(p));

    if (faltantes.length > 0) {
        console.error(`[CONSOLIDADOR] ERROR CRÍTICO: Faltan los siguientes checkpoints en la consolidación: ${faltantes.join(', ')}`);
        console.error('[CONSOLIDADOR] Abortando sin generar archivo de resultados JSON.');
        process.exit(1);
    }

    // 6. Construir objeto final
    const resultadoFinal = {
        tc: 'TC-M09-G08-v2.0',
        ambiente: 'TEST',
        fecha: new Date().toISOString(),
        checkpoints: checkpointsProcesados,
        checkpoints_no_contabilizados: []
    };

    // 7. Escribir archivo de resultados computable
    if (!fs.existsSync(RESULTADOS_DIR)) {
        fs.mkdirSync(RESULTADOS_DIR, { recursive: true });
    }
    fs.writeFileSync(JSON_OUT, JSON.stringify(resultadoFinal, null, 2), 'utf8');
    console.log(`[CONSOLIDADOR] ÉXITO: Reporte computable generado en ${JSON_OUT}`);
    console.log(`[CONSOLIDADOR] Total checkpoints procesados: ${checkpointsProcesados.length}/19`);

    const totalOk = checkpointsProcesados.filter(c => c.estado === 'OK').length;
    const totalFalla = checkpointsProcesados.filter(c => c.estado === 'FALLA').length;
    console.log(`[CONSOLIDADOR] Resumen: ${totalOk} OK, ${totalFalla} FALLA`);

    process.exit(0);
}

main();
