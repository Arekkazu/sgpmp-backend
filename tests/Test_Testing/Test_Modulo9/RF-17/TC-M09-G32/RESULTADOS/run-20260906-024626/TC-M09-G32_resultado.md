# TC-M09-G32 — RESULTADO

## DECISIÓN GENERAL

`BLOCKED — CONFIGURACIÓN EFECTIVA DE MONITOREO NO VERIFICABLE EN TEST`

TC-M09-69 exige demostrar `CONFIG_BEFORE → modificación → CONFIG_AFTER → Monitoreo utiliza CONFIG_AFTER`. La API disponible permite consultar y editar RF-17, pero Monitoreo no expone el umbral, rango efectivo, versión ni un contexto especie–activo que permita relacionar una configuración RF-17 concreta con los sensores monitorizados.

| Caso | Resultado | Motivo | Categoría de error | Equipo responsable | Acción |
| --- | --- | --- | --- | --- |
| TC-M09-69 | BLOCKED | No existe un mecanismo API correlacionable para comprobar la configuración efectiva utilizada por Monitoreo antes y después. | No aplica — bloqueo de observabilidad e integración | Desarrollo — responsable del desbloqueo | REPORTAR A DESARROLLO PARA DESBLOQUEO |

## ENTORNO Y EJECUCIÓN

| Dato | Valor |
| --- | --- |
| Fecha / ejecución | 2026-09-06 / `run-20260906-024626` |
| Backend TEST | `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| API Monitoreo | `GET /iot/monitoreo/dashboard` y `GET /iot/monitoreo/historial` |
| Rama backend | `qa/juan-esteban-m09` |
| SHA backend | `adc3932b9f0293a76ebec7e89ed877274791b6a1` |
| Rama frontend | `qa/juan-esteban-m09` |
| SHA frontend | `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56` |
| SHA desplegado en TEST | No confirmado. |
| Actor | Administrador TEST, identidad HTTP 200, rol Administrador |
| Newman / htmlextra | 6.2.2 / 1.23.1 |

## CONTRATO Y ORÁCULO

RF-17 expone `PATCH /configuracion/umbrales/{id_umbral_ambiental}` con `valor_min`, `valor_max` y los tres niveles de alerta. Monitoreo expone Dashboard e Historial, ambos accesibles con HTTP 200 durante esta ejecución.

Ninguna respuesta de Monitoreo expone `id_umbral_ambiental`, `valor_min`, `valor_max`, versión de configuración ni un rango equivalente. El Dashboard incluye sensor, variable y estado, pero no especie o activo. El Historial incluye especie y activo como campos opcionales; las cinco lecturas recientes recibidas los devolvieron nulos.

La revisión estática de la rama QA respalda el resultado: el Dashboard lee estados actuales y el Historial utiliza `UmbralHistoricoM09Adapter`, marcado como stub. Como el SHA desplegado no está confirmado, esta evidencia estática no se clasifica como defecto de producto.

El detalle sanitizado está en `investigacion-contrato.json`.

## CONFIGURACIÓN Y MONITOREO BEFORE

Se seleccionó solo para discovery el umbral activo que coincide por variable con lecturas recientes. No se declaró apto para modificar, porque no se pudo demostrar la especie/activo del mismo contexto en Monitoreo.

| Dato | CONFIG_BEFORE | MONITORING_BEFORE |
| --- | --- | --- |
| ID/contexto | Umbral 11; especie Cachama Blanca; variable 3 | No expone referencia de umbral ni especie/activo correlacionable |
| Variable | Oxígeno disuelto, `mg/L` | Sensores y lecturas de Oxígeno disuelto presentes |
| valor_min | 0.00 | No expuesto |
| valor_max | 100.00 | No expuesto |
| Nivel normal | 4.00–12.00 | No expuesto |
| Nivel precaución | 2.00–4.00 | No expuesto |
| Nivel crítico | 0.00–2.00 | No expuesto |
| Estado | Activo | Dashboard e Historial: HTTP 200; semáforos históricos recibidos en GRIS |

La coincidencia de variable no es suficiente: puede corresponder a Cachama Blanca, Trucha Arcoíris u otro contexto. Por esa razón, `CONFIG_BEFORE == MONITORING_BEFORE` no está demostrado.

## PROPAGACIÓN HACIA MONITOREO

| Campo | Config BEFORE | Monitoreo BEFORE | Config AFTER | Monitoreo AFTER | Esperado |
| --- | --- | --- | --- | --- | --- |
| ID/contexto | Umbral 11 / Cachama Blanca / variable 3 | No expuesto | No aplica | No aplica | Mismo contexto |
| Especie | Cachama Blanca | No correlacionable | No aplica | No aplica | Coincide |
| Variable | Oxígeno disuelto | Oxígeno disuelto sin especie/activo | No aplica | No aplica | Coincide |
| valor_min | 0.00 | No expuesto | No aplica | No aplica | Nuevo valor |
| valor_max | 100.00 | No expuesto | No aplica | No aplica | Nuevo valor |

`Configuración central modificada: No.`

`Monitoreo consultable: Sí.`

`Monitoreo utilizaba BEFORE antes del cambio: No verificable.`

`Monitoreo utiliza AFTER después del cambio: No aplica; no se consumió una modificación.`

`Propagación comprobada: No.`

## CONTROL DE ESCRITURAS Y EVIDENCIA

No se ejecutó `PATCH /configuracion/umbrales/{id}`. El contador de modificaciones funcionales para TC-M09-69 permanece en **0 de 2**. No se creó, restauró, desactivó ni eliminó ningún umbral.

Newman ejecutó solo Login, identidad, `CONFIG_BEFORE`, Dashboard e Historial. Registró cinco aserciones aprobadas y cero fallos. La evidencia está en:

- `newman-TC-M09-69-intento1.json`
- `newman/newman-TC-M09-69-intento1.html`

## ORIGEN DEL FALLO

| Origen | Resultado |
| --- | --- |
| Producto | No confirmado. No se demostró un comportamiento desplegado incorrecto. |
| Automatización/prueba | No. Las consultas y aserciones de discovery finalizaron correctamente. |
| Entorno | No. Los endpoints RF-17 y Monitoreo respondieron HTTP 200. |
| Bloqueo | Sí. Falta un oráculo observable y correlacionable de la configuración efectiva de Monitoreo. |
| Categoría | No aplica — bloqueo de observabilidad. |
| Equipo responsable | Desarrollo — responsable del desbloqueo, no defecto confirmado. |
| Acción | REPORTAR A DESARROLLO PARA DESBLOQUEO. |

No existe un defecto funcional confirmado porque no se pudo ejecutar una modificación con un oráculo válido. Aun así, el bloqueo debe ser atendido por **Desarrollo**: el backend debe proveer la integración o el mecanismo oficial que permita correlacionar especie, activo, sensor, variable, umbral efectivo y resultado de Monitoreo. No corresponde a Implementación porque los endpoints TEST respondieron correctamente; tampoco a DBA, AIoT ni QA porque no hay evidencia de fallo de datos, dispositivo o automatización.

**Acción requerida: REPORTAR A DESARROLLO PARA DESBLOQUEO.** El reporte debe solicitar el mecanismo de correlación y propagación descrito, para reanudar TC-M09-69 sin asumir datos ni modificar umbrales innecesariamente. Esta acción no declara un defecto funcional todavía.

## CONDICIÓN PARA REANUDAR

Desarrollo debe entregar uno de estos mecanismos oficiales en TEST:

1. una respuesta de Monitoreo que exponga el identificador y rango efectivo del umbral; o
2. una respuesta correlacionable que incluya especie, activo, sensor, variable y el resultado calculado con el rango aplicado.

Con esa evidencia se podrá seleccionar un único umbral apto, capturar BEFORE, ejecutar una sola modificación válida y comparar AFTER sin suposiciones.

## SEGURIDAD Y GIT

- No se persistieron credenciales, datos de sesión, cabeceras de autenticación ni cadenas de conexión.
- No se ejecutó SQL ni hubo conexión a PostgreSQL.
- No se modificó código funcional, datos de negocio, configuración, infraestructura ni dependencias.
- No hubo commit, push, pull, merge ni cambio de rama.
- No se ejecutó ningún grupo anterior ni se avanzó a G33.

## VALIDACIÓN Y GIT FINAL

- `node --check run-newman.cjs` y la validación JSON de la colección terminaron correctamente.
- Newman ejecutó las cinco consultas previstas sin fallos de aserción.
- La sanitización final revisó cuatro artefactos de texto —HTML, JSON y Markdown— sin detectar secretos ni valores de sesión.
- En backend, `git diff --stat` solo muestra la eliminación preexistente del archivo vacío `TC-M09-G32/.gitkeep`. Los archivos de G32 creados durante esta ejecución son artefactos QA sin seguimiento. Los artefactos sin seguimiento de G24–G30 y RF-24 ya estaban presentes y se preservaron.
- En frontend no se creó ni modificó contenido para G32. Su estado conserva las eliminaciones y artefactos QA preexistentes de otros grupos.

El grupo queda detenido para revisión humana.
