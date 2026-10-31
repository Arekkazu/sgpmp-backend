# TC-M03-G88 — RECHAZADO

## Decisión del caso

**Caso agrupado:** TC-M03-G88, RF-58. **Casos originales:** TC-M03-169, TC-M03-170, TC-M03-171, TC-M03-172, TC-M03-180, TC-M03-266.
**Decisión:** RECHAZADO. **Motivo:** 2 aprobados, 4 rechazados; 170/171 conservan 30 VERDE ante seis lecturas externas, 172 carece de T en API/UI y 266 conserva 15 VERDE tras editar M09.
**RUN oficial:** sí. **Qué falta:** Resolver las tres incidencias funcionales y repetirlas en evaluación autorizada.

| Caso | Comprobación | Decisión | Motivo breve |
| --- | --- | --- | --- |
| TC-M03-169 | API-169-01, API-169-02, API-169-03, API-169-04 | APROBADO | Los tres valores observados fueron VERDE en los bordes y dentro del rango ejecutado. |
| TC-M03-170 | API-170-01, API-170-02, API-170-03, API-170-04, API-170-05 | RECHAZADO | Las 4 lecturas quedaron FUERA_DE_RANGO y el dashboard conservó 30 VERDE con indicador de anomalía; no mostró el color exigido. |
| TC-M03-171 | API-171-01, API-171-02, API-171-03 | RECHAZADO | Las 2 lecturas quedaron FUERA_DE_RANGO y el dashboard conservó 30 VERDE con indicador de anomalía; no mostró el color exigido. |
| TC-M03-172 | API-172-A, UI-172 | RECHAZADO | API y formulario no permiten acreditar ni configurar T=2; faltó el dato exigido en ambos canales. |
| TC-M03-180 | API-180-01, API-180-03, API-180-02, API-180-04, UI-180-01, UI-180-02, UI-180-03 | APROBADO | Valor, unidad, GRIS, etiqueta y permanencia de la variable quedaron acreditados; el correo se deja como observación de alcance. |
| TC-M03-266 | API-266-01, API-266-02 | RECHAZADO | La misma lectura no se recalculó tras la edición: permaneció VERDE bajo 20–30. |

## Detalle por caso

### TC-M03-169

**Qué se hizo:** Administrador: sensor 552, especie 126 y umbral M09 15–30; ingresó 15, 22.5 y 30 y consultó el dashboard tras cada lectura.
**Qué se esperaba:** HTTP 200; 35, 37 y 39 en VERDE con umbral 35-39. (matriz G88, RF-58).
**Qué se observó:** POST de lecturas HTTP 201; GET HTTP 200; HTTP 200; ultimo_valor=15.0000; estado_semaforo=VERDE; HTTP 200; ultimo_valor=22.5000; estado_semaforo=VERDE; HTTP 200; ultimo_valor=30.0000; estado_semaforo=VERDE.
**Por qué APROBADO:** Los tres valores observados fueron VERDE en los bordes y dentro del rango ejecutado.

### TC-M03-170

**Qué se hizo:** Administrador: sensor 552, especie 126, umbral M09 15–30 y tolerancia derivada 1.5; ingresó 13.65, 14.85, 30.15, 31.35 y consultó el dashboard después de cada lectura.
**Qué se esperaba:** HTTP 200; 19.1, 19.9, 30.1 y 30.9 en AMARILLO; T por defecto=1 (10 % de 20-30). (matriz G88, RF-58).
**Qué se observó:** POST HTTP 201 y GET HTTP 200; HTTP 200; entrada=13.65; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango; HTTP 200; entrada=14.85; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango; HTTP 200; entrada=30.15; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango; HTTP 200; entrada=31.35; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango.
**Por qué RECHAZADO:** Las 4 lecturas quedaron FUERA_DE_RANGO y el dashboard conservó 30 VERDE con indicador de anomalía; no mostró el color exigido.

### TC-M03-171

**Qué se hizo:** Administrador: sensor 552, especie 126, umbral M09 15–30 y tolerancia derivada 1.5; ingresó 13.35, 31.65 y consultó el dashboard después de cada lectura.
**Qué se esperaba:** HTTP 200; 18.9 y 31.1 en ROJO con umbral 20-30 y T=1. (matriz G88, RF-58).
**Qué se observó:** POST HTTP 201 y GET HTTP 200; HTTP 200; entrada=13.35; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango; HTTP 200; entrada=31.65; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango.
**Por qué RECHAZADO:** Las 2 lecturas quedaron FUERA_DE_RANGO y el dashboard conservó 30 VERDE con indicador de anomalía; no mostró el color exigido.

### TC-M03-172

**Qué se hizo:** Administrador: consultó cuatro umbrales M09 por API y abrió en Cypress el formulario de umbral para buscar la tolerancia T configurada en 2.
**Qué se esperaba:** HTTP 200; 18.5 y 31.5 en AMARILLO con T=2 configurada en M09. (matriz G88, RF-58).
**Qué se observó:** GET HTTP 200 sin campo T en umbral o niveles; Cypress ejecutó 1 prueba y registró formulario sin control T; captura real.
**Por qué RECHAZADO:** API y formulario no permiten acreditar ni configurar T=2; faltó el dato exigido en ambos canales.

### TC-M03-180

**Qué se hizo:** Administrador: ingirió NH3=5 ppm del sensor 737 sin umbral; Productor: abrió el dashboard y verificó tarjeta, valor, unidad, etiqueta y color en cuatro pruebas Cypress.
**Qué se esperaba:** HTTP 200; variable visible con valor, unidad, GRIS, etiqueta Sin umbral configurado y notificación al administrador. (matriz G88, RF-58).
**Qué se observó:** POST HTTP 201; GET HTTP 200 con 5 ppm y GRIS; etiqueta “Sin umbral configurado” visible; 4 pruebas UI, 0 fallidas. Auditoría E7: aviso nuevo=0, previo registrado; entrega de correo no verificable por API.
**Por qué APROBADO:** Valor, unidad, GRIS, etiqueta y permanencia de la variable quedaron acreditados; el correo se deja como observación de alcance.

### TC-M03-266

**Qué se hizo:** Administrador: especie 220, área 504 y sensor 738; creó umbral M09 10–20, ingirió una sola lectura 15, consultó dashboard e historial, cambió M09 a 20–30 y repitió ambas consultas sin otra ingesta. Las barreras Edge quedaron pendientes.
**Qué se esperaba:** Lectura 15 VERDE con 10-20; sin cambiarla, al reconfigurar a 20-30 se recalcula a ROJO/AMARILLO. (matriz G88, RF-58).
**Qué se observó:** Alta HTTP 201, edición HTTP 200 y GET HTTP 200; lectura 118471 con 15 VERDE antes y después; HTTP 200; valor=15.0000; semáforo=VERDE; misma_lectura=true; barrera=true.
**Por qué RECHAZADO:** La misma lectura no se recalculó tras la edición: permaneció VERDE bajo 20–30.

## Identificación y alcance

RUN RUN-G88-V1-20261030-202846; intento 15; V1; ambiente TEST; autorización AUT-G88-V1-R16-20261030; inicio 2026-10-30T20:28:47.048Z; fin 2026-10-30T20:30:23.150Z; commit NO VERIFICADO.
Herramientas verificadas: node: v22.15.1; newman: 6.2.2; una ejecución; JSON y HTML reales; cypress: Cypress 14.5.4; Chrome headless 156.0.8078.74; 5 pruebas. Newman: 6 casos en una colección; Cypress: 5 pruebas.
Fuente de oráculos: fila TC-M03-G88 de Casos_Prueba(Modulo3 Agrupado).csv y RF-58, Fase 3, CA-2/12/16, E7 y Restricción 4. Los ejemplos de matriz 35–39 y 20–30 se ejecutaron con la semilla 15–30 y valores proporcionales; los colores esperados se conservaron. Esta sustitución de datos no prueba literalmente los valores originales.

## Esperado y observado: comprobaciones API/UI

| Caso | Fuente | Comprobación | Decisión | Esperado | Observado |
| --- | --- | --- | --- | --- | --- |
| TC-M03-169 | API | API-169-01 | APROBADO | HTTP 200; 35, 37 y 39 en VERDE con umbral 35-39. | HTTP 200; sensor presente=true |
| TC-M03-169 | API | API-169-02 | APROBADO | HTTP 200; 35, 37 y 39 en VERDE con umbral 35-39. | HTTP 200; ultimo_valor=15.0000; estado_semaforo=VERDE |
| TC-M03-169 | API | API-169-03 | APROBADO | HTTP 200; 35, 37 y 39 en VERDE con umbral 35-39. | HTTP 200; ultimo_valor=22.5000; estado_semaforo=VERDE |
| TC-M03-169 | API | API-169-04 | APROBADO | HTTP 200; 35, 37 y 39 en VERDE con umbral 35-39. | HTTP 200; ultimo_valor=30.0000; estado_semaforo=VERDE |
| TC-M03-170 | API | API-170-01 | APROBADO | HTTP 200; 19.1, 19.9, 30.1 y 30.9 en AMARILLO; T por defecto=1 (10 % de 20-30). | HTTP 200; sensor presente=true |
| TC-M03-170 | API | API-170-02 | RECHAZADO | HTTP 200; 19.1, 19.9, 30.1 y 30.9 en AMARILLO; T por defecto=1 (10 % de 20-30). | HTTP 200; entrada=13.65; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango |
| TC-M03-170 | API | API-170-03 | RECHAZADO | HTTP 200; 19.1, 19.9, 30.1 y 30.9 en AMARILLO; T por defecto=1 (10 % de 20-30). | HTTP 200; entrada=14.85; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango |
| TC-M03-170 | API | API-170-04 | RECHAZADO | HTTP 200; 19.1, 19.9, 30.1 y 30.9 en AMARILLO; T por defecto=1 (10 % de 20-30). | HTTP 200; entrada=30.15; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango |
| TC-M03-170 | API | API-170-05 | RECHAZADO | HTTP 200; 19.1, 19.9, 30.1 y 30.9 en AMARILLO; T por defecto=1 (10 % de 20-30). | HTTP 200; entrada=31.35; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango |
| TC-M03-171 | API | API-171-01 | APROBADO | HTTP 200; 18.9 y 31.1 en ROJO con umbral 20-30 y T=1. | HTTP 200; sensor presente=true |
| TC-M03-171 | API | API-171-02 | RECHAZADO | HTTP 200; 18.9 y 31.1 en ROJO con umbral 20-30 y T=1. | HTTP 200; entrada=13.35; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango |
| TC-M03-171 | API | API-171-03 | RECHAZADO | HTTP 200; 18.9 y 31.1 en ROJO con umbral 20-30 y T=1. | HTTP 200; entrada=31.65; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango |
| TC-M03-172 | API | API-172-A | RECHAZADO | HTTP 200; 18.5 y 31.5 en AMARILLO con T=2 configurada en M09. | HTTP 200; 4 umbrales; campos umbral=es_activo,estado_sincronizacion,fecha_actualizacion,fecha_ultima_sincronizacion,id_especie,id_umbral_ambiental,id_variable_ambiental,motivo_fallo_sincronizacion,niveles,unidad_medida,valor_max,valor_min; campos niveles=limite_inferior,limite_superior,nivel / limite_inferior,limite_superior,nivel / limite_inferior,limite_superior,nivel; ausencia T=true |
| TC-M03-172 | UI | UI-172 | RECHAZADO | HTTP 200; 18.5 y 31.5 en AMARILLO con T=2 configurada en M09. | Formulario sin control T/tolerancia; captura real. |
| TC-M03-180 | API | API-180-01 | APROBADO | HTTP 200; variable visible con valor, unidad, GRIS, etiqueta Sin umbral configurado y notificación al administrador. | HTTP 200; sensor presente=true |
| TC-M03-180 | API | API-180-03 | APROBADO | HTTP 200; variable visible con valor, unidad, GRIS, etiqueta Sin umbral configurado y notificación al administrador. | estado_semaforo=GRIS; etiqueta=Sin umbral configurado |
| TC-M03-180 | API | API-180-02 | APROBADO | HTTP 200; variable visible con valor, unidad, GRIS, etiqueta Sin umbral configurado y notificación al administrador. | HTTP 200; ultimo_valor=5.0000; estado_semaforo=GRIS |
| TC-M03-180 | API | API-180-04 | APROBADO | HTTP 200; variable visible con valor, unidad, GRIS, etiqueta Sin umbral configurado y notificación al administrador. | Bitácora E7 nueva=0; aviso previo=2026-10-30T19:25:34.419419Z, sensor 737, variable NH3, administradores_avisados=15; deduplicación de 24 h impidió observar un aviso nuevo en este RUN; HTTP 200; espera 15096 ms; correo SMTP irreversible, entrega no verificable por API. |
| TC-M03-180 | UI | UI-180-01 | APROBADO | HTTP 200; variable visible con valor, unidad, GRIS, etiqueta Sin umbral configurado y notificación al administrador. | tarjeta del sensor NH3 visible; captura cypress/g88.cy.js/TC-M03-180_productor_sensor_sin_umbral.png |
| TC-M03-180 | UI | UI-180-02 | APROBADO | HTTP 200; variable visible con valor, unidad, GRIS, etiqueta Sin umbral configurado y notificación al administrador. | tarjeta del sensor NH3: valor 5 ppm visible; captura cypress/g88.cy.js/TC-M03-180_productor_sensor_sin_umbral.png |
| TC-M03-180 | UI | UI-180-03 | APROBADO | HTTP 200; variable visible con valor, unidad, GRIS, etiqueta Sin umbral configurado y notificación al administrador. | etiqueta "Sin umbral configurado" y píldora GRIS visibles; captura cypress/g88.cy.js/TC-M03-180_productor_sensor_sin_umbral.png |
| TC-M03-266 | API | API-266-01 | APROBADO | Lectura 15 VERDE con 10-20; sin cambiarla, al reconfigurar a 20-30 se recalcula a ROJO/AMARILLO. | HTTP 200; valor=15.0000; semáforo=VERDE; lectura=118482; barrera=true |
| TC-M03-266 | API | API-266-02 | RECHAZADO | Lectura 15 VERDE con 10-20; sin cambiarla, al reconfigurar a 20-30 se recalcula a ROJO/AMARILLO. | HTTP 200; valor=15.0000; semáforo=VERDE; misma_lectura=true; barrera=true |

## Observaciones y alcance

E7, hecho: la auditoría registró cero avisos nuevos y un aviso previo para el sensor 737. Inferencia: el patrón es compatible con deduplicación de 24 h. La entrega SMTP no es comprobable por API y queda como observación; el resto de 180 se evaluó por API y UI.
Cypress: 172 ejecutó 1 prueba; 180 ejecutó 4. Ningún APROBADO de UI se basa en cero ejecuciones.
RF-61-A: 10 hallazgos de vínculo registrados por separado en resultado.json; no cambian RF-58.

## Incidencias de producto

### DEV-G88-01 — Lecturas de advertencia y críticas permanecen en 30 VERDE

**Casos:** TC-M03-170, TC-M03-171. **Equipo inicial:** Desarrollo. **Certeza:** CONFIRMADA para la discrepancia pública; causa raíz no confirmada.
**Severidad e impacto:** ALTA: seis condiciones de advertencia o crítica no llegan al semáforo operativo; el usuario ve 30 VERDE y carece de ese aviso.
**Requisito:** RF-58 Fase 3, CA-2 y CA-16; matriz G88 pasos 2 y 3: AMARILLO dentro de T y ROJO fuera de T.
**Precondiciones:** Sensor 552, especie 126, umbral M09 15–30 y T derivada 1.5; lecturas aceptadas por HTTP 201.
**Pasos reales:**
1. Autenticar Administrador y comprobar sensor 552 y umbral M09 15–30.
2. Ingresar 13.65, 14.85, 30.15, 31.35, 13.35 y 31.65; consultar dashboard después de cada lectura.
3. Comparar valor, calidad, anomalía y color del dashboard con la zona de tolerancia.

**Esperado:** Los primeros cuatro valores deben mostrar AMARILLO; 13.35 y 31.65 deben mostrar ROJO con la tolerancia derivada.
**Obtenido:** Los seis GET HTTP 200 conservaron valor 30.0000 VERDE; las lecturas se clasificaron FUERA_DE_RANGO con indicador_anomalia=true.
- API-170-02 RECHAZADO: HTTP 200; entrada=13.65; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango
- API-170-03 RECHAZADO: HTTP 200; entrada=14.85; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango
- API-170-04 RECHAZADO: HTTP 200; entrada=30.15; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango
- API-170-05 RECHAZADO: HTTP 200; entrada=31.35; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango
- API-171-02 RECHAZADO: HTTP 200; entrada=13.35; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango
- API-171-03 RECHAZADO: HTTP 200; entrada=31.65; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango
**Evidencia:** [0](./resultado.json), [1](./newman/newman-TC-M03-G88.json); comprobaciones API-170-02, API-170-03, API-170-04, API-170-05, API-171-02, API-171-03.
**Fundamento del primer contacto:** discrepancia en API pública; Desarrollo atiende la funcionalidad observada, sin atribuirle causa técnica.
**Hecho probado:** Los seis GET HTTP 200 conservaron valor 30.0000 VERDE; las lecturas se clasificaron FUERA_DE_RANGO con indicador_anomalia=true. **Inferencia de impacto:** El dashboard puede ocultar una condición que la matriz exige presentar en AMARILLO o ROJO. **Hipótesis:** la clasificación de calidad excluye estas lecturas del valor operativo; la interacción con CA-6 requiere análisis de Desarrollo. No se confirma causa raíz.
**Para cerrar:** Aclarar la relación entre CA-6 y la matriz G88, corregir la discrepancia y repetir las seis lecturas con dashboard e historial.

### DEV-G88-02 — T configurable ausente en API y formulario M09

**Casos:** TC-M03-172. **Equipo inicial:** Desarrollo. **Certeza:** CONFIRMADA para la discrepancia pública; causa raíz no confirmada.
**Severidad e impacto:** MEDIA: la configuración específica T=2 está impedida; otros umbrales y el valor por defecto siguen disponibles.
**Requisito:** RF-58 Fase 3 y matriz G88 paso 4: T=2 configurada prevalece sobre T por defecto; 18.5 y 31.5 AMARILLO.
**Precondiciones:** Administrador con acceso de lectura a cuatro umbrales M09 y formulario de umbral abierto en Cypress.
**Pasos reales:**
1. Autenticar Administrador y consultar GET de umbrales M09.
2. Revisar campos del umbral y sus niveles para T.
3. Abrir el formulario M09 en Cypress y buscar control de T antes de guardar.

**Esperado:** API y UI exponen y permiten configurar T=2 para evaluar 18.5 y 31.5 como AMARILLO.
**Obtenido:** GET HTTP 200 sin T en cuatro umbrales ni niveles; una prueba Cypress encontró formulario sin control T y guardó captura.
- API-172-A RECHAZADO: HTTP 200; 4 umbrales; campos umbral=es_activo,estado_sincronizacion,fecha_actualizacion,fecha_ultima_sincronizacion,id_especie,id_umbral_ambiental,id_variable_ambiental,motivo_fallo_sincronizacion,niveles,unidad_medida,valor_max,valor_min; campos niveles=limite_inferior,limite_superior,nivel / limite_inferior,limite_superior,nivel / limite_inferior,limite_superior,nivel; ausencia T=true
- UI-172 RECHAZADO: Formulario sin control T/tolerancia; captura real.
**Evidencia:** [0](./resultado.json), [1](./newman/newman-TC-M03-G88.json), [2](./cypress/g88.cy.js/TC-M03-172%20%E2%80%94%20T%20configurable%20en%20M09%20--%20%5BTC-M03-172%5D%5BASSERT%5D%5BUI-172%5D%20El%20formulario%20de%20umbral%20permite%20configurar%20T%20(failed).png), [3](./cypress/g88.cy.js/TC-M03-172_formulario_umbral_sin_guardar.png); comprobaciones API-172-A, UI-172.
**Fundamento del primer contacto:** discrepancia en API pública y UI; Desarrollo atiende la funcionalidad observada, sin atribuirle causa técnica.
**Hecho probado:** GET HTTP 200 sin T en cuatro umbrales ni niveles; una prueba Cypress encontró formulario sin control T y guardó captura. **Inferencia de impacto:** No se puede aplicar la tolerancia propia exigida para el caso 172. **Hipótesis:** Hipótesis de implementación: revisar DTO/API M09 y control de formulario. La causa técnica no se establece con las dos observaciones públicas.
**Para cerrar:** Exponer y persistir T en API/UI y ejecutar 18.5 y 31.5 con T=2 en un RUN autorizado.

### DEV-G88-03 — El semáforo no se recalcula después de editar M09

**Casos:** TC-M03-266. **Equipo inicial:** Desarrollo. **Certeza:** CONFIRMADA para la discrepancia pública; causa raíz no confirmada.
**Severidad e impacto:** ALTA: el recálculo dinámico exigido queda bloqueado sin alternativa en el dashboard; el estado visible permanece obsoleto.
**Requisito:** RF-58 Restricción 4 y matriz G88 paso 6: misma lectura 15 VERDE con 10–20 y ROJO/AMARILLO tras 20–30.
**Precondiciones:** Especie 220, sensor 738, lectura 118471; umbral inicial 10–20 y barreras M09→Edge sin publicación aplicada.
**Pasos reales:**
1. Autenticar Administrador, comprobar área 504 y ausencia inicial de umbral.
2. Crear M09 10–20, ingresar una lectura 15 y leer dashboard e historial.
3. Editar M09 a 20–30 y repetir los GET sin nueva ingesta.

**Esperado:** La misma lectura 15 deja de verse VERDE después de editar el umbral.
**Obtenido:** POST M09 HTTP 201, PATCH HTTP 200; ambos GET HTTP 200 mostraron lectura 118471 con 15 VERDE.
- API-266-02 RECHAZADO: HTTP 200; valor=15.0000; semáforo=VERDE; misma_lectura=true; barrera=true
**Evidencia:** [0](./resultado.json), [1](./newman/newman-TC-M03-G88.json); comprobaciones API-266-02.
**Fundamento del primer contacto:** discrepancia en API pública; Desarrollo atiende la funcionalidad observada, sin atribuirle causa técnica.
**Hecho probado:** POST M09 HTTP 201, PATCH HTTP 200; ambos GET HTTP 200 mostraron lectura 118471 con 15 VERDE. **Inferencia de impacto:** Los cambios M09 no actualizan el color de la lectura ya presentada. **Hipótesis:** el dashboard conserva un estado calculado con el umbral inicial; se requiere trazar el cálculo y persistencia antes de afirmar causa.
**Para cerrar:** Repetir sin ingesta adicional y acreditar el nuevo color en dashboard e historial tras la corrección.

## Comprobaciones técnicas DBA-01

| Comprobación | Estado | Observado |
| --- | --- | --- |
| DBA-01-01 | APROBADO | Login Administrador HTTP 200; /usuarios/me HTTP 200; rol e identidad=true |
| DBA-01-02 | APROBADO | Dos logins Productor HTTP 200/200; /usuarios/me HTTP 200/200; identidad sin herencia=true |
| DBA-01-03 | APROBADO | Login Administrador HTTP 200; /usuarios/me HTTP 200; rol e identidad=true |
| DBA-01-04 | APROBADO | Segundo login Administrador HTTP 200; /usuarios/me HTTP 200; rol e identidad=true |
| DBA-01-05 | APROBADO | DELETE 573 ms; HTTP 200; timeout en RUN=false |

Cuentas: ADMIN_INICIAL: HTTP 200, rol=true, identidad=true; ADMIN_A_PRODUCTOR: HTTP 200, rol=true, identidad=true; PRODUCTOR_A_ADMIN: HTTP 200, rol=true, identidad=true; ADMIN_REPETIDO: HTTP 200, rol=true, identidad=true; PRODUCTOR_VIGENTE: HTTP 200, rol=true, identidad=true.
Acceso Administrador: /configuracion/infraestructuras/349: HTTP 200; /configuracion/infraestructuras/504: HTTP 200; /configuracion/umbrales?id_especie=126: HTTP 200; /configuracion/umbrales?id_especie=220: HTTP 200.

## Barrera M09→Edge y Newman/Cypress

Barrera: ALTA_M09: PENDIENTE; EDICION_M09: PENDIENTE. No se infiere reversión MQTT por DELETE.
Newman: [newman/newman-TC-M03-G88.json](./newman/newman-TC-M03-G88.json) y [newman/newman-TC-M03-G88.html](./newman/newman-TC-M03-G88.html). Cypress: [0](./cypress/g88.cy.js/TC-M03-172%20%E2%80%94%20T%20configurable%20en%20M09%20--%20%5BTC-M03-172%5D%5BASSERT%5D%5BUI-172%5D%20El%20formulario%20de%20umbral%20permite%20configurar%20T%20(failed).png), [1](./cypress/g88.cy.js/TC-M03-172_formulario_umbral_sin_guardar.png), [2](./cypress/g88.cy.js/TC-M03-180_productor_sensor_sin_umbral.png), [3](./cypress/g88.cy.js/TC-M03-180_vista_monitoreo.png).

## Historial de intentos

| Intento | RUN | Estado registrado | Clasificación según campo oficial |
| --- | --- | --- | --- |
| 9 | RUN-G88-V1-20261025-020636 | CONCLUIDA | INCIERTO: sin campo oficial |
| 10 | RUN-G88-V1-20261030-191447 | INTERRUMPIDA | INCIERTO: sin campo oficial |
| 11 | RUN-G88-V1-20261030-192500 | INTERRUMPIDA | INCIERTO: sin campo oficial |
| 12 | RUN-G88-V1-20261030-193401 | CONCLUIDA | INCIERTO: sin campo oficial |
| 13 | RUN-G88-V1-20261030-194838 | CONCLUIDA | INCIERTO: sin campo oficial |
| 14 | RUN-G88-V1-20261030-201041 | CONCLUIDA | INCIERTO: sin campo oficial |
| 15 | RUN-G88-V1-20261030-202846 | CONCLUIDA | OFICIAL |

Motivos de los intentos anteriores: [README del grupo](./../../README.md) y sus informes conservados.

## Cierre y rollback

DELETE HTTP 200; rollback verificado; conclusión ROLLBACK_CONFIRMADO. Umbral 266: REVERTIDO_VERIFICADO; umbral QA 91: REVERTIDO_VERIFICADO. Cierre y rollback son comprobaciones distintas del veredicto RF-58.

## Evidencias y acciones

[0](./resultado.json), [1](./newman/newman-TC-M03-G88.html), [2](./newman/newman-TC-M03-G88.json), [3](./cypress/UI-172.json), [4](./cypress/UI-172.log), [5](./cypress/UI-172-excepciones.json), [6](./cypress/UI-172-login-error.json), [7](./cypress/UI-172-operaciones.json), [8](./cypress/UI-172-solicitudes.json), [9](./cypress/g88.cy.js/TC-M03-172%20%E2%80%94%20T%20configurable%20en%20M09%20--%20%5BTC-M03-172%5D%5BASSERT%5D%5BUI-172%5D%20El%20formulario%20de%20umbral%20permite%20configurar%20T%20(failed).png), [10](./cypress/g88.cy.js/TC-M03-172_formulario_umbral_sin_guardar.png), [11](./cypress/UI-180.json), [12](./cypress/UI-180.log), [13](./cypress/UI-180-login-error.json), [14](./cypress/UI-180-solicitudes.json), [15](./cypress/g88.cy.js/TC-M03-180_productor_sensor_sin_umbral.png), [16](./cypress/g88.cy.js/TC-M03-180_vista_monitoreo.png)

Estado final: RECHAZADO. Conservar este RUN para registro QA y atender DEV-G88-01/02/03.
