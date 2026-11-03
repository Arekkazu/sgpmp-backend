# Datos de prueba y metodología - E2 Cerdo

Complemento de [plan_E2_cerdo.md](plan_E2_cerdo.md). Reúne **todos los datos que la prueba automática guarda y usa**, y para cada elemento su descripción y su metodología de verificación.

Estado: actualizado el 2026-11-03 con lo observado en el ambiente DEV (`https://api.inmero.co/api-sgpmp-dev`), finca de QA «QA Pruebas Flujo» (id 3). Resultados detallados en `../Flujo/Cerdo/`; mapa consolidado en `../Flujo/MAPA_DE_TESTEO_FLUJO_MULTIESPECIE.md`.

**Origen de cada valor.** `[RF]` viene de un requisito (reqMod3y4.xlsx, fichas de M09 o los casos ya ejecutados). `[QA]` es una **propuesta de QA que no está en ningún requisito ni en el repositorio** y debe confirmarse con Desarrollo/M09 antes de formalizar los TC. `[DEV]` es un valor **observado en DEV el 2026-11-02/03**, que no es un requisito: describe cómo está configurado y cómo respondió ese ambiente. Donde hay `[DEV]` ese valor sustituye a mi propuesta `[QA]` original; los demás valores `[QA]` siguen sin confirmar.

## 1. Modelo de IA, métricas y parámetros

### 1.1 Modelo

| Elemento | Valor | Descripción | Metodología |
|---|---|---|---|
| `tipo_modelo` | `MODELO_PORCINOS` | Modelo de IA que corresponde al `grupo_manejo` **PORCINOS** (RF-15/RF-20). `[RF]` | Registrar la especie con su grupo (F1) y comprobar en la API que `tipo_modelo` se deriva solo del grupo y que no se envía en el cuerpo. |
| `paradigma` | **POBLACIONAL** | Se deriva del tipo; decide qué validaciones, métricas y campos aplican (RF-65/69/70/73). `[RF]` | Leer `paradigma` del resultado de la API y compararlo con este valor (criterio de aceptación). |
| `componente` | `DETECTOR`, `SEGUIMIENTO`, `METRICAS`, `ANOMALIAS` | Un modelo poblacional se versiona y se despliega **por componente** (RF-69/RF-70). `[RF]` | Consultar la versión activa de cada componente: debe haber 4 y exactamente una `ACTIVO` por (`tipo_modelo`, `componente`). |

### 1.2 Parámetros operativos del motor (RF-65)

| Parámetro | Rango o valor de prueba | Descripción | Metodología |
|---|---|---|---|
| `umbral_score_anomalia` | sin restricción de orden `[RF]`; valor de prueba 0.60 `[QA]` | Score de anomalía del área a partir del cual se alerta. | Guardar 0.0, 0.60 y 1.0 y comprobar que el motor aplica el nuevo valor en el ciclo siguiente. |
| `ventana_temporal_minutos` | 5-15 `[RF]`; valor de prueba 10 `[QA]` | Ventana de análisis. | Valores 4, 5, 15 y 16: 5 y 15 se aceptan; 4 y 16 se rechazan. |
| `modo_ejecucion` | `CLOUD`, `EDGE`, `HIBRIDO`; prueba con `EDGE` `[QA]` | Dónde corre la inferencia. EDGE exige el modelo descargado en el nodo Raspberry. | Cambiar el modo y comprobar la sincronización con el nodo y el fallback automático en modo EDGE/HIBRIDO. |

**Observado en DEV `[DEV]`:** `MODELO_PORCINOS` está configurado (`umbral_score_anomalia` 0.5, ventana de 5 minutos, modo `SERVIDOR`). El valor de prueba 0.60 de arriba es una propuesta; no se cambió la configuración. F10 no se ejecutó.

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

Regla `[RF]` (RF-20): capacidad del área = `floor(densidad × superficie)`; en un área multiespecie manda la **menor** densidad. Unidad contada: cerdos en un lote (activo POBLACIONAL con conteo). **Confirmada en DEV `[DEV]`:** Porqueriza 1 (La florida, 50 m², Porcino) tiene `capacidad_maxima` 50.

**Cambio respecto a la propuesta inicial:** en DEV la especie es **Porcino (id 4)**, grupo `PORCINOS`, densidad **1.0** (no 1.5). Para no llenar DEV se usó un área de 10.5 m² (capacidad 10) en lugar de 200 m² (capacidad 300): se prueban los mismos límites con pocos registros.

| Elemento | Valor | Descripción | Metodología |
|---|---|---|---|
| Especie | Porcino, id 4 `[DEV]` | Existe en DEV. | Leerla con `GET /configuracion/especies`. |
| `densidad_poblacional_max` | 1.0 ind/m² `[DEV]` | Densidad máxima. | Comprobar que la capacidad sale de este valor. |
| Superficie del área de prueba | 10.5 m² `[QA]` | Da `floor(10.5)` = 10: prueba también el redondeo hacia abajo. Tipo de área `Corral` (no existe «Porqueriza»). | Crear el área y comprobar la superficie. |
| **Capacidad con Porcino sola** | **10** `[DEV]` | `floor(1.0 × 10.5)`. | Resultado: 201, capacidad 10. |
| Especie de apoyo (multiespecie) | **no hay** en DEV | No existe una segunda especie `PORCINOS` (en TEST sí: `Marranos`). | Pendiente: la capacidad multiespecie de cerdo no se probó. |

### Cargas de prueba en el área de 10.5 m² (capacidad 10) - ejecutadas en DEV

| Carga | Cantidad | Resultado observado | Descripción | Metodología |
|---|---|---|---|---|
| **Un cerdo sobre el límite, en área vacía** | 11 | **422 `CAPACIDAD_EXCEDIDA`** | Primer valor inválido. | `POST /activos-biologicos`, tipo POBLACIONAL, con `cantidad_inicial` y `soporte_documental` (obligatorio si el origen es "compra"). |
| Un cerdo bajo el límite | 9 | 201 | Lote normal. | Registrar el lote. |
| **Límite exacto** | +1 (total 10) | 201 | Capacidad completa. | Registrar un segundo lote de 1. |
| Uno más | +1 (total 11) | **422 `CAPACIDAD_EXCEDIDA`** | Sobre el límite acumulado. | Registrar un tercer lote de 1. |
| Reducir superficie a 10.0 m² con 10 | - | 200 | Capacidad 10, límite. | `PATCH` del área con `fecha_actualizacion` (si no, 412 `CONFLICTO_CONCURRENCIA`). |
| **Reducir superficie a 9.99 m² con 10** | - | **422 `CAPACIDAD_EXCEDIDA`** | Capacidad 9 < carga 10. | La superficie queda en 10.0. |
| Área con Porcino + Bovino (`PORCINOS` + `ESPECIES_GRANDES`) | - | **422 `GRUPOS_MANEJO_INCOMPATIBLES`** | Prueba negativa de grupos distintos. | Crear el área con las dos especies. |

En el paradigma poblacional cada tanda es **un lote con conteo**, no un activo por animal. DEV **no tiene sandbox**: la limpieza es dar de baja el lote completo (`eventos/baja` sin `cantidad_afectada`, con **fecha UTC**: la local puede ir un día atrás y da 400 `FECHA_INVALIDA`) y desactivar el área. Un dispositivo, aunque esté desactivado, impide desactivar su área y no se puede mover ni borrar, por eso queda un área por especie. Un área desactivada conserva su nombre (409 `RECURSO_DUPLICADO`): los nombres llevan sufijo.

## 3. Dispositivos y sensores

Todo área lleva **1 Gateway Edge (Raspberry)** que habla con el broker MQTT; los sensores se asocian al área y a un dispositivo activo (RF-21/22). Sin sensor asociado al momento de la captura la ingesta responde 401.

| Dispositivo / sensor | Variable (código I3P-1) | Cantidad | Descripción | Metodología |
|---|---|---|---|---|
| Gateway Edge (Raspberry) | n/a | 1 por área | Nodo que procesa en el borde (RF-55), guarda el buffer local (RF-54) y publica al broker. | Registrar el dispositivo, comprobar `ACTIVO` y que su heartbeat llega (`ONLINE`). |
| Nodo ambiental | `TEMPERATURA_AMBIENTAL` | 1 por área | Mide `TEMPERATURA_AMBIENTAL`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Nodo ambiental | `HUMEDAD_RELATIVA` | 1 por área | Mide `HUMEDAD_RELATIVA`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Nodo de gases | `NH3` | 1 por área | Mide `NH3`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Nodo de gases | `CO2` | 1 por área | Mide `CO2`. | Asociarlo al área, enviar una lectura válida por `POST /iot/telemetria` con el token del broker y leerla en el historial (RF-59). |
| Cámara de visión | `(conteo/ACTIVIDAD, RF-24)` | 1 por área | Cámara para conteo/actividad y calibración de línea base por (área, especie), RF-24. | Calibrar, enviar una observación por `/iot/telemetria/vision` y verificar una línea base por cada par (área, especie). |

Frecuencia de muestreo de prueba: 60 s `[QA]`; la frecuencia global sale de M09 (G16). La cantidad de sensores por área (1 de cada tipo) es una propuesta `[QA]`.

**Observado en DEV `[DEV]`:** la única cámara de porcinos (`CAM-PORC-001`) está en Porqueriza 1 de La florida (finca de la entrega) y no se usó. Las pruebas usaron un dispositivo de QA (tipo `GENERICO`) con sensores de categoría TEMPERATURA, HUMEDAD y AMONIACO. Las categorías de sensor disponibles son HUMEDAD, TEMPERATURA, OXIGENO, PH, AMONIACO, SALINIDAD y LUMINOSIDAD: **no hay una para CO₂**, así que el sensor de CO₂ del plan no se pudo probar. **Un lote solo admite un sensor poblacional** (409 `ACTIVO_YA_TIENE_SENSOR_POBLACIONAL`): los otros sensores quedan asociados al área y sus lecturas igual se aceptan.

## 4. Umbrales ambientales (RF-17)

**Observado en DEV `[DEV]`:** Porcino **no tiene ningún umbral** (`GET /configuracion/umbrales?id_especie=4` devuelve 0). **No se crearon:** el umbral es por especie y Porqueriza 1 (La florida, finca de la entrega) usa esta especie; habría cambiado su semáforo y sus alertas. La tabla siguiente es la propuesta `[QA]` del plan y está **sin crear**. Sin umbral no se pueden probar las fronteras ni las alertas por umbral.

Los 3 niveles (`normal`, `precaucion`, `critico`) deben ser contiguos y cubrir exactamente `[valor_min, valor_max]` `[RF]`, y el rango debe caber en el rango físico de la variable. El orden de los niveles en el cuerpo no importa. Al guardar, el umbral se propaga al Gateway Edge y queda `APLICADA` / `PENDIENTE` / `NO_CONF`.

| Variable | Unidad | `valor_min` | `valor_max` | Nivel: límites | Descripción | Metodología |
|---|---|---|---|---|---|---|
| `TEMPERATURA_AMBIENTAL` | °C | 10 | 40 | critico 10-16; normal 16-26; precaucion 26-40 | Umbral `[QA]`. crítico por frío (bajo) / precaución por calor (alto). | Crear el umbral; verificar 201 y `estado_sincronizacion`; probar un hueco y un solapamiento entre niveles (deben dar 422/400). |
| `HUMEDAD_RELATIVA` | % | 30 | 95 | critico 30-50; normal 50-80; precaucion 80-95 | Umbral `[QA]`. | Crear el umbral; verificar 201 y `estado_sincronizacion`; probar un hueco y un solapamiento entre niveles (deben dar 422/400). |
| `NH3` | ppm | 0 | 60 | normal 0-15; precaucion 15-25; critico 25-60 | Umbral `[QA]`. mayor es peor; 25 ppm = límite de la regla compuesta NH3+CO2 de RF-55. | Crear el umbral; verificar 201 y `estado_sincronizacion`; probar un hueco y un solapamiento entre niveles (deben dar 422/400). |
| `CO2` | ppm | 0 | 5000 | normal 0-1500; precaucion 1500-2000; critico 2000-5000 | Umbral `[QA]`. 2000 ppm = límite de la regla compuesta NH3+CO2 de RF-55. | Crear el umbral; verificar 201 y `estado_sincronizacion`; probar un hueco y un solapamiento entre niveles (deben dar 422/400). |

## 5. Lecturas de prueba y resultado observado `[DEV]`

Porcino no tiene umbrales, así que se probó el comportamiento **sin umbral**: un dispositivo de QA con tres sensores (temperatura ambiental, humedad y amoniaco), 20 lecturas por `POST /iot/telemetria` con el token de servicio del broker.

| Variable | Rango físico (inclusivo) | Valores aceptados | Valores rechazados |
|---|---|---|---|
| `TEMPERATURA_AMBIENTAL` (°C) | -50 a 100 | 24, 35, 99.9, 100, -50 | 100.5 y -50.5 (422 `ERROR_SENSOR`) |
| `HUMEDAD_RELATIVA` (%) | 0 a 100 | 60, 95, 100, 0 | 100.5 y -0.5 (422 `ERROR_SENSOR`) |
| `NH3` (ppm) | 0 a 500 | 10, 40, 499.9, 500, 0 | 500.5 y -0.5 (422 `ERROR_SENSOR`) |

Todo valor aceptado queda `LECTURA_VALIDA`, con semáforo **GRIS** (`sin_umbral=true`) y **sin alerta**, sea cual sea el valor (por ejemplo 35 °C, 95 % de humedad o 40 ppm de NH₃). El estado general de la unidad también es GRIS. Un valor fuera del rango físico se rechaza y **no se guarda**. En total: 20 lecturas enviadas, 14 guardadas, 6 rechazadas.

Las filas de la propuesta del plan (valores sobre cada frontera de un umbral) **no se ejecutaron**: dependen de crear los umbrales de la sección 4.

## 6. Estados del sistema

| Dominio | Valores | Descripción | Metodología |
|---|---|---|---|
| Calidad de la lectura (RF-53) | `LECTURA_VALIDA`, `FUERA_DE_RANGO`, `ERROR_CALIBRACION` | Resultado de validar cada lectura. | Una lectura por valor, estado leído en el historial. |
| Desviación (RF-55) | `NORMAL`, `DESVIACION_LEVE`, `DESVIACION_MODERADA`, `DESVIACION_CRITICA`, `DESVIACION_COMPUESTA`, `ERROR_CONFIGURACION` | Clasificación del nodo Edge. | Enviar la lectura y leer `estado_desviacion`; sin umbrales debe salir `ERROR_CONFIGURACION`. |
| Origen del dato (RF-53/54) | `TIEMPO_REAL`, `BUFFER_LOCAL`, `EDGE_AGREGADO` | Cómo llegó la lectura. | Enviar un lote `BUFFER_LOCAL` repetido: solo el primero crea registro (idempotencia). |
| Severidad de alerta (RF-57) | `LEVE`, `MODERADO`, `CRITICO` | Gravedad. | Una alerta por severidad. |
| Ciclo de vida de alerta (RF-57) | `ACTIVA`, `EN_ATENCION`, `RESUELTA`, `DESCARTADA`, `VENCIDA` | Estados; `CERRADA` no existe y da 422 `TRANSICION_INVALIDA`. **Una alerta sin atender pasa sola a `VENCIDA` a los 5 min y es terminal** `[DEV]`. | Recorrer las transiciones válidas y las inválidas dentro de esos 5 minutos (no ejecutado en esta especie: sin umbral no se generan alertas). |
| Conectividad del dispositivo (RF-60) | `ONLINE`, `OFFLINE`, `SIN_SEÑAL`, `EN_MANTENIMIENTO` | Estado según heartbeat y buffer. | Enviar heartbeats y consultar; SIN_SEÑAL/OFFLINE no tienen disparador de prueba (dependencia de Desarrollo). |
| Semáforo del dashboard (RF-58) | `VERDE`, `AMARILLO`, `ROJO` (confirmados en DEV), `GRIS` (sensor sin umbral) | Estado visual. `estado_general` de la unidad queda GRIS si algún sensor no tiene umbral. | Un caso por color con las lecturas de la sección 5. |
| Sincronización de umbral (RF-17) | `PENDIENTE`, `APLICADA`, `NO_CONF` | Resultado de propagar el umbral al Edge. | Con Edge conectado: `APLICADA`; sin ACK en 30 s: `NO_CONF` (500). |
| Versión de modelo (RF-69) | `EN_VALIDACION`, `APROBADO`, `RECHAZADO`, `ACTIVO`, `DEPRECADO` | Ver 1.4. | Ver 1.4. |

## 7. Datos que la prueba automática crea y usa

**En DEV no hay sandbox** (`/test-control` no existe): lo que se crea queda; la limpieza es manual (baja de animales y lotes, asociaciones inactivas, dispositivos desactivados). En TEST sí hay sandbox (`X-Test-Run-Id`, `DELETE /test-control/runs/{id}`). Los secretos (`X-Sandbox-Secret`, token del broker, `QA_PROD_*`) salen de variables de entorno, nunca de este documento.

| Dato | Contenido | Quién lo crea | Descripción | Metodología |
|---|---|---|---|---|
| Especie | Porcino (id 4, existente), grupo PORCINOS, densidad 1.0 `[DEV]` | ya existe | No se crea ni se modifica. | Leerla y comprobar grupo y modelo. |
| Etapas | Lechón, Levante, Engorde | RF-16 | Etapas productivas. | Crear las tres y comprobar el orden. |
| Patología | Síndrome respiratorio porcino de prueba (QA); variables: TEMPERATURA_AMBIENTAL, HUMEDAD_RELATIVA, NH3, CO2 | M04 RF-64 | Patología mínima para la predicción. Las variables se envían como **IDs** del catálogo I3P-1, no como nombres (TC-M04-G003). | Registrar y leer de vuelta las variables. |
| Umbrales | Ninguno: Porcino no tiene umbrales en DEV `[DEV]` (no se crearon) | RF-17 | Sin umbral el semáforo es GRIS y no hay alertas. | Comprobarlo con `GET /configuracion/umbrales?id_especie=4`. |
| Finca y área | Finca QA Pruebas Flujo (id 3); área de 10.5 m² (capacidad 10) y una por corrida de lecturas | RF-19/20 | Contenedor. | Crear y leer la capacidad. |
| Dispositivos y sensores | 1 dispositivo de QA (tipo `GENERICO`) por corrida, con sensores propios `[DEV]`; no se usó la Raspberry física ni los dispositivos de las otras fincas | RF-21/22 | Fuente de telemetría. | Crear, asociar al área y al lote o animal, calibrar y, al terminar, desactivar el dispositivo. |
| Activos | cargas de la sección 2 | M02 | Población. | Crear y comprobar la capacidad. |
| Lecturas | tabla de la sección 5 | `POST /iot/telemetria` | Telemetría de prueba. En DEV la hora de captura debe ser **posterior** a la asociación del sensor (si no, 401 `ERROR_AUTENTICACION` aunque el token sea válido); en TEST con sandbox, en cambio, las horas con `now()` fallan y se envían en el pasado. | Enviar y leer del historial. |
| Versiones de modelo | una por estado de la sección 1.4 | RF-69 | Datos de ciclo de vida. | Registrar con métricas sobre y bajo el umbral. |
| Usuarios | Administrador (setup), Productor (`QA_PROD_*`), Ingeniero de Campo (lectura del monitoreo) | variables de entorno | Roles de la prueba. | Una sesión por rol; un login invalida el token anterior. |

## 8. Resultados de ejecución en DEV (2026-11-02/03)

| Fase | Qué se hizo | Resultado | Evidencia |
|---|---|---|---|
| Capacidad (lotes) | Área de 10.5 m², lotes de 11, 9 y 1, reducción de superficie, grupos incompatibles | 10 de 10 pasan | `Flujo/Cerdo/resultados_capacidad_cerdo_finca3.json` |
| F7 lecturas sin umbral | 20 lecturas en tres sensores sin umbral | 14 guardadas (semáforo GRIS, sin alerta) y 6 rechazadas por rango físico | `Flujo/Cerdo/resultados_sin_umbral_cerdo_finca3.json` |
| Fronteras de umbral y alertas | No ejecutadas | Porcino no tiene umbrales en DEV | - |
| F9 calibración de visión | No ejecutada | La cámara de porcinos está en La florida | - |
| F10 predicción | No ejecutada | `MODELO_PORCINOS` está configurado; solo se podría revisar en lectura | - |

**Pendiente de confirmar con Desarrollo:** Umbrales de Porcino (decisión de Desarrollo; afectan a La florida); una segunda especie `PORCINOS` para la capacidad multiespecie; categoría de sensor para CO₂; un tipo de área «Porqueriza»; el motivo de que un lote solo admita un sensor poblacional.
