// Matriz oficial M03, fila TC-M03-G92. El sensor 55 es el único ROJO.
export const GRUPO = Object.freeze({
  id: 'TC-M03-G92', corto: 'G92', modulo: 'M03', rf: 'RF-58',
  rfNombre: 'RF-58 — Monitoreo ambiental en tiempo real', cu: 'CU04',
  cuNombre: 'CU04 — Monitorear variables (modo tiempo real)',
  titulo: 'Consolidación por unidad y paginación completa',
  objetivo: 'Verificar peor semáforo entre todos los sensores, filtrado por unidad y cálculo independiente de la página.',
  tipo: 'Funcional / Validación', herramientas: 'Postman/Newman (API)',
  endpoint: 'GET /iot/monitoreo/dashboard', responsable: 'Juan Esteban', prioridad: 'Alta',
  fuenteMatriz: 'Casos_Prueba(Modulo3 Agrupado).csv — fila TC-M03-G92',
  casosMatriz: ['TC-M03-181', 'TC-M03-182', 'TC-M03-183'],
});
export const ARCHIVOS_AUTOMATIZACION = Object.freeze([
  'g92_casos.mjs', 'g92_lib.mjs', 'ejecutar_tc_m03_g92.mjs',
  'TC-M03-G92.postman_collection.json', 'validar_local_g92.mjs',
]);
export const CASOS = Object.freeze([
  { id: 'TC-M03-181', titulo: 'Peor semáforo de la unidad', actor: 'Productor Agropecuario',
    criterios: 'RF-58 CA-14', datos: 'Unidad QA con al menos VERDE, AMARILLO y ROJO, todos accesibles.',
    esperado: 'Resumen ROJO, variables de atención/críticas y alertas activas asociadas con timestamp de actualización.',
    aserciones: [
      { id: 'PRE-181-01', tipo: 'PRE', fuente: 'API', desc: 'Lecturas válidas en las tres bandas y semáforos VERDE, AMARILLO y ROJO' },
      { id: 'API-181-01', tipo: 'ASSERT', fuente: 'API', desc: 'Resumen de unidad informa ROJO' },
      { id: 'API-181-02', tipo: 'ASSERT', fuente: 'API', desc: 'Resumen incluye alertas activas y timestamp; sensores señalan variables en atención y críticas' },
    ] },
  { id: 'TC-M03-182', titulo: 'Monitoreo limitado a la unidad seleccionada', actor: 'Productor Agropecuario',
    criterios: 'RF-58 CU04, selección de unidad', datos: 'Dos unidades QA con sensor y lectura; Productor con acceso a ambas.',
    esperado: 'Filtro de unidad devuelve únicamente sus sensores e información, excluyendo la otra unidad.',
    aserciones: [
      { id: 'PRE-182-01', tipo: 'PRE', fuente: 'API', desc: 'Dos unidades distintas visibles y con datos' },
      { id: 'API-182-01', tipo: 'ASSERT', fuente: 'API', desc: 'Consulta filtrada devuelve solo sensores de la unidad seleccionada' },
      { id: 'API-182-02', tipo: 'ASSERT', fuente: 'API', desc: 'Resumen filtrado contiene únicamente la unidad seleccionada' },
    ] },
  { id: 'TC-M03-183', titulo: 'Peor semáforo fuera de la primera página', actor: 'Productor Agropecuario',
    criterios: 'RF-58 CA-14', datos: '60 sensores de una unidad; único ROJO en posición 55; pagina=1&por_pagina=50.',
    esperado: 'estado_general ROJO en página 1 pese a que su arreglo de sensores no incluye el ROJO.',
    aserciones: [
      { id: 'PRE-183-01', tipo: 'PRE', fuente: 'API', desc: '60 sensores, único ROJO en posición 55 según orden de la API' },
      { id: 'API-183-01', tipo: 'ASSERT', fuente: 'API', desc: 'Página 1 tiene 50 sensores y no contiene ROJO' },
      { id: 'API-183-02', tipo: 'ASSERT', fuente: 'API', desc: 'Resumen de página 1 mantiene estado_general ROJO' },
    ] },
]);
const sensores = Array.from({ length: 60 }, (_, i) => ({ clave: String(i + 1).padStart(2, '0'), categoria: 'TEMPERATURA', calibrar: true }));
export const PLAN = Object.freeze({
  actores: ['setup', 'prod'], patronSetup: /administrador/i, alcance: { prod: GRUPO.casosMatriz },
  rutasRequeridas: ['/iot/monitoreo/dashboard', '/iot/telemetria', '/iot/alertas', '/sesiones/', '/usuarios/me',
    '/configuracion/fincas', '/configuracion/infraestructuras', '/configuracion/infraestructuras/{id_infraestructura}',
    '/configuracion/dispositivos-iot', '/configuracion/dispositivos-iot/{id_dispositivo_iot}/sensores',
    '/configuracion/sensores/{id_sensor}/asociar', '/configuracion/sensores/{id_sensor}/calibrar',
    '/configuracion/sensores/{id_sensor}/calibraciones', '/configuracion/sensores/rangos-calibracion',
    '/configuracion/variables-ambientales', '/configuracion/especies', '/configuracion/metricas',
    '/configuracion/umbrales', '/activos-biologicos', '/test-control/query', '/test-control/runs/{run_id}'],
  variables: [9], sensores, activo: true, segundaUnidad: true,
  especie: { requisitos: ['sin_gateway', 'sin_umbral:9', 'sin_metricas_obligatorias_individual'] },
  casosUI: [],
  efectosPersistentes: [{ id: 'notificacion-login', descripcion: 'Los logins QA generan notificaciones fuera del rollback.' }],
  efectosExternos: 'Dispositivos sin gateway, especie sin destinos Edge. Datos de ambas unidades creados por contratos oficiales dentro del sandbox.',
  derivar(ctx) { const v = ctx.variables[9]; return { bloqueos: [19, 19.5, 20, 25, 30, 31].filter((x) => x < Number(v.valor_fisico_min) || x > Number(v.valor_fisico_max)).map((x) => `Valor ${x} fuera del rango físico.`), valores: {} }; },
  entornoNewman(ctx) { return { id_segunda_infraestructura: String(ctx.idSegundaArea ?? ''), sensor_segunda: String(ctx.idSegundoSensor ?? ''), segundo_device_id: String(ctx.idSegundoDisp ?? ''), segunda_access_key: String(ctx.segundoSerial ?? '') }; },
  entornoCypress() { return {}; },
  riesgos: ['El resumen global puede basarse en estados persistidos distintos del semáforo efectivo. La primera página no debe recalcular el estado general.', 'El sensor 55 se identifica mediante IDs del RUN ordenados como devuelve la API, no por un ID fijo.'],
});
