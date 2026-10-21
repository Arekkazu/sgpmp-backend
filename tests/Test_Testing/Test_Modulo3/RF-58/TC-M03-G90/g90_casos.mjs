// Matriz oficial M03, fila TC-M03-G90. Los criterios de color simultáneo
// alerta crítica + sin señal son ambiguos: deliberadamente no se califican.
export const GRUPO = Object.freeze({
  id: 'TC-M03-G90', corto: 'G90', modulo: 'M03', rf: 'RF-58',
  rfNombre: 'RF-58 — Monitoreo ambiental en tiempo real', cu: 'CU04',
  cuNombre: 'CU04 — Monitorear variables (modo tiempo real)',
  titulo: 'Sensor sin señal y conservación de alerta activa',
  objetivo: 'Comprobar la retención de la última lectura y de la alerta crítica activa al superar la frecuencia de muestreo.',
  tipo: 'Funcional / Integración', herramientas: 'Postman/Newman (API) y Cypress (UI)',
  endpoint: 'GET /iot/monitoreo/dashboard', responsable: 'Juan Esteban', prioridad: 'Alta',
  fuenteMatriz: 'Casos_Prueba(Modulo3 Agrupado).csv — fila TC-M03-G90',
  casosMatriz: ['TC-M03-175', 'TC-M03-176'],
});
export const ARCHIVOS_AUTOMATIZACION = Object.freeze([
  'g90_casos.mjs', 'g90_lib.mjs', 'ejecutar_tc_m03_g90.mjs',
  'TC-M03-G90.postman_collection.json', 'tc_m03_g90.cy.js', 'cypress.config.cjs', 'validar_local_g90.mjs',
]);
export const CASOS = Object.freeze([
  {
    id: 'TC-M03-175', titulo: 'Alerta crítica visible al quedar el sensor sin señal',
    actor: 'Productor Agropecuario', criterios: 'CA-5 y CA-11 (RF-58)',
    datos: 'Última lectura válida y alerta CRITICO ACTIVA del sensor; superar frecuencia_muestreo.',
    esperado: 'HTTP 200; sensor, último valor, tiempo sin reporte y alerta activa permanecen visibles. No se juzga ROJO frente a GRIS.',
    aserciones: [
      { id: 'PRE-175-01', tipo: 'PRE', fuente: 'API', desc: 'Lectura válida y alerta CRITICO activa asociada' },
      { id: 'PRE-175-02', tipo: 'PRE', fuente: 'API', desc: 'Dispositivo alcanzó SIN_SEÑAL por mecanismo aislado y tiempo mayor que frecuencia_muestreo' },
      { id: 'API-175-01', tipo: 'ASSERT', fuente: 'API', desc: 'Dashboard 200 conserva sensor y último valor válido' },
      { id: 'API-175-02', tipo: 'ASSERT', fuente: 'API', desc: 'Tiempo sin reporte informado y alerta crítica activa asociada' },
      { id: 'UI-175-01', tipo: 'ASSERT', fuente: 'UI', desc: 'Panel conserva sensor, valor y alerta visual' },
    ],
  },
  {
    id: 'TC-M03-176', titulo: 'Último valor y estado gris ante falta de reporte',
    actor: 'Productor Agropecuario', criterios: 'CA-5 (RF-58)',
    datos: 'Sensor con última lectura válida y frecuencia_muestreo conocida; sin nueva lectura por más de un intervalo.',
    esperado: 'Sensor visible, último valor no nulo, dato desactualizado, tiempo sin reporte y estado visual GRIS.',
    aserciones: [
      { id: 'PRE-176-01', tipo: 'PRE', fuente: 'API', desc: 'Lectura válida inicial y frecuencia de 5 minutos' },
      { id: 'PRE-176-02', tipo: 'PRE', fuente: 'API', desc: 'Sin señal comprobada mediante transición real aislada' },
      { id: 'API-176-01', tipo: 'ASSERT', fuente: 'API', desc: 'Dashboard conserva sensor y último valor válido' },
      { id: 'API-176-02', tipo: 'ASSERT', fuente: 'API', desc: 'dato_desactualizado, tiempo transcurrido y GRIS' },
      { id: 'UI-176-01', tipo: 'ASSERT', fuente: 'UI', desc: 'Tarjeta muestra valor anterior, desactualizado y GRIS' },
    ],
  },
]);
const sensor = (clave) => ({ clave, categoria: 'TEMPERATURA', calibrar: true });
export const PLAN = Object.freeze({
  actores: ['setup', 'prod'], patronSetup: /administrador/i,
  alcance: { prod: GRUPO.casosMatriz },
  rutasRequeridas: ['/iot/monitoreo/dashboard', '/iot/telemetria', '/iot/alertas', '/iot/alertas/{id_alerta}',
    '/sesiones/', '/usuarios/me', '/configuracion/fincas', '/configuracion/infraestructuras',
    '/configuracion/infraestructuras/{id_infraestructura}', '/configuracion/dispositivos-iot',
    '/configuracion/dispositivos-iot/{id_dispositivo_iot}/sensores', '/configuracion/sensores/{id_sensor}/asociar',
    '/configuracion/sensores/{id_sensor}/calibrar', '/configuracion/sensores/{id_sensor}/calibraciones',
    '/configuracion/sensores/rangos-calibracion', '/configuracion/variables-ambientales',
    '/configuracion/especies', '/configuracion/metricas', '/configuracion/umbrales',
    '/activos-biologicos', '/test-control/query', '/test-control/runs/{run_id}'],
  variables: [9], sensores: [sensor('175'), sensor('176')], activo: true,
  especie: { requisitos: ['sin_gateway', 'sin_umbral:9', 'sin_metricas_obligatorias_individual'] },
  casosUI: GRUPO.casosMatriz,
  efectosPersistentes: [{ id: 'notificacion-login', descripcion: 'Los logins QA generan notificaciones fuera del rollback.' }],
  efectosExternos: 'Lecturas y alerta creadas por API oficial dentro del sandbox. La tarea periódica RF-60 es global: el ejecutor no la invoca ni escribe SQL; espera el tiempo real y exige observar SIN_SEÑAL y aislamiento antes de evaluar.',
  derivar(ctx) {
    const v = ctx.variables[9];
    const min = Number(v.valor_fisico_min), max = Number(v.valor_fisico_max);
    return { bloqueos: [19, 20, 25, 30, 31].filter((x) => x < min || x > max).map((x) => `Valor ${x} fuera del rango físico.`), valores: {} };
  },
  entornoNewman(ctx) { return { alerta_175: String(ctx.alerta175 ?? ''), lectura_175: ctx.lecturas?.['175']?.timestamp ?? '', lectura_176: ctx.lecturas?.['176']?.timestamp ?? '' }; },
  entornoCypress() { return {}; },
  riesgos: ['El backend no expone un reloj de pruebas ni un disparador aislado de evaluación de estado RF-60. El RUN solo continúa si el dashboard confirma la transición real en el mismo sandbox. Cypress cy.clock no altera el reloj del backend.'],
});

// Comprobación pura de la capacidad temporal. No evalúa los resultados finales
// (valor, alerta, tiempo informado, semáforo): esas son aserciones de los casos.
export function comprobarSinSenal(dashboard, { sensor175, sensor176, lecturas, ahora }) {
  const sensores = Array.isArray(dashboard?.sensores) ? dashboard.sensores : [];
  const pendientes = [];
  const observado = {};
  for (const [clave, id] of [['175', sensor175], ['176', sensor176]]) {
    const s = sensores.find((x) => Number(x.id_sensor) === Number(id));
    if (!s) { pendientes.push(`sensor ${clave} ausente`); continue; }
    const edadMin = (ahora - Date.parse(lecturas[clave].timestamp)) / 60000;
    observado[clave] = {
      id_sensor: s.id_sensor, ultimo_valor: s.ultimo_valor,
      ultimo_timestamp_captura: s.ultimo_timestamp_captura,
      estado_conectividad: s.estado_conectividad,
      dato_desactualizado: s.dato_desactualizado,
      tiempo_sin_reporte_min: s.tiempo_sin_reporte_min,
      edad_min: Number.isFinite(edadMin) ? Math.round(edadMin * 10) / 10 : null,
      id_alerta: s.id_alerta, severidad_alerta: s.severidad_alerta,
    };
    if (!Number.isFinite(edadMin) || edadMin <= 5) pendientes.push(`sensor ${clave}: aún no supera 5 min`);
    if (s.estado_conectividad !== 'SIN_SEÑAL') pendientes.push(`sensor ${clave}: sin transición SIN_SEÑAL`);
  }
  return { listo: pendientes.length === 0, pendientes, observado };
}
