# Mapa de testeo - Flujo multiespecie (6 especies) en DEV

Generado el 2026-11-03 a partir de los resultados guardados en `Flujo/<Especie>/` y de las ejecuciones de la sesión del 2026-11-02. Es una foto del momento: DEV cambia (otros equipos escriben allí) y las cifras de abajo solo valen para esas corridas. Plan de origen: `planes_multiespecie/` (`plan_E*.md` y `datos_E*.md`).

## Resumen de resultados

Las seis especies pasaron todas las pruebas que se pudieron ejecutar: **0 fallos** en capacidad y en ciclo de vida de alertas. Lo que no pasó limpio son bloqueos y huecos de configuración en DEV, no errores de la lógica probada. Las cifras salen de las secciones 4 a 7.

| Indicador | Resultado |
|---|---|
| B. Capacidad | 72 pasos en 6 especies, 0 fallos |
| C. Fronteras de umbrales | 56 pasan, 33 informativas, **11 bloqueadas** (temperatura del agua de la cachama: 404) |
| D. Lecturas sin umbral | 2 corridas (porcino y pollo): 14 aceptadas y 6 rechazadas por rango físico en cada una, 0 alertas |
| E. Ciclo de vida de alertas | 40 pasos en 4 especies, 0 fallos |
| A. Solo lectura (bovino de Potrero 1) | 36 pasan, 0 fallan, 11 informativas |
| Fases del plan | F3, F5 y F6 completas en las seis; F4 en cuatro (faltan porcino y pollo); **F9 y F10 no se ejecutaron en ninguna** |
| Hallazgos para Desarrollo | 16 (sección 7) |

**Los cuatro que más pesan**
1. La temperatura del agua (y amoniaco, nitrito, salinidad y turbidez) no tiene `codigo_telemetria`: no se puede enviar y bloquea la capa de fronteras de la cachama.
2. Porcino y pollo no tienen umbrales en DEV: semáforo GRIS y sin alertas, así que no hay nada que probar en fronteras ni en alertas.
3. `MODELO_ESPECIES_GRANDES` no tiene configuración del motor, lo que deja sin predicción a bovino y avestruz.
4. El pH en ROJO no genera alerta (el oxígeno sí). Falta confirmar si es la regla esperada.

**Conclusión:** la regla de capacidad, la regla multiespecie (manda la menor densidad), las fronteras `(inferior, superior]` y el ciclo de vida de alertas se comportan como se espera en todas las especies probadas. No se puede dar por cubierto el flujo completo mientras no se resuelvan los hallazgos 1 a 3 y no se ejecuten F9 y F10.

## 1. Alcance y condiciones

| Aspecto | Valor |
|---|---|
| Ambiente | DEV (`https://api.inmero.co/api-sgpmp-dev`). **No tiene sandbox ni borrado por API**: lo creado queda (con baja o desactivación) |
| Finca de las pruebas | **QA Pruebas Flujo (id 3)**, creada para esto. El rosal y La florida son de la entrega y los scripts se niegan a escribir en ellas |
| Excepción | Las primeras corridas del bovino se hicieron en El rosal (id 1); se repitieron en la finca 3. Sus ids están en `Bovino/IDS_PRUEBAS_EL_ROSAL.md` y se decidió dejarlos allí |
| Tipo de prueba | Funcional contra la API (scripts Python propios). No es Cypress, Newman ni pytest del repositorio |
| Telemetría | `POST /iot/telemetria` con el token de servicio del broker, a dispositivos y sensores de QA propios. **No se usó la Raspberry física** ni el simulador del Potrero 1 |
| Credenciales | No se guardan en ningún archivo |

## 2. Capas de prueba

| Capa | Qué cubre | Archivos por especie |
|---|---|---|
| **A. Solo lectura** | Telemetría, semáforo, estadísticas, alertas y dashboard del bovino real de Potrero 1 | `Bovino/verificar_vaca_dev.py` |
| **B. Capacidad** | `floor(densidad × superficie)`, límites ±1, reducción de superficie, identificador repetido, grupos incompatibles, **multiespecie (menor densidad)** | `capacidad_<especie>_dev.py` |
| **C. Lecturas en fronteras** | Valores sobre cada frontera de los umbrales, fuera de rango y fuera del rango físico | `fronteras_<especie>_dev.py` |
| **D. Lecturas sin umbral** | Qué hace el sistema con una especie sin umbrales | `sin_umbral_<especie>_dev.py` |
| **E. Ciclo de vida de alertas** | ACTIVA → EN_ATENCION → RESUELTA / DESCARTADA y transiciones inválidas | `alertas_ciclo_<especie>_dev.py` |

## 3. Las seis especies

| Especie | Id en DEV | Grupo / modelo | Paradigma | Densidad (ind/m²) | Origen | Umbrales en DEV |
|---|---|---|---|---|---|---|
| Bovino (plan E1 «Vaca») | 2 | `ESPECIES_GRANDES` | Individual | 0.1 | Existía | 2: temperatura corporal y frecuencia cardiaca |
| Porcino (E2 «Cerdo») | 4 | `PORCINOS` | Poblacional | 1.0 | Existía | **Ninguno** |
| Pollo De Engorde (E3 «Pollo») | 5 | `AVES` | Poblacional | 10 | Existía | **Ninguno** |
| Cachama Blanca (E4) | 1 | `ACUICULTURA` | Poblacional | 5 | Existía | 3: temperatura del agua, temperatura ambiental y humedad |
| Tortuga Qa (E5) | 6 | `ACUICULTURA` (propuesto) | Poblacional | 2 `[QA]` | **Creada** para la prueba, desactivada | 2 creados por QA (pH, oxígeno), desactivados |
| Avestruz Qa (E7) | 7 | `ESPECIES_GRANDES` (propuesto) | Individual | 0.02 `[QA]` | **Creada** para la prueba, desactivada | 2 creados por QA (temperatura corporal, frecuencia cardiaca), desactivados |

## 4. Resultados por especie y capa

| Especie | B. Capacidad | C. Fronteras | D. Sin umbral | E. Alertas |
|---|---|---|---|---|
| Bovino | 11/11 | 22 lecturas: 14 pasan, 8 informativas | - | 10/10 |
| Porcino | 10/10 | No aplica (sin umbrales) | 14 aceptadas, 6 rechazadas por rango físico; 0 alertas | No aplica |
| Pollo | 10/10 | No aplica (sin umbrales) | 14 aceptadas, 6 rechazadas; 0 alertas | No aplica |
| Cachama | 10/10 | Temperatura ambiental y humedad: 14 pasan, 8 informativas. **Temperatura del agua: 11 envíos rechazados (404)** | - | 10/10 |
| Tortuga Qa | 14/14 (incluye multiespecie con Cachama) | pH y oxígeno: 14 pasan, 9 informativas | - | 10/10 |
| Avestruz Qa | 17/17 (incluye multiespecie con Bovino) | 22 lecturas: 14 pasan, 8 informativas | - | 10/10 |
| **Total** | **72 pasos, 0 fallos** | **56 pasan, 33 informativas, 11 bloqueadas** | 2 corridas | 40 pasos, 0 fallos |

Además: capa A del bovino, 36 pasan, 0 fallan y 11 informativas. «Informativa» = una frontera exacta (el requisito no define su pertenencia) o un valor fuera de rango, donde se anota lo observado.

## 5. Mapa de fases del plan (F1-F11) por especie

✅ ejecutada · ◐ parcial · ❌ no ejecutada · ➖ no aplica

| Fase | Qué es | Bovino | Porcino | Pollo | Cachama | Tortuga | Avestruz |
|---|---|---|---|---|---|---|---|
| F1 | Especie con grupo y densidad | ◐ existente, leída | ◐ existente | ◐ existente | ◐ existente | ✅ creada | ✅ creada |
| F2 | Etapas, patologías y umbrales | ◐ solo umbrales | ❌ sin umbrales | ❌ sin umbrales | ◐ 3 umbrales; el del agua no se puede ingerir | ◐ umbrales de QA | ◐ umbrales de QA |
| F3 | Área con la especie sola y su capacidad | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| F4 | Área multiespecie (menor densidad) | ✅ con Avestruz | ❌ sin especie de apoyo | ❌ sin especie de apoyo | ✅ con Tortuga | ✅ con Cachama | ✅ con Bovino |
| F5 | Dispositivo y sensor asociados | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| F6 | Activo (animal o lote) respetando la capacidad | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| F7 | Ingesta de lecturas | ✅ | ◐ sin umbral | ◐ sin umbral | ◐ sin la temperatura del agua | ✅ | ✅ |
| F8 | Alerta, estado e historial | ✅ | ➖ | ➖ | ✅ | ✅ | ✅ |
| F9 | Calibración de visión | ❌ sin cámara en el Potrero | ❌ cámara en La florida | ❌ cámara en La florida | ❌ cámara en La florida | ❌ | ❌ |
| F10 | Predicción con el modelo del grupo | ❌ **sin configuración del motor** | ❌ (configurado) | ❌ (configurado) | ❌ (configurado) | ❌ | ❌ |
| F11 | Rollback | ➖ DEV sin sandbox; limpieza manual | ➖ | ➖ | ➖ | ➖ | ➖ |

Casos negativos comunes del plan: `GRUPOS_MANEJO_INCOMPATIBLES` ✅ en las seis; `CAPACIDAD_EXCEDIDA` ✅ en las seis (carga y reducción de superficie). **Sin cubrir:** retirar una especie con activos alojados (`ESPECIE_CON_ACTIVOS_ALOJADOS`), `ESPECIE_SIN_DENSIDAD` y lista de especies vacía o repetida.

## 6. Reglas verificadas (se repiten en todas las especies)

| Regla | Comprobación |
|---|---|
| Capacidad = `floor(densidad × superficie)` | Con superficies en el límite (p. ej. 30 m² da 3 y 29.99 m² da 2) |
| Área multiespecie: manda la **menor** densidad, sin importar el orden | Tortuga + Cachama (10 en vez de 25) y Avestruz + Bovino (3 en vez de 15) |
| Un área solo admite especies del mismo grupo de manejo | 422 `GRUPOS_MANEJO_INCOMPATIBLES` |
| Una carga mayor que la capacidad se rechaza; la reducción de superficie bajo la carga también | 422 `CAPACIDAD_EXCEDIDA`, y la superficie no cambia |
| **Inclusividad de las fronteras: (inferior, superior]**, con el mínimo en la primera banda | Confirmada con bandas críticas arriba (bovino, cachama, avestruz) y abajo (pH y oxígeno de la tortuga) |
| Fuera de [min, max] pero dentro del rango físico → `FUERA_DE_RANGO`, sin alerta | Semáforo AMARILLO dentro de la tolerancia (10 % del rango por defecto, RF-58) y ROJO más allá |
| Fuera del rango físico de la variable → 422 `ERROR_SENSOR`, no se guarda | Límites inclusivos (p. ej. −50 y 100 °C se aceptan; 100.5 no) |
| Una sola alerta CRITICO por sensor y ventana (las siguientes suman `frecuencia_evento`); la precaución no alerta | |
| Una alerta sin atender vence sola a los 5 minutos (VENCIDA, terminal) | Transiciones válidas e inválidas probadas en 4 especies |
| Un lote (poblacional) solo admite un sensor poblacional | 409 `ACTIVO_YA_TIENE_SENSOR_POBLACIONAL` en cerdo y pollo |
| Un sensor necesita la especie en `especies-compatibles` y calibración | 400 `COMPATIBILIDAD_SENSOR_NO_CONFIGURADA`; `ERROR_CALIBRACION` sin calibración |

## 7. Hallazgos para Desarrollo (ordenados por impacto)

| # | Hallazgo | Especies | Qué falta decidir |
|---|---|---|---|
| 1 | La **temperatura del agua** (y amoniaco total, nitrito, salinidad, turbidez) no tiene `codigo_telemetria`: 404 `VARIABLE_NO_ENCONTRADA` al enviarla, aunque la cachama tiene umbral para ella | Cachama, Tortuga | Qué código usa un sensor de agua, o asignarlo en el catálogo |
| 2 | **Porcino y Pollo no tienen ningún umbral en DEV**: semáforo GRIS, sin alertas | Cerdo, Pollo | Valores de umbral de esas especies |
| 3 | `MODELO_ESPECIES_GRANDES` **no tiene configuración del motor** (404 `CONFIGURACION_MOTOR_NO_ENCONTRADA`), aunque hay una inferencia de bovino en modo sombra | Bovino, Avestruz | Si es intencional |
| 4 | **El pH en ROJO no genera alerta**; el oxígeno en ROJO sí (`RIESGO_HIDRICO`) | Tortuga (y Cachama, que no tiene umbral de pH) | Si el pH solo alerta en la regla compuesta con oxígeno (RF-55) |
| 5 | Un lote solo admite un sensor poblacional, pero el plan prevé varios sensores por área | Cerdo, Pollo, Cachama | Si es la regla esperada |
| 6 | Frontera: el límite superior pertenece a la banda de abajo; el requisito no lo dice | Todas | Documentarlo en el RF |
| 7 | Semáforo fuera de rango por tolerancia (AMARILLO dentro del 10 % del rango, ROJO más allá) | Todas | Confirmar que es lo previsto |
| 8 | Los umbrales de la cachama (y los de QA) quedan en `PENDIENTE` de sincronización con el Edge; los del bovino están `APLICADA` | Cachama | Si falta un Gateway Edge |
| 9 | El Bovino no tiene umbral de frecuencia respiratoria, actividad, temperatura ambiental ni humedad: el estado general de Potrero 1 queda GRIS | Bovino | Crearlos (afecta a la demo) |
| 10 | No hay categoría de sensor para CO₂ (el plan de pollo y cerdo lo prevé) | Cerdo, Pollo | Añadirla |
| 11 | El catálogo de tipos de área no incluye «Porqueriza» | Cerdo | Añadirla o dejar «Corral» |
| 12 | El historial muestra la versión de umbral vigente, no la que regía al capturar; `pct_fuera_rango` cuenta lo que sale de la banda normal, no de [min, max] | Bovino | Confirmar |
| 13 | Una captura con hora anterior a la asociación del sensor responde 401 `ERROR_AUTENTICACION` aunque el token sea válido | Todas | Mensaje más claro |
| 14 | La asociación lectura-alerta es asíncrona (la alerta puede quedar ligada a una lectura crítica posterior) | Bovino, Avestruz | Informativo |
| 15 | DEV no permite borrar; un dispositivo (aun desactivado) impide desactivar su área; un nombre desactivado sigue reservado | Todas | Informativo |
| 16 | Grupos de manejo de tortuga (`ACUICULTURA`) y avestruz (`ESPECIES_GRANDES`) siguen sin confirmar; faltan sus densidades reales | Tortuga, Avestruz | Confirmar |

## 8. Huecos (lo que este mapa NO cubre)

- **F9 y F10:** calibración de visión y predicción con el modelo del grupo.
- **La Raspberry física** (`RASPBERRY3B-TEST`, en el Estanque Checho de El rosal) y el procesamiento Edge (RF-55); tampoco el buffer local y la sincronización (RF-54) ni la conectividad y el heartbeat (RF-60).
- **Etapas y patologías por especie** (RF-16, RF-64) y el resto de variables de cada plan: frecuencia respiratoria, actividad, CO₂, pH y oxígeno de la cachama, temperatura del agua.
- **Capacidad multiespecie** para Cerdo y Pollo (no hay una segunda especie de su grupo en DEV).
- **Escenarios con Productor** (`QA_PROD_*`) y otros roles: todas las pruebas se hicieron con el rol de administración.
- **Unitarias, integración, accesibilidad y regresión visual** de estas funciones: no se miraron aquí; ver `MAPA_DE_TESTEO_M01_M02_M09.md` para esas capas en M01, M02 y M09.

## 9. Datos que quedan en DEV

| Dónde | Qué | Estado |
|---|---|---|
| Finca 3 (QA Pruebas Flujo) | Áreas, animales, lotes, dispositivos, sensores, lecturas y alertas de las seis especies | Animales y lotes con baja; dispositivos desactivados; áreas de capacidad desactivadas. **Siguen activas las áreas 14 (bovino), 16 (cerdo), 18 (pollo), 20 (cachama), 25 (tortuga) y 29 (avestruz)**, una por especie, porque tienen dispositivos |
| Catálogo global | Especies «Tortuga Qa» (6) y «Avestruz Qa» (7) y 4 umbrales | Desactivados, pero visibles en el listado como `INACTIVA` |
| El rosal (id 1) | Áreas 9, 11 y 12, animales 8 a 13, dispositivos 11 a 13, sensores 21 a 26 y 4 alertas | Se decidió dejarlos; la lista está en `Bovino/IDS_PRUEBAS_EL_ROSAL.md` |

## 10. Cómo repetir

Cada especie tiene su carpeta con los scripts y sus `resultados_*_finca3.json`. Todos se ejecutan con `QA_FINCA_ID=<id de una finca de QA> python3 <script> <token_sesion> [<env_broker>] <salida.json> [<id_area>]` y se niegan a correr en las fincas 1 y 2. El detalle de cada una está en `Flujo/<Especie>/RESULTADOS_GENERALES_<ESPECIE>.md`.
