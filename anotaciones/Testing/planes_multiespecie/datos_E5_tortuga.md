# Datos de prueba y metodología - E5 Tortuga

Complemento de [plan_E5_tortuga.md](plan_E5_tortuga.md). Reúne **todos los datos que la prueba automática guarda y usa**, y para cada elemento su descripción y su metodología de verificación.

Estado: borrador del 2026-11-02.

**Origen de cada valor.** `[RF]` viene de un requisito (reqMod3y4.xlsx, fichas de M09 o los casos ya ejecutados). `[QA]` es una **propuesta de QA que no está en ningún requisito ni en el repositorio** y debe confirmarse con Desarrollo/M09 antes de formalizar los TC. Las densidades, umbrales por especie y conteos de esta ficha son `[QA]`.

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

Regla `[RF]` (RF-20): capacidad del área = `floor(densidad × superficie)`; en un área multiespecie manda la **menor** densidad. Unidad contada: tortugas en un lote (activo LOTE con conteo).

| Elemento | Valor | Descripción | Metodología |
|---|---|---|---|
| `densidad_poblacional_max` de Tortuga | 2 ind/m² `[QA]` | Densidad máxima de la especie (RF-15). | Registrar la especie con este valor y leerlo de vuelta. |
| Superficie del área | 500 m² `[QA]` | Superficie conocida para calcular la capacidad. | Crear el área y comprobar la superficie guardada. |
| **Capacidad con Tortuga sola** | **1000** | `floor(2 × 500)`. | Crear el área y comparar la capacidad devuelta con 1000. |
| Especie de apoyo (multiespecie) | E4 Cachama; densidad 5 ind/m² `[QA]` | Segunda especie del mismo grupo. | Crear el área con las dos especies. |
| **Capacidad multiespecie** | **1000** | `floor(MIN(2, 5) × 500)`. | Comparar con 1000; cambiar el orden de las especies no debe cambiar el resultado. |

### Cargas de prueba en el área de 500 m² (capacidad 1000)

| Carga | Cantidad | Resultado esperado | Descripción | Metodología |
|---|---|---|---|---|
| Lote/hato de referencia | 500 individuos (50 %) | 201 | Caso normal. | Registrar y comprobar que la carga restante es 500. |
| Límite inferior de capacidad | 999 individuos | 201 | Un individuo bajo el límite. | Registrar y confirmar 201. |
| **Límite exacto** | **1000 individuos** | 201 | Capacidad completa. | Registrar y confirmar 201 y capacidad libre 0. |
| **Un individuo sobre el límite** | **1001 individuos** | 422 `CAPACIDAD_EXCEDIDA` | Primer valor inválido. | Registrar y confirmar el 422 sin persistencia. |
| Reducir superficie bajo la carga | de 500 a 499 m² con 1000 individuos alojados | 422 `CAPACIDAD_EXCEDIDA` | Capacidad nueva = 998 < 1000. | Editar el área y confirmar el 422 y que la superficie no cambió. |
| Área multiespecie al límite | 1000 individuos | 201 | Límite con la menor densidad. | Registrar y confirmar 201; con 1001 confirmar 422. |

En el paradigma poblacional el lote es **un solo activo con conteo**, no un activo por animal: la cantidad es un campo del lote.

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

## 4. Umbrales ambientales (RF-17)

Los 3 niveles (`normal`, `precaucion`, `critico`) deben ser contiguos y cubrir exactamente `[valor_min, valor_max]` `[RF]`, y el rango debe caber en el rango físico de la variable. El orden de los niveles en el cuerpo no importa. Al guardar, el umbral se propaga al Gateway Edge y queda `APLICADA` / `PENDIENTE` / `NO_CONF`.

| Variable | Unidad | `valor_min` | `valor_max` | Nivel: límites | Descripción | Metodología |
|---|---|---|---|---|---|---|
| `TEMPERATURA_AGUA (código por verificar en variables_ambientales)` | °C | 16 | 36 | critico 16-22; normal 22-30; precaucion 30-36 | Umbral `[QA]`. crítico por frío (bajo) / precaución por calor (alto). | Crear el umbral; verificar 201 y `estado_sincronizacion`; probar un hueco y un solapamiento entre niveles (deben dar 422/400). |
| `PH_AGUA` | pH | 5 | 10 | critico 5-6.5; normal 6.5-8.5; precaucion 8.5-10 | Umbral `[QA]`. 6.5-8.5 es el rango de la regla compuesta pH+O2 de RF-55. | Crear el umbral; verificar 201 y `estado_sincronizacion`; probar un hueco y un solapamiento entre niveles (deben dar 422/400). |
| `OXIGENO_DISUELTO` | mg/L | 0 | 15 | critico 0-5; precaucion 5-6; normal 6-15 | Umbral `[QA]`. 5 mg/L = límite de la regla compuesta pH+O2 de RF-55. | Crear el umbral; verificar 201 y `estado_sincronizacion`; probar un hueco y un solapamiento entre niveles (deben dar 422/400). |

## 5. Lecturas de prueba y resultado esperado

Por cada variable se envían valores dentro de cada banda, sobre cada frontera y fuera de `[valor_min, valor_max]`. **Inclusividad de las fronteras:** el requisito no fija si el límite pertenece a la banda inferior o a la superior (G44 de M3 se rechazó por esto); las filas de frontera quedan "por definir" hasta que Desarrollo lo defina.

Nota: clasificar `FUERA_DE_RANGO` contra el umbral de la especie depende de la corrección DB-02 de `fn_ingesta_telemetria` (pendiente); hasta entonces el estado de esas filas puede diferir.

| Variable | Valor | Posición | Estado de la lectura | Nivel esperado | Metodología |
|---|---|---|---|---|---|
| `TEMPERATURA_AGUA` | 15.9 | bajo `valor_min` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado en el historial; no debe generar alerta de umbral. |
| `TEMPERATURA_AGUA` | 19 | centro de la banda critico | `LECTURA_VALIDA` | critico | Enviar y comprobar nivel/alerta. |
| `TEMPERATURA_AGUA` | 26 | centro de la banda normal | `LECTURA_VALIDA` | normal | Enviar y comprobar nivel/alerta. |
| `TEMPERATURA_AGUA` | 33 | centro de la banda precaucion | `LECTURA_VALIDA` | precaucion | Enviar y comprobar nivel/alerta. |
| `TEMPERATURA_AGUA` | 22 | frontera critico/normal | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `TEMPERATURA_AGUA` | 30 | frontera normal/precaucion | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `TEMPERATURA_AGUA` | 36.1 | sobre `valor_max` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado. |
| `PH_AGUA` | 4.9 | bajo `valor_min` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado en el historial; no debe generar alerta de umbral. |
| `PH_AGUA` | 5.75 | centro de la banda critico | `LECTURA_VALIDA` | critico | Enviar y comprobar nivel/alerta. |
| `PH_AGUA` | 7.5 | centro de la banda normal | `LECTURA_VALIDA` | normal | Enviar y comprobar nivel/alerta. |
| `PH_AGUA` | 9.25 | centro de la banda precaucion | `LECTURA_VALIDA` | precaucion | Enviar y comprobar nivel/alerta. |
| `PH_AGUA` | 6.5 | frontera critico/normal | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `PH_AGUA` | 8.5 | frontera normal/precaucion | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `PH_AGUA` | 10.1 | sobre `valor_max` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado. |
| `OXIGENO_DISUELTO` | -0.1 | bajo `valor_min` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado en el historial; no debe generar alerta de umbral. |
| `OXIGENO_DISUELTO` | 2.5 | centro de la banda critico | `LECTURA_VALIDA` | critico | Enviar y comprobar nivel/alerta. |
| `OXIGENO_DISUELTO` | 5.5 | centro de la banda precaucion | `LECTURA_VALIDA` | precaucion | Enviar y comprobar nivel/alerta. |
| `OXIGENO_DISUELTO` | 10.5 | centro de la banda normal | `LECTURA_VALIDA` | normal | Enviar y comprobar nivel/alerta. |
| `OXIGENO_DISUELTO` | 5 | frontera critico/precaucion | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `OXIGENO_DISUELTO` | 6 | frontera precaucion/normal | `LECTURA_VALIDA` | por definir (inclusividad) | Enviar el valor exacto y registrar a qué banda se asigna. |
| `OXIGENO_DISUELTO` | 15.1 | sobre `valor_max` | `FUERA_DE_RANGO` | n/a (no se clasifica) | Enviar y leer el estado. |

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
| Especie | Tortuga, grupo ACUICULTURA (propuesta, por confirmar), densidad 2 | RF-15 | Especie de la prueba. | Crear en F1 y borrar con el rollback. |
| Etapas | Neonato, Juvenil, Adulto | RF-16 | Etapas productivas. | Crear las tres y comprobar el orden. |
| Patología | Infección de caparazón de prueba (QA); variables: PH_AGUA, OXIGENO_DISUELTO, TEMPERATURA_AMBIENTAL | M04 RF-64 | Patología mínima para la predicción. Las variables se envían como **IDs** del catálogo I3P-1, no como nombres (TC-M04-G003). | Registrar y leer de vuelta las variables. |
| Umbrales | 3 variables de la sección 4 | RF-17 | Reglas de alerta. | Crear y verificar la sincronización. |
| Finca y área | 1 finca, 1 área de 500 m² | RF-19/20 | Contenedor. | Crear y leer la capacidad. |
| Dispositivos y sensores | 1 Gateway Edge + 4 sensores/cámaras | RF-21/22 | Fuente de telemetría. | Crear y asociar al área. |
| Activos | cargas de la sección 2 | M02 | Población. | Crear y comprobar la capacidad. |
| Lecturas | tabla de la sección 5 | `POST /iot/telemetria` | Telemetría de prueba. Las horas se envían en el pasado (el sandbox congela `now()`). | Enviar y leer del historial. |
| Versiones de modelo | una por estado de la sección 1.4 | RF-69 | Datos de ciclo de vida. | Registrar con métricas sobre y bajo el umbral. |
| Usuarios | Administrador (setup), Productor (`QA_PROD_*`), Ingeniero de Campo (lectura del monitoreo) | variables de entorno | Roles de la prueba. | Una sesión por rol; un login invalida el token anterior. |
