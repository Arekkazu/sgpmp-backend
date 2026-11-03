# Datos de prueba y metodología - E4 Cachama

Complemento de [plan_E4_cachama.md](plan_E4_cachama.md). Reúne **todos los datos que la prueba automática guarda y usa**, y para cada elemento su descripción y su metodología de verificación.

Estado: actualizado el 2026-11-03 con lo observado en el ambiente DEV (`https://api.inmero.co/api-sgpmp-dev`), finca de QA «QA Pruebas Flujo» (id 3). Resultados detallados en `../Flujo/Cachama/`; mapa consolidado en `../Flujo/MAPA_DE_TESTEO_FLUJO_MULTIESPECIE.md`.

**Origen de cada valor.** `[RF]` viene de un requisito (reqMod3y4.xlsx, fichas de M09 o los casos ya ejecutados). `[QA]` es una **propuesta de QA que no está en ningún requisito ni en el repositorio** y debe confirmarse con Desarrollo/M09 antes de formalizar los TC. `[DEV]` es un valor **observado en DEV el 2026-11-02/03**, que no es un requisito: describe cómo está configurado y cómo respondió ese ambiente. Donde hay `[DEV]` ese valor sustituye a mi propuesta `[QA]` original; los demás valores `[QA]` siguen sin confirmar.

## 1. Modelo de IA, métricas y parámetros

### 1.1 Modelo

| Elemento | Valor | Descripción | Metodología |
|---|---|---|---|
| `tipo_modelo` | `MODELO_ACUICULTURA` | Modelo de IA que corresponde al `grupo_manejo` **ACUICULTURA** (RF-15/RF-20). `[RF]` | Registrar la especie con su grupo (F1) y comprobar en la API que `tipo_modelo` se deriva solo del grupo y que no se envía en el cuerpo. |
| `paradigma` | **POBLACIONAL** | Se deriva del tipo; decide qué validaciones, métricas y campos aplican (RF-65/69/70/73). `[RF]` | Leer `paradigma` del resultado de la API y compararlo con este valor (criterio de aceptación). |
| `componente` | `DETECTOR`, `SEGUIMIENTO`, `METRICAS`, `ANOMALIAS` | Un modelo poblacional se versiona y se despliega **por componente** (RF-69/RF-70). `[RF]` | Consultar la versión activa de cada componente: debe haber 4 y exactamente una `ACTIVO` por (`tipo_modelo`, `componente`). |

### 1.2 Parámetros operativos del motor (RF-65)

| Parámetro | Rango o valor de prueba | Descripción | Metodología |
|---|---|---|---|
| `umbral_score_anomalia` | sin restricción de orden `[RF]`; valor de prueba 0.60 `[QA]` | Score de anomalía del área a partir del cual se alerta. | Guardar 0.0, 0.60 y 1.0 y comprobar que el motor aplica el nuevo valor en el ciclo siguiente. |
| `ventana_temporal_minutos` | 5-15 `[RF]`; valor de prueba 10 `[QA]` | Ventana de análisis. | Valores 4, 5, 15 y 16: 5 y 15 se aceptan; 4 y 16 se rechazan. |
| `modo_ejecucion` | `CLOUD`, `EDGE`, `HIBRIDO`; prueba con `EDGE` `[QA]` | Dónde corre la inferencia. EDGE exige el modelo descargado en el nodo Raspberry. | Cambiar el modo y comprobar la sincronización con el nodo y el fallback automático en modo EDGE/HIBRIDO. |

**Observado en DEV `[DEV]`:** `MODELO_ACUICULTURA` está configurado (`umbral_score_anomalia` 0.5, ventana de 5 minutos, modo `SERVIDOR`). El valor de prueba 0.60 de arriba es una propuesta; no se cambió la configuración. F10 no se ejecutó.

### 1.3 Métricas de validación del modelo (RF-69)

| Métrica | Umbral de aprobación | Descripción | Metodología |
|---|---|---|---|
| Calibración | estado `COMPLETADA` `[RF]` | El modelo poblacional se valida por calibración en sitio, no por F1. | Registrar una versión sin calibración completada y verificar que no se aprueba. |
| Tasa de falsos positivos en rutina | umbral por confirmar (`[RF]` sin valor numérico) | Alertas que no corresponden a un evento real en operación normal. | Reproducir 72 h de lecturas normales (sección 5) y contar alertas: debe ser el valor que fije Desarrollo. |
| Tasa de detección en eventos clínicos | umbral por confirmar (`[RF]` sin valor numérico) | Eventos inducidos que el modelo detecta. | Inyectar los eventos de la sección 5 y medir cuántos generan alerta. |
| Latencia de inferencia | ≤ 2 s `[RF]` (RF-66 CA-1) | Tiempo desde recibir el paquete hasta la salida. | Medir 10 inferencias y tomar el máximo; el caso falla si alguna supera 2000 ms. |

### 1.4 Estados de una versión del modelo

| Estado | Descripción | Metodología |
|---|---|---|
| `EN_VALIDACION` | Versión recién registrada por RF-71. | Registrar y comprobar el estado inicial. |
| `APROBADO` / `RECHAZADO` | Resultado de la validación automática (RF-69). | Registrar con métricas sobre y bajo el umbral. |
| `ACTIVO` | En producción tras el despliegue OTA exitoso (RF-70). | Activar solo desde `APROBADO`; activar desde `RECHAZADO` debe fallar. |
| `DEPRECADO` | Versión anterior desplazada al activar otra. | Activar una segunda versión y verificar que la primera queda `DEPRECADO`. |

## 2. Población y capacidad por área productiva

Regla `[RF]` (RF-20): capacidad del área = `floor(densidad × superficie)`; en un área multiespecie manda la **menor** densidad. Unidad contada: peces en un lote (activo POBLACIONAL con conteo). **Confirmada en DEV `[DEV]`:** Estanque Checho (El rosal, 10 m², Cachama Blanca) tiene `capacidad_maxima` 50.

**Cambio respecto a la propuesta inicial:** en DEV la especie es **Cachama Blanca (id 1)**, grupo `ACUICULTURA`, densidad **5** (coincide con el plan). Para no llenar DEV se usó un área de 2.05 m² (capacidad 10) en lugar de 500 m² (capacidad 2500).

| Elemento | Valor | Descripción | Metodología |
|---|---|---|---|
| Especie | Cachama Blanca, id 1 `[DEV]` | Existe en DEV. | Leerla con `GET /configuracion/especies`. |
| `densidad_poblacional_max` | 5 ind/m² `[DEV]` | Densidad máxima. | Comprobar que la capacidad sale de este valor. |
| Superficie del área de prueba | 2.05 m² `[QA]` | Da `floor(10.25)` = 10. Tipo de área `Estanque`. | Crear el área y comprobar la superficie. |
| **Capacidad con Cachama sola** | **10** `[DEV]` | `floor(5 × 2.05)`. | Resultado: 201, capacidad 10. |
| Especie de apoyo (multiespecie) | **Tortuga Qa** (id 6, densidad 2), creada para la prueba | Segunda especie del grupo `ACUICULTURA`. | Con Tortuga + Cachama en 5.05 m²: capacidad **10** (la cachama sola daría 25); en orden inverso también 10. Ver `datos_E5_tortuga.md`. |

### Cargas de prueba en el área de 2.05 m² (capacidad 10) - ejecutadas en DEV

| Carga | Cantidad | Resultado observado | Descripción | Metodología |
|---|---|---|---|---|
| **Un pez sobre el límite, en área vacía** | 11 | **422 `CAPACIDAD_EXCEDIDA`** | Primer valor inválido. | `POST /activos-biologicos`, tipo POBLACIONAL, con `cantidad_inicial` y `soporte_documental` (obligatorio si el origen es "compra"). |
| Un pez bajo el límite | 9 | 201 | Lote normal. | Registrar el lote. |
| **Límite exacto** | +1 (total 10) | 201 | Capacidad completa. | Registrar un segundo lote de 1. |
| Uno más | +1 (total 11) | **422 `CAPACIDAD_EXCEDIDA`** | Sobre el límite acumulado. | Registrar un tercer lote de 1. |
| Reducir superficie a 2.0 m² con 10 | - | 200 | Capacidad 10, límite. | `PATCH` del área con `fecha_actualizacion` (si no, 412 `CONFLICTO_CONCURRENCIA`). |
| **Reducir superficie a 1.99 m² con 10** | - | **422 `CAPACIDAD_EXCEDIDA`** | Capacidad 9 < carga 10. | La superficie queda en 2.0. |
| Área con Cachama + Bovino (`ACUICULTURA` + `ESPECIES_GRANDES`) | - | **422 `GRUPOS_MANEJO_INCOMPATIBLES`** | Prueba negativa de grupos distintos. | Crear el área con las dos especies. |

En el paradigma poblacional cada tanda es **un lote con conteo**, no un activo por animal. DEV **no tiene sandbox**: la limpieza es dar de baja el lote completo (`eventos/baja` sin `cantidad_afectada`, con **fecha UTC**: la local puede ir un día atrás y da 400 `FECHA_INVALIDA`) y desactivar el área. Un dispositivo, aunque esté desactivado, impide desactivar su área y no se puede mover ni borrar, por eso queda un área por especie. Un área desactivada conserva su nombre (409 `RECURSO_DUPLICADO`): los nombres llevan sufijo.

## 3. Dispositivos y sensores

Todo área lleva **1 Gateway Edge (Raspberry)** que habla con el broker MQTT; los sensores se asocian al área y a un dispositivo activo (RF-21/22). Sin sensor asociado al momento de la captura la ingesta responde 401.

| Dispositivo / sensor | Variable (código I3P-1) | Cantidad | Descripción | Metodología |
|---|---|---|---|---|
| Gateway Edge (Raspberry) | n/a | 1 por área | Nodo que procesa en el borde (RF-55), guarda el buffer local (RF-54) y publica al broker. | Registrar el dispositivo, comprobar `ACTIVO` y que su heartbeat llega (`ONLINE`). |
| Sonda multiparamétrica | `TEMPERATURA_AGUA` | 1 por estanque | Mide `TEMPERATURA_AGUA`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Sonda multiparamétrica | `PH_AGUA` | 1 por estanque | Mide `PH_AGUA`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Sonda multiparamétrica | `OXIGENO_DISUELTO` | 1 por estanque | Mide `OXIGENO_DISUELTO`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Cámara de visión | `(conteo/ACTIVIDAD, RF-24)` | 1 por estanque | Cámara para conteo/actividad y calibración de línea base por (área, especie), RF-24. | Calibrar, enviar una observación por `/iot/telemetria/vision` y verificar una línea base por cada par (área, especie). |

Frecuencia de muestreo de prueba: 60 s `[QA]`; la frecuencia global sale de M09 (G16). La cantidad de sensores por área (1 de cada tipo) es una propuesta `[QA]`.

**Observado en DEV `[DEV]`:** la Raspberry física (`RASPBERRY3B-TEST`) está en el Estanque Checho de El rosal, ACTIVA, y **no se usó**; la cámara de acuicultura (`CAM-ACUI-001`) está en La florida. Las pruebas usaron un dispositivo de QA (tipo `GENERICO`) con tres sensores (temperatura del agua, temperatura ambiental y humedad), **cada uno asociado a su propio lote de 1 pez**, porque un lote solo admite un sensor poblacional (409 `ACTIVO_YA_TIENE_SENSOR_POBLACIONAL`). **La temperatura del agua no se puede enviar:** su variable no tiene código de telemetría y la API responde 404 `VARIABLE_NO_ENCONTRADA` (probado con `TEMPERATURA_AGUA`, `Temperatura del agua` e `id_variable`). Lo mismo pasa con amoniaco total, nitrito, salinidad y turbidez.

## 4. Umbrales ambientales (RF-17)

Los 3 niveles (`normal`, `precaucion`, `critico`) deben ser contiguos y cubrir exactamente `[valor_min, valor_max]` `[RF]`. **Los umbrales de la tabla son los vigentes en DEV `[DEV]` y sustituyen a mis propuestas.**

| Variable | Unidad | `valor_min` | `valor_max` | Niveles `[DEV]` | Sincronización | Metodología |
|---|---|---|---|---|---|---|
| Temperatura del agua (id 1) | °C | 24 | 34 | normal 24-30; precaución 30-32; crítico 32-34 | `PENDIENTE` | Leer con `GET /configuracion/umbrales?id_especie=1`. **No se puede alimentar** (sin código de telemetría). |
| `TEMPERATURA_AMBIENTAL` (id 9) | °C | 18 | 40 | normal 18-32; precaución 32-35; crítico 35-40 | `PENDIENTE` | Igual. |
| `HUMEDAD_RELATIVA` (id 10) | % | 40 | 100 | normal 40-70; precaución 70-80; crítico 80-100 | `PENDIENTE` | Igual. |
| `PH_AGUA`, `OXIGENO_DISUELTO` | pH / mg/L | - | - | **sin umbral para Cachama en DEV** | - | Pendiente: crearlos (propuesta `[QA]` en `datos_E5_tortuga.md`). |

Los tres umbrales están en `PENDIENTE` de sincronización con el Edge (en el bovino estaban `APLICADA`); aun así el backend evaluó las lecturas y generó las alertas.

## 5. Lecturas de prueba y resultado observado `[DEV]`

Se enviaron 33 lecturas por `POST /iot/telemetria` con el token de servicio del broker. Resultado en DEV, con los umbrales de la sección 4:

| Variable | Valor | Posición | Calidad | Semáforo | Alerta |
|---|---|---|---|---|---|
| `TEMPERATURA_AMBIENTAL` | 17.99 | bajo `valor_min` | `FUERA_DE_RANGO` | AMARILLO | no |
| | 18.0 | mínimo | `LECTURA_VALIDA` | VERDE | no |
| | 31.99 / **32.0** | normal / frontera normal-precaución | `LECTURA_VALIDA` | VERDE / **VERDE** | no |
| | 32.01 / 34.99 | precaución | `LECTURA_VALIDA` | AMARILLO | no |
| | **35.0** | frontera precaución-crítico | `LECTURA_VALIDA` | **AMARILLO** | no |
| | 35.01 | crítico | `LECTURA_VALIDA` | ROJO | **sí** (alerta 270, CRITICO) |
| | 39.99 / 40.0 | crítico / máximo | `LECTURA_VALIDA` | ROJO | no (misma alerta) |
| | 40.01 | sobre `valor_max` | `FUERA_DE_RANGO` | AMARILLO | no |
| `HUMEDAD_RELATIVA` | 39.99 | bajo `valor_min` | `FUERA_DE_RANGO` | AMARILLO | no |
| | 40.0 / 69.99 | mínimo / normal | `LECTURA_VALIDA` | VERDE | no |
| | **70.0** | frontera normal-precaución | `LECTURA_VALIDA` | **VERDE** | no |
| | 70.01 / 79.99 | precaución | `LECTURA_VALIDA` | AMARILLO | no |
| | **80.0** | frontera precaución-crítico | `LECTURA_VALIDA` | **AMARILLO** | no |
| | 80.01 | crítico | `LECTURA_VALIDA` | ROJO | **sí** (alerta 271, CRITICO) |
| | 99.99 / 100.0 | crítico / máximo | `LECTURA_VALIDA` | ROJO | no (misma alerta) |
| | 100.01 | sobre el rango físico | - | - | rechazada 422 `ERROR_SENSOR` |
| Temperatura del agua | 23.99 a 34.01 (11 valores) | - | - | - | **todas rechazadas: 404 `VARIABLE_NO_ENCONTRADA`** |

**Regla observada de inclusividad** (el requisito no la fija): el límite superior de cada banda pertenece a la banda de abajo, (inferior, superior], con el mínimo del umbral en la primera banda. Una lectura fuera de [min, max] se guarda como `FUERA_DE_RANGO` y no genera alerta. Semáforo fuera de [min, max]: AMARILLO dentro de la tolerancia (por defecto el 10 % del rango del umbral, RF-58) y ROJO más allá.

## 6. Estados del sistema

| Dominio | Valores | Descripción | Metodología |
|---|---|---|---|
| Calidad de la lectura (RF-53) | `LECTURA_VALIDA`, `FUERA_DE_RANGO`, `ERROR_CALIBRACION` | Resultado de validar cada lectura. | Una lectura por valor, estado leído en el historial. |
| Desviación (RF-55) | `NORMAL`, `DESVIACION_LEVE`, `DESVIACION_MODERADA`, `DESVIACION_CRITICA`, `DESVIACION_COMPUESTA`, `ERROR_CONFIGURACION` | Clasificación del nodo Edge. | Enviar la lectura y leer `estado_desviacion`; sin umbrales debe salir `ERROR_CONFIGURACION`. |
| Origen del dato (RF-53/54) | `TIEMPO_REAL`, `BUFFER_LOCAL`, `EDGE_AGREGADO` | Cómo llegó la lectura. | Enviar un lote `BUFFER_LOCAL` repetido: solo el primero crea registro (idempotencia). |
| Severidad de alerta (RF-57) | `LEVE`, `MODERADO`, `CRITICO` | Gravedad. | Una alerta por severidad. |
| Ciclo de vida de alerta (RF-57) | `ACTIVA`, `EN_ATENCION`, `RESUELTA`, `DESCARTADA`, `VENCIDA` | Estados; `CERRADA` no existe y da 422 `TRANSICION_INVALIDA`. **Una alerta sin atender pasa sola a `VENCIDA` a los 5 min y es terminal** `[DEV]`. | Recorrer las transiciones válidas y las inválidas dentro de esos 5 minutos (ejecutado: 10 de 10 pasan). |
| Conectividad del dispositivo (RF-60) | `ONLINE`, `OFFLINE`, `SIN_SEÑAL`, `EN_MANTENIMIENTO` | Estado según heartbeat y buffer. | Enviar heartbeats y consultar; SIN_SEÑAL/OFFLINE no tienen disparador de prueba (dependencia de Desarrollo). |
| Semáforo del dashboard (RF-58) | `VERDE`, `AMARILLO`, `ROJO` (confirmados en DEV), `GRIS` (sensor sin umbral) | Estado visual. `estado_general` de la unidad queda GRIS si algún sensor no tiene umbral. | Un caso por color con las lecturas de la sección 5. |
| Sincronización de umbral (RF-17) | `PENDIENTE`, `APLICADA`, `NO_CONF` | Resultado de propagar el umbral al Edge. | Con Edge conectado: `APLICADA`; sin ACK en 30 s: `NO_CONF` (500). |
| Versión de modelo (RF-69) | `EN_VALIDACION`, `APROBADO`, `RECHAZADO`, `ACTIVO`, `DEPRECADO` | Ver 1.4. | Ver 1.4. |

## 7. Datos que la prueba automática crea y usa

**En DEV no hay sandbox** (`/test-control` no existe): lo que se crea queda; la limpieza es manual (baja de animales y lotes, asociaciones inactivas, dispositivos desactivados). En TEST sí hay sandbox (`X-Test-Run-Id`, `DELETE /test-control/runs/{id}`). Los secretos (`X-Sandbox-Secret`, token del broker, `QA_PROD_*`) salen de variables de entorno, nunca de este documento.

| Dato | Contenido | Quién lo crea | Descripción | Metodología |
|---|---|---|---|---|
| Especie | Cachama Blanca (id 1, existente), grupo ACUICULTURA, densidad 5 `[DEV]` | ya existe | No se crea ni se modifica. | Leerla y comprobar grupo y modelo. |
| Etapas | Alevino, Juvenil, Engorde | RF-16 | Etapas productivas. | Crear las tres y comprobar el orden. |
| Patología | Hipoxia en estanque de prueba (QA); variables: PH_AGUA, OXIGENO_DISUELTO, TEMPERATURA_AMBIENTAL | M04 RF-64 | Patología mínima para la predicción. Las variables se envían como **IDs** del catálogo I3P-1, no como nombres (TC-M04-G003). | Registrar y leer de vuelta las variables. |
| Umbrales | 3 existentes en DEV (temperatura del agua, temperatura ambiental, humedad) `[DEV]`; solo se leen | RF-17 | Reglas de alerta. | Leerlos y comprobar niveles y sincronización (`PENDIENTE`). |
| Finca y área | Finca QA Pruebas Flujo (id 3); área de 2.05 m² (capacidad 10) y un área por corrida de lecturas | RF-19/20 | Contenedor. | Crear y leer la capacidad. |
| Dispositivos y sensores | 1 dispositivo de QA (tipo `GENERICO`) por corrida, con sensores propios `[DEV]`; no se usó la Raspberry física ni los dispositivos de las otras fincas | RF-21/22 | Fuente de telemetría. | Crear, asociar al área y al lote o animal, calibrar y, al terminar, desactivar el dispositivo. |
| Activos | cargas de la sección 2 | M02 | Población. | Crear y comprobar la capacidad. |
| Lecturas | tabla de la sección 5 | `POST /iot/telemetria` | Telemetría de prueba. En DEV la hora de captura debe ser **posterior** a la asociación del sensor (si no, 401 `ERROR_AUTENTICACION` aunque el token sea válido); en TEST con sandbox, en cambio, las horas con `now()` fallan y se envían en el pasado. | Enviar y leer del historial. |
| Versiones de modelo | una por estado de la sección 1.4 | RF-69 | Datos de ciclo de vida. | Registrar con métricas sobre y bajo el umbral. |
| Usuarios | Administrador (setup), Productor (`QA_PROD_*`), Ingeniero de Campo (lectura del monitoreo) | variables de entorno | Roles de la prueba. | Una sesión por rol; un login invalida el token anterior. |

## 8. Resultados de ejecución en DEV (2026-11-02/03)

| Fase | Qué se hizo | Resultado | Evidencia |
|---|---|---|---|
| Capacidad (lotes) | Área de 2.05 m², lotes de 11, 9 y 1, reducción de superficie, grupos incompatibles | 10 de 10 pasan | `Flujo/Cachama/resultados_capacidad_cachama_finca3.json` |
| F7 lecturas en fronteras | 33 lecturas: temperatura ambiental y humedad (22) y temperatura del agua (11) | Temperatura ambiental y humedad: 14 pasan y 8 informativas, 0 fallan. **Temperatura del agua: 11 rechazadas (404)** | `Flujo/Cachama/resultados_fronteras_cachama_finca3.json` |
| F8 alertas | Ciclo de vida completo | 10 de 10 pasan | `Flujo/Cachama/resultados_alertas_ciclo_cachama_finca3.json` |
| F4 multiespecie | Cachama + Tortuga Qa | Pasa (ver `datos_E5_tortuga.md`) | `Flujo/Tortuga/resultados_capacidad_tortuga_finca3.json` |
| F9 calibración de visión | No ejecutada | La cámara de acuicultura está en La florida | - |
| F10 predicción | No ejecutada | `MODELO_ACUICULTURA` está configurado; solo se podría revisar en lectura | - |

**Pendiente de confirmar con Desarrollo:** Código de telemetría de la temperatura del agua (y de amoniaco total, nitrito, salinidad y turbidez); umbrales de pH y oxígeno disuelto para Cachama; sincronización de los umbrales con el Edge (`PENDIENTE`); la Raspberry física del Estanque Checho no se usó.
