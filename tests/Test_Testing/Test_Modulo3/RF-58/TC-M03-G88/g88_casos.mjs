// TC-M03-G88 — Catálogo de casos y plan de datos del grupo.
// Fuente: Casos_Prueba(Modulo3 Agrupado).csv, fila TC-M03-G88 (RF-58, CU04).
//
// Cada aserción tiene un id estable. Newman y Cypress nombran sus pruebas con el
// prefijo `[CASO][PRE|ASSERT|INFO][ID]` y el ejecutor las agrega por id:
//   PRE    = precondición: si falla, el caso queda BLOQUEADO (no RECHAZADO).
//   ASSERT = criterio esperado de la matriz: si falla con evidencia del producto, RECHAZADO.
//   INFO   = comprobación complementaria: se informa, no decide el veredicto.
//
// Representación de los umbrales de la matriz en M09 (RF-17). El contrato de RF-17 no
// tiene tolerancia T y exige tres niveles contiguos (normal, precaucion, critico) que
// cubran exactamente [valor_min, valor_max]. Cada umbral «mín–máx con T» se registra así:
//   zona de tolerancia inferior: precaucion [mín−T, mín] · normal [mín, máx] · critico [máx, máx+T]
//   zona de tolerancia superior: critico [mín−T, mín] · normal [mín, máx] · precaucion [máx, máx+T]
// Un mismo umbral no admite AMARILLO a ambos lados, por eso cada lado se evalúa con su
// propia configuración (la colección edita el umbral entre fases, siempre antes de las
// lecturas de esa fase). T por defecto = 10 % de (máx − mín), calculada por la automatización.

export const GRUPO = Object.freeze({
  id: 'TC-M03-G88',
  corto: 'G88',
  modulo: 'M03',
  rf: 'RF-58',
  rfNombre: 'RF-58 — Monitoreo Ambiental en Tiempo Real',
  cu: 'CU04',
  cuNombre: 'CU04 — Monitorear variables (modo tiempo real)',
  titulo:
    'Calcular el estado del semáforo según umbrales configurados en M09 (bordes, tolerancia, ausencia de umbral ' +
    'y reconfiguración dinámica)',
  objetivo:
    'Verificar que el estado del semáforo del dashboard se deriva de los umbrales configurados en M09: VERDE en los ' +
    'bordes inclusivos, AMARILLO dentro de la tolerancia T (por defecto o configurada), ROJO fuera de ella, GRIS con ' +
    '«Sin umbral configurado» cuando no hay umbral, y recálculo tras reconfigurar el umbral sin cambios de código.',
  tipo: 'Valores límite / Funcional / Validación / Configuración',
  herramientas: 'Postman/Newman (API) + Cypress (UI de TC-M03-180)',
  endpoint: 'GET /iot/monitoreo/dashboard',
  responsable: 'Juan Esteban',
  prioridad: 'Alta',
  fuenteMatriz: 'Casos_Prueba(Modulo3 Agrupado).csv — fila TC-M03-G88',
  casosMatriz: ['TC-M03-169', 'TC-M03-170', 'TC-M03-171', 'TC-M03-172', 'TC-M03-180', 'TC-M03-266'],
});

export const ARCHIVOS_AUTOMATIZACION = Object.freeze([
  'g88_casos.mjs',
  'g88_lib.mjs',
  'ejecutar_tc_m03_g88.mjs',
  'TC-M03-G88.postman_collection.json',
  'tc_m03_g88.cy.js',
  'validar_local_g88.mjs',
  'cypress_seguro.mjs',
  'cypress.g88.config.cjs',
]);

const sesion = (caso, n) => ({ id: `PRE-${caso}-${n}`, tipo: 'PRE', fuente: 'API', desc: 'La sesión del Productor está vigente al consultar el dashboard (no 401)' });
const lecturas = (caso, n, valores) => ({ id: `PRE-${caso}-${n}`, tipo: 'PRE', fuente: 'API', desc: `Lecturas ${valores} aceptadas (201) como LECTURA_VALIDA` });
const vinculadas = (caso, n) => ({ id: `PRE-${caso}-${n}`, tipo: 'PRE', fuente: 'API', desc: 'Lecturas VINCULADAS al único activo del área (RF-61), condición para clasificarlas con el umbral de la especie' });

export const CASOS = Object.freeze([
  {
    id: 'TC-M03-169',
    titulo: 'Verificar VERDE en los bordes inclusivos del rango óptimo.',
    objetivo: 'Con umbral 35–39, las lecturas 35, 37 y 39 se presentan con estado_semaforo VERDE.',
    actor: 'Productor Agropecuario',
    criterios: 'CA-2 (RF-58); Fase 3: VERDE si valor ∈ [umbral_min, umbral_max]',
    valoresLimite: 'valor = umbral_min y valor = umbral_max, ambos inclusivos, devuelven VERDE.',
    datos: 'Umbral 35-39. Lecturas con valor 35, 37 y 39.',
    esperado: 'HTTP 200. estado_semaforo="VERDE" en los tres casos.',
    aserciones: [
      { id: 'PRE-169-01', tipo: 'PRE', fuente: 'API', desc: 'Umbral 35–39 (T por defecto 0,4) registrado en M09 para la especie y TEMPERATURA_AMBIENTAL' },
      lecturas('169', '02', '35, 37 y 39'),
      vinculadas('169', '03'),
      sesion('169', '04'),
      { id: 'API-169-01', tipo: 'ASSERT', fuente: 'API', desc: 'Dashboard HTTP 200 con los tres sensores' },
      { id: 'API-169-02', tipo: 'ASSERT', fuente: 'API', desc: 'Valor 35 (borde inferior) → estado_semaforo VERDE' },
      { id: 'API-169-03', tipo: 'ASSERT', fuente: 'API', desc: 'Valor 37 → estado_semaforo VERDE' },
      { id: 'API-169-04', tipo: 'ASSERT', fuente: 'API', desc: 'Valor 39 (borde superior) → estado_semaforo VERDE' },
    ],
  },
  {
    id: 'TC-M03-170',
    titulo: 'Verificar AMARILLO dentro de la tolerancia T (10% del rango por defecto).',
    objetivo: 'Con umbral 20–30 y T = 1 (10 % del rango), las lecturas 19.1, 19.9, 30.1 y 30.9 se presentan AMARILLO.',
    actor: 'Productor Agropecuario',
    criterios: 'CA-2, CA-16 (RF-58); Fase 3: AMARILLO si valor ∈ (min−T, min) ∪ (max, max+T)',
    valoresLimite: 'T = 10% de (umbral_max-umbral_min) si no hay tolerancia configurada; umbral 20-30 → T=1; AMARILLO en (19,20) y (30,31).',
    datos: 'Umbral 20-30 (T=1 por defecto). Lecturas con valor 19.1, 19.9, 30.1 y 30.9.',
    esperado: 'HTTP 200. estado_semaforo="AMARILLO" en los cuatro casos; la T aplicada corresponde a la configurada en M09 o al 10% del rango por defecto.',
    aserciones: [
      { id: 'PRE-170-01', tipo: 'PRE', fuente: 'API', desc: 'Umbral 20–30 con zona de tolerancia inferior de ancho T=1 configurado en M09' },
      { id: 'PRE-170-02', tipo: 'PRE', fuente: 'API', desc: 'Umbral 20–30 con zona de tolerancia superior de ancho T=1 configurado en M09' },
      lecturas('170', '03', '19.1, 19.9, 30.1 y 30.9'),
      vinculadas('170', '04'),
      sesion('170', '05'),
      { id: 'API-170-01', tipo: 'ASSERT', fuente: 'API', desc: 'Dashboard HTTP 200 con los cuatro sensores' },
      { id: 'API-170-02', tipo: 'ASSERT', fuente: 'API', desc: 'Valor 19.1 → estado_semaforo AMARILLO' },
      { id: 'API-170-03', tipo: 'ASSERT', fuente: 'API', desc: 'Valor 19.9 → estado_semaforo AMARILLO' },
      { id: 'API-170-04', tipo: 'ASSERT', fuente: 'API', desc: 'Valor 30.1 → estado_semaforo AMARILLO' },
      { id: 'API-170-05', tipo: 'ASSERT', fuente: 'API', desc: 'Valor 30.9 → estado_semaforo AMARILLO' },
    ],
  },
  {
    id: 'TC-M03-171',
    titulo: 'Verificar ROJO fuera del rango de tolerancia.',
    objetivo: 'Con umbral 20–30 y T = 1, las lecturas 18.9 y 31.1 se presentan ROJO.',
    actor: 'Productor Agropecuario',
    criterios: 'CA-2 (RF-58); Fase 3: ROJO si valor < min−T o valor > max+T',
    valoresLimite: 'valor < umbral_min - T o valor > umbral_max + T; umbral 20-30, T=1: ROJO con 18.9 y 31.1.',
    datos: 'Umbral 20-30, T=1. Lecturas con valor 18.9 y 31.1.',
    esperado: 'HTTP 200. estado_semaforo="ROJO" en ambos casos.',
    aserciones: [
      { id: 'PRE-171-01', tipo: 'PRE', fuente: 'API', desc: 'Umbral 20–30 con T=1 configurado en M09 (las dos configuraciones de TC-M03-170)' },
      lecturas('171', '02', '18.9 y 31.1'),
      vinculadas('171', '03'),
      sesion('171', '04'),
      { id: 'API-171-01', tipo: 'ASSERT', fuente: 'API', desc: 'Dashboard HTTP 200 con los dos sensores' },
      { id: 'API-171-02', tipo: 'ASSERT', fuente: 'API', desc: 'Valor 18.9 → estado_semaforo ROJO' },
      { id: 'API-171-03', tipo: 'ASSERT', fuente: 'API', desc: 'Valor 31.1 → estado_semaforo ROJO' },
    ],
  },
  {
    id: 'TC-M03-172',
    titulo: 'Verificar que la tolerancia T configurada en M09 prevalece sobre la T por defecto.',
    objetivo: 'Con umbral 20–30 y T configurada = 2, las lecturas 18.5 y 31.5 se presentan AMARILLO (con T=1 serían ROJO).',
    actor: 'Productor Agropecuario',
    criterios: 'CA-2, CA-16 (RF-58); Fase 3: T configurable por variable en M09',
    valoresLimite: 'Umbral 20-30 con T configurada=2; la tolerancia configurada debe usarse en lugar de la T por defecto de 1.',
    datos: 'Umbral 20-30 con T configurada=2. Lecturas 18.5 y 31.5.',
    esperado: 'HTTP 200. estado_semaforo="AMARILLO" para 18.5 y 31.5 usando T=2 configurada; el sistema no aplica la T por defecto de 1.',
    aserciones: [
      { id: 'PRE-172-01', tipo: 'PRE', fuente: 'API', desc: 'Umbral 20–30 con zona de tolerancia inferior de ancho T=2 configurado en M09' },
      { id: 'PRE-172-02', tipo: 'PRE', fuente: 'API', desc: 'Umbral 20–30 con zona de tolerancia superior de ancho T=2 configurado en M09' },
      lecturas('172', '03', '18.5 y 31.5'),
      vinculadas('172', '04'),
      sesion('172', '05'),
      { id: 'API-172-01', tipo: 'ASSERT', fuente: 'API', desc: 'Dashboard HTTP 200 con los dos sensores' },
      { id: 'API-172-02', tipo: 'ASSERT', fuente: 'API', desc: 'Valor 18.5 → estado_semaforo AMARILLO (T=2, no la T por defecto)' },
      { id: 'API-172-03', tipo: 'ASSERT', fuente: 'API', desc: 'Valor 31.5 → estado_semaforo AMARILLO (T=2, no la T por defecto)' },
    ],
  },
  {
    id: 'TC-M03-180',
    titulo: 'Verificar que una variable sin umbral configurado se muestre en GRIS sin ocultarse.',
    objetivo:
      'Una variable con datos y sin rangos operativos en M09 para la especie muestra valor y unidad, estado GRIS con la ' +
      'etiqueta «Sin umbral configurado», se notifica al administrador y la variable no se oculta.',
    actor: 'Productor Agropecuario (consulta) y Administrador (notificación)',
    criterios: 'CA-12 (RF-58); flujo alterno E7',
    valoresLimite: 'Variable con datos y sin umbral_min ni umbral_max configurados.',
    datos: 'Lecturas de una variable sin rangos operativos definidos en M09 para esa especie.',
    esperado:
      'HTTP 200. Se presenta valor y unidad, estado_semaforo="GRIS" con etiqueta "Sin umbral configurado", se notifica al ' +
      'administrador y la variable no se oculta.',
    aserciones: [
      { id: 'PRE-180-01', tipo: 'PRE', fuente: 'API', desc: 'La especie no tiene umbral M09 para HUMEDAD_RELATIVA' },
      lecturas('180', '02', 'de HUMEDAD_RELATIVA'),
      vinculadas('180', '03'),
      sesion('180', '04'),
      { id: 'API-180-01', tipo: 'ASSERT', fuente: 'API', desc: 'Dashboard HTTP 200 y la variable sin umbral no se oculta' },
      { id: 'API-180-02', tipo: 'ASSERT', fuente: 'API', desc: 'Se presentan el valor y la unidad de la lectura' },
      { id: 'API-180-03', tipo: 'ASSERT', fuente: 'API', desc: 'estado_semaforo = GRIS' },
      { id: 'API-180-04', tipo: 'ASSERT', fuente: 'API', desc: 'El administrador recibe una notificación nueva sobre la variable sin umbral configurado' },
      { id: 'PRE-UI-01', tipo: 'PRE', fuente: 'UI', desc: 'La UI recibe el dashboard real desde el sandbox (HTTP 200, X-Test-Run-Id devuelto, sin caché)' },
      { id: 'UI-180-01', tipo: 'ASSERT', fuente: 'UI', desc: 'La tarjeta de la variable sin umbral es visible' },
      { id: 'UI-180-02', tipo: 'ASSERT', fuente: 'UI', desc: 'La tarjeta muestra el valor y la unidad' },
      { id: 'UI-180-03', tipo: 'ASSERT', fuente: 'UI', desc: 'La tarjeta muestra la etiqueta «Sin umbral configurado»' },
    ],
  },
  {
    id: 'TC-M03-266',
    titulo: 'Verificar que el semáforo se recalcule dinámicamente tras reconfigurar los umbrales en M09.',
    objetivo:
      'Con umbral 10–20 la lectura 15 es VERDE; tras reconfigurar el umbral a 20–30, sin nueva lectura ni cambios de código, ' +
      'la misma lectura se presenta ROJO o AMARILLO.',
    actor: 'Productor Agropecuario',
    criterios: 'Restricción 4 (RF-58): configuración dinámica del semáforo derivada de M09',
    valoresLimite: 'El estado del semáforo debe derivarse exclusivamente de los umbrales configurados en M09 para la variable y especie, no de valores fijos en el código.',
    datos: 'Umbral inicial 10-20 en M09 con lectura de valor 15 (VERDE esperado); luego se reconfigura el umbral a 20-30 sin cambiar la lectura.',
    esperado: 'Con umbral inicial la lectura de valor 15 es VERDE; tras reconfigurar a 20-30 la misma lectura se recalcula a ROJO/AMARILLO sin cambio de código ni despliegue.',
    aserciones: [
      { id: 'PRE-266-01', tipo: 'PRE', fuente: 'API', desc: 'Umbral inicial 10–20 (T=1) configurado en M09' },
      lecturas('266', '02', '15'),
      vinculadas('266', '03'),
      sesion('266', '04'),
      { id: 'API-266-01', tipo: 'ASSERT', fuente: 'API', desc: 'Con el umbral inicial, la lectura 15 se presenta VERDE' },
      { id: 'PRE-266-05', tipo: 'PRE', fuente: 'API', desc: 'Umbral reconfigurado a 20–30 en M09 (PATCH 200)' },
      { id: 'PRE-266-06', tipo: 'PRE', fuente: 'API', desc: 'El dashboard sigue mostrando la misma lectura (mismo valor y timestamp: no hubo nueva medición)' },
      { id: 'API-266-02', tipo: 'ASSERT', fuente: 'API', desc: 'Tras reconfigurar, la misma lectura 15 se presenta ROJO o AMARILLO' },
    ],
  },
]);

// ---------------------------------------------------------------------------
// Plan de datos: lo que el ejecutor descubre y prepara por API oficial.
// ---------------------------------------------------------------------------

const TEMPERATURA = 9; // TEMPERATURA_AMBIENTAL (I3P-1)
const HUMEDAD = 10; // HUMEDAD_RELATIVA (I3P-1), variable sin umbral de TC-M03-180

const TODOS = CASOS.map((c) => c.id);
const sensorTemp = (clave) => ({ clave, categoria: 'TEMPERATURA', calibrar: true });

export const PLAN = Object.freeze({
  actores: ['setup', 'prod'],
  // El administrador debe recibir la notificación de TC-M03-180 y editar umbrales.
  patronSetup: /administrador/i,
  alcance: { prod: TODOS },
  rutasRequeridas: [
    '/iot/monitoreo/dashboard', '/iot/telemetria', '/iot/vinculaciones', '/sesiones/', '/usuarios/me', '/notificaciones',
    '/configuracion/fincas', '/configuracion/infraestructuras', '/configuracion/infraestructuras/{id_infraestructura}',
    '/configuracion/dispositivos-iot', '/configuracion/dispositivos-iot/{id_dispositivo_iot}/sensores',
    '/configuracion/sensores/{id_sensor}/asociar', '/configuracion/sensores/{id_sensor}/calibrar',
    '/configuracion/sensores/{id_sensor}/calibraciones', '/configuracion/sensores/rangos-calibracion',
    '/configuracion/variables-ambientales', '/configuracion/especies', '/configuracion/metricas',
    '/configuracion/umbrales', '/configuracion/umbrales/{id_umbral_ambiental}', '/activos-biologicos',
    '/test-control/query', '/test-control/runs/{run_id}',
  ],
  variables: [TEMPERATURA, HUMEDAD],
  // Un sensor por lectura: el dashboard muestra el estado de la última lectura de cada sensor.
  sensores: [
    sensorTemp('169A'), sensorTemp('169B'), sensorTemp('169C'),
    sensorTemp('266'),
    sensorTemp('170A'), sensorTemp('170B'), sensorTemp('171A'),
    sensorTemp('170C'), sensorTemp('170D'), sensorTemp('171B'),
    sensorTemp('172A'), sensorTemp('172B'),
    { clave: '180H', categoria: 'HUMEDAD', calibrar: true },
  ],
  // RF-61: la lectura solo se clasifica con el umbral de la especie si queda VINCULADA,
  // y eso exige exactamente un activo operativo en el área del dispositivo.
  activo: true,
  // La colección registra y edita el umbral: la especie no puede tener destinos Edge
  // (sin publicación MQTT), ni umbral previo para las variables usadas (evita 409 y no
  // altera configuraciones ajenas), ni métricas obligatorias para el activo INDIVIDUAL.
  especie: { requisitos: ['sin_gateway', `sin_umbral:${TEMPERATURA}`, `sin_umbral:${HUMEDAD}`, 'sin_metricas_obligatorias_individual'] },
  casosUI: ['TC-M03-180'],

  efectosPersistentes: [
    {
      id: 'notificacion-login',
      descripcion:
        'cada login exitoso agenda en segundo plano (sesion_sistema, fuera del sandbox) una notificación ' +
        'TIPO_LOGIN_EXITOSO que se persiste y puede despachar correo/FCM a la cuenta QA; el RUN hace 3 logins ' +
        '(2 del ejecutor y 1 de la UI)',
    },
  ],
  efectosExternos:
    'Dispositivo sin gateway (sin sincronización MQTT). Los umbrales se registran y editan para una especie sin Gateway Edge ' +
    '(verificado por SQL antes de preparar; sin publicación MQTT). Activo INDIVIDUAL (sin disparo M02→M09 de VISION). ' +
    'No revertible: notificaciones de login (efecto aceptado expresamente en la ejecución).',

  /** Comprueba que los valores fijos de la matriz caben en los rangos físicos del catálogo. */
  derivar(ctx) {
    const bloqueos = [];
    const dentro = (id, valores) => {
      const v = ctx.variables[id];
      const min = Number(v.valor_fisico_min);
      const max = Number(v.valor_fisico_max);
      for (const x of valores) if (!(x >= min && x <= max)) bloqueos.push(`El valor ${x} de la matriz está fuera del rango físico [${min}, ${max}] de la variable ${id}.`);
    };
    dentro(TEMPERATURA, [9, 10, 15, 18, 18.5, 18.9, 19.1, 19.9, 20, 21, 30, 30.1, 30.9, 31.1, 31.5, 32, 34.6, 35, 37, 39, 39.4]);
    dentro(HUMEDAD, [55]);
    return { bloqueos, valores: { valor_humedad: 55, unidad_humedad: '%' } };
  },

  entornoNewman() {
    return {};
  },

  entornoCypress(ctx) {
    return { VALOR_H: ctx.derivados.valor_humedad, UNIDAD_H: ctx.derivados.unidad_humedad };
  },

  riesgos: [
    'El semáforo del dashboard se fija al ingerir (`fn_actualizar_estado_sensor` = VERDE) y solo se reclasifica con las bandas RF-17 (`SemaforoCalculator.calcular_por_niveles`) cuando la lectura queda VINCULADA; la fórmula con T de la Fase 3 (`SemaforoCalculator.calcular`) no se usa en el dashboard.',
    'Ningún proceso recalcula `estados_actuales_sensores` al editar un umbral; lo confirma o descarta API-266-02.',
    'Sin umbral, la reclasificación no ocurre y el estado queda como lo dejó el trigger de ingesta; lo confirma o descarta API-180-03.',
  ],
});
