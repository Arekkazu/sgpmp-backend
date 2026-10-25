# TC-M03-G88 — ÚLTIMO RUN CONSERVADO — EVALUACIÓN NO OFICIAL / PENDIENTE DE CIERRE FUNCIONAL

## 1. Identificación del RUN

Grupo TC-M03-G88; RF-58; V1; RUN RUN-G88-V1-20261025-020636; intento 9; operación REINTENTAR; autorización AUT-G88-V1-R10-20261025.
Inicio 2026-10-25T02:06:36.217Z; fin 2026-10-25T02:10:44.947Z; ambiente TEST; commit local/desplegado NO VERIFICADO.
Herramientas verificadas: Node v22.15.1, Newman con JSON/HTML conservados, Cypress Chrome headless; 5 pruebas.

## 2. Alcance y ambiente

Se evaluaron TC-M03-169, 170, 171, 172, 180 y 266 en TEST mediante API pública y Cypress donde la matriz exige UI. Fuente de oráculos: fila TC-M03-G88 de Casos_Prueba(Modulo3 Agrupado).csv. Para DBA se consultaron realmente src/shared/database.py, src/shared/rollback/infraestructure/testing_sandbox.py y testing_middlaware.py, src/identity_access/infrastructure/dependencies.py y las migraciones RLS 8d80fb56a30b_rls_modulo1.py y 98389cebef99_f5.py. Estas lecturas locales no acreditan despliegue en TEST.
La matriz usa ejemplos 35–39 para 169 y 20–30/T=1 para 170–171. El intento 9 sustituyó solo datos de entrada por el umbral M09 existente 15–30, T=1,5, según bitácora RF-17: 169=15/22,5/30; 170=13,65/14,85/30,15/31,35; 171=13,35/31,65. Se preservan los colores exigidos VERDE/AMARILLO/ROJO. Los niveles RF-17 observados (normal 20–30, precaución 19–20, crítico 15–19) pueden requerir conciliación con la fórmula RF-58 para valores inferiores; no se alteran los valores observados ni los veredictos históricos.

## 3. Resumen ejecutivo

Intento 9: un APROBADO, tres RECHAZADOS y dos casos ERROR_QA sin veredicto funcional completo. No es un cierre oficial de G88. Los ocho intentos anteriores y sus motivos constan en [historial](../../README.md).

## 4. Veredictos de los seis casos

| Caso | Veredicto funcional | Estado técnico | Fundamento breve |
| --- | --- | --- | --- |
| TC-M03-169 | APROBADO | OK | Todas las comprobaciones obligatorias aprobadas. |
| TC-M03-170 | RECHAZADO | OK | Lecturas 13,65; 14,85; 30,15; 31,35 aceptadas (HTTP 201); dashboard conservó 30 VERDE en vez de AMARILLO (DEV-170). |
| TC-M03-171 | RECHAZADO | OK | Lecturas 13,35 y 31,65 aceptadas (HTTP 201); dashboard conservó 30 VERDE en vez de ROJO (DEV-171). |
| TC-M03-172 | sin veredicto | ERROR_QA | La ausencia de T requiere API y UI concordantes. |
| TC-M03-180 | sin veredicto | ERROR_QA | API: NH3 5 ppm aceptado (HTTP 201), VERDE en vez de GRIS y sin notificación (DEV-180); UI no evaluable: login Productor HTTP 500 por violación RLS en modulo1.sesiones (DBA-01). |
| TC-M03-266 | RECHAZADO | OK | Misma lectura sigue VERDE tras PATCH M09. |

## 5. Esperado y observado por caso

### TC-M03-169

Esperado: Con 15–30 ejecutado, 15, 22,5 y 30 VERDE, conservando bordes inclusivos de la matriz.

Observado: Con umbral ejecutado 15–30, POST 201 y GET 200 mostraron 15, 22,5 y 30 VERDE.

### TC-M03-170

Esperado: Con T=1,5, los cuatro valores sustituidos en la banda de tolerancia AMARILLO.

Observado: POST 201 para 13,65; 14,85; 30,15; 31,35. Cada dashboard GET 200 conservó 30 VERDE.

### TC-M03-171

Esperado: Con T=1,5, ambos valores fuera de la banda ROJO.

Observado: POST 201 para 13,35 y 31,65. Cada dashboard GET 200 conservó 30 VERDE.

### TC-M03-172

Esperado: T=2 configurable en M09 y prevalente sobre T=1 del ejemplo 20–30; 18,5 y 31,5 AMARILLO, con UI y API.

Observado: GET umbrales HTTP 200 mostró valor_min, valor_max y niveles sin campo T; UI-172 falló antes de llegar al formulario.

### TC-M03-180

Esperado: NH3 5 ppm visible con unidad, GRIS, etiqueta “Sin umbral configurado” y notificación Administrador.

Observado: NH3 5 ppm aceptado HTTP 201; dashboard GET 200 mostró 5 ppm VERDE, sin etiqueta expuesta por API; cero nuevas notificaciones. UI-180 no completó acceso.

### TC-M03-266

Esperado: 15 VERDE con 10–20; después de PATCH a 20–30, misma lectura ROJO/AMARILLO sin nueva ingesta.

Observado: Telemetría 117074 de valor 15 estuvo VERDE bajo 10–20. PATCH M09 a 20–30 dio HTTP 200; sin nueva ingesta, el dashboard siguió VERDE.

## 6. Comprobaciones API y Cypress

API: 169 API-169-01..04 aprobadas; 170 API-170-02..05 rechazadas; 171 API-171-02..03 rechazadas; 172 API-172-A rechazó ausencia de T; 180 API-180-03 y 04 rechazadas pese a ingesta y sensor acreditados; 266 API-266-01 aprobada y 02 rechazada. Detalle sin truncar en resultado.json y JSON Newman de cada caso.
Cypress: UI-172 ejecutó 1 prueba, 1 fallida por promesa rechazada no capturada relacionada con GET /configuracion/personalizacion/dashboard/datos; no llegó al formulario M09. UI-180 ejecutó 4 pruebas, 4 fallidas: la precondición de login Productor recibió HTTP 500 frente a 200 y las tres aserciones de tarjeta no encontraron el control requerido. La captura real muestra la ausencia de tarjeta; no acredita GRIS ni etiqueta.

## 7. Incidencias funcionales de Desarrollo

### DEV-170 — AMARILLO no reflejado tras cuatro lecturas aceptadas

1. **Identificador y título:** DEV-170 — AMARILLO no reflejado tras cuatro lecturas aceptadas

2. **Caso:** TC-M03-170

3. **Requerimiento:** RF-58, CA-2/CA-16: clasificación según umbral M09 y tolerancia T por defecto.

4. **Componente:** Ingesta, clasificación y GET /iot/monitoreo/dashboard.

5. **Responsable inicial:** Desarrollo; primera discrepancia comprobada en la API pública. Causa raíz pendiente.

6. **Tipo:** Defecto funcional

7. **Severidad y fundamento:** ALTA, CONFIRMADA en su efecto: cuatro valores de tolerancia no se muestran y el monitoreo mantiene el valor/color anterior.

8. **Funcionamiento evaluado:** Bandas inmediatas externas a 15–30 con T=1,5; entradas 13,65; 14,85; 30,15; 31,35.

9. **Precondiciones:** Sensor 552, especie 126, umbral M09 existente 15–30, T por defecto 1,5; lecturas de prueba aceptadas.

10. **Pasos concretos:** Ingerir secuencialmente las cuatro lecturas por POST /iot/telemetria y consultar GET dashboard después de cada una.

11. **Resultado esperado:** Las cuatro lecturas deben figurar como AMARILLO con su valor actual, conforme a la sustitución de datos RF-17 documentada en el RUN.

12. **Resultado obtenido:** Los cuatro POST dieron HTTP 201; cada GET devolvió último valor 30 y VERDE, correspondiente a la lectura anterior.

13. **Evidencia precisa:** Comprobaciones API-170-02..05 en [resultado.json](./resultado.json); [newman/newman-TC-M03-170-0.json](./newman/newman-TC-M03-170-0.json), [newman/newman-TC-M03-170-1.json](./newman/newman-TC-M03-170-1.json), [newman/newman-TC-M03-170-2.json](./newman/newman-TC-M03-170-2.json), [newman/newman-TC-M03-170-3.json](./newman/newman-TC-M03-170-3.json).

14. **Impacto:** El tablero puede ocultar condiciones de precaución tras ingesta aceptada; afecta la lectura operativa de cuatro escenarios.

15. **Causa confirmada e hipótesis:** Confirmado: el dashboard no reflejó los valores de las lecturas aceptadas. Hipótesis: tratamiento de calidad FUERA_DE_RANGO o conservación de la última lectura válida, patrón REF-G87-01; requiere contrastar clasificación y persistencia. No se confirma la causa técnica.

16. **Acción correctiva solicitada:** Revisar el flujo de ingesta, calidad de lectura, cálculo con T y selección de valor/estado del dashboard; corregir la discrepancia sin modificar el oráculo RF-58.

17. **Criterio de acreditación:** Con la misma semilla y umbral, cada lectura aceptada se muestra con su valor y color exigido en GET dashboard; corroborar con historial/calidad y una nueva comprobación autorizada.

18. **Estado actual:** RECHAZADO/OK en el intento 9; incidencia abierta para Desarrollo.

### DEV-171 — ROJO no reflejado tras dos lecturas aceptadas

1. **Identificador y título:** DEV-171 — ROJO no reflejado tras dos lecturas aceptadas

2. **Caso:** TC-M03-171

3. **Requerimiento:** RF-58, CA-2/CA-16: clasificación según umbral M09 y tolerancia T por defecto.

4. **Componente:** Ingesta, clasificación y GET /iot/monitoreo/dashboard.

5. **Responsable inicial:** Desarrollo; primera discrepancia comprobada en la API pública. Causa raíz pendiente.

6. **Tipo:** Defecto funcional

7. **Severidad y fundamento:** ALTA, CONFIRMADA en su efecto: dos condiciones fuera de T permanecen visualmente VERDE.

8. **Funcionamiento evaluado:** Entradas 13,35 y 31,65, situadas más allá de 15−1,5 y 30+1,5.

9. **Precondiciones:** Sensor 552, especie 126, umbral M09 existente 15–30, T por defecto 1,5; lecturas de prueba aceptadas.

10. **Pasos concretos:** Ingerir ambas lecturas por POST /iot/telemetria y consultar GET dashboard tras cada POST.

11. **Resultado esperado:** Valor vigente y estado ROJO para ambas lecturas.

12. **Resultado obtenido:** Ambos POST HTTP 201; dashboard mantuvo 30 VERDE.

13. **Evidencia precisa:** API-171-02..03 en [resultado.json](./resultado.json); [newman/newman-TC-M03-171-0.json](./newman/newman-TC-M03-171-0.json), [newman/newman-TC-M03-171-1.json](./newman/newman-TC-M03-171-1.json).

14. **Impacto:** Una condición crítica de la variable no aparece como ROJO en el monitoreo.

15. **Causa confirmada e hipótesis:** Confirmado: el dashboard no reflejó los valores de las lecturas aceptadas. Hipótesis: tratamiento de calidad FUERA_DE_RANGO o conservación de la última lectura válida, patrón REF-G87-01; requiere contrastar clasificación y persistencia. No se confirma la causa técnica.

16. **Acción correctiva solicitada:** Revisar el flujo de ingesta, calidad de lectura, cálculo con T y selección de valor/estado del dashboard; corregir la discrepancia sin modificar el oráculo RF-58.

17. **Criterio de acreditación:** Con la misma semilla y umbral, cada lectura aceptada se muestra con su valor y color exigido en GET dashboard; corroborar con historial/calidad y una nueva comprobación autorizada.

18. **Estado actual:** RECHAZADO/OK en el intento 9; incidencia abierta para Desarrollo.

### DEV-266 — El semáforo no se recalcula después de editar M09

1. **Identificador y título:** DEV-266 — El semáforo no se recalcula después de editar M09

2. **Caso:** TC-M03-266

3. **Requerimiento:** RF-58 restricción 4 y TC-M03-266: recálculo dinámico con la misma lectura.

4. **Componente:** M09 y consulta de monitoreo.

5. **Responsable inicial:** Desarrollo; la primera discrepancia es API-266-02.

6. **Tipo:** Defecto funcional

7. **Severidad y fundamento:** ALTA, CONFIRMADA en su efecto: una edición válida no actualiza la clasificación relevante.

8. **Funcionamiento evaluado:** Umbral inicial 10–20; lectura 15, telemetría 117074; edición a 20–30 sin nueva ingesta.

9. **Precondiciones:** Semilla 266 acreditada, lectura inicial 15 VERDE y umbral QA 91 creado dentro del RUN.

10. **Pasos concretos:** Consultar lectura inicial, enviar PATCH M09 a 20–30, volver a consultar el mismo sensor sin ingerir de nuevo.

11. **Resultado esperado:** El mismo valor 15 cambia a ROJO/AMARILLO según el oráculo de la matriz; PATCH correcto HTTP 200.

12. **Resultado obtenido:** PATCH HTTP 200; la misma lectura permaneció VERDE. El umbral QA 91 quedó REVERTIDO_VERIFICADO tras DELETE del RUN.

13. **Evidencia precisa:** API-266-01/02, bitácora y cierre en [resultado.json](./resultado.json); [newman/newman-TC-M03-266-lectura-final.json](./newman/newman-TC-M03-266-lectura-final.json).

14. **Impacto:** El tablero puede conservar un estado obsoleto tras una reconfiguración M09.

15. **Causa confirmada e hipótesis:** Confirmado: ausencia de recálculo observable después del PATCH. Hipótesis de origen no determinada; el PATCH y el rollback sí funcionaron según sus comprobaciones.

16. **Acción correctiva solicitada:** Revisar el disparador/cálculo de estado al editar umbral y actualizar el dashboard para la lectura existente.

17. **Criterio de acreditación:** Con 15 VERDE bajo 10–20, PATCH 20–30 HTTP 200 y sin nueva ingesta, GET dashboard cambia a ROJO/AMARILLO; verificar rollback aparte.

18. **Estado actual:** RECHAZADO/OK; corrección pendiente.

### DEV-172-T — La API M09 no expone tolerancia T configurable

1. **Identificador y título:** DEV-172-T — La API M09 no expone tolerancia T configurable

2. **Caso:** TC-M03-172

3. **Requerimiento:** RF-58: T configurada en M09 prevalece sobre 10 % por defecto; escenario 20–30, T=2, lecturas 18,5 y 31,5.

4. **Componente:** GET /configuracion/umbrales y contrato M09.

5. **Responsable inicial:** Desarrollo; primera discrepancia API-172-A.

6. **Tipo:** Hallazgo funcional acreditado, sin veredicto integral del caso.

7. **Severidad y fundamento:** MEDIA, CONFIRMADA para la respuesta API: falta configurabilidad visible; el caso completo requiere UI.

8. **Funcionamiento evaluado:** Inspección de campos del umbral y de sus niveles en la especie/variable del caso.

9. **Precondiciones:** Umbral M09 consultable; API respondió HTTP 200.

10. **Pasos concretos:** Consultar umbrales M09 y examinar campos del objeto y de niveles; intentar abrir formulario UI-172.

11. **Resultado esperado:** API y formulario permiten configurar T=2 y prevalece sobre T=1 por defecto.

12. **Resultado obtenido:** API-172-A devolvió campos de umbral y niveles sin T. UI-172 terminó antes del formulario por excepción de la aplicación.

13. **Evidencia precisa:** [newman/newman-TC-M03-172-consulta.json](./newman/newman-TC-M03-172-consulta.json); API-172-A y UI-172 en [resultado.json](./resultado.json); [cypress/UI-172.json](./cypress/UI-172.json).

14. **Impacto:** No se pudo acreditar el escenario con T configurada y la API observada no la expone.

15. **Causa confirmada e hipótesis:** Confirmada la ausencia del campo en la respuesta examinada. La razón de diseño o implementación no está determinada; el fallo de UI es separado.

16. **Acción correctiva solicitada:** Aportar contrato público y configuración efectiva de T en M09; corregir API/UI si la ausencia se reproduce.

17. **Criterio de acreditación:** GET/edición pública exponen T y un RUN autorizado comprueba 18,5 y 31,5 AMARILLO con T=2, incluida UI.

18. **Estado actual:** ERROR_QA sin veredicto funcional completo; hallazgo API pendiente de Desarrollo.

### DEV-180 — NH3 sin umbral aparece VERDE y no genera aviso

1. **Identificador y título:** DEV-180 — NH3 sin umbral aparece VERDE y no genera aviso

2. **Caso:** TC-M03-180

3. **Requerimiento:** RF-58 CA-12/E7: variable sin umbral visible en GRIS, etiqueta “Sin umbral configurado” y aviso al Administrador.

4. **Componente:** Ingesta, dashboard y notificaciones.

5. **Responsable inicial:** Desarrollo; discrepancias API-180-03/04.

6. **Tipo:** Hallazgo funcional acreditado, caso sin veredicto integral.

7. **Severidad y fundamento:** ALTA, CONFIRMADA para API: presentación y aviso requeridos fallan; UI no concluyó.

8. **Funcionamiento evaluado:** NH3 del sensor 737 sin umbral activo para especie 126; lectura 5 ppm.

9. **Precondiciones:** Semilla 737/357/522/69 acreditada; lectura NH3 aceptada HTTP 201.

10. **Pasos concretos:** Comprobar ausencia de umbral NH3, ingerir 5 ppm, consultar dashboard y notificaciones Administrador.

11. **Resultado esperado:** Dashboard muestra 5 ppm, GRIS, etiqueta y variable visible; llega aviso al Administrador.

12. **Resultado obtenido:** GET devolvió 5 ppm VERDE; la API no expone etiqueta; nuevas notificaciones sobre umbral: 0. La UI no pudo comprobarse.

13. **Evidencia precisa:** API-180-01..04 en [resultado.json](./resultado.json); [newman/newman-TC-M03-180-0.json](./newman/newman-TC-M03-180-0.json).

14. **Impacto:** La ausencia de configuración se presenta como estado normal y el Administrador no recibe el aviso requerido.

15. **Causa confirmada e hipótesis:** Confirmados los resultados API. Causa técnica no determinada; el HTTP 500 del login UI es un impedimento distinto.

16. **Acción correctiva solicitada:** Corregir clasificación, etiqueta y aviso de variable sin umbral; revisar por separado acceso UI.

17. **Criterio de acreditación:** API devuelve GRIS y aviso, y Cypress acredita tarjeta visible con 5 ppm, unidad y etiqueta en un RUN autorizado.

18. **Estado actual:** ERROR_QA sin veredicto integral por UI incompleta; hallazgos API abiertos.

### DEV-172-UI — Excepción de aplicación interrumpe UI-172 antes del formulario

1. **Identificador y título:** DEV-172-UI — Excepción de aplicación interrumpe UI-172 antes del formulario

2. **Caso:** TC-M03-172

3. **Requerimiento:** RF-58/TC-M03-172 exige comprobación de T en formulario M09.

4. **Componente:** Frontend, carga inicial del dashboard y GET /configuracion/personalizacion/dashboard/datos.

5. **Responsable inicial:** Desarrollo, atención inicial frontend; origen exacto pendiente.

6. **Tipo:** Incidencia técnica de aplicación.

7. **Severidad y fundamento:** MEDIA, CONFIRMADA para la interrupción; impide comprobar solo la UI del caso.

8. **Funcionamiento evaluado:** Cypress inicia sesión Administrador y navega hacia el formulario M09.

9. **Precondiciones:** UI-172 inició con cabecera RUN; operaciones registradas de login y GET de lectura.

10. **Pasos concretos:** Abrir UI-172 en dashboard y avanzar hacia edición de umbral sin guardar.

11. **Resultado esperado:** Formulario M09 accesible para inspeccionar T.

12. **Resultado obtenido:** Una promesa rechazada no capturada ligada a GET de personalización cortó la prueba antes del formulario.

13. **Evidencia precisa:** [cypress/UI-172.json](./cypress/UI-172.json), [cypress/UI-172.log](./cypress/UI-172.log), [cypress/UI-172-operaciones.json](./cypress/UI-172-operaciones.json).

14. **Impacto:** UI-172 sin comprobación funcional; distinto del login Productor con RLS de UI-180.

15. **Causa confirmada e hipótesis:** Confirmada la excepción en Cypress. Su origen en aplicación/interceptor o respuesta de backend no se aisló con el resumen conservado.

16. **Acción correctiva solicitada:** Investigar la petición y el manejo de rechazo en frontend; conservar código HTTP y traza saneada en la siguiente validación.

17. **Criterio de acreditación:** La UI llega al formulario M09 sin excepción; Cypress ejecuta su aserción real de T.

18. **Estado actual:** ERROR_QA; incidencia abierta para Desarrollo.

## 8. Incidencias técnicas del DBA

### DBA-01 — Violación RLS al alternar identidades en una Session del sandbox

1. **Identificador y título:** DBA-01 — Violación RLS al alternar identidades en una Session del sandbox

2. **Caso:** TC-M03-180 (acceso UI); TC-M03-172 como contraste de identidad

3. **Requerimiento:** Sandbox QA debe aislar escrituras de un RUN y permitir peticiones de usuarios diferentes con RLS vigente.

4. **Componente:** SQLAlchemy Session del sandbox, contexto PostgreSQL y política RLS de modulo1.sesiones.

5. **Responsable inicial:** DBA; Desarrollo apoya el cambio del ciclo de Session/identidad.

6. **Tipo:** Incidencia técnica de entorno.

7. **Severidad y fundamento:** ALTA, CONFIRMADA para el rechazo RLS informado y PROBABLE para la herencia de identidad; impide cerrar UI-180.

8. **Funcionamiento evaluado:** testing_sandbox.py conserva una Session/conexión/transacción por RUN; database.py guarda identidad en Session.info y la reaplica en after_begin. declarar_identidad_si_anonima no sustituye una identidad previa.

9. **Precondiciones:** Última petición Bearer directa antes de Cypress como Administrador; UI-172 inicia con Administrador y UI-180 intenta iniciar con QA_PROD_UI.

10. **Pasos concretos:** En un RUN aislado, autenticar Administrador, ejecutar GET Bearer; después POST /sesiones/ como Productor UI con cabecera RUN. Repetir en orden inverso y con mismo usuario.

11. **Resultado esperado:** Cada petición usa su propia identidad RLS y POST /sesiones/ inserta únicamente la sesión de la cuenta autenticada.

12. **Resultado obtenido:** UI-180 POST /sesiones/ respondió HTTP 500 en 399 ms con cabecera RUN; UI-172 llegó más lejos. Log comunicado por Desarrollo: InfrastructureError [ERROR_INTERNO], ProgrammingError psycopg2.errors.InsufficientPrivilege: new row violates row-level security policy for table “sesiones”.

13. **Evidencia precisa:** [cypress/UI-180-solicitudes.json](./cypress/UI-180-solicitudes.json), [cypress/UI-180.json](./cypress/UI-180.json), [resultado.json](./resultado.json); anexo técnico entregado al DBA por la orquestación QA (HALLAZGO-G88-RLS-SANDBOX y REGRESION-RLS-SANDBOX-PROPUESTA). El log fue comunicado, no se conserva como archivo del RUN.

14. **Impacto:** Login Productor UI bloqueado; no se ejecutan las aserciones de tarjeta sin umbral. Riesgo de contaminación entre usuarios del mismo RUN.

15. **Causa confirmada e hipótesis:** Confirmado por el log comunicado: violación RLS en INSERT de sesiones. Hipótesis sólida no confirmada en TEST: Session.info heredó identidad Administrador al procesar login Productor; falta traza de identidad efectiva y política desplegada.

16. **Acción correctiva solicitada:** DBA y Desarrollo deben observar identidad efectiva por petición, impedir herencia y reinicializar app.current_user_id, app.current_role y app.usuario_id; login anónimo debe adoptar la identidad autenticada. Conservar políticas RLS, sin BYPASSRLS ni relajación.

17. **Criterio de acreditación:** En PostgreSQL/RLS reales: Administrador→Productor, Productor→Administrador y login repetido del mismo usuario; sin 500 ni contaminación, rollback comprobado y corrección desplegada en TEST confirmada.

18. **Estado actual:** Abierta; hipótesis de mecanismo PROBABLE. Requiere validación de DBA y apoyo de Desarrollo antes de otro RUN QA.

### DBA-02 — Esperas al mezclar peticiones dentro y fuera de la transacción del RUN

1. **Identificador y título:** DBA-02 — Esperas al mezclar peticiones dentro y fuera de la transacción del RUN

2. **Caso:** Antecedentes intentos 5–8; no observado en intento 9

3. **Requerimiento:** Aislamiento de RUN sin bloquear accesos de la misma cuenta en contextos paralelos.

4. **Componente:** Transacciones PostgreSQL, ultimo_acceso y dependencia de autenticación.

5. **Responsable inicial:** DBA; Desarrollo apoya revisión del código de autenticación.

6. **Tipo:** Incidencia técnica de entorno.

7. **Severidad y fundamento:** MEDIA, PROBABLE para el mecanismo: los timeouts históricos impedían casos; mitigación comprobada en intento 9.

8. **Funcionamiento evaluado:** dependencies.py:149-151 actualiza y confirma ultimo_acceso por petición autenticada; la transacción externa del sandbox retiene bloqueos hasta el cierre.

9. **Precondiciones:** Misma cuenta usada en peticiones autenticadas dentro y fuera del RUN.

10. **Pasos concretos:** Comparar latencias de peticiones a asociaciones, dashboard y umbrales con la misma cuenta, primero mezclando contextos y después serializando todo dentro del RUN.

11. **Resultado esperado:** Peticiones completadas sin espera de bloqueo y aislamiento intacto.

12. **Resultado obtenido:** Intentos 5–8 registraron timeouts de 30 s en rutas distintas; en intento 9 no se repitieron después de mantener las peticiones autenticadas dentro del RUN.

13. **Evidencia precisa:** [historial G88](./../../README.md); el análisis de transacciones se resume en funcionamiento, resultado obtenido y causa de esta incidencia; [resultado.json](./resultado.json) del intento 9 para ausencia de nuevo timeout.

14. **Impacto:** Puede bloquear comprobaciones de otros grupos QA si mezclan contextos para una misma cuenta.

15. **Causa confirmada e hipótesis:** Confirmado: timeouts históricos y mitigación de secuencia en G88. Hipótesis de bloqueo por ultimo_acceso sustentada en código local; no hay traza de locks de PostgreSQL.

16. **Acción correctiva solicitada:** Revisar retención de bloqueo y diseño de actualización de ultimo_acceso con Desarrollo; establecer pauta para otros grupos.

17. **Criterio de acreditación:** Prueba controlada en PostgreSQL real sin esperas de 30 s al alternar contexto y con rollback conservado.

18. **Estado actual:** Mitigado en G88 intento 9; revisión preventiva pendiente, sin bloqueo activo demostrado.

### DBA-03 — Session compartida expuesta a concurrencia y cierre con peticiones activas

1. **Identificador y título:** DBA-03 — Session compartida expuesta a concurrencia y cierre con peticiones activas

2. **Caso:** Riesgo transversal G88; no atribuido a 172 ni 180

3. **Requerimiento:** Sandbox QA debe proteger integridad de transacción y cierre seguro bajo peticiones simultáneas.

4. **Componente:** testing_sandbox.py, conexión y Session compartidas; ciclo de petición y cancelación.

5. **Responsable inicial:** DBA con apoyo de Desarrollo para sincronización y ciclo de vida.

6. **Tipo:** Incidencia técnica de diseño; riesgo no demostrado como fallo.

7. **Severidad y fundamento:** MEDIA, certeza NO DETERMINADA como fallo: una carrera podría comprometer aislamiento, sin ocurrencia acreditada en el intento 9.

8. **Funcionamiento evaluado:** sandbox_lock protege el registro; no serializa todo el uso posterior de Session. El cierre puede coincidir con peticiones activas; cancelar cliente no prueba cancelación de servidor.

9. **Precondiciones:** Peticiones simultáneas o cliente que aborta mientras el servidor conserva trabajo.

10. **Pasos concretos:** En entorno aislado, instrumentar dos peticiones concurrentes sobre un RUN y un cierre mientras una sigue activa; repetir con aborto del cliente.

11. **Resultado esperado:** Acceso serializado o transacciones independientes seguras; DELETE espera o cancela trabajo y rollback se acredita.

12. **Resultado obtenido:** Solo riesgo deducido de código local; no se observó carrera, cierre inseguro ni nexo causal con UI-172/180.

13. **Evidencia precisa:** Anexo técnico entregado al DBA por la orquestación QA (HALLAZGO-G88-RLS-SANDBOX y REGRESION-RLS-SANDBOX-PROPUESTA); rutas locales testing_sandbox.py:23-80/database.py:182-198; sin evidencia de ejecución concurrente en TEST.

14. **Impacto:** Potencial contaminación/cierre incompleto en RUN de varios usuarios o navegador concurrente.

15. **Causa confirmada e hipótesis:** Confirmado en código: candado limitado al registro y Session compartida. Hipótesis de fallo efectivo no determinada.

16. **Acción correctiva solicitada:** DBA y Desarrollo deben revisar modelo de transacciones, conexiones, concurrencia, cancelación del servidor y cierre seguro.

17. **Criterio de acreditación:** Regresión en PostgreSQL/RLS real con simultaneidad, aborto y DELETE: identidades aisladas, sin uso de Session cerrada y rollback verificado.

18. **Estado actual:** Riesgo de diseño abierto; no usarlo como explicación del 500 o de UI-172.

## 9. Casos sin veredicto funcional — impedimentos técnicos

TC-M03-172 permanece ERROR_QA: API-172-A acredita ausencia de T en la respuesta consultada, pero UI-172 se interrumpió por la excepción de la aplicación durante GET de personalización antes del formulario M09. Atención inicial Desarrollo/frontend. No se confunde con el error RLS de 180.
TC-M03-180 permanece ERROR_QA: ingesta y API acreditan discrepancias de GRIS/aviso; la UI dependía del login QA_PROD_UI, que devolvió HTTP 500. El log comunicado atribuye el 500 a violación RLS de modulo1.sesiones; atención inicial DBA con apoyo de Desarrollo. Cuatro pruebas Cypress fallidas no constituyen comprobación satisfactoria de tarjeta, etiqueta y unidad.

## 10. Hallazgos adicionales

### DEV-RF61-A — Once lecturas sin vinculación al activo acreditado

1. **Identificador y título:** DEV-RF61-A — Once lecturas sin vinculación al activo acreditado

2. **Caso:** TC-M03-169/170/171/180/266; hallazgo independiente

3. **Requerimiento:** RF-61-A vinculación de telemetría al activo aplicable; no altera oráculos RF-58.

4. **Componente:** GET /iot/vinculaciones y asociación telemetría-activo.

5. **Responsable inicial:** Desarrollo, primera discrepancia en API pública; causa raíz sin atribuir.

6. **Tipo:** Hallazgo adicional.

7. **Severidad y fundamento:** MEDIA, PROBABLE: once lecturas sin vínculo reducen trazabilidad; falta evaluación específica RF-61-A.

8. **Funcionamiento evaluado:** Lecturas 117064–117073 con activo 884 en área 349; 117074 con activo 885 en área 504.

9. **Precondiciones:** Activos únicos vinculables y lecturas aceptadas según semilla del intento 9.

10. **Pasos concretos:** Ingerir lecturas del escenario y consultar GET /iot/vinculaciones por cada id_telemetria.

11. **Resultado esperado:** Cada lectura vinculada al activo aplicable.

12. **Resultado obtenido:** Las once consultas registraron SIN_VINCULACION, sin activo ni área, cero registros.

13. **Evidencia precisa:** [resultado.json](./resultado.json) → hallazgos_producto, entradas 169a–c, 170a–d, 171a–b, 180 y 266.

14. **Impacto:** Trazabilidad RF-61-A posiblemente incompleta; los veredictos RF-58 permanecen independientes.

15. **Causa confirmada e hipótesis:** Confirmadas las respuestas de vínculo; aplicabilidad y causa de RF-61-A requieren evaluación propia.

16. **Acción correctiva solicitada:** Revisar vinculación y abrir evaluación RF-61-A separada.

17. **Criterio de acreditación:** Lecturas equivalentes devuelven vínculo al activo esperado por API pública en una evaluación autorizada de RF-61-A.

18. **Estado actual:** Hallazgo adicional único, pendiente; sin cambio de veredictos G88.

## 11. Evidencias

[resultado.json](./resultado.json) y [contexto_operacion.json](./contexto_operacion.json) identifican el intento y sus comprobaciones. [newman/newman-G88-consolidado.html](./newman/newman-G88-consolidado.html) es el HTML consolidado; se conservan doce JSON Newman individuales por caso.
Cypress conserva [cypress/UI-172.json](./cypress/UI-172.json), [cypress/UI-172.log](./cypress/UI-172.log), [cypress/UI-180.json](./cypress/UI-180.json), [cypress/UI-180.log](./cypress/UI-180.log), [cypress/UI-172-operaciones.json](./cypress/UI-172-operaciones.json), [cypress/UI-180-solicitudes.json](./cypress/UI-180-solicitudes.json) y [cypress/g88.cy.js/TC-M03-180_sin_tarjeta.png](./cypress/g88.cy.js/TC-M03-180_sin_tarjeta.png). Las dos trazas JSON y la captura fueron reubicadas desde _cypress_capturas/ por el defecto de salida corregido en ORD-G88-038; su contenido no se modificó.
El log de PostgreSQL citado en DBA-01 fue comunicado por Desarrollo; no consta como archivo del RUN y no se presenta como evidencia adjunta.

## 12. Cierre y rollback

DELETE del RUN HTTP 200; verificación CONFIRMADA. Resultado guardado: ROLLBACK_CONFIRMADO. Umbral QA 91: REVERTIDO_VERIFICADO. Las comparaciones API de asociaciones, dashboard, umbrales e historiales figuran en resultado.json. Este cierre no acredita corrección funcional ni descarta efectos fuera de la transacción.

## 13. Estado final y condiciones pendientes

ÚLTIMO RUN CONSERVADO — EVALUACIÓN NO OFICIAL / PENDIENTE DE CIERRE FUNCIONAL. G88 requiere atención de Desarrollo a las discrepancias RF-58 y de DBA con Desarrollo al sandbox RLS, más acceso UI completo para 172/180. Una nueva evaluación solo corresponde al lanzador externo con autorización humana específica; este informe no altera resultado.json ni convierte los hallazgos API en veredictos integrales.
