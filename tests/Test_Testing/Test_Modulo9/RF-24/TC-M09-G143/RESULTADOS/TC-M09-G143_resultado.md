# TC-M09-G143 — Resultado

**Resultado general: RECHAZADO.**

- **Requisito:** RF-24 v2.0 · **Caso de uso:** CU05 — Gestionar Dispositivos IoT, Flujo F
- **Tipo:** Auditoría / Integridad · **Responsable:** Juan Esteban · **Prioridad:** Alta
- **RUN TEST:** `run-test-20261007-152405` (Newman + Pytest)
- **RUN LOCAL:** `run-local-20261007-153512` (Pytest). El RUN `run-local-20261007-152405` quedó
  invalidado por un falso positivo del detector y se conserva con su constancia en
  `EJECUCION_INVALIDA.md`.
- **Rama:** `qa/juan-esteban-rf24-v2` · **HEAD:** `30ddd72144102a60af006b265a20cb18c1c72c85` ·
  **origin/test:** `30ddd72144102a60af006b265a20cb18c1c72c85` · **divergencia:** `0 0`

El grupo es **RECHAZADO** porque TC-M09-291 alcanza su oráculo y demuestra un incumplimiento
concluyente, aunque los otros dos casos queden bloqueados. Eso es exactamente lo que anticipa la
§48 del paquete: la matriz de TC-291 trata la ausencia de la operación manual VISION como fallo con
evidencia OpenAPI, no como bloqueo.

## Decisión general

| Caso | Ambiente | Prueba local | Resultado | Motivo |
|---|---|---|---|---|
| TC-M09-290 | TEST | NO | BLOQUEADO / NO VERIFICABLE | No existe fuente VISION cuya ventana pudiera tener `count = 0`: ausencia de estructura no es cero observaciones funcionales. |
| TC-M09-291 | TEST | NO | **RECHAZADO** | TEST no publica ninguna operación manual VISION; la única calibración publicada es de SENSOR. |
| TC-M09-292 | LOCAL AISLADO | SÍ | BLOQUEADO / NO VERIFICABLE | El artefacto no implementa la publicación VISION ni una auditoría obligatoria identificable que revocar. |

## Hallazgo transversal: VISION no está implementado

El contrato desplegado en TEST respondió HTTP 200 y publica **210 rutas** y **305 esquemas**.
La palabra `VISION` aparece **0 veces** como token en todo el contrato. Las 10 coincidencias por
subcadena son todas de *provisión* de suministros NIC-41 (`monto_provision`, `id_provision`,
`ProvisionNic41Response`, `naprovisionada`…). Contarlas como presencia sería un falso positivo, así
que la automatización cuenta la palabra con bordes de token, no por subcadena.

Términos del algoritmo del Flujo F presentes en el contrato:

| Término | Ocurrencias |
|---|---|
| `modo_calibracion` | 0 |
| `vector_comportamiento` | 0 |
| `ventana_observacion` | 0 |
| `linea_base` / `baseline` | 0 / 0 |
| `epsilon` / `max_iter` | 0 / 0 |
| `p95` / `winsoriz` / `percentil` | 0 / 0 / 0 |
| `refinamiento` / `convergencia` | 0 / 0 |
| `camara` | 0 |
| `apto_para_ia` | 2 (solo en `TelemetriaCalidadSchema`) |

Las únicas operaciones de calibración publicadas son:

```text
GET  /configuracion/sensores/rangos-calibracion
GET  /configuracion/sensores/{id_sensor}/calibraciones
POST /configuracion/sensores/{id_sensor}/calibrar      ← la única escritura
GET  /iot/monitoreo/historial
```

`POST /configuracion/sensores/{id_sensor}/calibrar` es de **SENSOR**: exige `id_sensor` en la ruta y
su `RegistrarCalibracionDTO` declara
`id_dispositivo_iot, id_infraestructura, valor_referencia, ganancia, offset, fecha_calibracion,
observaciones` — **sin `modo_calibracion`** y sin forma de pedir un cálculo por área.

En el artefacto de la rama, `VISION` aparece 7 veces como palabra y **ninguna** sobrevive al filtro
de falsos positivos.

### Falsos positivos descartados

Darlos por buenos habría llevado a montar un laboratorio para una función inexistente y, en
TC-292, a revocar privilegios sobre una tabla equivocada.

| Coincidencia | Qué es en realidad | Por qué no acredita VISION |
|---|---|---|
| `CAMARA_VISION`, `ATRIBUTOS_VISION`, `_atributos_vision` (7 líneas) | Tipo de dispositivo cámara y sus atributos (resolución, fps, área de cobertura), sembrado por la migración `cf12e716a4ec` en `modulo9.tipos_dispositivo_iot` | Es el **hardware**. Que la cámara exista como dispositivo no implica que exista la operación de calibración por visión. |
| `modulo9.auditorias_visuales` + `AuditoriaIdentidadVisual` (55 líneas) | Auditoría de **identidad visual** de RF-26: logo y colores de marca (`valor_anterior`/`valor_nuevo` en JSONB) | "Visual" no es "visión por computador". **Revocar INSERT aquí habría sido revocar una tabla al azar** y el resultado no diría nada sobre VISION. |
| `integridad_baseline`, "línea base de integridad" (21 líneas) | Baseline de integridad de **RF-10** | No es la línea base del Flujo F. |
| `provisión` / `revisión` | Vocabulario de suministros NIC-41 | Contienen "vision" como subcadena. |
| `EventoAuditoriaSuministro(… PROVISION_INCREMENTAL_ENTREGADA …)` | Auditoría de suministros NIC-41 | Este es el falso positivo que invalidó el primer RUN local; ver `EJECUCION_INVALIDA.md`. |

## TC-M09-290 — disparo automático sin observaciones

**Escenario esperado.** Con A1 activa (especie AVES, `MODELO_AVES`), C1 categoría CAMARA activa y
asociada a A1, y **0 observaciones VISION aplicables**, registrar un lote POBLACIONAL por
`POST /activos-biologicos` debía disparar el cálculo automático y producir: ninguna línea base
nueva, auditoría M09 con `resultado = FALLIDO`, motivo de etapa de filtrado / datos insuficientes y
`usuario_id = null`. La IP no se verifica, porque el disparo es automático.

**Por qué no se ejecutó el disparador.** La §11 exige distinguir dos cosas que no son lo mismo:

```text
existe la fuente VISION pero para (C1, A1) la ventana tiene count = 0   → precondición válida
la fuente VISION no existe en TEST                                      → BLOQUEADO
```

Aquí se da el segundo caso. No existe entidad, ruta ni esquema de observación/vector VISION: el
único `apto_para_ia` del contrato pertenece a `TelemetriaCalidadSchema`, la calidad de telemetría de
**sensores**, y no se asume que sea el vector de comportamiento VISION solo por llevar ese campo —
el caso exige una entidad con cámara, área, ventana y aptitud. Tampoco existe superficie de línea
base donde comprobar que no se publicó ninguna, ni un evento M09 de calibración VISION que pudiera
quedar en FALLIDO.

Por eso `observaciones_count` **no se reporta como 0 sino como no determinable**: no hay fuente
consultable cuyo conteo pudiera ser cero.

La ausencia de ruta manual VISION **no** se usó como motivo del bloqueo (§12): la integración
M02→M09 podría ser interna. El bloqueo se apoya en la fuente de datos y en la superficie de
verificación, no en el endpoint.

**Qué sí está disponible.** `POST /activos-biologicos` existe y el área admite
`tipo_modelo_asignado = MODELO_AVES`. El impedimento no es el fixture. Y precisamente porque el
fixture era viable, **no se registró el lote**: hacerlo habría creado un activo biológico real en
TEST sin ningún oráculo que observar (§14).

**Decisión: BLOQUEADO / NO VERIFICABLE.** No se afirma que la auditoría automática M09 haya fallado,
porque el disparador nunca se ejecutó. No hay tiempo transcurrido que reportar y no se deduce nada
de un retraso: RF-24 no fija SLA y el paquete prohíbe usar "esperé N segundos" como prueba de
ausencia (§16, §20).

## TC-M09-291 — rechazo manual por área sin cámara

**Escenario esperado.** El Ingeniero dispara VISION sobre A2 (activa, especie AVES, `MODELO_AVES`,
**0 cámaras asociadas**) y recibe HTTP 422 con el mensaje contractual
`Calibración por visión no disponible: El área <ID_AREA> no cuenta con observaciones de cámara
aptas o no tiene un modelo poblacional asignado. Verifique las cámaras (RF-21/22) y la
configuración del área (RF-20).`, y RF-10 registra un evento `FALLIDO` del Módulo 9 con usuario
Ingeniero, IP presente y fecha dentro de ventana.

**Qué se observó.** La §22 establece la compuerta: se consulta `GET /openapi.json` y, si la
operación manual VISION no existe, el caso es **RECHAZADO** con evidencia OpenAPI. La operación no
existe. No se inventó la ruta y **no se creó A2**, porque la ausencia ya estaba confirmada.

| Eslabón del oráculo | Estado |
|---|---|
| Operación manual VISION publicada | **NO** |
| HTTP esperado 422 | no alcanzable |
| Mensaje contractual | no alcanzable |
| Auditoría RF-10 `FALLIDO`, Módulo 9, Ingeniero, IP, ventana | no alcanzable |

No se consultó `GET /auditoria/` con Administrador: sin POST no hay ventana `t_before`/`t_after` que
filtrar, y buscar un evento que nadie pudo generar no aportaría evidencia.

**Decisión: RECHAZADO.** El incumplimiento es concluyente y no depende de ninguna precondición de
datos: la operación que el caso evalúa no está desplegada. Este es el único de los tres casos que
alcanza su oráculo, y es el que decide el grupo.

## TC-M09-292 — rollback de la publicación VISION con auditoría denegada

**Escenario esperado.** Con L1 vigente y una ventana W2 que produciría una línea base válida,
denegar el INSERT de la auditoría de publicación debía provocar que la publicación se revirtiera: sin
L2, con L1 intacta y vigente, y una respuesta que informara fallo de trazabilidad. RF-24 no fija
código HTTP exacto para esta variante VISION, así que no se exigía un 500.

**Compuerta previa (§28).** Antes de levantar nada hay que comprobar que el artefacto contiene
VISION, porque el paquete prohíbe mockearlo para volverlo ejecutable. Resultado: **0 de 6 piezas**.

| Pieza requerida | Presente |
|---|---|
| Operación VISION | NO |
| `modo_calibracion` | NO |
| Fuente de observaciones VISION | NO |
| Cálculo de línea base (p5/p95, refinamiento) | NO |
| Persistencia de línea base | NO |
| Auditoría de publicación VISION | NO |

Como contexto, y **sin computarse** como pieza: el artefacto sí tiene transacciones y `rollback`
(252 coincidencias genéricas). Tener rollback no acerca el caso a ser ejecutable si no hay una
publicación VISION que revertir, así que no entra en el denominador.

**Identificación de la auditoría objetivo (§31–§32).** Esta es la compuerta decisiva, y falla por
separado. El paquete exige **no asumir** que VISION reutiliza `modulo1.eventos` ni
`modulo9.auditorias_calibraciones`, y derivar la tabla de una **publicación VISION positiva de
control**. Esa publicación de control no puede ejecutarse, así que la tabla no puede derivarse
empíricamente. Las superficies existentes se examinaron y ninguna sirve de sustituto:

| Superficie | Por qué no es la auditoría de publicación VISION |
|---|---|
| `modulo9.calibraciones` | `id_sensor` y `id_usuario` son **NOT NULL**; no tiene área, especie, vigencia ni origen de disparo. Estructuralmente no puede alojar una línea base de (área, especie) calculada automáticamente con usuario nulo. |
| `modulo9.auditorias_calibraciones` | Depende de un `id_calibracion` de sensor y su `id_usuario` es **NOT NULL**. Es la auditoría de la calibración SENSOR. |
| `modulo9.auditorias_visuales` | Identidad visual de RF-26. |
| `modulo1.integridad_baseline` | Baseline de RF-10. |

Se descartaron **34 tablas candidatas** de auditoría/eventos/bitácora sin elegir ninguna. Conforme a
§32, no se revoca al azar: **no se ejecutó ningún `REVOKE` ni `GRANT`**, y los privilegios
antes/durante/después quedan en `null`, no en `false`.

**Laboratorio.** No se levantó. No se creó compose, base, migraciones, roles ni semillas; no se
reutilizó la BD de desarrollo ni los laboratorios de G79 o G136. Los nombres quedaron reservados y
registrados (`sgpmp-g143-292`, `sgpmp_g143_292`, puerto 55443, backend `127.0.0.1:18043`, volumen
`sgpmp_g143_292_pgdata`) para cuando VISION exista. No se creó `backend.log`: sin POST objetivo no
hay log que capturar, y el paquete pide no generar reportes vacíos.

**Decisión: BLOQUEADO / NO VERIFICABLE.** Los eslabones del oráculo —L1 vigente, W2 válida, INSERT
antes/durante/después, respuesta de trazabilidad, ausencia de L2— son **inalcanzables, no
incumplidos**. No se afirma que el rollback de VISION esté roto: no hay rollback de VISION que
evaluar.

## Presupuesto de operaciones y trazabilidad

| Operación | Planificada | Ejecutada |
|---|---|---|
| `POST /activos-biologicos` (TC-290) | 1 | **0** |
| POST manual VISION (TC-291) | 1 | **0** |
| POST VISION de setup para L1 (TC-292) | 1 | **0** |
| POST VISION objetivo (TC-292) | 1 | **0** |
| `REVOKE` / `GRANT` | 1 + 1 | **0** |

- **Escrituras en TEST: 0.** Ninguna fila creada, modificada ni borrada. La BD TEST se mantuvo de
  solo lectura y de hecho no se abrió ninguna conexión: la decisión se resolvió con el contrato
  público, de modo que el paso de *discovery* por SELECT read-only de la §9 no fue necesario.
- **STOP_ALL: no activado.** Sin POST VISION no pudo generarse una línea base inesperada.
- **Git:** ninguna operación de escritura durante los RUN. `git status --short` solo muestra
  carpetas no rastreadas; `git diff --stat` y `git diff --cached --stat` vacíos. Código productivo
  sin modificar.
- **Secretos:** la colección y ambos módulos solo leen contrato público y archivos del repositorio.
  No hay login, token, cookie ni cabecera `Authorization` en ningún artefacto. Las apariciones
  textuales de `authorization` y `password` en `newman.html` son **nombres de parámetros y campos
  del propio OpenAPI**, no valores.

## Incidencias

Se abren **dos incidencias separadas**, no una consolidada. La §51 permite consolidar solo cuando
comparten causa raíz, y aquí el nivel de afirmación es distinto: una declara un incumplimiento
demostrado del producto; la otra pide aclarar el estado de una entrega.

### Incidencia 1 — operación manual VISION no publicada

```text
INCIDENCIA REQUERIDA: SÍ

Grupo responsable: Desarrollo
Grupo: TC-M09-G143
Caso(s): TC-M09-291
Ambiente: TEST
Resultado: RECHAZADO

Motivo:
RF-24 v2.0 / CU05 Flujo F exige una operación manual de calibración por visión que, sobre un área
sin cámara, responda HTTP 422 con el mensaje contractual y deje un evento RF-10 FALLIDO. El
contrato desplegado en TEST no publica ninguna operación VISION.

Esperado:
Una operación manual VISION publicada en el contrato, capaz de recibir un disparo por área y de
rechazar con 422 el área sin cámara.

Obtenido:
0 ocurrencias de VISION como palabra en 210 rutas y 305 esquemas. La única escritura de calibración
es POST /configuracion/sensores/{id_sensor}/calibrar, de SENSOR, cuyo RegistrarCalibracionDTO no
declara modo_calibracion. Las coincidencias de "vision" son "provisión" de suministros NIC-41.

Causa raíz:
Flujo F de CU05 no implementado o no desplegado en TEST.

Type: bug
Severity: Important
Priority: High
Evidencia:
RESULTADOS/run-test-20261007-152405/{evidencia.json, newman.html, pytest.xml}
```

### Incidencia 2 — dependencias de VISION que impiden cubrir TC-290 y TC-292

```text
INCIDENCIA REQUERIDA: SÍ (aclaración de dependencia; no se declara bug de integración)

Grupo responsable: Por determinar
Componentes a aclarar: M03 (cámara → observación → vector), M09 (línea base y su auditoría),
                       integración M02 → M09
Grupo: TC-M09-G143
Caso(s): TC-M09-290, TC-M09-292
Ambiente: TEST y LOCAL AISLADO
Resultado: BLOQUEADO / NO VERIFICABLE

Motivo:
Falta la fuente formal de observaciones VISION y la superficie de línea base. Sin ellas no puede
demostrarse una ventana con count = 0 (TC-290) ni identificarse la auditoría obligatoria cuya falla
debería revertir la publicación (TC-292).

Esperado:
Fuente de observaciones VISION con cámara, área, ventana y aptitud; umbral N; persistencia de línea
base consultable; y una auditoría de publicación VISION identificable como obligatoria para la
trazabilidad.

Obtenido:
Ninguna de esas piezas en el contrato de TEST ni en el artefacto de la rama (0/6 en la compuerta
local). El tipo de dispositivo CAMARA_VISION existe, pero es el hardware. Las superficies de
auditoría existentes son de otros requisitos: modulo9.auditorias_visuales es identidad visual de
RF-26 y modulo1.integridad_baseline es de RF-10; modulo9.calibraciones y
modulo9.auditorias_calibraciones son de SENSOR, con id_usuario NOT NULL.

Causa raíz:
Por determinar: implementación pendiente, contrato no publicado, o despliegue/documentación no
accesible. La inspección de contrato y artefacto no distingue entre esas posibilidades.

Type: question
Severity: Normal
Priority: Normal
Evidencia:
RESULTADOS/run-test-20261007-152405/evidencia.json
RESULTADOS/run-local-20261007-153512/evidencia.json

Nota: el REVOKE intencional previsto para TC-292 no es incidencia DBA, y en este RUN ni siquiera se
ejecutó. No se reclasifica a DBA porque no existe un esquema de auditoría VISION formal que pudiera
estar mal aplicado.
```

## Conclusión

**TC-M09-G143 → RECHAZADO.**

La calibración por visión del Flujo F no está implementada ni en el contrato desplegado en TEST ni
en el artefacto de la rama. De los tres casos, solo **TC-M09-291** alcanza su oráculo, y lo alcanza
demostrando el incumplimiento: la operación manual VISION que el caso evalúa no existe, y su propia
matriz trata esa ausencia como fallo con evidencia OpenAPI. Eso basta para rechazar el grupo.

**TC-M09-290** y **TC-M09-292** quedan **BLOQUEADOS / NO VERIFICABLES** y se reportan como tales, sin
convertir el bloqueo en un defecto: no se afirma que el disparo automático omita la auditoría
FALLIDO ni que el rollback de VISION esté roto, porque ninguno de los dos mecanismos existe para ser
evaluado.

No se escribió nada en TEST, no se ejecutó ningún fault injection y no se levantó ningún
laboratorio. Cuando VISION esté disponible, ambas compuertas pasarán automáticamente y el trabajo
pendiente será construir los datasets de W2 y derivar la tabla de auditoría objetivo con una
publicación positiva de control.
