// TC-M03-G87 — Catálogo de casos y plan de datos del grupo.
// Fuente: Casos_Prueba(Modulo3 Agrupado).csv, fila TC-M03-G87 (RF-58, CU04).
//
// Cada aserción tiene un id estable. Newman y Cypress nombran sus pruebas con el
// prefijo `[CASO][PRE|ASSERT|INFO][ID]` y el runner las agrega por id:
//   PRE    = precondición de datos: si falla, el caso queda BLOQUEADO (no RECHAZADO).
//   ASSERT = criterio esperado de la matriz: si falla, el caso queda RECHAZADO.
//   INFO   = comprobación complementaria: se informa, no decide el veredicto.

export const GRUPO = Object.freeze({
  id: 'TC-M03-G87',
  corto: 'G87',
  modulo: 'M03',
  rf: 'RF-58',
  rfNombre: 'RF-58 — Monitoreo Ambiental en Tiempo Real',
  cu: 'CU04',
  cuNombre: 'CU04 — Monitorear variables (modo tiempo real)',
  titulo:
    'Uso de la última lectura válida como referencia operativa ante datos anómalos ' +
    '(FUERA_DE_RANGO, ERROR_CALIBRACION) y diferenciación por rol',
  objetivo:
    'Verificar que una lectura no válida (FUERA_DE_RANGO o ERROR_CALIBRACION) nunca reemplaza a la última ' +
    'lectura operativa válida en el dashboard de monitoreo, que la anomalía permanece visible y que la ' +
    'presentación de ERROR_CALIBRACION se diferencia entre Productor e Ingeniero de Campo.',
  tipo: 'Funcional / Validación',
  herramientas: 'Postman/Newman (API) + Cypress (UI)',
  endpoint: 'GET /iot/monitoreo/dashboard',
  responsable: 'Juan Esteban',
  prioridad: 'Alta',
  fuenteMatriz: 'Casos_Prueba(Modulo3 Agrupado).csv — fila TC-M03-G87',
  // «IDs originales agrupados» de la matriz: el catálogo debe cubrirlos exactamente.
  casosMatriz: ['TC-M03-168', 'TC-M03-177', 'TC-M03-178'],
});

export const ARCHIVOS_AUTOMATIZACION = Object.freeze([
  'g87_casos.mjs',
  'g87_lib.mjs',
  'ejecutar_tc_m03_g87.mjs',
  'TC-M03-G87.postman_collection.json',
  'tc_m03_g87.cy.js',
  'validar_local_g87.mjs',
  'cypress_seguro.mjs',
  'cypress.g87.config.cjs',
]);

export const CASOS = Object.freeze([
  {
    id: 'TC-M03-168',
    titulo:
      'Visualizar la última lectura válida de cada sensor activo, ignorando una lectura posterior FUERA_DE_RANGO.',
    objetivo:
      'Comprobar que, tras tres lecturas LECTURA_VALIDA y una posterior FUERA_DE_RANGO, el dashboard devuelve ' +
      'ultimo_valor, ultima_unidad y ultimo_timestamp_captura de la última lectura válida.',
    actor: 'Productor Agropecuario',
    criterios: 'CA-1 (RF-58); Restricción 2',
    valoresLimite: 'Solo lecturas con estado LECTURA_VALIDA; valor, unidad y timestamp no nulos.',
    datos: 'Sensor con tres lecturas válidas y una posterior con estado FUERA_DE_RANGO.',
    esperado:
      'HTTP 200. Por cada sensor se devuelven ultimo_valor, ultima_unidad y ultimo_timestamp_captura ' +
      'correspondientes a la última lectura LECTURA_VALIDA, no a la posterior inválida.',
    aserciones: [
      { id: 'PRE-168-01', tipo: 'PRE', fuente: 'API', desc: 'Las tres lecturas del sensor A son aceptadas (201) como LECTURA_VALIDA' },
      { id: 'PRE-168-02', tipo: 'PRE', fuente: 'API', desc: 'La lectura posterior del sensor A queda clasificada FUERA_DE_RANGO por RF-53' },
      { id: 'PRE-168-03', tipo: 'PRE', fuente: 'API', desc: 'La sesión del Productor está vigente al consultar (no 401)' },
      { id: 'API-168-01', tipo: 'ASSERT', fuente: 'API', desc: 'GET /iot/monitoreo/dashboard (Productor) responde HTTP 200' },
      { id: 'API-168-02', tipo: 'ASSERT', fuente: 'API', desc: 'El sensor A aparece en el dashboard' },
      { id: 'API-168-03', tipo: 'ASSERT', fuente: 'API', desc: 'ultimo_valor = valor de la tercera lectura válida' },
      { id: 'API-168-04', tipo: 'ASSERT', fuente: 'API', desc: 'ultima_unidad = unidad de la última lectura válida' },
      { id: 'API-168-05', tipo: 'ASSERT', fuente: 'API', desc: 'ultimo_timestamp_captura = timestamp de la última lectura válida' },
      { id: 'API-168-06', tipo: 'ASSERT', fuente: 'API', desc: 'El valor y el timestamp devueltos no son los de la lectura FUERA_DE_RANGO' },
    ],
  },
  {
    id: 'TC-M03-177',
    titulo:
      'No utilizar una lectura FUERA_DE_RANGO como valor operativo del Productor, manteniendo visible la anomalía.',
    objetivo:
      'Comprobar que la lectura FUERA_DE_RANGO no reemplaza la lectura válida conocida (25) como dato operativo ' +
      'del Productor y que la anomalía permanece visible con un indicador claro.',
    actor: 'Productor Agropecuario',
    criterios: 'CA-6 (RF-58); CU04 FA-06; Restricción 2',
    valoresLimite: 'Una lectura con estado_dato = FUERA_DE_RANGO posterior a una lectura LECTURA_VALIDA.',
    datos: 'Sensor con lectura válida conocida (valor 25) seguida de lectura FUERA_DE_RANGO; consulta con Productor autorizado.',
    esperado:
      'La lectura FUERA_DE_RANGO no se utiliza como lectura operativa activa; el dashboard conserva la última ' +
      'LECTURA_VALIDA como referencia y la anomalía permanece visible mediante un indicador claro (ROJO/ícono), ' +
      'sin ocultarse ni descartarse.',
    aserciones: [
      { id: 'PRE-177-01', tipo: 'PRE', fuente: 'API', desc: 'La lectura de valor 25 del sensor B es aceptada como LECTURA_VALIDA' },
      { id: 'PRE-177-02', tipo: 'PRE', fuente: 'API', desc: 'La lectura posterior del sensor B queda clasificada FUERA_DE_RANGO por RF-53' },
      { id: 'PRE-177-03', tipo: 'PRE', fuente: 'API', desc: 'La sesión del Productor está vigente al consultar (no 401)' },
      { id: 'API-177-01', tipo: 'ASSERT', fuente: 'API', desc: 'Dashboard del Productor HTTP 200 y el sensor B no se oculta' },
      { id: 'API-177-02', tipo: 'ASSERT', fuente: 'API', desc: 'ultimo_valor del sensor B = 25 (la lectura anómala no es operativa)' },
      { id: 'API-177-03', tipo: 'ASSERT', fuente: 'API', desc: 'La anomalía es visible en el payload (estado_calidad FUERA_DE_RANGO o semáforo ROJO)' },
      { id: 'PRE-UI-01', tipo: 'PRE', fuente: 'UI', desc: 'La UI recibe el dashboard real desde el sandbox (HTTP 200, X-Test-Run-Id devuelto, sin caché)' },
      { id: 'UI-177-01', tipo: 'ASSERT', fuente: 'UI', desc: 'Monitoreo del Productor muestra la tarjeta del sensor B' },
      { id: 'UI-177-02', tipo: 'ASSERT', fuente: 'UI', desc: 'La tarjeta del sensor B muestra 25 y no el valor anómalo' },
      { id: 'UI-177-03', tipo: 'ASSERT', fuente: 'UI', desc: 'La tarjeta del sensor B señala visualmente la anomalía (ROJO / ícono)' },
    ],
  },
  {
    id: 'TC-M03-178',
    titulo:
      'Diferenciar la presentación de un sensor con ERROR_CALIBRACION entre Productor e Ingeniero de Campo.',
    objetivo:
      'Comprobar que una lectura ERROR_CALIBRACION no se presenta como lectura operativa ni genera alerta operativa ' +
      'al Productor (sin información técnica), y que el Ingeniero de Campo identifica el error técnico con el detalle ' +
      'necesario, permaneciendo visible el sensor.',
    actor: 'Productor Agropecuario e Ingeniero de Campo',
    criterios: 'CA-6, CA-8 (RF-58); flujo alterno E2; Restricción 2',
    valoresLimite: 'Sensor cuyas lecturas recientes presentan estado_dato = ERROR_CALIBRACION.',
    datos:
      'Sensor autorizado con lecturas recientes en ERROR_CALIBRACION; se consulta el mismo sensor con un usuario ' +
      'Productor y luego con un Ingeniero de Campo.',
    esperado:
      'Productor: ERROR_CALIBRACION no se presenta como lectura operativa ni genera alerta operativa, sin exponer ' +
      'información técnica reservada al Ingeniero. Ingeniero de Campo: identifica el sensor con condición de error ' +
      'técnico y visualiza el detalle necesario para reconocer que requiere calibración. El sensor permanece visible y ' +
      'la lectura inválida no se trata como operacional normal.',
    aserciones: [
      { id: 'PRE-178-01', tipo: 'PRE', fuente: 'API', desc: 'Las lecturas del sensor C (sin calibración) quedan clasificadas ERROR_CALIBRACION' },
      { id: 'PRE-178-02', tipo: 'PRE', fuente: 'API', desc: 'La sesión del Productor está vigente al consultar (no 401)' },
      { id: 'PRE-178-03', tipo: 'PRE', fuente: 'API', desc: 'La sesión del Ingeniero de Campo está vigente al consultar (no 401)' },
      { id: 'API-178-01', tipo: 'ASSERT', fuente: 'API', desc: 'Productor: dashboard HTTP 200 y el sensor C permanece visible' },
      { id: 'API-178-02', tipo: 'ASSERT', fuente: 'API', desc: 'Productor: el valor ERROR_CALIBRACION no se presenta como lectura operativa' },
      { id: 'API-178-03', tipo: 'ASSERT', fuente: 'API', desc: 'Productor: el sensor C no presenta alerta operativa asociada' },
      { id: 'API-178-04', tipo: 'ASSERT', fuente: 'API', desc: 'Productor: no recibe información técnica (batería, RSSI, SNR)' },
      { id: 'API-178-05', tipo: 'ASSERT', fuente: 'API', desc: 'Ingeniero: dashboard HTTP 200 y el sensor C permanece visible' },
      { id: 'API-178-06', tipo: 'ASSERT', fuente: 'API', desc: 'Ingeniero: la condición de error técnico (ERROR_CALIBRACION) es identificable' },
      { id: 'API-178-07', tipo: 'ASSERT', fuente: 'API', desc: 'Ingeniero: recibe el detalle técnico del dispositivo' },
      { id: 'API-178-08', tipo: 'ASSERT', fuente: 'API', desc: 'Ingeniero: la lectura inválida no se presenta como operacional normal' },
      { id: 'INF-178-01', tipo: 'INFO', fuente: 'API', desc: 'Complementaria: RF-57 no registra alertas ACTIVA del sensor C (consulta del Ingeniero)' },
      { id: 'PRE-UI-01', tipo: 'PRE', fuente: 'UI', desc: 'La UI recibe el dashboard real desde el sandbox (HTTP 200, X-Test-Run-Id devuelto, sin caché)' },
      { id: 'UI-178-01', tipo: 'ASSERT', fuente: 'UI', desc: 'Productor: la tarjeta del sensor C es visible' },
      { id: 'UI-178-02', tipo: 'ASSERT', fuente: 'UI', desc: 'Productor: la tarjeta no muestra el valor inválido como lectura operativa' },
      { id: 'UI-178-03', tipo: 'ASSERT', fuente: 'UI', desc: 'Productor: la tarjeta no muestra datos técnicos (batería %, dBm)' },
      { id: 'UI-178-04', tipo: 'ASSERT', fuente: 'UI', desc: 'Ingeniero: la tarjeta del sensor C es visible' },
      { id: 'UI-178-05', tipo: 'ASSERT', fuente: 'UI', desc: 'Ingeniero: el detalle del sensor muestra la condición ERROR_CALIBRACION / requiere calibración' },
    ],
  },
]);

// ---------------------------------------------------------------------------
// Plan de datos: lo que el runner descubre y prepara por API oficial.
// ---------------------------------------------------------------------------

const VARIABLE_TEMPERATURA = 9; // TEMPERATURA_AMBIENTAL en el catálogo I3P-1
const r1 = (x) => Math.round(x * 10) / 10;

export const PLAN = Object.freeze({
  // Cuentas que inician sesión (setup = QA_SETUP_EMAIL, prod = QA_PROD_EMAIL, eng = QA_ENG_EMAIL).
  actores: ['setup', 'prod', 'eng'],
  // Actores que deben tener alcance sobre el área del RUN, y casos que se bloquean si no lo tienen.
  alcance: { prod: ['TC-M03-168', 'TC-M03-177', 'TC-M03-178'], eng: ['TC-M03-178'] },
  // Contrato mínimo que TEST debe publicar (OpenAPI) antes de preparar datos.
  rutasRequeridas: [
    '/iot/monitoreo/dashboard', '/iot/telemetria', '/iot/alertas', '/sesiones/', '/usuarios/me',
    '/configuracion/fincas', '/configuracion/infraestructuras', '/configuracion/infraestructuras/{id_infraestructura}',
    '/configuracion/dispositivos-iot', '/configuracion/dispositivos-iot/{id_dispositivo_iot}', '/configuracion/dispositivos-iot/{id_dispositivo_iot}/sensores',
    '/configuracion/sensores/{id_sensor}/asociar', '/configuracion/sensores/{id_sensor}/calibrar',
    '/configuracion/sensores/{id_sensor}/calibraciones', '/configuracion/sensores/rangos-calibracion',
    '/configuracion/variables-ambientales', '/configuracion/especies', '/configuracion/umbrales',
    '/test-control/runs/{run_id}',
  ],
  variables: [VARIABLE_TEMPERATURA],
  sensores: [
    { clave: 'A', categoria: 'TEMPERATURA', calibrar: true },
    { clave: 'B', categoria: 'TEMPERATURA', calibrar: true },
    // C sin calibración: todas sus lecturas deben quedar ERROR_CALIBRACION (no se le envían lecturas válidas).
    { clave: 'C', categoria: 'TEMPERATURA', calibrar: false },
  ],
  activo: false,

  // Rango operativo de la variable (RF-53 CA-5 / Fase 5: «rango biológico según I3P-1»; RF-58
  // precondición 4: rangos configurados en RF-17). La ejecución exige un umbral
  // RF-17 existente y verificable por API; la referencia solo alimenta pruebas locales.
  rangoOperativo: {
    variable: VARIABLE_TEMPERATURA,
    unidad: '°C',
    referencia: { min: 20, max: 30, fuente: 'RF-53 Fase 5, ejemplo I3P-1 «Temperatura ambiental: 20–30 °C»' },
    // Valor fijo de la matriz (TC-M03-177): el rango operativo usado debe contenerlo.
    debeContener: [25],
  },

  casosUI: ['TC-M03-177', 'TC-M03-178'],

  // Efectos que el rollback del sandbox NO revierte. El ejecutor se detiene antes de iniciar
  // sesión salvo que QA los acepte expresamente con --aceptar-efectos <id>.
  efectosPersistentes: [
    {
      id: 'notificacion-login',
      descripcion:
        'cada login exitoso agenda en segundo plano (sesion_sistema, fuera del sandbox) una notificación ' +
        'TIPO_LOGIN_EXITOSO que se persiste y puede despachar correo/FCM a la cuenta QA; el RUN hace hasta 6 logins ' +
        '(1 observador externo, 3 del ejecutor y 2 de la UI)',
    },
    {
      id: 'sesion-observador',
      descripcion: 'el observador inicia y cierra una sesión fuera del sandbox; el historial de sesión y auditoría puede persistir',
    },
  ],
  efectosExternos:
    'Dispositivo sin gateway (sin sincronización MQTT). Se usa un umbral RF-17 existente; G87 no crea umbrales. ' +
    'Lecturas por ingesta HTTP dentro del sandbox. No revertibles: notificaciones de login y actividad de sesión del observador ' +
    '(efectos aceptados expresamente en la ejecución).',

  /**
   * Valores del escenario a partir del rango físico (catálogo) y del rango operativo resuelto.
   * Distingue: físicamente imposible (fuera del rango físico, ERROR_SENSOR: no se envía),
   * físicamente válido pero fuera del rango operativo (FUERA_DE_RANGO esperado) y válido.
   */
  derivar(ctx) {
    const v = ctx.variables[VARIABLE_TEMPERATURA];
    const fisMin = Number(v.valor_fisico_min);
    const fisMax = Number(v.valor_fisico_max);
    const { min, max } = ctx.rangoOperativo;
    const bloqueos = [];
    if (!(fisMin <= min && min < max && max <= fisMax)) {
      bloqueos.push(`Rango operativo [${min}, ${max}] incoherente con el rango físico [${fisMin}, ${fisMax}].`);
    }
    // Primero por encima del máximo operativo; si no hay margen, por debajo del mínimo.
    let fuera = r1(max + (fisMax - max) / 2);
    if (!(fuera > max && fuera < fisMax)) fuera = r1(min - (min - fisMin) / 2);
    if (!(fuera >= fisMin && fuera <= fisMax && (fuera > max || fuera < min))) {
      bloqueos.push(`No existe un valor físicamente válido fuera del rango operativo [${min}, ${max}] dentro de [${fisMin}, ${fisMax}].`);
    }
    const c = (min + max) / 2;
    const validos = { a1: r1(c - 0.9), a2: r1(c - 0.4), a3: r1(c + 0.2), b: 25, c1: r1(c - 1.6), c2: r1(c - 1.1) };
    for (const [k, x] of Object.entries(validos)) {
      if (!(x >= min && x <= max)) bloqueos.push(`El valor ${k}=${x} queda fuera del rango operativo [${min}, ${max}].`);
    }
    return {
      bloqueos,
      valores: { valor_fuera: fuera, validos, fisico_min: fisMin, fisico_max: fisMax },
    };
  },

  entornoNewman(ctx) {
    const d = ctx.derivados;
    return {
      tipo_variable: 'TEMPERATURA_AMBIENTAL',
      unidad: '°C',
      valor_fuera: String(d.valor_fuera),
      valor_a1: String(d.validos.a1),
      valor_a2: String(d.validos.a2),
      valor_a3: String(d.validos.a3),
      valor_b: String(d.validos.b),
      valor_c1: String(d.validos.c1),
      valor_c2: String(d.validos.c2),
    };
  },

  entornoCypress(ctx) {
    const d = ctx.derivados;
    return { UNIDAD: '°C', VALOR_B: d.validos.b, VALOR_FUERA: d.valor_fuera, VALORES_C: [d.validos.c1, d.validos.c2] };
  },

  // Hipótesis del análisis estático previo (origin/test bd952649). Contexto del informe; NO son
  // defectos confirmados en TEST y no modifican los resultados esperados.
  riesgos: [
    'RF-53 (`ingerir_telemetria_use_case._evaluar_rango`) tiene pendiente (TODO) la clasificación FUERA_DE_RANGO: un valor fuera del rango físico se rechaza como ERROR_SENSOR y uno dentro se persiste como LECTURA_VALIDA o ERROR_CALIBRACION. Lo confirma o descarta PRE-168-02 / PRE-177-02.',
    'El trigger `fn_actualizar_estado_sensor` solo alimenta `estados_actuales_sensores` con LECTURA_VALIDA y el dashboard lee únicamente esa tabla: un sensor con solo ERROR_CALIBRACION podría no aparecer. Lo confirma o descarta API-178-01 / API-178-05.',
    'ERROR_CALIBRACION se produce cuando el sensor no tiene calibración registrada (`calibracion_m09_adapter`); las calibraciones no vencen.',
  ],
});
