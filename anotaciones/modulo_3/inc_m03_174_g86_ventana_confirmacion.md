# INC-M03-174-G86 — Ventana de confirmación temporal de RF-57 (TC-M03-G86)

**RF:** RF-57 Fase 5 ("Ventana de confirmación: 2 lecturas consecutivas en ≤ N min") y RF-55 (detección
de desviaciones en el Edge). **Issue:** #753.
**Estado:** **bloqueado**, por decisión del equipo. La ventana de confirmación le corresponde a quien
**detecta** la desviación (el Edge, RF-55), no a `POST /iot/alertas`. Se pide a Análisis que el RF lo diga
explícitamente.

## Lo que reporta QA

Una sola lectura anómala por `POST /iot/alertas` genera la alerta de inmediato, en las 8 variables con
ventana (alertas 378 a 430). Una segunda lectura fuera de la ventana también la genera, en lugar de contar
como una nueva primera lectura.

## Por qué no se implementa en el backend

1. **`POST /iot/alertas` recibe desviaciones ya detectadas, no lecturas.** Las Entradas de RF-57 describen
   el evento como "generado en Edge (RF-55) o Backend", con `timestamp_evento` = "momento en que se
   **detectó la desviación**" y `tipo_evento` = `DESVIACION_SIMPLE`, `EVENTO_COMPUESTO` o
   `UMBRAL_EXCEDIDO`. El backend no recibe la serie de lecturas (tampoco las normales intermedias), así que
   no puede saber si dos lecturas anómalas fueron **consecutivas**.
2. **El diseño vigente ya delega la ventana al Edge.** La sincronización de reglas hacia el Edge (DEV-08,
   `sincronizar_regla_edge_use_case.py`, comando `regla_compuesta` del broker) le envía
   `ventana_confirmacion_min` y `lectura_confirmacion_max` de `modulo3.reglas_alertas` junto con los
   umbrales. Es decir, el Edge recibe la regla completa, ventana incluida, para evaluarla donde están las
   lecturas.
3. **RF-55 evalúa las lecturas en tiempo real** en el dispositivo (agregación por ventanas, persistencia
   local en RF-54) y es quien emite el evento cuando la condición se cumple.
4. **Aplicarla también en el backend la duplicaría:** el Edge ya filtra con su ventana, y el backend
   exigiría una segunda desviación confirmada, que tardaría al menos el doble en alertar.

Esto es coherente con lo anotado en G68 (#740): "la confirmación le toca a quien detecta (RF-55)".

## Qué falta y a quién le toca

| Responsable | Pendiente |
|---|---|
| **Análisis** | Aclarar en RF-57 Fase 5 que la ventana de confirmación se aplica **en la detección (RF-55, Edge)** y que `POST /iot/alertas` recibe la desviación ya confirmada. Si se decide lo contrario (que la aplique el backend), definir cómo sabe el backend que las lecturas fueron consecutivas sin recibir las normales |
| **Equipo IoT (firmware Edge)** | Aplicar `ventana_confirmacion_min` y `lectura_confirmacion_max` de la regla sincronizada antes de emitir el evento. En G43 (#647) se confirmó que el `edge_agent` todavía no implementa la clasificación de RF-55 |
| **QA** | Probar la ventana de punta a punta (lecturas en el Edge → evento), no con `POST /iot/alertas` directo, que por contrato ya es una desviación confirmada |

## Ventanas de RF-57 Fase 5 (referencia)

| Variable | Ventana |
|---|---|
| Temperatura ambiental, humedad relativa | 2 lecturas en ≤ 20 min |
| NH3, CO2 | 2 lecturas en ≤ 30 min |
| Temperatura corporal, frecuencia cardíaca, frecuencia respiratoria | 2 lecturas en ≤ 10 min |
| Actividad | Ventana deslizante de 30 min |
| pH, oxígeno disuelto, TDS | 1 lectura (dato puntual, sin ventana) |

## Cambios

Ninguno en código. Solo esta anotación.
