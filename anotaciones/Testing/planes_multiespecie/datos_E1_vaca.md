# Datos de prueba y metodología - E1 Vaca

Complemento de [plan_E1_vaca.md](plan_E1_vaca.md). Reúne **todos los datos que la prueba automática guarda y usa**, y para cada elemento su descripción y su metodología de verificación.

Estado: actualizado el 2026-11-02 con lo observado en el ambiente DEV (`https://api.inmero.co/api-sgpmp-dev`). Los resultados de las ejecuciones están en `../Flujo/Bovino/`.

**Origen de cada valor.** `[RF]` viene de un requisito (reqMod3y4.xlsx, fichas de M09 o los casos ya ejecutados). `[QA]` es una **propuesta de QA que no está en ningún requisito ni en el repositorio** y debe confirmarse con Desarrollo/M09 antes de formalizar los TC. `[DEV]` es un valor **observado en DEV el 2026-11-02**, que no es un requisito: describe cómo está configurado y cómo respondió ese ambiente. Donde hay `[DEV]` ese valor sustituye a mi propuesta `[QA]` original; los demás valores `[QA]` siguen sin confirmar.

## 1. Modelo de IA, métricas y parámetros

### 1.1 Modelo

| Elemento | Valor | Descripción | Metodología |
|---|---|---|---|
| `tipo_modelo` | `MODELO_ESPECIES_GRANDES` | Modelo de IA que corresponde al `grupo_manejo` **ESPECIES_GRANDES** (RF-15/RF-20). `[RF]` | Registrar la especie con su grupo (F1) y comprobar en la API que `tipo_modelo` se deriva solo del grupo y que no se envía en el cuerpo. |
| `paradigma` | **INDIVIDUAL** | Se deriva del tipo; decide qué validaciones, métricas y campos aplican (RF-65/69/70/73). `[RF]` | Leer `paradigma` del resultado de la API y compararlo con este valor (criterio de aceptación). |
| `componente` | no aplica | Los modelos individuales no tienen componentes (son del paradigma poblacional). `[RF]` | Pedir un componente en un modelo individual y verificar el rechazo. |

### 1.2 Parámetros operativos del motor (RF-65)

| Parámetro | Rango o valor de prueba | Descripción | Metodología |
|---|---|---|---|
| `umbral_riesgo_alto` | 0.50-0.95 `[RF]`; valor de prueba 0.70 `[QA]` | Probabilidad mínima para clasificar Riesgo Alto. | Valores 0.49, 0.50, 0.95 y 0.96: los extremos válidos se aceptan y los externos devuelven 400/422. |
| `umbral_alerta_critica` | ≥ `umbral_riesgo_alto`; valor de prueba 0.85 `[QA]` | Probabilidad que dispara la alerta crítica. | Guardar un valor menor que `umbral_riesgo_alto` y verificar el rechazo; guardar uno igual (límite) y verificar que se acepta. |
| `ventana_temporal_minutos` | 5-15 `[RF]`; valor de prueba 10 `[QA]` | Ventana de análisis. | Valores 4, 5, 15 y 16: 5 y 15 se aceptan; 4 y 16 se rechazan. |
| `modo_ejecucion` | `CLOUD`, `EDGE`, `HIBRIDO`; prueba con `EDGE` `[QA]` | Dónde corre la inferencia. EDGE exige el modelo descargado en el nodo Raspberry. | Cambiar el modo y comprobar la sincronización con el nodo y el fallback automático en modo EDGE/HIBRIDO. |

**Observado en DEV `[DEV]`:** `MODELO_ESPECIES_GRANDES` **no tiene configuración del motor** (`GET /prediccion/motor-ia/MODELO_ESPECIES_GRANDES` responde 404 `CONFIGURACION_MOTOR_NO_ENCONTRADA`), aunque existen las de aves, porcinos, acuicultura, medianas y contagio. Hay una inferencia de bovino en modo sombra (animal BOV-003-DEV, versión `ESPECIES_GRANDES_4_261025_ed219d41`, latencia 47 ms frente al límite de 2 s). Crear esa configuración es una decisión de Desarrollo: la configuración es compartida y puede afectar a los animales de demo. Por eso F10 no se ejecutó con escritura.

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

Regla `[RF]` (RF-20): capacidad del área = `floor(densidad × superficie)`; en un área multiespecie manda la **menor** densidad. Unidad contada: animal con arete (activo INDIVIDUAL). **Confirmada en DEV `[DEV]`:** Potrero 1 (100 m², Bovino) tiene `capacidad_maxima` 10, igual a `floor(0.1 × 100)`.

**Cambio respecto a la propuesta inicial:** en DEV no existe "Vaca"; la especie es **Bovino (id 2)**, grupo `ESPECIES_GRANDES`, modelo `MODELO_ESPECIES_GRANDES`, densidad **0.1** (no 0.05). Para no llenar DEV, la prueba usa un área pequeña de 35 m² (capacidad 3) en lugar de 400 m² (capacidad 40): se prueban los mismos límites con 4 animales.

| Elemento | Valor | Descripción | Metodología |
|---|---|---|---|
| Especie | Bovino, id 2 `[DEV]` | Especie existente en DEV. | Leerla con `GET /configuracion/especies` y comprobar grupo y modelo. |
| `densidad_poblacional_max` | 0.1 ind/m² `[DEV]` | Densidad máxima. | Comprobar que la capacidad de las áreas sale de este valor. |
| Superficie del área de prueba | 35 m² `[QA]` | Da `floor(3.5)` = 3: prueba también el redondeo hacia abajo. | Crear el área y comprobar la superficie. |
| **Capacidad con Bovino sola** | **3** `[DEV]` | `floor(0.1 × 35)`. | Crear el área; `capacidad_maxima` debe ser 3. Resultado: 201, capacidad 3. |
| Especie de otro grupo | Ternero (id 3, `ESPECIES_MEDIANAS`) `[DEV]` | Para la prueba negativa de grupos distintos. | Área con Bovino + Ternero: 422 `GRUPOS_MANEJO_INCOMPATIBLES`. |
| Capacidad multiespecie | no probada | En DEV no hay una segunda especie `ESPECIES_GRANDES` (E7 Avestruz no existe). | Pendiente: requiere crear la especie de apoyo (escribe en el catálogo). |

### Cargas de prueba en el área de 35 m² (capacidad 3) - ejecutadas en DEV

| Carga | Cantidad | Resultado observado | Descripción | Metodología |
|---|---|---|---|---|
| Animales 1 y 2 | 2 | 201 | Bajo el límite. | `POST /activos-biologicos`, tipo INDIVIDUAL, con `soporte_documental` (obligatorio si el origen es "compra"). |
| **Límite exacto** | **3** | 201 | Capacidad completa. | Registrar el tercero. |
| **Un animal sobre el límite** | **4** | **422 `CAPACIDAD_EXCEDIDA`** | Primer valor inválido. | El mensaje indica "3 individuos = MIN d…". |
| Identificador duplicado | 1 | 409 `IDENTIFICADOR_DUPLICADO` | Unicidad del identificador. | Repetir el identificador del primero. |
| Reducir superficie a 30 m² con 3 animales | - | 200 | Capacidad 3, límite. | `PATCH` del área; hay que enviar `fecha_actualizacion` o responde 412 `CONFLICTO_CONCURRENCIA`. |
| **Reducir superficie a 29.99 m² con 3 animales** | - | **422 `CAPACIDAD_EXCEDIDA`** | Capacidad 2 < carga 3. | La superficie queda en 30.00. |

Cada animal es un activo propio: las cargas grandes se crean con un script. DEV **no tiene sandbox**, así que no hay rollback: la limpieza es dar de baja los animales (tipo `perdida`; el cierre de ciclo responde 422 `SIN_FASE_ACTIVA`) y desactivar el área. Un dispositivo, aunque esté desactivado, impide desactivar su área y no se puede mover ni borrar, por eso se reutiliza un **área fija de QA (id 12)**. Un área desactivada conserva su nombre (409 `RECURSO_DUPLICADO`).

## 3. Dispositivos y sensores

Todo área lleva **1 Gateway Edge (Raspberry)** que habla con el broker MQTT; los sensores se asocian al área y a un dispositivo activo (RF-21/22). Sin sensor asociado al momento de la captura la ingesta responde 401.

| Dispositivo / sensor | Variable (código I3P-1) | Cantidad | Descripción | Metodología |
|---|---|---|---|---|
| Gateway Edge (Raspberry) | n/a | 1 por área | Nodo que procesa en el borde (RF-55), guarda el buffer local (RF-54) y publica al broker. | Registrar el dispositivo, comprobar `ACTIVO` y que su heartbeat llega (`ONLINE`). |
| Collar biométrico | `TEMP_CORPORAL` | 1 por animal | Mide `TEMP_CORPORAL`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Collar biométrico | `FRECUENCIA_CARDIACA` | 1 por animal | Mide `FRECUENCIA_CARDIACA`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Collar biométrico | `FRECUENCIA_RESPIRATORIA` | 1 por animal | Mide `FRECUENCIA_RESPIRATORIA`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Collar biométrico | `ACTIVIDAD` | 1 por animal | Mide `ACTIVIDAD`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Estación ambiental | `TEMPERATURA_AMBIENTAL` | 1 por área | Mide `TEMPERATURA_AMBIENTAL`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Estación ambiental | `HUMEDAD_RELATIVA` | 1 por área | Mide `HUMEDAD_RELATIVA`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |

**Observado en DEV `[DEV]`:** el Potrero 1 no usa Raspberry física: sus datos vienen de `PC-BOV-001`, un **simulador Edge** en el servidor (FC, temperatura corporal y actividad, más temperatura ambiental y humedad del potrero; una lectura cada 5 min). La Raspberry física (`RASPBERRY3B-TEST`) está en el Estanque Checho (acuicultura). Por eso la prueba de vaca cubre el recorrido broker y backend, no el firmware físico. Las pruebas con escritura usan dispositivos y sensores de QA propios (tipo `GENERICO`) para no alterar al simulador.

Frecuencia de muestreo de prueba: 60 s `[QA]`; la frecuencia global sale de M09 (G16). La cantidad de sensores por área (1 de cada tipo) es una propuesta `[QA]`.

## 4. Umbrales ambientales (RF-17)

Los 3 niveles (`normal`, `precaucion`, `critico`) deben ser contiguos y cubrir exactamente `[valor_min, valor_max]` `[RF]`, y el rango debe caber en el rango físico de la variable. El orden de los niveles en el cuerpo no importa. Al guardar, el umbral se propaga al Gateway Edge y queda `APLICADA` / `PENDIENTE` / `NO_CONF`. **Los umbrales de la tabla son los vigentes en DEV `[DEV]` y sustituyen a mis propuestas** (que ponían, por ejemplo, 36-41.5 °C para temperatura corporal).

| Variable | Unidad | `valor_min` | `valor_max` | Niveles `[DEV]` | Sincronización | Metodología |
|---|---|---|---|---|---|---|
| `TEMP_CORPORAL` (id 13) | °C | 38 | 43 | normal 38-39.5; precaución 39.5-40; crítico 40-43 | `APLICADA` | Leer con `GET /configuracion/umbrales?id_especie=2`; comprobar que son 3 niveles contiguos que cubren [min, max]. |
| `FRECUENCIA_CARDIACA` (id 14) | bpm | 40 | 160 | normal 40-120; precaución 120-140; crítico 140-160 | `APLICADA` | Igual. |
| `FRECUENCIA_RESPIRATORIA` | rpm | - | - | **sin umbral en DEV** | - | Pendiente: crearlo (propuesta `[QA]`: normal 10-30; precaución 30-80; crítico 5-10). |
| `TEMPERATURA_AMBIENTAL`, `HUMEDAD_RELATIVA` (Potrero 1) | °C / % | - | - | **sin umbral para Bovino en DEV** (`sin_umbral=True`) | - | Por eso el semáforo de esos sensores es GRIS y el estado general de la unidad también. Propuesta `[QA]`: temperatura 5-45 °C, humedad 20-95 %. |
| `ACTIVIDAD` | m/s² | - | - | **sin umbral en DEV** | - | Igual (semáforo GRIS). |

## 5. Lecturas de prueba y resultado observado `[DEV]`

Se enviaron 22 lecturas por `POST /iot/telemetria` con el token de servicio del broker, a sensores de un dispositivo de QA (no a los del simulador). Resultado en DEV, con los umbrales de la sección 4:

| Variable | Valor | Posición | Calidad | Semáforo | Alerta |
|---|---|---|---|---|---|
| `TEMP_CORPORAL` | 37.99 | bajo `valor_min` | `FUERA_DE_RANGO` | AMARILLO | no |
| | 38.00 | mínimo | `LECTURA_VALIDA` | VERDE | no |
| | 39.49 | dentro de normal | `LECTURA_VALIDA` | VERDE | no |
| | **39.50** | frontera normal/precaución | `LECTURA_VALIDA` | **VERDE** | no |
| | 39.51 | precaución | `LECTURA_VALIDA` | AMARILLO | no |
| | 39.99 | precaución | `LECTURA_VALIDA` | AMARILLO | no |
| | **40.00** | frontera precaución/crítico | `LECTURA_VALIDA` | **AMARILLO** | no |
| | 40.01 | crítico | `LECTURA_VALIDA` | ROJO | **sí** (CRITICO) |
| | 42.99 / 43.00 | crítico / máximo | `LECTURA_VALIDA` | ROJO | no (misma alerta) |
| | 43.01 | sobre `valor_max` | `FUERA_DE_RANGO` | AMARILLO | no |
| `FRECUENCIA_CARDIACA` | 39.99 | bajo `valor_min` | `FUERA_DE_RANGO` | AMARILLO | no |
| | 40 / 119.99 | mínimo / normal | `LECTURA_VALIDA` | VERDE | no |
| | **120** | frontera normal/precaución | `LECTURA_VALIDA` | **VERDE** | no |
| | 120.01 / 139.99 | precaución | `LECTURA_VALIDA` | AMARILLO | no |
| | **140** | frontera precaución/crítico | `LECTURA_VALIDA` | **AMARILLO** | no |
| | 140.01 | crítico | `LECTURA_VALIDA` | ROJO | **sí** (CRITICO) |
| | 159.99 / 160 | crítico / máximo | `LECTURA_VALIDA` | ROJO | no (misma alerta) |
| | 160.01 | sobre `valor_max` | `FUERA_DE_RANGO` | AMARILLO | no |

**Regla observada de inclusividad** (el requisito no la fija): el límite superior de cada banda pertenece a la banda de abajo, es decir (inferior, superior], y el valor mínimo del umbral entra en la primera banda. Falta que Desarrollo la confirme.

Observaciones: (1) una lectura fuera de [min, max] se guarda (con `valor_ajustado`) y **no genera alerta** (coincide con TC-M03-016), pero su semáforo es AMARILLO también por encima del máximo; hay que confirmar si debería ser ROJO. (2) Las lecturas críticas sucesivas del mismo sensor no crean otra alerta (se suma a `frecuencia_evento`, ventana de 30 min). (3) Las lecturas en precaución no generan alerta. (4) Una captura con hora anterior a la asociación del sensor responde 401 `ERROR_AUTENTICACION` aunque el token sea válido. (5) El sensor debe tener la especie en `especies-compatibles` (`PUT` con `ids_especies`) o la asociación al animal da 400 `COMPATIBILIDAD_SENSOR_NO_CONFIGURADA`, y debe estar calibrado (sin calibración las lecturas quedan `ERROR_CALIBRACION` con `valor_ajustado` vacío).

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

**En DEV no hay sandbox** (`/test-control` no existe): lo que se crea queda; la limpieza es manual (baja de animales, asociaciones inactivas, dispositivos desactivados). En TEST sí hay sandbox (`X-Test-Run-Id`, `DELETE /test-control/runs/{id}`). Los secretos (`X-Sandbox-Secret`, token del broker, `QA_PROD_*`) salen de variables de entorno, nunca de este documento.

| Dato | Contenido | Quién lo crea | Descripción | Metodología |
|---|---|---|---|---|
| Especie | Bovino (id 2, existente), grupo ESPECIES_GRANDES, densidad 0.1 `[DEV]` | ya existe | No se crea ni se modifica. | Leerla y comprobar grupo y modelo. |
| Etapas | Cría, Levante, Producción | RF-16 | Etapas productivas. | Crear las tres y comprobar el orden. |
| Patología | Fiebre bovina de prueba (QA); variables: TEMP_CORPORAL, FRECUENCIA_CARDIACA, FRECUENCIA_RESPIRATORIA | M04 RF-64 | Patología mínima para la predicción. Las variables se envían como **IDs** del catálogo I3P-1, no como nombres (TC-M04-G003). | Registrar y leer de vuelta las variables. |
| Umbrales | 5 variables de la sección 4 | RF-17 | Reglas de alerta. | Crear y verificar la sincronización. |
| Finca y área | Finca El rosal (id 1); área de 35 m² (capacidad 3); área fija de QA id 12 para lecturas y alertas | RF-19/20 | Contenedor. | Crear/reutilizar y leer la capacidad. |
| Dispositivos y sensores | 1 Gateway Edge + 6 sensores/cámaras | RF-21/22 | Fuente de telemetría. | Crear y asociar al área. |
| Activos | cargas de la sección 2 | M02 | Población. | Crear y comprobar la capacidad. |
| Lecturas | tabla de la sección 5 | `POST /iot/telemetria` | Telemetría de prueba. Las horas se envían en el pasado (el sandbox congela `now()`). | Enviar y leer del historial. |
| Versiones de modelo | una por estado de la sección 1.4 | RF-69 | Datos de ciclo de vida. | Registrar con métricas sobre y bajo el umbral. |
| Usuarios | Administrador (setup), Productor (`QA_PROD_*`), Ingeniero de Campo (lectura del monitoreo) | variables de entorno | Roles de la prueba. | Una sesión por rol; un login invalida el token anterior. |

## 8. Resultados de ejecución en DEV (2026-11-02)

Las corridas hechas en la finca El rosal se retiraron de la carpeta (la finca es la de la entrega); sus ids están en `Flujo/Bovino/IDS_PRUEBAS_EL_ROSAL.md` para pedir su limpieza. La evidencia vigente es la repetición en la finca de QA (id 3), con los mismos resultados.

| Fase | Qué se hizo | Resultado | Evidencia |
|---|---|---|---|
| Solo lectura | 43 verificaciones sobre el bovino de Potrero 1 (telemetría, semáforo, estadísticas, alertas, dashboard) | 36 pasan, 0 fallan, 11 informativos | `Flujo/Bovino/REPORTE_vaca_dev_solo_lectura.md` |
| F3 / F6 capacidad | Área de 35 m², 3 animales, el 4.º, identificador repetido, reducción de superficie, grupos incompatibles | 11 de 11 pasan | `Flujo/Bovino/resultados_capacidad_finca3.json` |
| F7 lecturas en fronteras | 22 lecturas en las fronteras de los umbrales | sin contradicciones; regla de inclusividad observada | `Flujo/Bovino/resultados_fronteras_finca3.json` |
| F8 alertas | Ciclo de vida completo | 10 de 10 pasan | `Flujo/Bovino/resultados_alertas_ciclo_finca3.json` |
| F9 calibración de visión | No ejecutada | El Potrero no tiene cámara en DEV (solo acuicultura, aves y porcinos) | - |
| F10 predicción | No ejecutada con escritura | `MODELO_ESPECIES_GRANDES` sin configuración del motor en DEV | ver 1.2 |


**Repeticion en finca de QA (2026-11-02):** las tres pruebas con escritura se repitieron en la finca 3 `QA Pruebas Flujo`, creada para esto, porque El rosal y La florida son de la entrega. Mismos resultados (capacidad 11/11; 22 lecturas sin contradicciones; alertas 10/10). Ver `Flujo/Bovino/REPORTE_repeticion_finca3.md`. Los scripts exigen `QA_FINCA_ID` y rechazan las fincas 1 y 2.

**Pendiente de confirmar con Desarrollo:** inclusividad de las fronteras; semáforo AMARILLO fuera de [min, max]; definición de `pct_fuera_rango` (la API cuenta lo que queda fuera de la banda normal, no fuera de [min, max]); la versión de umbral del historial muestra la vigente y no la del momento de la captura; faltan umbrales de frecuencia respiratoria, actividad, temperatura ambiental y humedad para Bovino; falta la configuración del motor de `MODELO_ESPECIES_GRANDES`.

