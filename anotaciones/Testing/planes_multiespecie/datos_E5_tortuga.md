# Datos de prueba y metodología - E5 Tortuga

Complemento de [plan_E5_tortuga.md](plan_E5_tortuga.md). Reúne **todos los datos que la prueba automática guarda y usa**, y para cada elemento su descripción y su metodología de verificación.

Estado: actualizado el 2026-11-03 con lo observado en el ambiente DEV (`https://api.inmero.co/api-sgpmp-dev`), finca de QA «QA Pruebas Flujo» (id 3). Resultados detallados en `../Flujo/Tortuga/`; mapa consolidado en `../Flujo/MAPA_DE_TESTEO_FLUJO_MULTIESPECIE.md`.

**Origen de cada valor.** `[RF]` viene de un requisito (reqMod3y4.xlsx, fichas de M09 o los casos ya ejecutados). `[QA]` es una **propuesta de QA que no está en ningún requisito ni en el repositorio** y debe confirmarse con Desarrollo/M09 antes de formalizar los TC. `[DEV]` es un valor **observado en DEV el 2026-11-02/03**, que no es un requisito: describe cómo está configurado y cómo respondió ese ambiente. Donde hay `[DEV]` ese valor sustituye a mi propuesta `[QA]` original; los demás valores `[QA]` siguen sin confirmar.

## 1. Modelo de IA, métricas y parámetros

### 1.1 Modelo

| Elemento | Valor | Descripción | Metodología |
|---|---|---|---|
| `tipo_modelo` | `MODELO_ACUICULTURA (por confirmar)` | Modelo de IA que corresponde al `grupo_manejo` **ACUICULTURA (propuesta, por confirmar)** (RF-15/RF-20). `[RF]` | Registrar la especie con su grupo (F1) y comprobar en la API que `tipo_modelo` se deriva solo del grupo y que no se envía en el cuerpo. |
| `paradigma` | **POBLACIONAL (decisión de QA)** | Se deriva del tipo; decide qué validaciones, métricas y campos aplican (RF-65/69/70/73). `[RF]` | Leer `paradigma` del resultado de la API y compararlo con este valor (criterio de aceptación). |
| `componente` | `DETECTOR`, `SEGUIMIENTO`, `METRICAS`, `ANOMALIAS` | Un modelo poblacional se versiona y se despliega **por componente** (RF-69/RF-70). `[RF]` | Consultar la versión activa de cada componente: debe haber 4 y exactamente una `ACTIVO` por (`tipo_modelo`, `componente`). |

### 1.2 Parámetros operativos del motor (RF-65)

| Parámetro | Rango o valor de prueba | Descripción | Metodología |
|---|---|---|---|
| `umbral_score_anomalia` | sin restricción de orden `[RF]`; valor de prueba 0.60 `[QA]` | Score de anomalía del área a partir del cual se alerta. | Guardar 0.0, 0.60 y 1.0 y comprobar que el motor aplica el nuevo valor en el ciclo siguiente. |
| `ventana_temporal_minutos` | 5-15 `[RF]`; valor de prueba 10 `[QA]` | Ventana de análisis. | Valores 4, 5, 15 y 16: 5 y 15 se aceptan; 4 y 16 se rechazan. |
| `modo_ejecucion` | `CLOUD`, `EDGE`, `HIBRIDO`; prueba con `EDGE` `[QA]` | Dónde corre la inferencia. EDGE exige el modelo descargado en el nodo Raspberry. | Cambiar el modo y comprobar la sincronización con el nodo y el fallback automático en modo EDGE/HIBRIDO. |

**Observado en DEV `[DEV]`:** como su grupo propuesto es `ACUICULTURA`, le corresponde `MODELO_ACUICULTURA`, que está configurado (`umbral_score_anomalia` 0.5, ventana de 5 minutos, modo `SERVIDOR`). F10 no se ejecutó.

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

Regla `[RF]` (RF-20): capacidad del área = `floor(densidad × superficie)`; en un área multiespecie manda la **menor** densidad. Unidad contada: tortugas en un lote (activo POBLACIONAL con conteo).

**Cambio respecto a la propuesta inicial:** la tortuga **no existía en DEV**, así que se creó la especie de prueba **«Tortuga Qa» (id 6)**: grupo `ACUICULTURA` (propuesto, sin confirmar), densidad **2** `[QA]` (no es un dato real de la especie), y se **desactivó** al terminar (sigue en el listado marcada `INACTIVA`). Se usó un área de 5.05 m² (capacidad 10) en lugar de 500 m² (capacidad 1000).

| Elemento | Valor | Descripción | Metodología |
|---|---|---|---|
| Especie | Tortuga Qa, id 6 `[DEV]` | Creada con `POST /configuracion/especies`. | El sistema normalizó el nombre a «Tortuga Qa». |
| `densidad_poblacional_max` | 2 ind/m² `[QA]` | Menor que la cachama (5), para que la regla de la menor densidad se vea. | Comprobar que la capacidad sale de este valor. |
| Superficie del área de prueba | 5.05 m² `[QA]` | Da `floor(10.1)` = 10. Tipo de área `Estanque`. | Crear el área y comprobar la superficie. |
| **Capacidad con Tortuga sola** | **10** `[DEV]` | `floor(2 × 5.05)`. | Resultado: 201, capacidad 10. |
| **Capacidad multiespecie con Cachama** | **10** `[DEV]` | `floor(MIN(2, 5) × 5.05)`; la cachama sola daría 25. | Área con las dos especies: 201, capacidad 10; en orden inverso (Cachama, Tortuga) también 10. |

### Cargas de prueba en el área de 5.05 m² (capacidad 10) - ejecutadas en DEV

| Carga | Cantidad | Resultado observado | Descripción | Metodología |
|---|---|---|---|---|
| **Un tortuga sobre el límite, en área vacía** | 11 | **422 `CAPACIDAD_EXCEDIDA`** | Primer valor inválido. | `POST /activos-biologicos`, tipo POBLACIONAL, con `cantidad_inicial` y `soporte_documental` (obligatorio si el origen es "compra"). |
| Un tortuga bajo el límite | 9 | 201 | Lote normal. | Registrar el lote. |
| **Límite exacto** | +1 (total 10) | 201 | Capacidad completa. | Registrar un segundo lote de 1. |
| Uno más | +1 (total 11) | **422 `CAPACIDAD_EXCEDIDA`** | Sobre el límite acumulado. | Registrar un tercer lote de 1. |
| Reducir superficie a 5.0 m² con 10 | - | 200 | Capacidad 10, límite. | `PATCH` del área con `fecha_actualizacion` (si no, 412 `CONFLICTO_CONCURRENCIA`). |
| **Reducir superficie a 4.99 m² con 10** | - | **422 `CAPACIDAD_EXCEDIDA`** | Capacidad 9 < carga 10. | La superficie queda en 5.0. |
| Área con Tortuga + Bovino (`ACUICULTURA` + `ESPECIES_GRANDES`) | - | **422 `GRUPOS_MANEJO_INCOMPATIBLES`** | Prueba negativa de grupos distintos. | Crear el área con las dos especies. |

| Lote de 10 tortugas en el área multiespecie | 10 | 201 | Límite con la menor densidad. | Registrar. |
| Una tortuga más en el área multiespecie | +1 (total 11) | **422 `CAPACIDAD_EXCEDIDA`** | Sobre el límite multiespecie. | Registrar. |

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

**Observado en DEV `[DEV]`:** no hay dispositivos ni cámaras de tortuga. Las pruebas usaron un dispositivo de QA (tipo `GENERICO`) con dos sensores (categorías PH y OXIGENO), **cada uno asociado a su propio lote de 1 tortuga** (un lote solo admite un sensor poblacional). La temperatura del agua no se puede enviar (variable sin código de telemetría, 404 `VARIABLE_NO_ENCONTRADA`).

## 4. Umbrales ambientales (RF-17)

Los 3 niveles (`normal`, `precaucion`, `critico`) deben ser contiguos y cubrir exactamente `[valor_min, valor_max]` `[RF]`. «Tortuga Qa» no tenía umbrales, así que **se le crearon dos umbrales de QA** (la especie es nuestra y no se usa en ninguna finca de la entrega); al terminar se desactivaron.

| Variable | Unidad | `valor_min` | `valor_max` | Niveles `[QA]` | Id | Metodología |
|---|---|---|---|---|---|---|
| `PH_AGUA` (id 2) | pH | 5 | 10 | crítico 5-6.5; normal 6.5-8.5; precaución 8.5-10 | 8 | `POST /configuracion/umbrales`: 201, `PENDIENTE` (la especie no tiene Gateway Edge). |
| `OXIGENO_DISUELTO` (id 3) | mg/L | 0 | 15 | crítico 0-5; precaución 5-6; normal 6-15 | 9 | Igual. |
| Temperatura del agua (id 1) | °C | - | - | **no se creó**: la variable no se puede enviar | - | Pendiente de Desarrollo. |

No se configuró `tolerancia_semaforo`: queda el 10 % del rango por defecto.

## 5. Lecturas de prueba y resultado observado `[DEV]`

Se enviaron 23 lecturas por `POST /iot/telemetria` con el token de servicio del broker. Resultado en DEV:

| Variable | Valor | Posición | Calidad | Semáforo | Alerta |
|---|---|---|---|---|---|
| `PH_AGUA` | 4.99 | bajo `valor_min` | `FUERA_DE_RANGO` | AMARILLO | no |
| | 5.0 / 6.49 / **6.5** | crítico (mínimo, interior, frontera) | `LECTURA_VALIDA` | ROJO | **no** |
| | 6.51 / 8.49 / **8.5** | normal (interior y frontera) | `LECTURA_VALIDA` | VERDE | no |
| | 8.51 / 9.99 / 10.0 | precaución | `LECTURA_VALIDA` | AMARILLO | no |
| | 10.01 | sobre `valor_max` | `FUERA_DE_RANGO` | AMARILLO | no |
| `OXIGENO_DISUELTO` | 0.0 / 4.99 / **5.0** | crítico (mínimo, interior, frontera) | `LECTURA_VALIDA` | ROJO | sí (alerta 277, `RIESGO_HIDRICO`, CRITICO) |
| | 5.01 / 5.99 / **6.0** | precaución (interior y frontera) | `LECTURA_VALIDA` | AMARILLO | no |
| | 6.01 / 14.99 / 15.0 | normal | `LECTURA_VALIDA` | VERDE | no |
| | 15.01 | sobre `valor_max`, dentro de la tolerancia | `FUERA_DE_RANGO` | AMARILLO | no |
| | 20.0 | sobre `valor_max`, más allá de la tolerancia (1.5) | `FUERA_DE_RANGO` | **ROJO** | no |
| | 20.5 | sobre el rango físico (20) | - | - | rechazada 422 `ERROR_SENSOR` |

**Inclusividad** (el requisito no la fija): el límite superior de cada banda pertenece a ella, (inferior, superior], también cuando la banda crítica está abajo (pH 6.5 y oxígeno 5.0 son ROJO). **Alertas:** el pH en ROJO no generó ninguna (3 lecturas), mientras el oxígeno sí; puede ser que el pH solo alerte en la regla compuesta con oxígeno (RF-55), hay que confirmarlo. Semáforo fuera de [min, max]: AMARILLO dentro de la tolerancia (por defecto el 10 % del rango del umbral, RF-58) y ROJO más allá.

## 6. Estados del sistema

| Dominio | Valores | Descripción | Metodología |
|---|---|---|---|
| Calidad de la lectura (RF-53) | `LECTURA_VALIDA`, `FUERA_DE_RANGO`, `ERROR_CALIBRACION` | Resultado de validar cada lectura. | Una lectura por valor, estado leído en el historial. |
| Desviación (RF-55) | `NORMAL`, `DESVIACION_LEVE`, `DESVIACION_MODERADA`, `DESVIACION_CRITICA`, `DESVIACION_COMPUESTA`, `ERROR_CONFIGURACION` | Clasificación del nodo Edge. | Enviar la lectura y leer `estado_desviacion`; sin umbrales debe salir `ERROR_CONFIGURACION`. |
| Origen del dato (RF-53/54) | `TIEMPO_REAL`, `BUFFER_LOCAL`, `EDGE_AGREGADO` | Cómo llegó la lectura. | Enviar un lote `BUFFER_LOCAL` repetido: solo el primero crea registro (idempotencia). |
| Severidad de alerta (RF-57) | `LEVE`, `MODERADO`, `CRITICO` | Gravedad. | Una alerta por severidad. |
| Ciclo de vida de alerta (RF-57) | `ACTIVA`, `EN_ATENCION`, `RESUELTA`, `DESCARTADA`, `VENCIDA` | Estados; `CERRADA` no existe y da 422 `TRANSICION_INVALIDA`. **Una alerta sin atender pasa sola a `VENCIDA` a los 5 min y es terminal** `[DEV]`. | Recorrer las transiciones válidas y las inválidas dentro de esos 5 minutos (ejecutado: 10 de 10 pasan, con dos sensores de oxígeno porque el pH no alerta). |
| Conectividad del dispositivo (RF-60) | `ONLINE`, `OFFLINE`, `SIN_SEÑAL`, `EN_MANTENIMIENTO` | Estado según heartbeat y buffer. | Enviar heartbeats y consultar; SIN_SEÑAL/OFFLINE no tienen disparador de prueba (dependencia de Desarrollo). |
| Semáforo del dashboard (RF-58) | `VERDE`, `AMARILLO`, `ROJO` (confirmados en DEV), `GRIS` (sensor sin umbral) | Estado visual. `estado_general` de la unidad queda GRIS si algún sensor no tiene umbral. | Un caso por color con las lecturas de la sección 5. |
| Sincronización de umbral (RF-17) | `PENDIENTE`, `APLICADA`, `NO_CONF` | Resultado de propagar el umbral al Edge. | Con Edge conectado: `APLICADA`; sin ACK en 30 s: `NO_CONF` (500). |
| Versión de modelo (RF-69) | `EN_VALIDACION`, `APROBADO`, `RECHAZADO`, `ACTIVO`, `DEPRECADO` | Ver 1.4. | Ver 1.4. |

## 7. Datos que la prueba automática crea y usa

**En DEV no hay sandbox** (`/test-control` no existe): lo que se crea queda; la limpieza es manual (baja de animales y lotes, asociaciones inactivas, dispositivos desactivados). En TEST sí hay sandbox (`X-Test-Run-Id`, `DELETE /test-control/runs/{id}`). Los secretos (`X-Sandbox-Secret`, token del broker, `QA_PROD_*`) salen de variables de entorno, nunca de este documento.

| Dato | Contenido | Quién lo crea | Descripción | Metodología |
|---|---|---|---|---|
| Especie | Tortuga Qa (id 6, creada para la prueba), grupo ACUICULTURA (propuesto), densidad 2 `[QA]` | `POST /configuracion/especies` | Especie de prueba, desactivada al terminar. | Crearla, usarla y desactivarla; sigue en el listado como `INACTIVA`. |
| Etapas | Neonato, Juvenil, Adulto | RF-16 | Etapas productivas. | Crear las tres y comprobar el orden. |
| Patología | Infección de caparazón de prueba (QA); variables: PH_AGUA, OXIGENO_DISUELTO, TEMPERATURA_AMBIENTAL | M04 RF-64 | Patología mínima para la predicción. Las variables se envían como **IDs** del catálogo I3P-1, no como nombres (TC-M04-G003). | Registrar y leer de vuelta las variables. |
| Umbrales | 2 de QA (pH, oxígeno disuelto), ids 8 y 9, desactivados al terminar | RF-17 | Reglas de alerta de la especie de prueba. | Crear (201, `PENDIENTE`) y desactivar con `PATCH …/desactivar`. |
| Finca y área | Finca QA Pruebas Flujo (id 3); áreas de 5.05 m² (capacidad 10) y una por corrida de lecturas | RF-19/20 | Contenedor. | Crear y leer la capacidad. |
| Dispositivos y sensores | 1 dispositivo de QA (tipo `GENERICO`) por corrida, con sensores propios `[DEV]`; no se usó la Raspberry física ni los dispositivos de las otras fincas | RF-21/22 | Fuente de telemetría. | Crear, asociar al área y al lote o animal, calibrar y, al terminar, desactivar el dispositivo. |
| Activos | cargas de la sección 2 | M02 | Población. | Crear y comprobar la capacidad. |
| Lecturas | tabla de la sección 5 | `POST /iot/telemetria` | Telemetría de prueba. En DEV la hora de captura debe ser **posterior** a la asociación del sensor (si no, 401 `ERROR_AUTENTICACION` aunque el token sea válido); en TEST con sandbox, en cambio, las horas con `now()` fallan y se envían en el pasado. | Enviar y leer del historial. |
| Versiones de modelo | una por estado de la sección 1.4 | RF-69 | Datos de ciclo de vida. | Registrar con métricas sobre y bajo el umbral. |
| Usuarios | Administrador (setup), Productor (`QA_PROD_*`), Ingeniero de Campo (lectura del monitoreo) | variables de entorno | Roles de la prueba. | Una sesión por rol; un login invalida el token anterior. |

## 8. Resultados de ejecución en DEV (2026-11-02/03)

| Fase | Qué se hizo | Resultado | Evidencia |
|---|---|---|---|
| F1 especie | Crear «Tortuga Qa» (ACUICULTURA, densidad 2) | 201, id 6; luego desactivada | - |
| Capacidad, incluida la multiespecie con Cachama | Área de 5.05 m², lotes, reducción de superficie, grupos incompatibles, Tortuga + Cachama en ambos órdenes | 14 de 14 pasan | `Flujo/Tortuga/resultados_capacidad_tortuga_finca3.json` |
| F7 lecturas en fronteras | 23 lecturas de pH y oxígeno, con umbrales de QA | 14 pasan y 9 informativas, 0 fallan | `Flujo/Tortuga/resultados_fronteras_tortuga_finca3.json` |
| F8 alertas | Ciclo de vida completo (dos sensores de oxígeno) | 10 de 10 pasan | `Flujo/Tortuga/resultados_alertas_ciclo_tortuga_finca3.json` |
| F9 calibración de visión | No ejecutada | No hay cámara de tortuga | - |
| F10 predicción | No ejecutada | `MODELO_ACUICULTURA` está configurado; solo se podría revisar en lectura | - |

**Pendiente de confirmar con Desarrollo:** Confirmar el grupo de manejo de la tortuga y su densidad real; el pH en ROJO no genera alerta; la temperatura del agua no se puede enviar; umbrales reales de la especie (los de QA se desactivaron).
