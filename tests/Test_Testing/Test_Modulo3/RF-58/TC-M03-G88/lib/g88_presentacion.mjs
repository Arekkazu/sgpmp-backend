// Presentación del intento 9. No modifica comprobaciones, oráculos ni veredictos.
// Las incidencias históricas se muestran solo para el RUN que las acreditó.
import { CASOS } from './g88_catalogo.mjs';
const RUN_9 = 'RUN-G88-V1-20261025-020636';
const casos = ['169', '170', '171', '172', '180', '266'];
const ev = (ruta, texto = ruta) => `[${texto}](./${ruta})`;

function incidencia(x) {
  const campos = [
    ['Identificador y título', `${x.id} — ${x.titulo}`], ['Caso', x.caso],
    ['Requerimiento', x.requisito], ['Componente', x.componente],
    ['Responsable inicial', x.responsable], ['Tipo', x.tipo],
    ['Severidad y fundamento', x.severidad], ['Funcionamiento evaluado', x.funcionamiento],
    ['Precondiciones', x.precondiciones], ['Pasos concretos', x.pasos],
    ['Resultado esperado', x.esperado], ['Resultado obtenido', x.obtenido],
    ['Evidencia precisa', x.evidencia], ['Impacto', x.impacto],
    ['Causa confirmada e hipótesis', x.causa], ['Acción correctiva solicitada', x.accion],
    ['Criterio de acreditación', x.criterio], ['Estado actual', x.estado],
  ];
  return `### ${x.id} — ${x.titulo}\n\n${campos.map(([n, v], i) => `${i + 1}. **${n}:** ${v}`).join('\n\n')}\n`;
}

function incidenciasRun9() {
  const comunes = {
    requisito: 'RF-58, CA-2/CA-16: clasificación según umbral M09 y tolerancia T por defecto.',
    componente: 'Ingesta, clasificación y GET /iot/monitoreo/dashboard.',
    responsable: 'Desarrollo; primera discrepancia comprobada en la API pública. Causa raíz pendiente.',
    tipo: 'Defecto funcional',
    precondiciones: 'Sensor 552, especie 126, umbral M09 existente 15–30, T por defecto 1,5; lecturas de prueba aceptadas.',
    causa: 'Confirmado: el dashboard no reflejó los valores de las lecturas aceptadas. Hipótesis: tratamiento de calidad FUERA_DE_RANGO o conservación de la última lectura válida, patrón REF-G87-01; requiere contrastar clasificación y persistencia. No se confirma la causa técnica.',
    accion: 'Revisar el flujo de ingesta, calidad de lectura, cálculo con T y selección de valor/estado del dashboard; corregir la discrepancia sin modificar el oráculo RF-58.',
    criterio: 'Con la misma semilla y umbral, cada lectura aceptada se muestra con su valor y color exigido en GET dashboard; corroborar con historial/calidad y una nueva comprobación autorizada.',
    estado: 'RECHAZADO/OK en el intento 9; incidencia abierta para Desarrollo.',
  };
  const desarrollo = [
    incidencia({ ...comunes, id: 'DEV-170', titulo: 'AMARILLO no reflejado tras cuatro lecturas aceptadas', caso: 'TC-M03-170',
      severidad: 'ALTA, CONFIRMADA en su efecto: cuatro valores de tolerancia no se muestran y el monitoreo mantiene el valor/color anterior.',
      funcionamiento: 'Bandas inmediatas externas a 15–30 con T=1,5; entradas 13,65; 14,85; 30,15; 31,35.',
      pasos: 'Ingerir secuencialmente las cuatro lecturas por POST /iot/telemetria y consultar GET dashboard después de cada una.',
      esperado: 'Las cuatro lecturas deben figurar como AMARILLO con su valor actual, conforme a la sustitución de datos RF-17 documentada en el RUN.',
      obtenido: 'Los cuatro POST dieron HTTP 201; cada GET devolvió último valor 30 y VERDE, correspondiente a la lectura anterior.',
      evidencia: `Comprobaciones API-170-02..05 en ${ev('resultado.json')}; ${[0,1,2,3].map(n => ev(`newman/newman-TC-M03-170-${n}.json`)).join(', ')}.`,
      impacto: 'El tablero puede ocultar condiciones de precaución tras ingesta aceptada; afecta la lectura operativa de cuatro escenarios.',
    }),
    incidencia({ ...comunes, id: 'DEV-171', titulo: 'ROJO no reflejado tras dos lecturas aceptadas', caso: 'TC-M03-171',
      severidad: 'ALTA, CONFIRMADA en su efecto: dos condiciones fuera de T permanecen visualmente VERDE.',
      funcionamiento: 'Entradas 13,35 y 31,65, situadas más allá de 15−1,5 y 30+1,5.',
      pasos: 'Ingerir ambas lecturas por POST /iot/telemetria y consultar GET dashboard tras cada POST.',
      esperado: 'Valor vigente y estado ROJO para ambas lecturas.',
      obtenido: 'Ambos POST HTTP 201; dashboard mantuvo 30 VERDE.',
      evidencia: `API-171-02..03 en ${ev('resultado.json')}; ${ev('newman/newman-TC-M03-171-0.json')}, ${ev('newman/newman-TC-M03-171-1.json')}.`,
      impacto: 'Una condición crítica de la variable no aparece como ROJO en el monitoreo.',
    }),
    incidencia({ id: 'DEV-266', titulo: 'El semáforo no se recalcula después de editar M09', caso: 'TC-M03-266',
      requisito: 'RF-58 restricción 4 y TC-M03-266: recálculo dinámico con la misma lectura.', componente: 'M09 y consulta de monitoreo.',
      responsable: 'Desarrollo; la primera discrepancia es API-266-02.', tipo: 'Defecto funcional',
      severidad: 'ALTA, CONFIRMADA en su efecto: una edición válida no actualiza la clasificación relevante.',
      funcionamiento: 'Umbral inicial 10–20; lectura 15, telemetría 117074; edición a 20–30 sin nueva ingesta.',
      precondiciones: 'Semilla 266 acreditada, lectura inicial 15 VERDE y umbral QA 91 creado dentro del RUN.',
      pasos: 'Consultar lectura inicial, enviar PATCH M09 a 20–30, volver a consultar el mismo sensor sin ingerir de nuevo.',
      esperado: 'El mismo valor 15 cambia a ROJO/AMARILLO según el oráculo de la matriz; PATCH correcto HTTP 200.',
      obtenido: 'PATCH HTTP 200; la misma lectura permaneció VERDE. El umbral QA 91 quedó REVERTIDO_VERIFICADO tras DELETE del RUN.',
      evidencia: `API-266-01/02, bitácora y cierre en ${ev('resultado.json')}; ${ev('newman/newman-TC-M03-266-lectura-final.json')}.`,
      impacto: 'El tablero puede conservar un estado obsoleto tras una reconfiguración M09.',
      causa: 'Confirmado: ausencia de recálculo observable después del PATCH. Hipótesis de origen no determinada; el PATCH y el rollback sí funcionaron según sus comprobaciones.',
      accion: 'Revisar el disparador/cálculo de estado al editar umbral y actualizar el dashboard para la lectura existente.',
      criterio: 'Con 15 VERDE bajo 10–20, PATCH 20–30 HTTP 200 y sin nueva ingesta, GET dashboard cambia a ROJO/AMARILLO; verificar rollback aparte.',
      estado: 'RECHAZADO/OK; corrección pendiente.',
    }),
    incidencia({ id: 'DEV-172-T', titulo: 'La API M09 no expone tolerancia T configurable', caso: 'TC-M03-172',
      requisito: 'RF-58: T configurada en M09 prevalece sobre 10 % por defecto; escenario 20–30, T=2, lecturas 18,5 y 31,5.',
      componente: 'GET /configuracion/umbrales y contrato M09.', responsable: 'Desarrollo; primera discrepancia API-172-A.', tipo: 'Hallazgo funcional acreditado, sin veredicto integral del caso.',
      severidad: 'MEDIA, CONFIRMADA para la respuesta API: falta configurabilidad visible; el caso completo requiere UI.',
      funcionamiento: 'Inspección de campos del umbral y de sus niveles en la especie/variable del caso.',
      precondiciones: 'Umbral M09 consultable; API respondió HTTP 200.', pasos: 'Consultar umbrales M09 y examinar campos del objeto y de niveles; intentar abrir formulario UI-172.',
      esperado: 'API y formulario permiten configurar T=2 y prevalece sobre T=1 por defecto.',
      obtenido: 'API-172-A devolvió campos de umbral y niveles sin T. UI-172 terminó antes del formulario por excepción de la aplicación.',
      evidencia: `${ev('newman/newman-TC-M03-172-consulta.json')}; API-172-A y UI-172 en ${ev('resultado.json')}; ${ev('cypress/UI-172.json')}.`,
      impacto: 'No se pudo acreditar el escenario con T configurada y la API observada no la expone.',
      causa: 'Confirmada la ausencia del campo en la respuesta examinada. La razón de diseño o implementación no está determinada; el fallo de UI es separado.',
      accion: 'Aportar contrato público y configuración efectiva de T en M09; corregir API/UI si la ausencia se reproduce.',
      criterio: 'GET/edición pública exponen T y un RUN autorizado comprueba 18,5 y 31,5 AMARILLO con T=2, incluida UI.',
      estado: 'ERROR_QA sin veredicto funcional completo; hallazgo API pendiente de Desarrollo.',
    }),
    incidencia({ id: 'DEV-180', titulo: 'NH3 sin umbral aparece VERDE y no genera aviso', caso: 'TC-M03-180',
      requisito: 'RF-58 CA-12/E7: variable sin umbral visible en GRIS, etiqueta “Sin umbral configurado” y aviso al Administrador.',
      componente: 'Ingesta, dashboard y notificaciones.', responsable: 'Desarrollo; discrepancias API-180-03/04.', tipo: 'Hallazgo funcional acreditado, caso sin veredicto integral.',
      severidad: 'ALTA, CONFIRMADA para API: presentación y aviso requeridos fallan; UI no concluyó.',
      funcionamiento: 'NH3 del sensor 737 sin umbral activo para especie 126; lectura 5 ppm.',
      precondiciones: 'Semilla 737/357/522/69 acreditada; lectura NH3 aceptada HTTP 201.',
      pasos: 'Comprobar ausencia de umbral NH3, ingerir 5 ppm, consultar dashboard y notificaciones Administrador.',
      esperado: 'Dashboard muestra 5 ppm, GRIS, etiqueta y variable visible; llega aviso al Administrador.',
      obtenido: 'GET devolvió 5 ppm VERDE; la API no expone etiqueta; nuevas notificaciones sobre umbral: 0. La UI no pudo comprobarse.',
      evidencia: `API-180-01..04 en ${ev('resultado.json')}; ${ev('newman/newman-TC-M03-180-0.json')}.`,
      impacto: 'La ausencia de configuración se presenta como estado normal y el Administrador no recibe el aviso requerido.',
      causa: 'Confirmados los resultados API. Causa técnica no determinada; el HTTP 500 del login UI es un impedimento distinto.',
      accion: 'Corregir clasificación, etiqueta y aviso de variable sin umbral; revisar por separado acceso UI.',
      criterio: 'API devuelve GRIS y aviso, y Cypress acredita tarjeta visible con 5 ppm, unidad y etiqueta en un RUN autorizado.',
      estado: 'ERROR_QA sin veredicto integral por UI incompleta; hallazgos API abiertos.',
    }),
    incidencia({ id: 'DEV-172-UI', titulo: 'Excepción de aplicación interrumpe UI-172 antes del formulario', caso: 'TC-M03-172',
      requisito: 'RF-58/TC-M03-172 exige comprobación de T en formulario M09.', componente: 'Frontend, carga inicial del dashboard y GET /configuracion/personalizacion/dashboard/datos.',
      responsable: 'Desarrollo, atención inicial frontend; origen exacto pendiente.', tipo: 'Incidencia técnica de aplicación.',
      severidad: 'MEDIA, CONFIRMADA para la interrupción; impide comprobar solo la UI del caso.',
      funcionamiento: 'Cypress inicia sesión Administrador y navega hacia el formulario M09.',
      precondiciones: 'UI-172 inició con cabecera RUN; operaciones registradas de login y GET de lectura.',
      pasos: 'Abrir UI-172 en dashboard y avanzar hacia edición de umbral sin guardar.',
      esperado: 'Formulario M09 accesible para inspeccionar T.', obtenido: 'Una promesa rechazada no capturada ligada a GET de personalización cortó la prueba antes del formulario.',
      evidencia: `${ev('cypress/UI-172.json')}, ${ev('cypress/UI-172.log')}, ${ev('cypress/UI-172-operaciones.json')}.`,
      impacto: 'UI-172 sin comprobación funcional; distinto del login Productor con RLS de UI-180.',
      causa: 'Confirmada la excepción en Cypress. Su origen en aplicación/interceptor o respuesta de backend no se aisló con el resumen conservado.',
      accion: 'Investigar la petición y el manejo de rechazo en frontend; conservar código HTTP y traza saneada en la siguiente validación.',
      criterio: 'La UI llega al formulario M09 sin excepción; Cypress ejecuta su aserción real de T.',
      estado: 'ERROR_QA; incidencia abierta para Desarrollo.',
    }),
  ];
  const dba = [
    incidencia({ id: 'DBA-01', titulo: 'Violación RLS al alternar identidades en una Session del sandbox', caso: 'TC-M03-180 (acceso UI); TC-M03-172 como contraste de identidad',
      requisito: 'Sandbox QA debe aislar escrituras de un RUN y permitir peticiones de usuarios diferentes con RLS vigente.',
      componente: 'SQLAlchemy Session del sandbox, contexto PostgreSQL y política RLS de modulo1.sesiones.',
      responsable: 'DBA; Desarrollo apoya el cambio del ciclo de Session/identidad.', tipo: 'Incidencia técnica de entorno.',
      severidad: 'ALTA, CONFIRMADA para el rechazo RLS informado y PROBABLE para la herencia de identidad; impide cerrar UI-180.',
      funcionamiento: 'testing_sandbox.py conserva una Session/conexión/transacción por RUN; database.py guarda identidad en Session.info y la reaplica en after_begin. declarar_identidad_si_anonima no sustituye una identidad previa.',
      precondiciones: 'Última petición Bearer directa antes de Cypress como Administrador; UI-172 inicia con Administrador y UI-180 intenta iniciar con QA_PROD_UI.',
      pasos: 'En un RUN aislado, autenticar Administrador, ejecutar GET Bearer; después POST /sesiones/ como Productor UI con cabecera RUN. Repetir en orden inverso y con mismo usuario.',
      esperado: 'Cada petición usa su propia identidad RLS y POST /sesiones/ inserta únicamente la sesión de la cuenta autenticada.',
      obtenido: 'UI-180 POST /sesiones/ respondió HTTP 500 en 399 ms con cabecera RUN; UI-172 llegó más lejos. Log comunicado por Desarrollo: InfrastructureError [ERROR_INTERNO], ProgrammingError psycopg2.errors.InsufficientPrivilege: new row violates row-level security policy for table “sesiones”.',
      evidencia: `${ev('cypress/UI-180-solicitudes.json')}, ${ev('cypress/UI-180.json')}, ${ev('resultado.json')}; anexo técnico entregado al DBA por la orquestación QA (HALLAZGO-G88-RLS-SANDBOX y REGRESION-RLS-SANDBOX-PROPUESTA). El log fue comunicado, no se conserva como archivo del RUN.`,
      impacto: 'Login Productor UI bloqueado; no se ejecutan las aserciones de tarjeta sin umbral. Riesgo de contaminación entre usuarios del mismo RUN.',
      causa: 'Confirmado por el log comunicado: violación RLS en INSERT de sesiones. Hipótesis sólida no confirmada en TEST: Session.info heredó identidad Administrador al procesar login Productor; falta traza de identidad efectiva y política desplegada.',
      accion: 'DBA y Desarrollo deben observar identidad efectiva por petición, impedir herencia y reinicializar app.current_user_id, app.current_role y app.usuario_id; login anónimo debe adoptar la identidad autenticada. Conservar políticas RLS, sin BYPASSRLS ni relajación.',
      criterio: 'En PostgreSQL/RLS reales: Administrador→Productor, Productor→Administrador y login repetido del mismo usuario; sin 500 ni contaminación, rollback comprobado y corrección desplegada en TEST confirmada.',
      estado: 'Abierta; hipótesis de mecanismo PROBABLE. Requiere validación de DBA y apoyo de Desarrollo antes de otro RUN QA.',
    }),
    incidencia({ id: 'DBA-02', titulo: 'Esperas al mezclar peticiones dentro y fuera de la transacción del RUN', caso: 'Antecedentes intentos 5–8; no observado en intento 9',
      requisito: 'Aislamiento de RUN sin bloquear accesos de la misma cuenta en contextos paralelos.', componente: 'Transacciones PostgreSQL, ultimo_acceso y dependencia de autenticación.',
      responsable: 'DBA; Desarrollo apoya revisión del código de autenticación.', tipo: 'Incidencia técnica de entorno.',
      severidad: 'MEDIA, PROBABLE para el mecanismo: los timeouts históricos impedían casos; mitigación comprobada en intento 9.',
      funcionamiento: 'dependencies.py:149-151 actualiza y confirma ultimo_acceso por petición autenticada; la transacción externa del sandbox retiene bloqueos hasta el cierre.',
      precondiciones: 'Misma cuenta usada en peticiones autenticadas dentro y fuera del RUN.',
      pasos: 'Comparar latencias de peticiones a asociaciones, dashboard y umbrales con la misma cuenta, primero mezclando contextos y después serializando todo dentro del RUN.',
      esperado: 'Peticiones completadas sin espera de bloqueo y aislamiento intacto.',
      obtenido: 'Intentos 5–8 registraron timeouts de 30 s en rutas distintas; en intento 9 no se repitieron después de mantener las peticiones autenticadas dentro del RUN.',
      evidencia: `${ev('../../README.md', 'historial G88')}; el análisis de transacciones se resume en funcionamiento, resultado obtenido y causa de esta incidencia; ${ev('resultado.json')} del intento 9 para ausencia de nuevo timeout.`,
      impacto: 'Puede bloquear comprobaciones de otros grupos QA si mezclan contextos para una misma cuenta.',
      causa: 'Confirmado: timeouts históricos y mitigación de secuencia en G88. Hipótesis de bloqueo por ultimo_acceso sustentada en código local; no hay traza de locks de PostgreSQL.',
      accion: 'Revisar retención de bloqueo y diseño de actualización de ultimo_acceso con Desarrollo; establecer pauta para otros grupos.',
      criterio: 'Prueba controlada en PostgreSQL real sin esperas de 30 s al alternar contexto y con rollback conservado.',
      estado: 'Mitigado en G88 intento 9; revisión preventiva pendiente, sin bloqueo activo demostrado.',
    }),
    incidencia({ id: 'DBA-03', titulo: 'Session compartida expuesta a concurrencia y cierre con peticiones activas', caso: 'Riesgo transversal G88; no atribuido a 172 ni 180',
      requisito: 'Sandbox QA debe proteger integridad de transacción y cierre seguro bajo peticiones simultáneas.',
      componente: 'testing_sandbox.py, conexión y Session compartidas; ciclo de petición y cancelación.',
      responsable: 'DBA con apoyo de Desarrollo para sincronización y ciclo de vida.', tipo: 'Incidencia técnica de diseño; riesgo no demostrado como fallo.',
      severidad: 'MEDIA, certeza NO DETERMINADA como fallo: una carrera podría comprometer aislamiento, sin ocurrencia acreditada en el intento 9.',
      funcionamiento: 'sandbox_lock protege el registro; no serializa todo el uso posterior de Session. El cierre puede coincidir con peticiones activas; cancelar cliente no prueba cancelación de servidor.',
      precondiciones: 'Peticiones simultáneas o cliente que aborta mientras el servidor conserva trabajo.',
      pasos: 'En entorno aislado, instrumentar dos peticiones concurrentes sobre un RUN y un cierre mientras una sigue activa; repetir con aborto del cliente.',
      esperado: 'Acceso serializado o transacciones independientes seguras; DELETE espera o cancela trabajo y rollback se acredita.',
      obtenido: 'Solo riesgo deducido de código local; no se observó carrera, cierre inseguro ni nexo causal con UI-172/180.',
      evidencia: `Anexo técnico entregado al DBA por la orquestación QA (HALLAZGO-G88-RLS-SANDBOX y REGRESION-RLS-SANDBOX-PROPUESTA); rutas locales testing_sandbox.py:23-80/database.py:182-198; sin evidencia de ejecución concurrente en TEST.`,
      impacto: 'Potencial contaminación/cierre incompleto en RUN de varios usuarios o navegador concurrente.',
      causa: 'Confirmado en código: candado limitado al registro y Session compartida. Hipótesis de fallo efectivo no determinada.',
      accion: 'DBA y Desarrollo deben revisar modelo de transacciones, conexiones, concurrencia, cancelación del servidor y cierre seguro.',
      criterio: 'Regresión en PostgreSQL/RLS real con simultaneidad, aborto y DELETE: identidades aisladas, sin uso de Session cerrada y rollback verificado.',
      estado: 'Riesgo de diseño abierto; no usarlo como explicación del 500 o de UI-172.',
    }),
  ];
  const adicional = incidencia({ id: 'DEV-RF61-A', titulo: 'Once lecturas sin vinculación al activo acreditado', caso: 'TC-M03-169/170/171/180/266; hallazgo independiente',
    requisito: 'RF-61-A vinculación de telemetría al activo aplicable; no altera oráculos RF-58.', componente: 'GET /iot/vinculaciones y asociación telemetría-activo.',
    responsable: 'Desarrollo, primera discrepancia en API pública; causa raíz sin atribuir.', tipo: 'Hallazgo adicional.',
    severidad: 'MEDIA, PROBABLE: once lecturas sin vínculo reducen trazabilidad; falta evaluación específica RF-61-A.',
    funcionamiento: 'Lecturas 117064–117073 con activo 884 en área 349; 117074 con activo 885 en área 504.',
    precondiciones: 'Activos únicos vinculables y lecturas aceptadas según semilla del intento 9.',
    pasos: 'Ingerir lecturas del escenario y consultar GET /iot/vinculaciones por cada id_telemetria.',
    esperado: 'Cada lectura vinculada al activo aplicable.', obtenido: 'Las once consultas registraron SIN_VINCULACION, sin activo ni área, cero registros.',
    evidencia: `${ev('resultado.json')} → hallazgos_producto, entradas 169a–c, 170a–d, 171a–b, 180 y 266.`,
    impacto: 'Trazabilidad RF-61-A posiblemente incompleta; los veredictos RF-58 permanecen independientes.',
    causa: 'Confirmadas las respuestas de vínculo; aplicabilidad y causa de RF-61-A requieren evaluación propia.',
    accion: 'Revisar vinculación y abrir evaluación RF-61-A separada.',
    criterio: 'Lecturas equivalentes devuelven vínculo al activo esperado por API pública en una evaluación autorizada de RF-61-A.',
    estado: 'Hallazgo adicional único, pendiente; sin cambio de veredictos G88.',
  });
  return { desarrollo, dba, adicional };
}

export function generarPresentacionG88(r) {
  const es9 = r.run_id === RUN_9;
  if (!es9) return generarPresentacionGeneral(r);
  const estado = (r.casos?.['TC-M03-172']?.veredicto_funcional == null || r.casos?.['TC-M03-180']?.veredicto_funcional == null)
    ? 'ÚLTIMO RUN CONSERVADO — EVALUACIÓN NO OFICIAL / PENDIENTE DE CIERRE FUNCIONAL'
    : 'EVALUACIÓN V1 — CIERRE FUNCIONAL PENDIENTE DE REVISIÓN QA';
  const L = [`# TC-M03-G88 — ${estado}`, '', '## 1. Identificación del RUN', '',
    `Grupo TC-M03-G88; RF-58; V${r.version}; RUN ${r.run_id}; intento ${r.intento}; operación ${r.operacion}; autorización ${r.referencia}.`,
    `Inicio ${r.inicio}; fin ${r.fin}; ambiente ${r.ambiente}; commit local/desplegado ${r.commit ?? 'NO VERIFICADO'}.`,
    `Herramientas verificadas: Node ${r.herramientas?.node ?? 'no consta'}, Newman con JSON/HTML conservados, Cypress ${r.herramientas?.cypress ?? 'no consta'}.`, '',
    '## 2. Alcance y ambiente', '',
    'Se evaluaron TC-M03-169, 170, 171, 172, 180 y 266 en TEST mediante API pública y Cypress donde la matriz exige UI. Fuente de oráculos: fila TC-M03-G88 de Casos_Prueba(Modulo3 Agrupado).csv. Para DBA se consultaron realmente src/shared/database.py, src/shared/rollback/infraestructure/testing_sandbox.py y testing_middlaware.py, src/identity_access/infrastructure/dependencies.py y las migraciones RLS 8d80fb56a30b_rls_modulo1.py y 98389cebef99_f5.py. Estas lecturas locales no acreditan despliegue en TEST.',
    'La matriz usa ejemplos 35–39 para 169 y 20–30/T=1 para 170–171. El intento 9 sustituyó solo datos de entrada por el umbral M09 existente 15–30, T=1,5, según bitácora RF-17: 169=15/22,5/30; 170=13,65/14,85/30,15/31,35; 171=13,35/31,65. Se preservan los colores exigidos VERDE/AMARILLO/ROJO. Los niveles RF-17 observados (normal 20–30, precaución 19–20, crítico 15–19) pueden requerir conciliación con la fórmula RF-58 para valores inferiores; no se alteran los valores observados ni los veredictos históricos.', '',
    '## 3. Resumen ejecutivo', '',
    'Intento 9: un APROBADO, tres RECHAZADOS y dos casos ERROR_QA sin veredicto funcional completo. No es un cierre oficial de G88. Los ocho intentos anteriores y sus motivos constan en [historial](../../README.md).', '',
    '## 4. Veredictos de los seis casos', '',
    '| Caso | Veredicto funcional | Estado técnico | Fundamento breve |', '| --- | --- | --- | --- |'];
  const fundamentos = {
    '170': 'Lecturas 13,65; 14,85; 30,15; 31,35 aceptadas (HTTP 201); dashboard conservó 30 VERDE en vez de AMARILLO (DEV-170).',
    '171': 'Lecturas 13,35 y 31,65 aceptadas (HTTP 201); dashboard conservó 30 VERDE en vez de ROJO (DEV-171).',
    '180': 'API: NH3 5 ppm aceptado (HTTP 201), VERDE en vez de GRIS y sin notificación (DEV-180); UI no evaluable: login Productor HTTP 500 por violación RLS en modulo1.sesiones (DBA-01).',
  };
  for (const n of casos) {
    const c = r.casos?.[`TC-M03-${n}`] ?? {};
    L.push(`| TC-M03-${n} | ${c.veredicto_funcional ?? 'sin veredicto'} | ${c.estado_tecnico ?? 'no consta'} | ${fundamentos[n] ?? c.motivo ?? 'no consta'} |`);
  }
  L.push('', '## 5. Esperado y observado por caso', '');
  const observado = {
    '169': 'Con umbral ejecutado 15–30, POST 201 y GET 200 mostraron 15, 22,5 y 30 VERDE.',
    '170': 'POST 201 para 13,65; 14,85; 30,15; 31,35. Cada dashboard GET 200 conservó 30 VERDE.',
    '171': 'POST 201 para 13,35 y 31,65. Cada dashboard GET 200 conservó 30 VERDE.',
    '172': 'GET umbrales HTTP 200 mostró valor_min, valor_max y niveles sin campo T; UI-172 falló antes de llegar al formulario.',
    '180': 'NH3 5 ppm aceptado HTTP 201; dashboard GET 200 mostró 5 ppm VERDE, sin etiqueta expuesta por API; cero nuevas notificaciones. UI-180 no completó acceso.',
    '266': 'Telemetría 117074 de valor 15 estuvo VERDE bajo 10–20. PATCH M09 a 20–30 dio HTTP 200; sin nueva ingesta, el dashboard siguió VERDE.',
  };
  const esperado = {
    '169': 'Con 15–30 ejecutado, 15, 22,5 y 30 VERDE, conservando bordes inclusivos de la matriz.',
    '170': 'Con T=1,5, los cuatro valores sustituidos en la banda de tolerancia AMARILLO.',
    '171': 'Con T=1,5, ambos valores fuera de la banda ROJO.',
    '172': 'T=2 configurable en M09 y prevalente sobre T=1 del ejemplo 20–30; 18,5 y 31,5 AMARILLO, con UI y API.',
    '180': 'NH3 5 ppm visible con unidad, GRIS, etiqueta “Sin umbral configurado” y notificación Administrador.',
    '266': '15 VERDE con 10–20; después de PATCH a 20–30, misma lectura ROJO/AMARILLO sin nueva ingesta.',
  };
  for (const n of casos) L.push(`### TC-M03-${n}`, '', `Esperado: ${esperado[n]}`, '', `Observado: ${observado[n]}`, '');
  L.push('## 6. Comprobaciones API y Cypress', '',
    'API: 169 API-169-01..04 aprobadas; 170 API-170-02..05 rechazadas; 171 API-171-02..03 rechazadas; 172 API-172-A rechazó ausencia de T; 180 API-180-03 y 04 rechazadas pese a ingesta y sensor acreditados; 266 API-266-01 aprobada y 02 rechazada. Detalle sin truncar en resultado.json y JSON Newman de cada caso.',
    'Cypress: UI-172 ejecutó 1 prueba, 1 fallida por promesa rechazada no capturada relacionada con GET /configuracion/personalizacion/dashboard/datos; no llegó al formulario M09. UI-180 ejecutó 4 pruebas, 4 fallidas: la precondición de login Productor recibió HTTP 500 frente a 200 y las tres aserciones de tarjeta no encontraron el control requerido. La captura real muestra la ausencia de tarjeta; no acredita GRIS ni etiqueta.', '',
    '## 7. Incidencias funcionales de Desarrollo', '');
  if (es9) L.push(...incidenciasRun9().desarrollo);
  else L.push('Para un RUN posterior, derivar incidencias solo de sus comprobaciones reales; el intento 9 se documenta por separado.', '');
  L.push('## 8. Incidencias técnicas del DBA', '');
  if (es9) L.push(...incidenciasRun9().dba);
  else L.push('Sin incidencia técnica DBA acreditada en este resultado; revisar evidencias propias del RUN.', '');
  L.push('## 9. Casos sin veredicto funcional — impedimentos técnicos', '',
    'TC-M03-172 permanece ERROR_QA: API-172-A acredita ausencia de T en la respuesta consultada, pero UI-172 se interrumpió por la excepción de la aplicación durante GET de personalización antes del formulario M09. Atención inicial Desarrollo/frontend. No se confunde con el error RLS de 180.',
    'TC-M03-180 permanece ERROR_QA: ingesta y API acreditan discrepancias de GRIS/aviso; la UI dependía del login QA_PROD_UI, que devolvió HTTP 500. El log comunicado atribuye el 500 a violación RLS de modulo1.sesiones; atención inicial DBA con apoyo de Desarrollo. Cuatro pruebas Cypress fallidas no constituyen comprobación satisfactoria de tarjeta, etiqueta y unidad.', '',
    '## 10. Hallazgos adicionales', '');
  if (es9) L.push(incidenciasRun9().adicional);
  L.push('## 11. Evidencias', '',
    `${ev('resultado.json')} y ${ev('contexto_operacion.json')} identifican el intento y sus comprobaciones. ${ev('newman/newman-G88-consolidado.html')} es el HTML consolidado; se conservan doce JSON Newman individuales por caso.`,
    `Cypress conserva ${ev('cypress/UI-172.json')}, ${ev('cypress/UI-172.log')}, ${ev('cypress/UI-180.json')}, ${ev('cypress/UI-180.log')}, ${ev('cypress/UI-172-operaciones.json')}, ${ev('cypress/UI-180-solicitudes.json')} y ${ev('cypress/g88.cy.js/TC-M03-180_sin_tarjeta.png')}. Las dos trazas JSON y la captura fueron reubicadas desde _cypress_capturas/ por el defecto de salida corregido en ORD-G88-038; su contenido no se modificó.`,
    'El log de PostgreSQL citado en DBA-01 fue comunicado por Desarrollo; no consta como archivo del RUN y no se presenta como evidencia adjunta.', '',
    '## 12. Cierre y rollback', '',
    `DELETE del RUN HTTP ${r.cierre?.cierre_http ?? 'no consta'}; verificación ${r.cierre?.rollback?.verificado ? 'CONFIRMADA' : 'NO CONFIRMADA'}. Resultado guardado: ${r.cierre?.rollback?.conclusion ?? 'no consta'}. Umbral QA 91: ${r.cierre?.rollback?.umbral_run_266?.estado ?? 'no consta'}. Las comparaciones API de asociaciones, dashboard, umbrales e historiales figuran en resultado.json. Este cierre no acredita corrección funcional ni descarta efectos fuera de la transacción.`, '',
    '## 13. Estado final y condiciones pendientes', '',
    'ÚLTIMO RUN CONSERVADO — EVALUACIÓN NO OFICIAL / PENDIENTE DE CIERRE FUNCIONAL. G88 requiere atención de Desarrollo a las discrepancias RF-58 y de DBA con Desarrollo al sandbox RLS, más acceso UI completo para 172/180. Una nueva evaluación solo corresponde al lanzador externo con autorización humana específica; este informe no altera resultado.json ni convierte los hallazgos API en veredictos integrales.', '');
  return L.join('\n');
}

function resumenObservado(check) {
  const s = String(check?.observado ?? 'sin observación registrada').replace(/[\r\n]+/g, ' ');
  // Evita recortar objetos JSON: conserva la comprobación y remite al dato nativo.
  return s.length > 300 ? `respuesta extensa en resultado.json, comprobación ${check.id}` : s;
}

function incidenciaGenerica(r, id, check, { tecnico = false } = {}) {
  const n = id.slice(-3);
  const c = r.casos?.[id] ?? {};
  const evidencia = (r.evidencias ?? []).filter(x => x.startsWith(`newman/newman-${id}-`)
    || x.startsWith(`cypress/UI-${n}`) || x.startsWith(`cypress/TC-M03-${n}`));
  const tipo = tecnico ? 'Incidencia técnica de aplicación/automatización según la comprobación guardada'
    : c.veredicto_funcional === 'RECHAZADO' ? 'Defecto funcional comprobado'
      : 'Hallazgo funcional con caso sin veredicto integral';
  const titulo = {
    '170': 'AMARILLO no reflejado por el dashboard', '171': 'ROJO no reflejado por el dashboard',
    '172': tecnico ? 'UI-172 interrumpida antes de evaluar T' : 'Configuración de T no acreditada por API',
    '180': tecnico ? 'UI-180 sin comprobación funcional completa' : 'Variable sin umbral no cumple GRIS/aviso',
    '266': 'Recálculo dinámico no reflejado tras M09',
  }[n] ?? 'Discrepancia de semáforo';
  const responsable = tecnico ? 'Desarrollo, primer contacto por la comprobación UI; origen técnico por determinar.'
    : 'Desarrollo, primera discrepancia en API pública; causa raíz no determinada.';
  return incidencia({ id: `DEV-${n}${tecnico ? '-UI' : ''}`, titulo, caso: id,
    requisito: `RF-58, oráculo ${id}: ${CASOS[id]?.esperado ?? 'consultar matriz TC-M03-G88'}`,
    componente: tecnico ? 'UI Cypress y ruta de la comprobación indicada' : 'API de ingesta, M09 y/o dashboard según la comprobación indicada',
    responsable, tipo,
    severidad: `${(r.incidencias ?? []).find(x => x.caso === id)?.severidad ?? 'MEDIA'}, certeza ${check?.estado === 'RECHAZADO' ? 'CONFIRMADA para el resultado observado' : 'NO DETERMINADA'}; impacto delimitado al caso y comprobación ${check?.id ?? 'sin ID'}.`,
    funcionamiento: `Comprobación ${check?.id ?? 'no registrada'} de ${id}; fuente ${check?.fuente ?? 'no consta'}.`,
    precondiciones: (r.comprobaciones ?? []).filter(x => x.caso === id && x.tipo === 'PRE')
      .map(x => `${x.id}=${x.estado}`).join('; ') || 'No constan PRE específicas; consultar resultado.json.',
    pasos: `Reproducir las entradas de ${id} registradas en resultado.json y consultar la API/UI de ${check?.id ?? 'la comprobación pendiente'} dentro de un RUN autorizado.`,
    esperado: CASOS[id]?.esperado ?? 'Consultar matriz original.',
    obtenido: check ? `${check.id} ${check.estado}: ${resumenObservado(check)}` : 'No consta ejecución suficiente.',
    evidencia: [check ? `${ev('resultado.json')} → ${check.id}` : ev('resultado.json'), ...evidencia.map(x => ev(x))].join('; '),
    impacto: tecnico ? `Impide concluir la comprobación UI de ${id}.` : `Afecta el comportamiento RF-58 del caso ${id}; alcance fuera del RUN no determinado.`,
    causa: 'Confirmado solo el resultado público indicado. Causa técnica no determinada; toda explicación de implementación requiere investigación separada.',
    accion: tecnico ? 'Investigar la interrupción UI y ejecutar su comprobación completa.' : 'Investigar y corregir la discrepancia manteniendo el oráculo de la matriz.',
    criterio: `Repetir ${id} por API y, si exige UI, Cypress; todas sus comprobaciones obligatorias deben registrar esperado y observado concordantes.`,
    estado: `${c.veredicto_funcional ?? 'sin veredicto'}/${c.estado_tecnico ?? 'no consta'} en ${r.run_id}.`,
  });
}

function generarPresentacionGeneral(r) {
  const ids = casos.map(n => `TC-M03-${n}`);
  const sinVeredicto = ids.filter(id => r.casos?.[id]?.veredicto_funcional == null);
  const noOficial = sinVeredicto.length > 0;
  const L = [`# TC-M03-G88 — ${noOficial ? 'EVALUACIÓN NO OFICIAL / PENDIENTE DE CIERRE FUNCIONAL' : `EVALUACIÓN V${r.version ?? '?'}`}`, '',
    '## 1. Identificación del RUN', '',
    `Grupo ${r.grupo ?? 'TC-M03-G88'}; RF ${r.rf ?? 'RF-58'}; V${r.version ?? '?'}; RUN ${r.run_id ?? 'no consta'}; intento ${r.intento ?? 'no consta'}; autorización ${r.referencia ?? 'no consta'}.`,
    `Ambiente ${r.ambiente ?? 'no consta'}; inicio ${r.inicio ?? 'no consta'}; fin ${r.fin ?? 'no consta'}; commit ${r.commit ?? 'NO VERIFICADO'}; herramientas ${Object.entries(r.herramientas ?? {}).map(([k,v])=>`${k}: ${v}`).join('; ') || 'no consta'}.`, '',
    '## 2. Alcance y ambiente', '',
    'Se conservan los oráculos de la fila TC-M03-G88 de la matriz Casos_Prueba(Modulo3 Agrupado).csv. Los datos sustituidos, si los hubo, figuran en la bitácora del resultado. Las lecturas de código local no acreditan el estado de TEST.', '',
    '## 3. Resumen ejecutivo', '',
    `${ids.filter(id => r.casos?.[id]?.veredicto_funcional === 'APROBADO').length} APROBADO, ${ids.filter(id => r.casos?.[id]?.veredicto_funcional === 'RECHAZADO').length} RECHAZADO y ${sinVeredicto.length} sin veredicto funcional. ${noOficial ? 'Evaluación no oficial por casos pendientes.' : 'Requiere revisión QA antes de cierre.'}`, '',
    '## 4. Veredictos de los seis casos', '',
    '| Caso | Veredicto | Estado técnico | Motivo |', '| --- | --- | --- | --- |'];
  for (const id of ids) {
    const c = r.casos?.[id] ?? {};
    L.push(`| ${id} | ${c.veredicto_funcional ?? 'sin veredicto'} | ${c.estado_tecnico ?? 'no consta'} | ${String(c.motivo ?? 'no consta').replace(/\|/g, '/')} |`);
  }
  L.push('', '## 5. Esperado y observado por caso', '');
  for (const id of ids) {
    const checks = (r.comprobaciones ?? []).filter(x => x.caso === id && x.tipo === 'ASSERT');
    L.push(`### ${id}`, '', `Esperado: ${CASOS[id]?.esperado ?? 'consultar matriz'}`, '',
      `Observado: ${checks.map(x => `${x.id} ${x.estado}: ${resumenObservado(x)}`).join('; ') || 'sin comprobación registrada'}.`, '');
  }
  L.push('## 6. Comprobaciones API y Cypress', '',
    '| Caso | Comprobación | Fuente | Estado | Observado |', '| --- | --- | --- | --- | --- |');
  for (const x of r.comprobaciones ?? []) L.push(`| ${x.caso ?? '—'} | ${x.id ?? '—'} | ${x.fuente ?? '—'} | ${x.estado ?? '—'} | ${resumenObservado(x).replace(/\|/g, '/')} |`);
  for (const id of ids.filter(x => CASOS[x]?.ui?.length)) {
    const fase = r.cypress?.casos?.[id];
    L.push(`| ${id} | fase Cypress | UI | ${fase?.estado ?? 'NO_EJECUTADO'} | ${fase?.total_pruebas ?? 0} pruebas; ${fase?.fallidas ?? 0} fallidas; ${fase?.error ?? fase?.causa ?? 'sin detalle adicional'} |`);
  }
  L.push('', '## 7. Incidencias funcionales de Desarrollo', '');
  for (const id of ids) {
    const x = (r.comprobaciones ?? []).find(c => c.caso === id && c.estado === 'RECHAZADO' && c.naturaleza === 'PRODUCTO');
    if (x) L.push(incidenciaGenerica(r, id, x));
    const ui = (r.comprobaciones ?? []).find(c => c.caso === id && c.fuente === 'UI' && c.estado !== 'APROBADO');
    if (ui && r.casos?.[id]?.veredicto_funcional == null) L.push(incidenciaGenerica(r, id, ui, { tecnico: true }));
  }
  L.push('## 8. Incidencias técnicas del DBA', '',
    'Solo se incorporan incidencias técnicas DBA cuando existen hechos de entorno específicos y evidencia correlacionada en este RUN. Consultar resultado.json y el análisis técnico del grupo; no se trasladan automáticamente hipótesis de otros intentos.', '',
    '## 9. Casos sin veredicto funcional — impedimentos técnicos', '');
  for (const id of sinVeredicto) {
    const c = r.casos?.[id]; const ui = r.cypress?.casos?.[id];
    L.push(`- ${id}: ${c?.estado_tecnico ?? 'no consta'}; ${c?.motivo ?? 'motivo no registrado'}. API y UI se distinguen en las comprobaciones anteriores; Cypress ${ui?.estado ?? 'NO_EJECUTADO'}, ${ui?.total_pruebas ?? 0} pruebas, ${ui?.fallidas ?? 0} fallidas. Sin veredicto funcional hasta completar las comprobaciones obligatorias.`);
  }
  if (!sinVeredicto.length) L.push('Ninguno registrado.');
  L.push('', '## 10. Hallazgos adicionales', '');
  const hallazgos = r.hallazgos_producto ?? [];
  if (hallazgos.length) L.push(`RF-61-A: ${hallazgos.length} hallazgos de vínculo registrados en resultado.json; casos ${[...new Set(hallazgos.map(x => x.caso))].join(', ')}. Evaluación independiente, sin alterar veredictos RF-58.`, '');
  else L.push('No constan hallazgos adicionales.', '');
  L.push('## 11. Evidencias', '',
    `${(r.evidencias ?? []).map(x => ev(x)).join(', ') || 'No constan rutas de evidencia.'}`, '',
    '## 12. Cierre y rollback', '',
    `DELETE HTTP ${r.cierre?.cierre_http ?? 'no consta'}; rollback ${r.cierre?.rollback?.verificado === true ? 'CONFIRMADO' : 'NO CONFIRMADO'}; ${r.cierre?.rollback?.conclusion ?? 'sin conclusión'}. Código 0 por sí solo no confirma funcionalidad ni rollback.`, '',
    '## 13. Estado final y condiciones pendientes', '',
    `${noOficial ? 'EVALUACIÓN NO OFICIAL / PENDIENTE DE CIERRE FUNCIONAL.' : 'Evaluación pendiente de revisión QA.'} Requiere resolver incidencias y ejecutar solo las verificaciones autorizadas necesarias.`, '');
  return L.join('\n');
}
