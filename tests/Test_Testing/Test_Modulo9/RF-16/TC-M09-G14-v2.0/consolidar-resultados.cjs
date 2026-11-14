/**
 * Consolidador de resultados oficial para TC-M09-G14-v2.0.
 *
 * Lee la salida de Newman (consola/HTML), ejecuta auditoría de seguridad y verificación en BD,
 * valida los 20 checkpoints requeridos (NW-01 a NW-20),
 * aborta sin escribir si falta cualquiera, y genera 'resultados/resultado_TC-M09-G14-v2.0.json'.
 */
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const BASE_DIR = __dirname;
const RESULTADOS_DIR = path.join(BASE_DIR, 'resultados');
const EVIDENCIAS_DIR = path.join(BASE_DIR, 'evidencias');

const HTML_FILE = path.join(RESULTADOS_DIR, 'resultado_TC-M09-G14-v2.0.html');
const CONSOLA_FILE = path.join(EVIDENCIAS_DIR, 'consola_TC-M09-G14-v2.0.txt');
const AUDITORIA_SCRIPT = path.join(BASE_DIR, 'auditoria-seguridad.cjs');
const VERIFICAR_BD_SCRIPT = path.join(BASE_DIR, 'verificar-bd.py');
const JSON_OUT = path.join(RESULTADOS_DIR, 'resultado_TC-M09-G14-v2.0.json');

// Definición estricta de los 20 checkpoints requeridos
const DEFINICION_CHECKPOINTS = [
    {
        paso: 'NW-01',
        esperado: 'HTTP 200 OK con token JWT administrativo emitido',
        obtenidoOk: 'HTTP 200 recibido con token JWT emitido'
    },
    {
        paso: 'NW-02',
        esPreflightAgrupado: true,
        esperado: 'HTTP 200 OK en health (NW-02a) y catálogo verificado con 7 nombres libres asignados (NW-02b)',
        obtenidoOk: 'HTTP 200 recibido; backend activo y 7 nombres libres seleccionados en preflight'
    },
    {
        paso: 'NW-03',
        esperado: 'HTTP 400 VAL_ENTRADA por unidad_medida vacía',
        obtenidoOk: 'HTTP 400 VAL_ENTRADA recibido; campo unidad_medida validado'
    },
    {
        paso: 'NW-04',
        esperado: 'HTTP 400 VAL_ENTRADA por tipo_medicion no perteneciente al catálogo',
        obtenidoOk: 'HTTP 400 VAL_ENTRADA recibido; tipo_medicion validado'
    },
    {
        paso: 'NW-05',
        esperado: 'HTTP 422 UNIDAD_MEDIDA_INCOHERENTE por combinación PESO con litros',
        obtenidoOk: 'HTTP 422 UNIDAD_MEDIDA_INCOHERENTE recibido; regla de negocio validada'
    },
    {
        paso: 'NW-06',
        esperado: 'HTTP 400 VAL_ENTRADA por aplica_a_tipo_activo no perteneciente al enum',
        obtenidoOk: 'HTTP 400 VAL_ENTRADA recibido; aplica_a_tipo_activo validado'
    },
    {
        paso: 'NW-07',
        esperado: 'HTTP 400 VAL_ENTRADA por nombre menor a 3 caracteres',
        obtenidoOk: 'HTTP 400 VAL_ENTRADA recibido; límite inferior validado'
    },
    {
        paso: 'NW-08',
        esperado: 'HTTP 400 VAL_ENTRADA por nombre mayor a 60 caracteres',
        obtenidoOk: 'HTTP 400 VAL_ENTRADA recibido; límite superior validado'
    },
    {
        paso: 'NW-09',
        esperado: 'HTTP 201 Created para nombre en límite inferior (3 caracteres)',
        obtenidoOk: 'HTTP 201 recibido; métrica de 3 caracteres creada'
    },
    {
        paso: 'NW-10',
        esperado: 'HTTP 201 Created para nombre en límite superior (60 caracteres)',
        obtenidoOk: 'HTTP 201 recibido; métrica de 60 caracteres creada'
    },
    {
        paso: 'NW-11',
        esperado: 'HTTP 400 VAL_ENTRADA por nombre vacío (0 caracteres)',
        obtenidoOk: 'HTTP 400 VAL_ENTRADA recibido; campo obligatorio validado'
    },
    {
        paso: 'NW-12',
        esperado: 'HTTP 201 Created para métrica base de prueba de duplicado',
        obtenidoOk: 'HTTP 201 recibido; métrica base creada'
    },
    {
        paso: 'NW-13',
        esperado: 'HTTP 409 METRICA_DUPLICADA al intentar registrar nombre existente con diferente casing',
        obtenidoOk: 'HTTP 409 METRICA_DUPLICADA recibido; unicidad case-insensitive confirmada'
    },
    {
        paso: 'NW-14',
        esperado: 'HTTP 201 Created para combinación coherente PESO / kg',
        obtenidoOk: 'HTTP 201 recibido; métrica creada exitosamente'
    },
    {
        paso: 'NW-15',
        esperado: 'HTTP 201 Created para combinación coherente VOLUMEN / ml',
        obtenidoOk: 'HTTP 201 recibido; métrica creada exitosamente'
    },
    {
        paso: 'NW-16',
        esperado: 'HTTP 201 Created para combinación coherente LONGITUD / cm',
        obtenidoOk: 'HTTP 201 recibido; métrica creada exitosamente'
    },
    {
        paso: 'NW-17',
        esperado: 'HTTP 201 Created para combinación coherente CONTEO / unidades',
        obtenidoOk: 'HTTP 201 recibido; métrica creada exitosamente'
    },
    {
        paso: 'NW-18',
        esTeardownAgrupado: true,
        esperado: 'HTTP 200 OK y es_activo=false en los 7 PATCH de desactivación (NW-18a a NW-18g)',
        obtenidoOk: 'Las 7 métricas creadas fueron desactivadas exitosamente (HTTP 200)'
    },
    {
        paso: 'NW-19',
        esSeguridad: true,
        esperado: '0 secretos expuestos en resultados/ y evidencias/',
        obtenidoOk: 'Auditoría de seguridad limpia: 0 tokens JWT ni contraseñas expuestas'
    },
    {
        paso: 'NW-20',
        esBD: true,
        esperado: 'Las 7 métricas en es_activo=false y registros CREATE/DEACTIVATE auditados en ventana cerrada con id_usuario=104',
        obtenidoOk: 'Integridad confirmada en BD: 0 residuales activos y auditorías CREATE/DEACTIVATE verificadas en ventana cerrada'
    }
];

function extraerPruebasDeNewman() {
    let contenido = '';
    if (fs.existsSync(CONSOLA_FILE)) {
        contenido += fs.readFileSync(CONSOLA_FILE, 'utf8') + '\n';
    }
    if (fs.existsSync(HTML_FILE)) {
        contenido += fs.readFileSync(HTML_FILE, 'utf8') + '\n';
    }

    const mapa = {};

    // Extraer y respaldar evidencias/nombres_corrida.json si se encuentra en la salida
    const mNombres = contenido.match(/NOMBRES_CORRIDA_JSON=(\{.*?\})/);
    if (mNombres) {
        try {
            const nombresData = JSON.parse(mNombres[1]);
            const nombresFile = path.join(EVIDENCIAS_DIR, 'nombres_corrida.json');
            fs.mkdirSync(EVIDENCIAS_DIR, { recursive: true });
            fs.writeFileSync(nombresFile, JSON.stringify(nombresData, null, 2), 'utf8');
        } catch (_) {}
    }

    // NW-02: Preflight consolidado (NW-02a y NW-02b)
    const preflightItems = ['NW-02a', 'NW-02b'];
    const preflightFallidos = [];
    const preflightExitosos = [];

    for (const pf of preflightItems) {
        const rePass = new RegExp('[√✓]\\s*' + pf + '[:\\s]', 'i');
        const reFail = new RegExp('AssertionError\\s+' + pf + '[:\\s]', 'i');

        if (reFail.test(contenido)) {
            preflightFallidos.push(pf);
        } else if (rePass.test(contenido)) {
            preflightExitosos.push(pf);
        } else {
            preflightFallidos.push(pf);
        }
    }

    if (preflightFallidos.length === 0 && preflightExitosos.length === 2) {
        mapa['NW-02'] = {
            estado: 'OK',
            obtenido: 'HTTP 200 recibido; backend activo y 7 nombres libres seleccionados en preflight'
        };
    } else {
        mapa['NW-02'] = {
            estado: 'FALLA',
            obtenido: `Falló el preflight en: ${preflightFallidos.join(', ')} (exitosos: ${preflightExitosos.length}/2)`
        };
    }

    // NW-01 y NW-03 a NW-17
    for (const def of DEFINICION_CHECKPOINTS) {
        if (def.esBD || def.esSeguridad || def.esTeardownAgrupado || def.esPreflightAgrupado) continue;

        const rePass = new RegExp('[√✓]\\s*' + def.paso + '[:\\s]', 'i');
        const reFail = new RegExp('AssertionError\\s+' + def.paso + '[:\\s]', 'i');

        if (reFail.test(contenido)) {
            const mDetail = contenido.match(new RegExp('AssertionError\\s+' + def.paso + '[^\r\n]*[\r\n]+\\s*([^\r\n]+)', 'i'));
            mapa[def.paso] = {
                estado: 'FALLA',
                obtenido: mDetail ? `Fallo en Newman: ${mDetail[1].trim()}` : 'AssertionError en Newman'
            };
        } else if (rePass.test(contenido)) {
            mapa[def.paso] = {
                estado: 'OK',
                obtenido: def.obtenidoOk
            };
        } else {
            mapa[def.paso] = {
                estado: 'FALLA',
                obtenido: 'No ejecutado o no encontrado en salida Newman'
            };
        }
    }

    // NW-18: Teardown consolidado de los 7 items (NW-18a a NW-18g)
    const teardownItems = ['NW-18a', 'NW-18b', 'NW-18c', 'NW-18d', 'NW-18e', 'NW-18f', 'NW-18g'];
    const teardownFallidos = [];
    const teardownExitosos = [];

    for (const td of teardownItems) {
        const rePass = new RegExp('[√✓]\\s*' + td + '[:\\s]', 'i');
        const reFail = new RegExp('AssertionError\\s+' + td + '[:\\s]', 'i');

        if (reFail.test(contenido)) {
            teardownFallidos.push(td);
        } else if (rePass.test(contenido)) {
            teardownExitosos.push(td);
        } else {
            teardownFallidos.push(td);
        }
    }

    if (teardownFallidos.length === 0 && teardownExitosos.length === 7) {
        mapa['NW-18'] = {
            estado: 'OK',
            obtenido: 'Las 7 métricas creadas fueron desactivadas exitosamente (HTTP 200)'
        };
    } else {
        mapa['NW-18'] = {
            estado: 'FALLA',
            obtenido: `Falló la desactivación en: ${teardownFallidos.join(', ')} (exitosas: ${teardownExitosos.length}/7)`
        };
    }

    return mapa;
}

function ejecutarAuditoriaSeguridad() {
    const res = spawnSync('node', [AUDITORIA_SCRIPT], { encoding: 'utf8', cwd: BASE_DIR });
    if (res.status === 0) {
        return {
            estado: 'OK',
            obtenido: 'Auditoría de seguridad limpia: 0 tokens JWT ni credenciales expuestas'
        };
    } else {
        return {
            estado: 'FALLA',
            obtenido: `Auditoría detectó secretos expuestos (código ${res.status}): ${res.stderr || res.stdout}`
        };
    }
}

function ejecutarVerificacionBD() {
    const pyExe = path.join(BASE_DIR, '../../../../../.venv/Scripts/python.exe');
    const exe = fs.existsSync(pyExe) ? pyExe : 'python';

    const res = spawnSync(exe, [VERIFICAR_BD_SCRIPT, '--json'], { encoding: 'utf8', cwd: BASE_DIR });
    if (res.status === 0) {
        try {
            const data = JSON.parse(res.stdout);
            return {
                estado: data.estado || 'OK',
                obtenido: data.motivo || 'Verificación de BD completada con éxito'
            };
        } catch (e) {
            return {
                estado: 'OK',
                obtenido: 'Integridad en BD y auditorías en ventana cerrada confirmadas'
            };
        }
    } else {
        let motivo = res.stderr || res.stdout || `Código de salida ${res.status}`;
        try {
            const data = JSON.parse(res.stdout);
            motivo = data.motivo || motivo;
        } catch (_) {}
        return {
            estado: 'FALLA',
            obtenido: `Verificación BD falló: ${motivo.trim()}`
        };
    }
}

function main() {
    console.log('=== CONSOLIDACIÓN DE RESULTADOS TC-M09-G14-v2.0 ===');

    const newmanMap = extraerPruebasDeNewman();
    const seguridadRes = ejecutarAuditoriaSeguridad();
    const bdRes = ejecutarVerificacionBD();

    const checkpoints = [];

    for (const def of DEFINICION_CHECKPOINTS) {
        let pasoData = null;
        if (def.esSeguridad) {
            pasoData = seguridadRes;
        } else if (def.esBD) {
            pasoData = bdRes;
        } else {
            pasoData = newmanMap[def.paso];
        }

        if (!pasoData) {
            console.error(`ERROR FATAL: Falta resultado para checkpoint requerido ${def.paso}.`);
            console.error('Aborta sin escribir el archivo JSON consolidado.');
            process.exit(1);
        }

        checkpoints.push({
            paso: def.paso,
            estado: pasoData.estado,
            esperado: def.esperado,
            obtenido: pasoData.obtenido
        });
    }

    if (checkpoints.length !== 20) {
        console.error(`ERROR FATAL: Se esperaban exactamente 20 checkpoints, encontrados ${checkpoints.length}.`);
        process.exit(1);
    }

    const consolidado = {
        tc: 'TC-M09-G14-v2.0',
        ambiente: 'TEST',
        fecha: new Date().toISOString(),
        checkpoints: checkpoints,
        checkpoints_no_contabilizados: []
    };

    fs.writeFileSync(JSON_OUT, JSON.stringify(consolidado, null, 2), 'utf8');
    console.log(`Consolidado generado exitosamente en: ${path.relative(BASE_DIR, JSON_OUT)}`);
    console.log(`Total checkpoints: ${checkpoints.length} (OK: ${checkpoints.filter(c => c.estado === 'OK').length}, FALLA: ${checkpoints.filter(c => c.estado === 'FALLA').length})`);
}

main();
