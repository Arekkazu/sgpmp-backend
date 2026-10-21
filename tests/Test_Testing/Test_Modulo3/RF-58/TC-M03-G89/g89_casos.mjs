// TC-M03-G89 — Catálogo de casos y plan de datos del grupo.
// Fuente: Casos_Prueba(Modulo3 Agrupado).csv, fila TC-M03-G89 (RF-58, CU04).
//
// Cada aserción tiene un id estable. Newman nombra sus pruebas con el prefijo
// `[CASO][PRE|ASSERT|INFO][ID]` y el ejecutor las agrega por id:
//   PRE    = precondición: si falla, el caso queda BLOQUEADO (no RECHAZADO).
//   ASSERT = criterio esperado de la matriz: si falla con evidencia del producto, RECHAZADO.
//
// «Rango óptimo»: umbral M09 (RF-17) 20–30 de TEMPERATURA_AMBIENTAL para la especie del
// área, registrado como precaucion [19, 20] · normal [20, 30] · critico [30, 31]. Las
// lecturas de 25 caen en la banda normal (VERDE), condición base de ambos casos.
// Las alertas se generan por el contrato oficial de RF-57 (POST /iot/alertas, con la
// credencial del dispositivo) y se gestionan con PATCH /iot/alertas/{id}/estado.

export const GRUPO = Object.freeze({
  id: 'TC-M03-G89',
  corto: 'G89',
  modulo: 'M03',
  rf: 'RF-58',
  rfNombre: 'RF-58 — Monitoreo Ambiental en Tiempo Real',
  cu: 'CU04',
  cuNombre: 'CU04 — Monitorear variables (modo tiempo real)',
  titulo: 'Forzar o elevar el semáforo según la severidad de alertas activas',
  objetivo:
    'Verificar que una alerta CRITICO activa de RF-57 fuerza el semáforo a ROJO aunque el valor esté en rango, que una ' +
    'alerta activa no crítica eleva un estado base VERDE a AMARILLO, y que una alerta resuelta o descartada no eleva el estado.',
  tipo: 'Funcional',
  herramientas: 'Postman/Newman (API)',
  endpoint: 'GET /iot/monitoreo/dashboard',
  responsable: 'Juan Esteban',
  prioridad: 'Alta',
  fuenteMatriz: 'Casos_Prueba(Modulo3 Agrupado).csv — fila TC-M03-G89',
  casosMatriz: ['TC-M03-173', 'TC-M03-174'],
});

export const ARCHIVOS_AUTOMATIZACION = Object.freeze([
  'g89_casos.mjs',
  'g89_lib.mjs',
  'ejecutar_tc_m03_g89.mjs',
  'TC-M03-G89.postman_collection.json',
  'validar_local_g89.mjs',
]);

export const CASOS = Object.freeze([
  {
    id: 'TC-M03-173',
    titulo: 'Forzar ROJO ante alerta CRÍTICA activa independientemente del valor.',
    objetivo: 'Con el valor en el rango óptimo (VERDE) y una alerta CRITICO activa asociada al sensor, el dashboard muestra ROJO y el id_alerta.',
    actor: 'Productor Agropecuario',
    criterios: 'CA-4 (RF-58); Fase 3: alerta CRITICA activa → ROJO obligatorio',
    valoresLimite: 'Alerta de severidad CRITICO activa fuerza ROJO independientemente del valor.',
    datos: 'Sensor con valor dentro del rango óptimo y una alerta CRITICO activa asociada (RF-57).',
    esperado: 'HTTP 200. estado_semaforo="ROJO" pese a que el valor está en rango VERDE, y se devuelve el id_alerta asociado.',
    aserciones: [
      { id: 'PRE-173-01', tipo: 'PRE', fuente: 'API', desc: 'Umbral 20–30 de la especie configurado en M09 (rango óptimo)' },
      { id: 'PRE-173-02', tipo: 'PRE', fuente: 'API', desc: 'Lectura 25 aceptada (201) como LECTURA_VALIDA' },
      { id: 'PRE-173-03', tipo: 'PRE', fuente: 'API', desc: 'Lectura VINCULADA al único activo del área (RF-61), condición para clasificarla con el umbral' },
      { id: 'PRE-173-04', tipo: 'PRE', fuente: 'API', desc: 'Antes de la alerta, el sensor está en VERDE (valor dentro del rango óptimo)' },
      { id: 'PRE-173-05', tipo: 'PRE', fuente: 'API', desc: 'Alerta CRITICO ACTIVA registrada en RF-57 para el sensor (201, no duplicada)' },
      { id: 'PRE-173-06', tipo: 'PRE', fuente: 'API', desc: 'La sesión del Productor está vigente al consultar el dashboard (no 401)' },
      { id: 'API-173-01', tipo: 'ASSERT', fuente: 'API', desc: 'Dashboard HTTP 200 con el sensor' },
      { id: 'API-173-02', tipo: 'ASSERT', fuente: 'API', desc: 'estado_semaforo = ROJO pese a que el valor está en el rango VERDE' },
      { id: 'API-173-03', tipo: 'ASSERT', fuente: 'API', desc: 'Se devuelve el id_alerta de la alerta CRITICO activa' },
    ],
  },
  {
    id: 'TC-M03-174',
    titulo: 'Elevar a mínimo AMARILLO ante alerta activa no crítica sobre estado base VERDE; verificar que no ocurra con alerta resuelta.',
    objetivo:
      'Con el valor en rango (VERDE), una alerta activa no crítica eleva el estado a AMARILLO; con la alerta resuelta o ' +
      'descartada el estado permanece VERDE.',
    actor: 'Productor Agropecuario',
    criterios: 'Fase 3 (RF-58): alerta ACTIVA asociada → al menos AMARILLO; depende del estado de la alerta, no de la existencia de un id_alerta',
    valoresLimite: 'Alerta ACTIVA no crítica sobre estado base VERDE eleva a AMARILLO.',
    datos: 'Sensor con valor dentro del rango y alerta activa de severidad no crítica; repetir con una alerta ya RESUELTA.',
    esperado: 'Con alerta activa: estado_semaforo="AMARILLO". Con alerta resuelta o descartada: estado_semaforo="VERDE", sin elevación indebida.',
    aserciones: [
      { id: 'PRE-174-01', tipo: 'PRE', fuente: 'API', desc: 'Umbral 20–30 de la especie configurado en M09 (rango óptimo)' },
      { id: 'PRE-174-02', tipo: 'PRE', fuente: 'API', desc: 'Lecturas 25 de los cuatro sensores aceptadas (201) como LECTURA_VALIDA' },
      { id: 'PRE-174-03', tipo: 'PRE', fuente: 'API', desc: 'Lecturas VINCULADAS al único activo del área (RF-61)' },
      { id: 'PRE-174-04', tipo: 'PRE', fuente: 'API', desc: 'Antes de las alertas, los cuatro sensores están en VERDE' },
      { id: 'PRE-174-05', tipo: 'PRE', fuente: 'API', desc: 'Alertas no críticas ACTIVA registradas en RF-57 (LEVE y MODERADO; 201, no duplicadas)' },
      { id: 'PRE-174-06', tipo: 'PRE', fuente: 'API', desc: 'Una alerta llevada a RESUELTA por el ciclo oficial (ACTIVA → EN_ATENCION → RESUELTA)' },
      { id: 'PRE-174-07', tipo: 'PRE', fuente: 'API', desc: 'Una alerta llevada a DESCARTADA (ACTIVA → DESCARTADA)' },
      { id: 'PRE-174-08', tipo: 'PRE', fuente: 'API', desc: 'La sesión del Productor está vigente al consultar el dashboard (no 401)' },
      { id: 'API-174-01', tipo: 'ASSERT', fuente: 'API', desc: 'Dashboard HTTP 200 con los cuatro sensores' },
      { id: 'API-174-02', tipo: 'ASSERT', fuente: 'API', desc: 'Alerta LEVE activa → estado_semaforo AMARILLO' },
      { id: 'API-174-03', tipo: 'ASSERT', fuente: 'API', desc: 'Alerta MODERADO activa → estado_semaforo AMARILLO' },
      { id: 'API-174-04', tipo: 'ASSERT', fuente: 'API', desc: 'Alerta RESUELTA → estado_semaforo VERDE (sin elevación indebida)' },
      { id: 'API-174-05', tipo: 'ASSERT', fuente: 'API', desc: 'Alerta DESCARTADA → estado_semaforo VERDE (sin elevación indebida)' },
    ],
  },
]);

// ---------------------------------------------------------------------------
// Plan de datos: lo que el ejecutor descubre y prepara por API oficial.
// ---------------------------------------------------------------------------

const TEMPERATURA = 9; // TEMPERATURA_AMBIENTAL (I3P-1)
const sensor = (clave) => ({ clave, categoria: 'TEMPERATURA', calibrar: true });

export const PLAN = Object.freeze({
  actores: ['setup', 'prod'],
  // El administrador registra el umbral y gestiona el ciclo de vida de las alertas (RF-57).
  patronSetup: /administrador/i,
  alcance: { prod: ['TC-M03-173', 'TC-M03-174'] },
  rutasRequeridas: [
    '/iot/monitoreo/dashboard', '/iot/telemetria', '/iot/vinculaciones', '/iot/alertas', '/iot/alertas/{id_alerta}/estado',
    '/sesiones/', '/usuarios/me',
    '/configuracion/fincas', '/configuracion/infraestructuras', '/configuracion/infraestructuras/{id_infraestructura}',
    '/configuracion/dispositivos-iot', '/configuracion/dispositivos-iot/{id_dispositivo_iot}/sensores',
    '/configuracion/sensores/{id_sensor}/asociar', '/configuracion/sensores/{id_sensor}/calibrar',
    '/configuracion/sensores/{id_sensor}/calibraciones', '/configuracion/sensores/rangos-calibracion',
    '/configuracion/variables-ambientales', '/configuracion/especies', '/configuracion/metricas',
    '/configuracion/umbrales', '/activos-biologicos',
    '/test-control/query', '/test-control/runs/{run_id}',
  ],
  variables: [TEMPERATURA],
  // Un sensor por situación de alerta (la deduplicación de RF-57 es por sensor y variable).
  sensores: [sensor('173'), sensor('174A'), sensor('174B'), sensor('174C'), sensor('174D')],
  activo: true,
  especie: { requisitos: ['sin_gateway', `sin_umbral:${TEMPERATURA}`, 'sin_metricas_obligatorias_individual'] },
  casosUI: [],

  efectosPersistentes: [
    {
      id: 'notificacion-login',
      descripcion:
        'cada login exitoso agenda en segundo plano (sesion_sistema, fuera del sandbox) una notificación ' +
        'TIPO_LOGIN_EXITOSO que se persiste y puede despachar correo/FCM a la cuenta QA; el RUN hace 2 logins (ejecutor)',
    },
  ],
  efectosExternos:
    'Dispositivo sin gateway (sin sincronización MQTT). El umbral se registra para una especie sin Gateway Edge (verificado ' +
    'por SQL; sin publicación MQTT). Las alertas de RF-57 solo escriben en modulo3 (triggers internos), dentro del sandbox. ' +
    'No revertible: notificaciones de login (efecto aceptado expresamente en la ejecución).',

  derivar(ctx) {
    const v = ctx.variables[TEMPERATURA];
    const min = Number(v.valor_fisico_min);
    const max = Number(v.valor_fisico_max);
    const bloqueos = [19, 20, 25, 30, 31].filter((x) => !(x >= min && x <= max))
      .map((x) => `El valor ${x} del escenario está fuera del rango físico [${min}, ${max}] de TEMPERATURA_AMBIENTAL.`);
    return { bloqueos, valores: {} };
  },

  entornoNewman() {
    return {};
  },

  entornoCypress() {
    return {};
  },

  riesgos: [
    'El semáforo se reclasifica con las bandas RF-17 solo si la lectura queda VINCULADA; el trigger `fn_sincronizar_alerta_en_sensor` fija ROJO/AMARILLO al crear la alerta.',
    'Al pasar una alerta a RESUELTA o DESCARTADA el trigger limpia `id_alerta` pero no restaura `estado_semaforo`, y el caso de uso del dashboard eleva a AMARILLO por la mera existencia de `id_alerta` (no por el estado ACTIVA); lo confirma o descarta API-174-04 / API-174-05.',
  ],
});
