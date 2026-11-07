# Compatibilidad de sensores G38 — instrucción Majo

Fecha: 2026-10-30. Análisis de código y evidencias. **No se publicó MQTT. No se ejecutó G38. No se modificó firmware, backend ni umbrales.**

Instrucción de Majo: *«Solo ten en cuenta las que nos dio Sergio».*  
Criterios de aceptación de matriz y de `casos_rf55.json` **no se cambian**. Si el laboratorio no cubre una variable, el escenario se adapta (mismos CA, otro identificador autorizado) o se **excluye**, no se aprueba por analogía.

No se trata `Humedad Relativa`, `humedad_relativa`, humedad ambiental ni `humedad_suelo` como la misma variable.

---

## 1. Qué dio o confirmó Sergio (y qué no)

### 1.1 Confirmado por Sergio en las instrucciones de este laboratorio G38

| Dato | Fuente |
|---|---|
| Raspberry de laboratorio, SSH `sgpmp`, Tailscale `100.96.29.65` | Instrucción de Sergio |
| Hostname observado `RASPBERRY3B` (informado `RASPBERRY3B-TEST`) | SSH |
| Serial Gateway `RASPBERRY3B-TEST`, nodo `QA-M03-272-A-088894` | Sergio + log `Settings(...)` + MQTT |
| Firmware `v0.4.0-rc.2` | Sergio + heartbeat + `/opt/sgpmp-edge/VERSION` (inspección previa) |
| Cómo leer umbrales: `sudo -u sgpmp-edge cat /var/lib/sgpmp-edge/umbrales.json` | Sergio, 2026-10-30 |

**No hay en el hilo de QA una lista verbal de Sergio** del tipo «DHT22», «DS18B20», `EDGE_FAKE_VARIABLES=…` o «usen temperatura_ambiente». `EDGE_SOURCE` y `EDGE_FAKE_VARIABLES` **no se leyeron** (env root 600).

### 1.2 Lo que el laboratorio de Sergio tiene en disco y en MQTT (observado)

Estos no son un catálogo oral; son el estado del Edge que Sergio nos indicó leer.

**Umbrales vigentes** (`UMBRALES_ORIGINALES.json`, 2026-10-30T15:28:28Z):

| id_umbral_ambiental | `variable` (texto en disco) | unidad | id de comando RF-17 |
|---|---|---|---|
| 65 | `Humedad Relativa` | % | `6743369e531944bea216d5511a4a554c` |
| 48 | `pH del agua` | pH | `7b899854cb97456991a732f4e22a7171` |

**Heartbeat** (ambos seriales): `sensores_operativos: [{ "sensor": "rf55_2", "operativo": true }]`.

`rf55_2` **no es una variable RF-17**. En firmware `origin/develop` `raspberry/edge_agent/reglas/perfil.py`, `SENSOR_RF55_2 = "rf55_2"` es el flag de **perfil de hardware RF-55.2** (CPU/RAM/disco), reutilizado en el array que el broker ya conoce. No identifica humedad, pH ni temperatura.

### 1.3 Alcance autorizado para G38 (aplicación de la instrucción de Majo)

Para no inventar sensores, el conjunto **utilizable** es:

1. Dispositivos: `RASPBERRY3B-TEST` y `QA-M03-272-A-088894`.
2. Variables cuyo umbral está en el JSON que Sergio enseñó a leer: **`Humedad Relativa` (65)** y **`pH del agua` (48)**.

Cualquier otra variable de `casos_rf55.json` queda **fuera** hasta que Sergio la confirme por escrito o aparezca en ese JSON / en `EDGE_FAKE_VARIABLES` leído con autorización.

---

## 2. Nombres reales (firmware vs catálogo backend)

El evaluador compara **cadenas exactas**: `if umbral.variable != reading.variable` (`evaluador.py` en `develop`).

| Rol | Identificador | Dónde |
|---|---|---|
| Catálogo M09 (migración RF-53) | `Humedad Relativa` / código `HUMEDAD_RELATIVA` | `alembic/.../f40c53a37834_dev40_rf53_catalogo_dinamico.py` |
| Catálogo M09 | `pH del agua` / `PH_AGUA` | misma migración |
| Catálogo M09 | `Temperatura Ambiental` / `TEMPERATURA_AMBIENTAL` | misma migración |
| Catálogo M09 | `Frecuencia Respiratoria` / `FRECUENCIA_RESPIRATORIA` | misma migración |
| Catálogo M09 | **`humedad_suelo` / humedad del suelo: no aparece** | búsqueda en `sgpmp-backend` (código de producto): **0 coincidencias** |
| Firmware `VARIABLES_DEFECTO` (THI, etc.) | `humedad_relativa`, `temperatura_ambiente`, `frecuencia_respiratoria`, `ph` | `reglas/formulas.py` |
| Firmware `casos_rf55.json` (E1–E6, S8) | `temperatura_ambiente`, `frecuencia_respiratoria`, `humedad_suelo` | `raspberry/scripts/casos_rf55.json` `e618a75` |
| Disco del lab | `Humedad Relativa`, `pH del agua` | `umbrales.json` |
| Fake source | `Reading.variable = FakeVariable.nombre` (el string de `EDGE_FAKE_VARIABLES`) | `sources.py` |
| Docs instalación | `EDGE_FAKE_VARIABLES`: el nombre **debe existir** en `modulo9.variables_ambientales` | `docs/INSTALACION_RASPBERRY.md` |

`GET /configuracion/variables-ambientales` en TEST (esta fase) → **401**. El catálogo **vivo** de TEST no está verificado; solo el seed de código y el JSON del Edge.

Incompatibilidad de identificadores: un umbral guardado como `Humedad Relativa` **no casa** con una lectura `humedad_relativa` ni con `humedad_suelo`. El firmware lo trataría como «sin umbral RF-17 para la variable», no como la variable 65.

`ph` (firmware) ≠ `pH del agua` (disco/M09).

---

## 3. Variables de cada escenario (`casos_rf55.json` develop)

| Escenario | Caso | Variables en el contrato firmware | Qué exige |
|---|---|---|---|
| E1 | TC-M03-083 | `temperatura_ambiente` (sin umbral) + `frecuencia_respiratoria` (con umbral id 8) | Lecturas de **dos** variables; CA: `ERROR_CONFIGURACION` en T y `DESVIACION_SIMPLE` MODERADO en FR; no bloquea las siguientes |
| S8 | TC-M03-083 | `humedad_suelo=99` | Lectura de una variable **sin** umbral; `esperado_sin_umbral` |
| E2 | TC-M03-095 | comando `temperatura_ambiente` id 7, min=max=0 | **ACK_UMBRAL ERROR**; no hace falta clasificar la lectura si el ACK rechaza |
| E3 | TC-M03-095 | mismo id/variable; banda precaución ancho 0 | ACK ERROR |
| E4 | TC-M03-095 | umbral T 0–10 **válido**; lecturas 0 °C y 9 °C | CA matriz «cero» vs firmware: límite 0 con ancho > 0 es **válido**; T=9 → `DESVIACION_SIMPLE` CRITICO. **No** es ERROR_CONFIGURACION |
| E5 | TC-M03-122 | T id 7, solo banda `normal` | ACK ERROR |
| E6 | TC-M03-122 | T id 7 incompleto **ya en disco**; lecturas 35 y 36 | `ERROR_CONFIGURACION`, `severidad_invalida: true`, sin `severidad`, sin inventar CRITICO |

CA de matriz (no se alteran): 083 umbrales ausentes; 095 umbral 0 sin división por cero; 122 severidad ausente / no inventar CRITICO.

---

## 4. Compatibilidad con el alcance de Sergio

| ID | Escenario | Variable del contrato | ¿En el set Sergio/lab? | ¿Hay umbral lab? | Lectura observada | Decisión recomendada |
|---|---|---|---|---|---|---|
| TC-M03-083 | E1 | `temperatura_ambiente` + `frecuencia_respiratoria` | **No** | No (el lab tiene HR y pH, ambos **con** umbral) | No (solo heartbeat `rf55_2`) | **Excluir tal cual.** Adaptación posible **sin cambiar CA**: una variable autorizada **con** umbral (p. ej. `Humedad Relativa`) y la otra autorizada **sin** umbral (habría que **quitar** temporalmente el umbral 48 o 65; eso muta disco y exige restauración). Hasta que Sergio autorice esa mutación o confirme T/FR: **no ejecutar** |
| TC-M03-083 | S8 | `humedad_suelo` | **No** | No | No | **Excluir.** No sustituir por `Humedad Relativa`. No está en el catálogo RF-53 del backend. El CA de «variable sin umbral» ya está cubierto por E1 si se adapta con las dos variables de Sergio |
| TC-M03-095 | E2 | `temperatura_ambiente` (id 7) | **No** el nombre/id del fixture | ACK no requiere emisión del sensor | — | **No ejecutar con id 7 / T.** **Adaptar identificador** a `id_umbral_ambiental` 65 o 48 y `variable` exactamente `Humedad Relativa` o `pH del agua`. CA intacto: comando min=max=0 → `ACK_UMBRAL` ERROR y **no** se guarda (código `handle_umbral` + `motivo_niveles`) |
| TC-M03-095 | E3 | igual | No | ACK | — | Igual que E2 (banda ancho 0) |
| TC-M03-095 | E4 | `temperatura_ambiente` + lecturas 0 y 9 | No | E4 **persiste** umbral; el original lab no es T 0–10 | Lecturas T **no observadas** | **No ejecutar tal cual.** Adaptar a HR o pH **solo si** hay fuente de lecturas de esa variable (fake/LoRa). `EDGE_FAKE_VARIABLES` no leído → **bloqueado por sensor**. CA firmware (cero válido + CRITICO en 9) **no se reescribe** a ERROR_CONFIGURACION para forzar la matriz |
| TC-M03-122 | E5 | `temperatura_ambiente` solo `normal` | No | ACK | — | Como E2/E3: **adaptar id/nombre** a 65 o 48; CA ACK ERROR intacto |
| TC-M03-122 | E6 | T incompleto en disco + lecturas | No | Haría falta escribir umbral incompleto de una variable autorizada | Lecturas no observadas | **No ejecutar tal cual.** Adaptación: umbral incompleto de HR o pH (`umbrales_guardados`) **solo con autorización** (sudo + recarga de memoria). CA intacto. Hoy: **excluir / bloqueado** (condición E6 + sensor no confirmado para lecturas) |

---

## 5. Resumen de decisiones

| Ejecutar en el lab de Sergio (cuando se autorice fase 2) | Condición |
|---|---|
| E2, E3, E5 **adaptados** a `Humedad Relativa` (65) o `pH del agua` (48) | Sí, son ACK; no requieren que el sensor emita. Restaurar JSON si el firmware no rechazara (el código de `develop` no debe hacer `set()` en ERROR) |
| E1, E4, E6, S8 **con los nombres de `casos_rf55.json`** | **No** (fuera del alcance que dio Sergio) |
| S8 | **Excluir** (variable distinta y ausente del catálogo de código) |
| E1 / E4 / E6 adaptados a HR/pH | Solo con lecturas reales de esas variables **y** (E1/E6) plan de restauración del JSON respaldado |

`test_tc_m03_g38.py` sigue siendo skip de motor; **no** es evidencia de estos escenarios.

---

## 6. Incompatibilidades que no se ocultan

1. Fixture firmware (`temperatura_ambiente` / `frecuencia_respiratoria` / `humedad_suelo`, ids 7 y 8) ≠ umbrales del Edge TEST (`Humedad Relativa` 65, `pH del agua` 48).
2. Snake_case del inyector ≠ nombres M09 con espacios y mayúsculas que están en disco.
3. `rf55_2` no autoriza ninguna variable ambiental.
4. Matriz 095 («umbral 0 → ERROR») vs E4 firmware (cero con ancho > 0 **válido**): se documenta; no se cambia el RF ni se marca E4 fallido por usar cero.
5. Catálogo TEST en vivo: **no leído** (401). Ausencia de `humedad_suelo` se afirma sobre el **código** del backend, no sobre un GET 200.

Referencias: `UMBRALES_ORIGINALES.json`, `ESTADO_INICIAL.md`, `SENSORES_DISPONIBLES.json`, `casos_rf55.json` @ `e618a75`, `formulas.py` `VARIABLES_DEFECTO`, `perfil.py` `SENSOR_RF55_2`, migración `f40c53a37834`.
