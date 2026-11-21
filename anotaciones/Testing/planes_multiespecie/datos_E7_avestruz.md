# Datos de prueba y metodología - E7 Avestruz

Complemento de [plan_E7_avestruz.md](plan_E7_avestruz.md). Reúne **todos los datos que la prueba automática guarda y usa**, y para cada elemento su descripción y su metodología de verificación.

Estado: actualizado el 2026-11-03 con lo observado en el ambiente DEV (`https://api.inmero.co/api-sgpmp-dev`), finca de QA «QA Pruebas Flujo» (id 3). Resultados detallados en `../Flujo/Avestruz/`; mapa consolidado en `../Flujo/MAPA_DE_TESTEO_FLUJO_MULTIESPECIE.md`.

**Origen de cada valor.** `[RF]` viene de un requisito (reqMod3y4.xlsx, fichas de M09 o los casos ya ejecutados). `[QA]` es una **propuesta de QA que no está en ningún requisito ni en el repositorio** y debe confirmarse con Desarrollo/M09 antes de formalizar los TC. `[DEV]` es un valor **observado en DEV el 2026-11-02/03**, que no es un requisito: describe cómo está configurado y cómo respondió ese ambiente. Donde hay `[DEV]` ese valor sustituye a mi propuesta `[QA]` original; los demás valores `[QA]` siguen sin confirmar.

## 1. Modelo de IA, métricas y parámetros

### 1.1 Modelo

| Elemento | Valor | Descripción | Metodología |
|---|---|---|---|
| `tipo_modelo` | `MODELO_ESPECIES_GRANDES (por confirmar)` | Modelo de IA que corresponde al `grupo_manejo` **ESPECIES_GRANDES (propuesta, por confirmar)** (RF-15/RF-20). `[RF]` | Registrar la especie con su grupo (F1) y comprobar en la API que `tipo_modelo` se deriva solo del grupo y que no se envía en el cuerpo. |
| `paradigma` | **INDIVIDUAL (decisión de QA)** | Se deriva del tipo; decide qué validaciones, métricas y campos aplican (RF-65/69/70/73). `[RF]` | Leer `paradigma` del resultado de la API y compararlo con este valor (criterio de aceptación). |
| `componente` | no aplica | Los modelos individuales no tienen componentes (son del paradigma poblacional). `[RF]` | Pedir un componente en un modelo individual y verificar el rechazo. |

### 1.2 Parámetros operativos del motor (RF-65)

| Parámetro | Rango o valor de prueba | Descripción | Metodología |
|---|---|---|---|
| `umbral_riesgo_alto` | 0.50-0.95 `[RF]`; valor de prueba 0.70 `[QA]` | Probabilidad mínima para clasificar Riesgo Alto. | Valores 0.49, 0.50, 0.95 y 0.96: los extremos válidos se aceptan y los externos devuelven 400/422. |
| `umbral_alerta_critica` | ≥ `umbral_riesgo_alto`; valor de prueba 0.85 `[QA]` | Probabilidad que dispara la alerta crítica. | Guardar un valor menor que `umbral_riesgo_alto` y verificar el rechazo; guardar uno igual (límite) y verificar que se acepta. |
| `ventana_temporal_minutos` | 5-15 `[RF]`; valor de prueba 10 `[QA]` | Ventana de análisis. | Valores 4, 5, 15 y 16: 5 y 15 se aceptan; 4 y 16 se rechazan. |
| `modo_ejecucion` | `CLOUD`, `EDGE`, `HIBRIDO`; prueba con `EDGE` `[QA]` | Dónde corre la inferencia. EDGE exige el modelo descargado en el nodo Raspberry. | Cambiar el modo y comprobar la sincronización con el nodo y el fallback automático en modo EDGE/HIBRIDO. |

**Observado en DEV `[DEV]`:** como su grupo propuesto es `ESPECIES_GRANDES`, le corresponde `MODELO_ESPECIES_GRANDES`, que **no tiene configuración del motor en DEV** (404 `CONFIGURACION_MOTOR_NO_ENCONTRADA`), aunque hay una inferencia de bovino en modo sombra. Crearla es una decisión de Desarrollo (la configuración es compartida). F10 no se ejecutó.

### 1.3 Métricas de validación del modelo (RF-69)

| Métrica | Umbral de aprobación | Descripción | Metodología |
|---|---|---|---|
| `f1_score_global` | ≥ 0.80 `[RF]` (trigger de degradación de RF-71) | Equilibrio entre precisión y sensibilidad en todas las clases. | Registrar una versión con F1 0.80 (límite, aprobada) y 0.79 (rechazada) y comprobar el estado resultante. |
| `recall_clase_riesgo_alto` | ≥ 0.85 `[RF]` (usado por TC-M04-G024) | Cuántos casos de riesgo alto detecta el modelo. | Mismo método con 0.85 y 0.84. |
| `precision_global`, `accuracy`, `roc_auc_score` | rango obligatorio 0.0-1.0 `[RF]` | Métricas complementarias. | Enviar -0.01 y 1.01: se rechazan. |
| `recall_por_clase`, `matriz_confusion` | presentes y coherentes `[RF]` | Detalle por patología del catálogo. | Verificar que cada clase del catálogo (RF-64) aparece en el detalle. |
| Latencia de inferencia | ≤ 2 s `[RF]` (RF-66 CA-1) | Tiempo desde recibir el paquete hasta la salida. | Medir 10 inferencias y tomar el máximo; el caso falla si alguna supera 2000 ms. |

### 1.4 Estados de una versión del modelo

| Estado | Descripción | Metodología |
|---|---|---|
| `EN_VALIDACION` | Versión recién registrada por RF-71. | Registrar y comprobar el estado inicial. |
| `APROBADO` / `RECHAZADO` | Resultado de la validación automática (RF-69). | Registrar con métricas sobre y bajo el umbral. |
| `ACTIVO` | En producción tras el despliegue OTA exitoso (RF-70). | Activar solo desde `APROBADO`; activar desde `RECHAZADO` debe fallar. |
| `DEPRECADO` | Versión anterior desplazada al activar otra. | Activar una segunda versión y verificar que la primera queda `DEPRECADO`. |

## 2. Población y capacidad por área productiva

Regla `[RF]` (RF-20): capacidad del área = `floor(densidad × superficie)`; en un área multiespecie manda la **menor** densidad. Unidad contada: animal con identificador (activo INDIVIDUAL).

**Cambio respecto a la propuesta inicial:** el avestruz **no existía en DEV**, así que se creó la especie de prueba **«Avestruz Qa» (id 7)**: grupo `ESPECIES_GRANDES` (propuesto, sin confirmar), densidad **0.02** `[QA]` (no 0.025 como en la propuesta, ni un dato real de la especie), y se **desactivó** al terminar (sigue en el listado marcada `INACTIVA`). Se usó un área de 155 m² (capacidad 3) en lugar de 400 m² (capacidad 10).

| Elemento | Valor | Descripción | Metodología |
|---|---|---|---|
| Especie | Avestruz Qa, id 7 `[DEV]` | Creada con `POST /configuracion/especies`. | El sistema normalizó el nombre a «Avestruz Qa». |
| `densidad_poblacional_max` | 0.02 ind/m² `[QA]` | Menor que el bovino (0.1), para que la regla de la menor densidad se vea. | Comprobar que la capacidad sale de este valor. |
| Superficie del área de prueba | 155 m² `[QA]` | Da `floor(3.1)` = 3. Tipo de área `Potrero`. | Crear el área y comprobar la superficie. |
| **Capacidad con Avestruz sola** | **3** `[DEV]` | `floor(0.02 × 155)`. | Resultado: 201, capacidad 3. |
| **Capacidad multiespecie con Bovino** | **3** `[DEV]` | `floor(MIN(0.02, 0.1) × 150)`; el bovino solo daría 15. | Área de 150 m² con las dos especies: 201, capacidad 3; en orden inverso también 3. |

### Cargas de prueba en el área de 155 m² (capacidad 3) - ejecutadas en DEV

| Carga | Cantidad | Resultado observado | Descripción | Metodología |
|---|---|---|---|---|
| Animales 1, 2 y 3 | 3 | 201 | Hasta el **límite exacto**. | `POST /activos-biologicos`, tipo INDIVIDUAL, con `raza`, `sexo` y `soporte_documental` (obligatorio si el origen es "compra"). |
| **Animal 4** | 4 | **422 `CAPACIDAD_EXCEDIDA`** | Un animal sobre el límite. | Registrar el cuarto. |
| Identificador repetido | 1 | 409 `IDENTIFICADOR_DUPLICADO` | Unicidad del identificador. | Repetir el del primero. |
| Reducir superficie a 150 m² con 3 animales | - | 200 | Capacidad 3, límite. | `PATCH` del área con `fecha_actualizacion`. |
| **Reducir superficie a 149.99 m² con 3** | - | **422 `CAPACIDAD_EXCEDIDA`** | Capacidad 2 < carga 3. | La superficie queda en 150.00. |
| Área con Avestruz + Ternero | - | **422 `GRUPOS_MANEJO_INCOMPATIBLES`** | `ESPECIES_GRANDES` + `ESPECIES_MEDIANAS`. | Crear el área con las dos especies. |
| Animales 1 a 3 en el área multiespecie / el 4.º | 3 / 1 | 201 / **422 `CAPACIDAD_EXCEDIDA`** | Límite con la menor densidad. | Registrar. |

Cada animal es un activo propio. DEV **no tiene sandbox**: la limpieza es dar de baja cada animal (tipo `perdida`, con **fecha UTC**) y desactivar el área; un dispositivo, aunque esté desactivado, impide desactivar su área, por eso queda un área por corrida de lecturas.

## 3. Dispositivos y sensores

Todo área lleva **1 Gateway Edge (Raspberry)** que habla con el broker MQTT; los sensores se asocian al área y a un dispositivo activo (RF-21/22). Sin sensor asociado al momento de la captura la ingesta responde 401.

| Dispositivo / sensor | Variable (código I3P-1) | Cantidad | Descripción | Metodología |
|---|---|---|---|---|
| Gateway Edge (Raspberry) | n/a | 1 por área | Nodo que procesa en el borde (RF-55), guarda el buffer local (RF-54) y publica al broker. | Registrar el dispositivo, comprobar `ACTIVO` y que su heartbeat llega (`ONLINE`). |
| Banda biométrica | `TEMP_CORPORAL` | 1 por animal | Mide `TEMP_CORPORAL`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Banda biométrica | `FRECUENCIA_CARDIACA` | 1 por animal | Mide `FRECUENCIA_CARDIACA`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Banda biométrica | `FRECUENCIA_RESPIRATORIA` | 1 por animal | Mide `FRECUENCIA_RESPIRATORIA`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Estación ambiental | `TEMPERATURA_AMBIENTAL` | 1 por área | Mide `TEMPERATURA_AMBIENTAL`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Estación ambiental | `HUMEDAD_RELATIVA` | 1 por área | Mide `HUMEDAD_RELATIVA`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |

Frecuencia de muestreo de prueba: 60 s `[QA]`; la frecuencia global sale de M09 (G16). La cantidad de sensores por área (1 de cada tipo) es una propuesta `[QA]`.

**Observado en DEV `[DEV]`:** no hay dispositivos de avestruz. Las pruebas usaron un dispositivo de QA (tipo `GENERICO`) con dos sensores (temperatura corporal, categoría TEMPERATURA, y frecuencia cardiaca, sin categoría), asociados al animal (`tipo_asociacion` DIRECTA). El sensor debe tener la especie en `especies-compatibles` y estar calibrado.

## 4. Umbrales ambientales (RF-17)

Los 3 niveles (`normal`, `precaucion`, `critico`) deben ser contiguos y cubrir exactamente `[valor_min, valor_max]` `[RF]`. «Avestruz Qa» no tenía umbrales, así que **se le crearon dos umbrales de QA** (la especie es nuestra y no se usa en ninguna finca de la entrega); al terminar se desactivaron. **Cambio respecto a mi propuesta:** el crítico quedó en el lado alto, como en el bovino de DEV, para que se generen alertas por fiebre; la propuesta original lo ponía en el lado bajo (hipotermia).

| Variable | Unidad | `valor_min` | `valor_max` | Niveles `[QA]` | Id | Metodología |
|---|---|---|---|---|---|---|
| `TEMP_CORPORAL` (id 13) | °C | 37 | 43 | normal 37-39.8; precaución 39.8-40.5; crítico 40.5-43 | 10 | `POST /configuracion/umbrales`: 201, `PENDIENTE` (la especie no tiene Gateway Edge). |
| `FRECUENCIA_CARDIACA` (id 14) | bpm | 30 | 180 | normal 30-100; precaución 100-140; crítico 140-180 | 11 | Igual. |
| `FRECUENCIA_RESPIRATORIA`, `TEMPERATURA_AMBIENTAL`, `HUMEDAD_RELATIVA` | - | - | - | **no se crearon** | - | Pendiente. |

## 5. Lecturas de prueba y resultado observado `[DEV]`

Se enviaron 22 lecturas por `POST /iot/telemetria` con el token de servicio del broker. Resultado en DEV:

| Variable | Valor | Posición | Calidad | Semáforo | Alerta |
|---|---|---|---|---|---|
| `TEMP_CORPORAL` | 36.99 | bajo `valor_min` | `FUERA_DE_RANGO` | AMARILLO | no |
| | 37.0 / 39.79 | mínimo / normal | `LECTURA_VALIDA` | VERDE | no |
| | **39.8** | frontera normal-precaución | `LECTURA_VALIDA` | **VERDE** | no |
| | 39.81 / 40.49 | precaución | `LECTURA_VALIDA` | AMARILLO | no |
| | **40.5** | frontera precaución-crítico | `LECTURA_VALIDA` | **AMARILLO** | no |
| | 40.51 | crítico | `LECTURA_VALIDA` | ROJO | **sí** (alerta 283, CRITICO) |
| | 42.99 / 43.0 | crítico / máximo | `LECTURA_VALIDA` | ROJO | no (misma alerta) |
| | 43.01 | sobre `valor_max` | `FUERA_DE_RANGO` | AMARILLO | no |
| `FRECUENCIA_CARDIACA` | 29.99 | bajo `valor_min` | `FUERA_DE_RANGO` | AMARILLO | no |
| | 30 / 99.99 | mínimo / normal | `LECTURA_VALIDA` | VERDE | no |
| | **100** | frontera normal-precaución | `LECTURA_VALIDA` | **VERDE** | no |
| | 100.01 / 139.99 | precaución | `LECTURA_VALIDA` | AMARILLO | no |
| | **140** | frontera precaución-crítico | `LECTURA_VALIDA` | **AMARILLO** | no |
| | 140.01 / 179.99 / 180 | crítico | `LECTURA_VALIDA` | ROJO | **sí** (alerta 284, CRITICO) |
| | 180.01 | sobre `valor_max` | `FUERA_DE_RANGO` | AMARILLO | no |

**Regla observada de inclusividad** (el requisito no la fija): el límite superior de cada banda pertenece a la banda de abajo, (inferior, superior], con el mínimo en la primera banda. La alerta de frecuencia cardiaca quedó asociada a la lectura de 179.99 y no a la primera crítica (la asociación lectura-alerta es asíncrona). Semáforo fuera de [min, max]: AMARILLO dentro de la tolerancia (por defecto el 10 % del rango del umbral, RF-58) y ROJO más allá.

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
| Especie | Avestruz Qa (id 7, creada para la prueba), grupo ESPECIES_GRANDES (propuesto), densidad 0.02 `[QA]` | `POST /configuracion/especies` | Especie de prueba, desactivada al terminar. | Crearla, usarla y desactivarla; sigue en el listado como `INACTIVA`. |
| Etapas | Polluelo, Juvenil, Adulto reproductor | RF-16 | Etapas productivas. | Crear las tres y comprobar el orden. |
| Patología | Hipertermia de avestruz de prueba (QA); variables: TEMP_CORPORAL, FRECUENCIA_CARDIACA, FRECUENCIA_RESPIRATORIA | M04 RF-64 | Patología mínima para la predicción. Las variables se envían como **IDs** del catálogo I3P-1, no como nombres (TC-M04-G003). | Registrar y leer de vuelta las variables. |
| Umbrales | 2 de QA (temperatura corporal, frecuencia cardiaca), ids 10 y 11, desactivados al terminar | RF-17 | Reglas de alerta de la especie de prueba. | Crear (201, `PENDIENTE`) y desactivar con `PATCH …/desactivar`. |
| Finca y área | Finca QA Pruebas Flujo (id 3); áreas de 155 y 150 m² (capacidad 3) y una por corrida de lecturas | RF-19/20 | Contenedor. | Crear y leer la capacidad. |
| Dispositivos y sensores | 1 dispositivo de QA (tipo `GENERICO`) por corrida, con sensores propios `[DEV]`; no se usó la Raspberry física ni los dispositivos de las otras fincas | RF-21/22 | Fuente de telemetría. | Crear, asociar al área y al lote o animal, calibrar y, al terminar, desactivar el dispositivo. |
| Activos | cargas de la sección 2 | M02 | Población. | Crear y comprobar la capacidad. |
| Lecturas | tabla de la sección 5 | `POST /iot/telemetria` | Telemetría de prueba. En DEV la hora de captura debe ser **posterior** a la asociación del sensor (si no, 401 `ERROR_AUTENTICACION` aunque el token sea válido); en TEST con sandbox, en cambio, las horas con `now()` fallan y se envían en el pasado. | Enviar y leer del historial. |
| Versiones de modelo | una por estado de la sección 1.4 | RF-69 | Datos de ciclo de vida. | Registrar con métricas sobre y bajo el umbral. |
| Usuarios | Administrador (setup), Productor (`QA_PROD_*`), Ingeniero de Campo (lectura del monitoreo) | variables de entorno | Roles de la prueba. | Una sesión por rol; un login invalida el token anterior. |

## 8. Resultados de ejecución en DEV (2026-11-02/03)

| Fase | Qué se hizo | Resultado | Evidencia |
|---|---|---|---|
| F1 especie | Crear «Avestruz Qa» (ESPECIES_GRANDES, densidad 0.02) | 201, id 7; luego desactivada | - |
| Capacidad, incluida la multiespecie con Bovino | Área de 155 m², animales 1 a 4, identificador repetido, reducción de superficie, grupos incompatibles, Avestruz + Bovino en ambos órdenes | 17 de 17 pasan | `Flujo/Avestruz/resultados_capacidad_avestruz_finca3.json` |
| F7 lecturas en fronteras | 22 lecturas de temperatura corporal y frecuencia cardiaca, con umbrales de QA | 14 pasan y 8 informativas, 0 fallan | `Flujo/Avestruz/resultados_fronteras_avestruz_finca3.json` |
| F8 alertas | Ciclo de vida completo | 10 de 10 pasan | `Flujo/Avestruz/resultados_alertas_ciclo_avestruz_finca3.json` |
| F9 calibración de visión | No ejecutada | No hay cámara de avestruz | - |
| F10 predicción | No ejecutada | `MODELO_ESPECIES_GRANDES` sin configuración del motor en DEV | - |

**Pendiente de confirmar con Desarrollo:** Confirmar el grupo de manejo del avestruz y su densidad real; configuración del motor de `MODELO_ESPECIES_GRANDES`; umbrales reales de la especie (los de QA se desactivaron); frecuencia respiratoria, temperatura ambiental y humedad.
