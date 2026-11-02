# Datos de prueba y metodología - E7 Avestruz

Complemento de [plan_E7_avestruz.md](plan_E7_avestruz.md). Reúne **todos los datos que la prueba automática guarda y usa**, y para cada elemento su descripción y su metodología de verificación.

Estado: borrador del 2026-11-02.

**Origen de cada valor.** `[RF]` viene de un requisito (reqMod3y4.xlsx, fichas de M09 o los casos ya ejecutados). `[QA]` es una **propuesta de QA que no está en ningún requisito ni en el repositorio** y debe confirmarse con Desarrollo/M09 antes de formalizar los TC. Las densidades, umbrales por especie y conteos de esta ficha son `[QA]`.

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

Regla `[RF]` (RF-20): capacidad del área = `floor(densidad × superficie)`; en un área multiespecie manda la **menor** densidad. Unidad contada: animal con anillo/identificador (activo INDIVIDUAL).

| Elemento | Valor | Descripción | Metodología |
|---|---|---|---|
| `densidad_poblacional_max` de Avestruz | 0.025 ind/m² `[QA]` | Densidad máxima de la especie (RF-15). | Registrar la especie con este valor y leerlo de vuelta. |
| Superficie del área | 400 m² `[QA]` | Superficie conocida para calcular la capacidad. | Crear el área y comprobar la superficie guardada. |
| **Capacidad con Avestruz sola** | **10** | `floor(0.025 × 400)`. | Crear el área y comparar la capacidad devuelta con 10. |
| Especie de apoyo (multiespecie) | E1 Vaca; densidad 0.05 ind/m² `[QA]` | Segunda especie del mismo grupo. | Crear el área con las dos especies. |
| **Capacidad multiespecie** | **10** | `floor(MIN(0.025, 0.05) × 400)`. | Comparar con 10; cambiar el orden de las especies no debe cambiar el resultado. |

### Cargas de prueba en el área de 400 m² (capacidad 10)

| Carga | Cantidad | Resultado esperado | Descripción | Metodología |
|---|---|---|---|---|
| Lote/hato de referencia | 5 animales (50 %) | 201 | Caso normal. | Registrar y comprobar que la carga restante es 5. |
| Límite inferior de capacidad | 9 animales | 201 | Un individuo bajo el límite. | Registrar y confirmar 201. |
| **Límite exacto** | **10 animales** | 201 | Capacidad completa. | Registrar y confirmar 201 y capacidad libre 0. |
| **Un individuo sobre el límite** | **11 animales** | 422 `CAPACIDAD_EXCEDIDA` | Primer valor inválido. | Registrar y confirmar el 422 sin persistencia. |
| Reducir superficie bajo la carga | de 400 a 399 m² con 10 animales alojados | 422 `CAPACIDAD_EXCEDIDA` | Capacidad nueva = 9 < 10. | Editar el área y confirmar el 422 y que la superficie no cambió. |
| Área multiespecie al límite | 10 animales | 201 | Límite con la menor densidad. | Registrar y confirmar 201; con 11 confirmar 422. |
| Identificador duplicado | 1 animal con el arete ya usado | rechazo (`existe_identificador`) | Unicidad del identificador. | Registrar dos veces el mismo identificador. |

En el paradigma individual cada animal es un activo propio: las cargas grandes se crean con un script que registra los animales uno por uno y los elimina con el rollback del sandbox.

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

## 4. Umbrales ambientales (RF-17)

Los 3 niveles (`normal`, `precaucion`, `critico`) deben ser contiguos y cubrir exactamente `[valor_min, valor_max]` `[RF]`, y el rango debe caber en el rango físico de la variable. El orden de los niveles en el cuerpo no importa. Al guardar, el umbral se propaga al Gateway Edge y queda `APLICADA` / `PENDIENTE` / `NO_CONF`.

| Variable | Unidad | `valor_min` | `valor_max` | Nivel: límites | Descripción | Metodología |
|---|---|---|---|---|---|---|
| `TEMP_CORPORAL` | °C | 36 | 41.5 | critico 36-38; normal 38-39.8; precaucion 39.8-41.5 | Umbral `[QA]`. | Crear el umbral; verificar 201 y `estado_sincronizacion`; probar un hueco y un solapamiento entre niveles (deben dar 422/400). |
| `FRECUENCIA_CARDIACA` | bpm | 30 | 180 | critico 30-50; normal 50-100; precaucion 100-180 | Umbral `[QA]`. | Crear el umbral; verificar 201 y `estado_sincronizacion`; probar un hueco y un solapamiento entre niveles (deben dar 422/400). |
| `FRECUENCIA_RESPIRATORIA` | rpm | 3 | 60 | critico 3-8; normal 8-30; precaucion 30-60 | Umbral `[QA]`. | Crear el umbral; verificar 201 y `estado_sincronizacion`; probar un hueco y un solapamiento entre niveles (deben dar 422/400). |
| `TEMPERATURA_AMBIENTAL` | °C | 5 | 48 | critico 5-10; normal 10-35; precaucion 35-48 | Umbral `[QA]`. crítico por frío (bajo) / precaución por calor (alto). | Crear el umbral; verificar 201 y `estado_sincronizacion`; probar un hueco y un solapamiento entre niveles (deben dar 422/400). |
| `HUMEDAD_RELATIVA` | % | 15 | 95 | critico 15-30; normal 30-70; precaucion 70-95 | Umbral `[QA]`. | Crear el umbral; verificar 201 y `estado_sincronizacion`; probar un hueco y un solapamiento entre niveles (deben dar 422/400). |

## 5. Lecturas de prueba y resultado esperado

Por cada variable se envían valores dentro de cada banda, sobre cada frontera y fuera de `[valor_min, valor_max]`. **Inclusividad de las fronteras:** el requisito no fija si el límite pertenece a la banda inferior o a la superior (G44 de M3 se rechazó por esto); las filas de frontera quedan "por definir" hasta que Desarrollo lo defina.

| Variable | Valor | Posición | Estado de la lectura | Nivel esperado | Metodología |
|---|---|---|---|---|---|
Nota: clasificar `FUERA_DE_RANGO` contra el umbral de la especie depende de la corrección DB-02 de `fn_ingesta_telemetria` (pendiente); hasta entonces el estado de esas filas puede diferir.

| `TEMP_CORPORAL` | 35.9 | bajo `valor_min` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado en el historial; no debe generar alerta de umbral. |
| `TEMP_CORPORAL` | 37 | centro de la banda critico | `LECTURA_VALIDA` | critico | Enviar y comprobar nivel/alerta. |
| `TEMP_CORPORAL` | 38.9 | centro de la banda normal | `LECTURA_VALIDA` | normal | Enviar y comprobar nivel/alerta. |
| `TEMP_CORPORAL` | 40.65 | centro de la banda precaucion | `LECTURA_VALIDA` | precaucion | Enviar y comprobar nivel/alerta. |
| `TEMP_CORPORAL` | 38 | frontera critico/normal | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `TEMP_CORPORAL` | 39.8 | frontera normal/precaucion | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `TEMP_CORPORAL` | 41.6 | sobre `valor_max` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado. |
| `FRECUENCIA_CARDIACA` | 29 | bajo `valor_min` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado en el historial; no debe generar alerta de umbral. |
| `FRECUENCIA_CARDIACA` | 40 | centro de la banda critico | `LECTURA_VALIDA` | critico | Enviar y comprobar nivel/alerta. |
| `FRECUENCIA_CARDIACA` | 75 | centro de la banda normal | `LECTURA_VALIDA` | normal | Enviar y comprobar nivel/alerta. |
| `FRECUENCIA_CARDIACA` | 140 | centro de la banda precaucion | `LECTURA_VALIDA` | precaucion | Enviar y comprobar nivel/alerta. |
| `FRECUENCIA_CARDIACA` | 50 | frontera critico/normal | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `FRECUENCIA_CARDIACA` | 100 | frontera normal/precaucion | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `FRECUENCIA_CARDIACA` | 181 | sobre `valor_max` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado. |
| `FRECUENCIA_RESPIRATORIA` | 2 | bajo `valor_min` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado en el historial; no debe generar alerta de umbral. |
| `FRECUENCIA_RESPIRATORIA` | 5.5 | centro de la banda critico | `LECTURA_VALIDA` | critico | Enviar y comprobar nivel/alerta. |
| `FRECUENCIA_RESPIRATORIA` | 19 | centro de la banda normal | `LECTURA_VALIDA` | normal | Enviar y comprobar nivel/alerta. |
| `FRECUENCIA_RESPIRATORIA` | 45 | centro de la banda precaucion | `LECTURA_VALIDA` | precaucion | Enviar y comprobar nivel/alerta. |
| `FRECUENCIA_RESPIRATORIA` | 8 | frontera critico/normal | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `FRECUENCIA_RESPIRATORIA` | 30 | frontera normal/precaucion | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `FRECUENCIA_RESPIRATORIA` | 61 | sobre `valor_max` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado. |
| `TEMPERATURA_AMBIENTAL` | 4 | bajo `valor_min` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado en el historial; no debe generar alerta de umbral. |
| `TEMPERATURA_AMBIENTAL` | 7.5 | centro de la banda critico | `LECTURA_VALIDA` | critico | Enviar y comprobar nivel/alerta. |
| `TEMPERATURA_AMBIENTAL` | 22.5 | centro de la banda normal | `LECTURA_VALIDA` | normal | Enviar y comprobar nivel/alerta. |
| `TEMPERATURA_AMBIENTAL` | 41.5 | centro de la banda precaucion | `LECTURA_VALIDA` | precaucion | Enviar y comprobar nivel/alerta. |
| `TEMPERATURA_AMBIENTAL` | 10 | frontera critico/normal | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `TEMPERATURA_AMBIENTAL` | 35 | frontera normal/precaucion | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `TEMPERATURA_AMBIENTAL` | 49 | sobre `valor_max` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado. |
| `HUMEDAD_RELATIVA` | 14 | bajo `valor_min` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado en el historial; no debe generar alerta de umbral. |
| `HUMEDAD_RELATIVA` | 22.5 | centro de la banda critico | `LECTURA_VALIDA` | critico | Enviar y comprobar nivel/alerta. |
| `HUMEDAD_RELATIVA` | 50 | centro de la banda normal | `LECTURA_VALIDA` | normal | Enviar y comprobar nivel/alerta. |
| `HUMEDAD_RELATIVA` | 82.5 | centro de la banda precaucion | `LECTURA_VALIDA` | precaucion | Enviar y comprobar nivel/alerta. |
| `HUMEDAD_RELATIVA` | 30 | frontera critico/normal | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `HUMEDAD_RELATIVA` | 70 | frontera normal/precaucion | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `HUMEDAD_RELATIVA` | 96 | sobre `valor_max` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado. |

Desviaciones RF-55.1 `[RF]` (porcentaje sobre el umbral): 9.9 %, 10 %, 10.1 %, 24.9 %, 25 %, 25.1 %. Menor o igual a 10 % → `LEVE`; entre 10 y 25 % → `MODERADO`; mayor a 25 % → `CRITICO`. Cada corte se prueba con el `valor_max` de arriba como referencia.

## 6. Estados del sistema

| Dominio | Valores | Descripción | Metodología |
|---|---|---|---|
| Calidad de la lectura (RF-53) | `LECTURA_VALIDA`, `FUERA_DE_RANGO`, `ERROR_CALIBRACION` | Resultado de validar cada lectura. | Una lectura por valor, estado leído en el historial. |
| Desviación (RF-55) | `NORMAL`, `DESVIACION_LEVE`, `DESVIACION_MODERADA`, `DESVIACION_CRITICA`, `DESVIACION_COMPUESTA`, `ERROR_CONFIGURACION` | Clasificación del nodo Edge. | Enviar la lectura y leer `estado_desviacion`; sin umbrales debe salir `ERROR_CONFIGURACION`. |
| Origen del dato (RF-53/54) | `TIEMPO_REAL`, `BUFFER_LOCAL`, `EDGE_AGREGADO` | Cómo llegó la lectura. | Enviar un lote `BUFFER_LOCAL` repetido: solo el primero crea registro (idempotencia). |
| Severidad de alerta (RF-57) | `LEVE`, `MODERADO`, `CRITICO` | Gravedad. | Una alerta por severidad. |
| Ciclo de vida de alerta (RF-57) | `ACTIVA`, `EN_ATENCION`, `RESUELTA`, `DESCARTADA`, `VENCIDA` | Estados; `CERRADA` no existe y da 422 `TRANSICION_INVALIDA`. | Recorrer las transiciones válidas y probar una inválida. |
| Conectividad del dispositivo (RF-60) | `ONLINE`, `OFFLINE`, `SIN_SEÑAL`, `EN_MANTENIMIENTO` | Estado según heartbeat y buffer. | Enviar heartbeats y consultar; SIN_SEÑAL/OFFLINE no tienen disparador de prueba (dependencia de Desarrollo). |
| Semáforo del dashboard (RF-58) | `VERDE` (nombre por verificar), `AMARILLO`, `ROJO`, `GRIS` (sin datos) | Estado visual de la unidad. | Un caso por color con las lecturas de la sección 5. |
| Sincronización de umbral (RF-17) | `PENDIENTE`, `APLICADA`, `NO_CONF` | Resultado de propagar el umbral al Edge. | Con Edge conectado: `APLICADA`; sin ACK en 30 s: `NO_CONF` (500). |
| Versión de modelo (RF-69) | `EN_VALIDACION`, `APROBADO`, `RECHAZADO`, `ACTIVO`, `DEPRECADO` | Ver 1.4. | Ver 1.4. |

## 7. Datos que la prueba automática crea y usa

Todo se crea dentro del sandbox (`X-Test-Run-Id`) y desaparece con `DELETE /test-control/runs/{id}`. Los secretos (`X-Sandbox-Secret`, token del broker, `QA_PROD_*`) salen de variables de entorno, nunca de este documento.

| Dato | Contenido | Quién lo crea | Descripción | Metodología |
|---|---|---|---|---|
| Especie | Avestruz, grupo ESPECIES_GRANDES (propuesta, por confirmar), densidad 0.025 | RF-15 | Especie de la prueba. | Crear en F1 y borrar con el rollback. |
| Etapas | Polluelo, Juvenil, Adulto reproductor | RF-16 | Etapas productivas. | Crear las tres y comprobar el orden. |
| Patología | Hipertermia de avestruz de prueba (QA); variables: TEMP_CORPORAL, FRECUENCIA_CARDIACA, FRECUENCIA_RESPIRATORIA | M04 RF-64 | Patología mínima para la predicción. Las variables se envían como **IDs** del catálogo I3P-1, no como nombres (TC-M04-G003). | Registrar y leer de vuelta las variables. |
| Umbrales | 5 variables de la sección 4 | RF-17 | Reglas de alerta. | Crear y verificar la sincronización. |
| Finca y área | 1 finca, 1 área de 400 m² | RF-19/20 | Contenedor. | Crear y leer la capacidad. |
| Dispositivos y sensores | 1 Gateway Edge + 5 sensores/cámaras | RF-21/22 | Fuente de telemetría. | Crear y asociar al área. |
| Activos | cargas de la sección 2 | M02 | Población. | Crear y comprobar la capacidad. |
| Lecturas | tabla de la sección 5 | `POST /iot/telemetria` | Telemetría de prueba. Las horas se envían en el pasado (el sandbox congela `now()`). | Enviar y leer del historial. |
| Versiones de modelo | una por estado de la sección 1.4 | RF-69 | Datos de ciclo de vida. | Registrar con métricas sobre y bajo el umbral. |
| Usuarios | Administrador (setup), Productor (`QA_PROD_*`), Ingeniero de Campo (lectura del monitoreo) | variables de entorno | Roles de la prueba. | Una sesión por rol; un login invalida el token anterior. |
