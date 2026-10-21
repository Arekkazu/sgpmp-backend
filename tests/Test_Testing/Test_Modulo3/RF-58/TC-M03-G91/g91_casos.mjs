// Matriz oficial M03, fila TC-M03-G91.
export const GRUPO = Object.freeze({
  id: 'TC-M03-G91', corto: 'G91', modulo: 'M03', rf: 'RF-58',
  rfNombre: 'RF-58 — Monitoreo ambiental en tiempo real', cu: 'CU04',
  cuNombre: 'CU04 — Monitorear variables (modo tiempo real)',
  titulo: 'Resincronización y recuperación automática del dashboard',
  objetivo: 'Verificar recuperación de estado real en backend ante pérdida de actualización y reconexión.',
  tipo: 'Integración / Resiliencia / Funcional', herramientas: 'Postman/Newman (API) y Cypress (UI)',
  endpoint: 'GET /iot/monitoreo/dashboard', responsable: 'Juan Esteban', prioridad: 'Alta',
  fuenteMatriz: 'Casos_Prueba(Modulo3 Agrupado).csv — fila TC-M03-G91',
  casosMatriz: ['TC-M03-179', 'TC-M03-194'],
});
export const ARCHIVOS_AUTOMATIZACION = Object.freeze([
  'g91_casos.mjs', 'g91_lib.mjs', 'ejecutar_tc_m03_g91.mjs',
  'TC-M03-G91.postman_collection.json', 'tc_m03_g91.cy.js', 'cypress.config.cjs', 'validar_local_g91.mjs',
]);
export const CASOS = Object.freeze([
  { id: 'TC-M03-179', titulo: 'Recuperar lectura B tras pérdida de actualización',
    actor: 'Productor Agropecuario', criterios: 'RF-58 restricción 11; CU04 FA-05',
    datos: 'Sensor con frecuencia_muestreo=5 minutos. Vista muestra A; B persiste en backend mientras su actualización no llega a la vista por más de 12 minutos.',
    esperado: 'Vista conserva A sin nulos durante la pérdida; se sincroniza con B después de 2 × frecuencia_muestreo sin recarga.',
    aserciones: [
      { id: 'PRE-179-01', tipo: 'PRE', fuente: 'API', desc: 'Lectura A válida y visible en backend' },
      { id: 'PRE-179-02', tipo: 'PRE', fuente: 'UI', desc: 'Lectura B real se confirma en backend mientras la vista conserva A' },
      { id: 'UI-179-01', tipo: 'ASSERT', fuente: 'UI', desc: 'A permanece visible sin nulos durante la pérdida de actualizaciones' },
      { id: 'UI-179-02', tipo: 'ASSERT', fuente: 'UI', desc: 'Vista recupera B automáticamente tras más de 12 minutos simulados' },
    ] },
  { id: 'TC-M03-194', titulo: 'Actualizar automáticamente al restablecer la conexión',
    actor: 'Productor Agropecuario', criterios: 'RF-58 CA-10; CU04 FA-04',
    datos: 'Dashboard con caché A, interrupción de red de API y lectura B persistida en backend.',
    esperado: 'Al restablecer red, desaparece indicador de desconexión y se muestra B sin recarga manual.',
    aserciones: [
      { id: 'PRE-194-01', tipo: 'PRE', fuente: 'API', desc: 'Lectura A inicial y sensor del RUN disponibles' },
      { id: 'PRE-194-02', tipo: 'PRE', fuente: 'UI', desc: 'Modo caché/desconexión observado; B verificada por API real' },
      { id: 'UI-194-01', tipo: 'ASSERT', fuente: 'UI', desc: 'Indicador de desconexión desaparece automáticamente' },
      { id: 'UI-194-02', tipo: 'ASSERT', fuente: 'UI', desc: 'Valor B aparece sin recarga manual ni nulos' },
    ] },
]);
export const PLAN = Object.freeze({
  actores: ['setup', 'prod'], patronSetup: /administrador/i,
  alcance: { prod: GRUPO.casosMatriz },
  rutasRequeridas: ['/iot/monitoreo/dashboard', '/iot/telemetria', '/sesiones/', '/usuarios/me',
    '/configuracion/fincas', '/configuracion/infraestructuras', '/configuracion/infraestructuras/{id_infraestructura}',
    '/configuracion/dispositivos-iot', '/configuracion/dispositivos-iot/{id_dispositivo_iot}/sensores',
    '/configuracion/sensores/{id_sensor}/asociar', '/configuracion/sensores/{id_sensor}/calibrar',
    '/configuracion/sensores/{id_sensor}/calibraciones', '/configuracion/sensores/rangos-calibracion',
    '/configuracion/variables-ambientales', '/configuracion/especies', '/configuracion/metricas',
    '/activos-biologicos', '/test-control/query', '/test-control/runs/{run_id}'],
  variables: [9], sensores: [{ clave: '179', categoria: 'TEMPERATURA', calibrar: true }, { clave: '194', categoria: 'TEMPERATURA', calibrar: true }],
  activo: true, especie: { requisitos: ['sin_gateway', 'sin_metricas_obligatorias_individual'] },
  casosUI: GRUPO.casosMatriz,
  efectosPersistentes: [{ id: 'notificacion-login', descripcion: 'Los logins QA generan notificaciones fuera del rollback.' }],
  efectosExternos: 'Dispositivos sin gateway y sin MQTT. Las lecturas se generan por API oficial dentro del sandbox. Pérdida de respuesta de polling simulada en navegador sin falsificar el estado del producto.',
  derivar(ctx) { const v = ctx.variables[9]; const a = [25, 26]; return { bloqueos: a.filter((x) => x < Number(v.valor_fisico_min) || x > Number(v.valor_fisico_max)).map((x) => `Valor ${x} fuera del rango físico.`), valores: {} }; },
  entornoNewman() { return {}; }, entornoCypress() { return {}; }, riesgos: [
    'Se debe comprobar que la lectura B esté confirmada por el backend y que ninguna respuesta simulada produzca una aprobación.',
    'El navegador debe conservar X-Test-Run-Id en cada solicitud real; el sandbox puede caducar tras 180 s de inactividad.',
  ],
});
