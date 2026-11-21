# TC-M09-G77 — REEVALUACIÓN V2

Caso original: **TC-M09-148 — Rechazar calibración realizada por usuario sin permisos**
Requerimiento: **RF-24 — Calibración de dispositivos IoT** · CU-05 Gestionar Dispositivos IoT
RUN_ID V2: `G77-REEVAL-V2-20260912-211848` · Fecha local: 2026-09-12 · Entorno: **TEST**

---

## DECISIÓN DE REEVALUACIÓN

### REEVALUACIÓN APROBADA

El Productor autenticado `m2m.nuevo@ejemplo.com` envió una calibración
funcionalmente válida en todos sus elementos y el backend respondió
**HTTP 403 `ACCESO_DENEGADO`** con el mensaje «Acceso denegado. Su rol no tiene
permisos para realizar esta operación.». El historial del sensor no cambió: 0
calibraciones antes y 0 después, sin registros nuevos, alterados ni
desaparecidos. Las 11 aserciones de la ejecución pasaron.

El bloqueo observado en la evaluación anterior ya no se reproduce bajo las
condiciones de la reevaluación V2: existe en TEST una cuenta activa con rol
Productor y fue posible ejecutar el POST negativo que V1 nunca pudo enviar.

| Caso | V1 | V2 | Motivo V2 | Categoría | Equipo | Acción |
| --- | --- | --- | --- | --- | --- | --- |
| TC-M09-148 | Rechazado (evidencia V1: BLOCKED) | **APROBADO** | Productor autenticado y activo recibe 403 RBAC (`ACCESO_DENEGADO`) ante una calibración válida y no se persiste ninguna calibración. | No aplica: no hay defecto de producto en V2 | No aplica | Registrar el desbloqueo verificado por QA sobre el reporte de entorno de V1 (INFRAESTRUC / cuentas TEST desactivadas). No corresponde reportar a Desarrollo ni crear incidencia nueva. |

---

## RESULTADO ANTERIOR

| Elemento | Valor |
| --- | --- |
| Resultado en la matriz | Rechazado |
| Resultado registrado en la evidencia V1 | BLOCKED (dos corridas) |
| Corridas V1 | `RESULTADOS/run-20260906-002256/` y `RESULTADOS/run-20260906-003326/` |
| HTTP esperado en V1 | 403 en el POST de calibración |
| HTTP obtenido en V1 | 403 en el **login**, por cuenta desactivada (nunca se llegó al POST) |
| Usuario V1 | Productor (preferido) y Contador (alternativa permitida) |
| Rol V1 | No verificable: ninguna sesión negativa se pudo abrir |
| Payload V1 | Preparado por contrato y discovery; **no enviado** |
| Dispositivo V1 | ID 1, `IOT-EST01-HLA-001`, activo |
| Sensor V1 | ID 3, «Sensor oxígeno disuelto estanque-01», OXIGENO |
| Área V1 | ID 1, asociación activa |
| Valor de referencia V1 | 10.0000, interior al rango 0.0000–20.0000 |
| Persistencia V1 | Ninguna: historial del sensor 3 con total 2, IDs [9, 3], sin cambios |
| Evidencia V1 | `precheck-rbac.json`, `precheck-rbac-reintento.json`, `TC-M09-G77_resultado.md` (×2). Sin HTML Newman: V1 decidió no fabricar evidencia de una ejecución inexistente. |
| Clasificación V1 | INFRAESTRUC — Infraestructura / Sistema Externo TEST |
| Equipo responsable V1 | DBA / Implementación en TEST |
| Incidencia asociada | **Ninguna registrada.** V1 no cita ningún ID; su acción fue «REPORTAR AL DBA» para habilitar una cuenta TEST con rol no autorizado. |

La evaluación V1 se conserva íntegra: no se modificó, movió ni eliminó ninguno
de sus archivos.

---

## CAUSA DEL RESULTADO ANTERIOR

La causa **no fue** «el Productor pudo calibrar». V1 no llegó a evaluar el
control RBAC.

Las dos únicas cuentas de actor no autorizado permitidas (Productor y Contador)
estaban desactivadas en TEST y su login devolvía 403 por estado de cuenta. Como
el caso exige demostrar «autenticado pero no autorizado», y un 403 de login
prueba lo contrario (que no hay sesión), V1 detuvo la ejecución sin consumir
ninguno de sus dos POST y clasificó el resultado como bloqueo de entorno.

Resumen previo exigido antes de ejecutar V2:

| Campo | Valor |
| --- | --- |
| RESULTADO ANTERIOR | Rechazado en matriz / BLOCKED en evidencia |
| CAUSA ANTERIOR | Actores no autorizados desactivados en TEST; sin sesión negativa disponible |
| ESPERADO | HTTP 403 RBAC en el POST de calibración, sin persistencia |
| OBTENIDO | HTTP 403 en el login por cuenta desactivada; POST nunca enviado |
| TIPO DE FALLO | Entorno (INFRAESTRUC), no producto ni automatización |
| INCIDENCIA ASOCIADA | Ninguna registrada en la evidencia V1 |
| QUÉ DEBE REEVALUARSE | Si existe hoy un Productor activo en TEST y, con esa sesión, si el endpoint de calibración deniega por RBAC sin persistir |

---

## OBJETIVO DE LA REEVALUACIÓN

Demostrar, con datos redescubiertos en TEST, la cadena completa que V1 no pudo
recorrer:

`Productor autenticado y activo` × `dispositivo activo` × `sensor válido y
asociado` × `área correcta vigente` × `valor de referencia interior al rango`
→ **HTTP 403 por RBAC** → **sin persistencia**.

La única invalidez del escenario debía ser el rol.

---

## ENTORNO

| Elemento | Valor |
| --- | --- |
| Entorno | TEST (G77 no usa MQTT, por lo que no corresponde DEV) |
| Backend | `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Frontend | `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io` (solo preflight; G77 no usa UI) |
| Health backend | 200 · `openapi.json` 200 · contrato del endpoint declara 400/401/403/404/422/500 |
| Herramientas | Newman 6.2.2 + newman-reporter-htmlextra 1.23.1 |
| Cypress | No ejecutado |
| MQTT | No utilizado |
| PostgreSQL | No utilizado; la persistencia se verificó por API |

**Nota sobre el esquema suministrado.** La URL base indicada para esta
reevaluación usaba `http://`. Ese esquema no está enrutado en el edge de TEST:
todas las rutas, incluida `/health`, devuelven un `404 page not found` en texto
plano emitido por el proxy, sin redirección a HTTPS. El mismo host por `https://`
responde 200 y sirve el contrato. La sustitución **no** fue automática: se
consultó al responsable QA y se ejecutó sobre HTTPS con su autorización
explícita. El hecho queda registrado en `precheck-v2.json`.

---

## GIT / SHAs

| Repositorio | Rama | SHA | Uso |
| --- | --- | --- | --- |
| sgpmp-backend | `qa/juan-esteban-re-evaluacion-M02` | `ff5f6c9f6161e46c94d3d6f325a7d07d80d84aa0` | Lectura de contrato (router, DTO, use case, RBAC) y única zona escribible: `RF-24/TC-M09-G77/EvaluacionV2/` |
| SGPMP-FRONT-END-PWA | `qa/juan-esteban-re-evaluacion-M02` | `49966d244673eb44d0be61e7df25c27d460b2c1c` | No utilizado; no se escribió ni leyó código funcional |

Ambos repositorios estaban en la rama obligatoria antes de empezar. No se
ejecutó ninguna operación de escritura de Git.

---

## DATOS DINÁMICOS UTILIZADOS

Los datos de V1 **no** se reutilizaron: se redescubrieron por API. El
descubrimiento seleccionó el primer dispositivo activo con sensor activo,
asociación de área vigente y rango técnico conocido, y resultó ser un
dispositivo distinto al de V1.

| Dato | Valor V2 | Verificación |
| --- | --- | --- |
| Dispositivo | ID 3 · `IOT-ALE01-HLA-003` | `GET /configuracion/dispositivos-iot?solo_activos=true` → `es_activo: true` |
| Sensor | ID 7 · «Sensor oxígeno disuelto alevinera-01» · OXIGENO | `GET /configuracion/dispositivos-iot/3/sensores` → activo y `id_dispositivo_iot: 3` |
| Área | ID 3 · asociación 7 · «Zona de alevinaje, profundidad 20 cm» | `GET /configuracion/sensores/7/asociaciones` → asociación vigente (`tiene_estado: true`, sin fecha de finalización) |
| Rango técnico OXIGENO | 0.0000 – 20.0000 | `GET /configuracion/sensores/rangos-calibracion` |
| Valor de referencia | 10.0000 | Punto medio del rango, claramente interior, compatible con `numeric(10,4)` |
| Observaciones | `QA TC-M09-148 REEVALUACION V2 G77-REEVAL-V2-20260912-211848` | Correlacionable, sin secretos |

**Actor de descubrimiento.** RF-24 §10 prevé al Ingeniero de Campo para las
lecturas. En TEST el Ingeniero (`ingeniero@pecuaria.co`) autentica y tiene
permisos de sensores, pero no tiene fincas asignadas y su rol no es global: el
alcance de finca le devuelve `total: 0` en la lista de dispositivos y 404 en el
detalle del dispositivo y en las asociaciones del sensor. Lo mismo le ocurre al
Productor. Por eso, y solo para GET, se escaló al Administrador
`administador.dev@gmail.com` (rol global) conforme a §11. El Administrador
**no** ejecutó ninguna calibración: no hubo calibración positiva de control.

Observaciones de entorno detectadas de paso, ajenas al alcance de G77 y no
reportadas como defecto de este caso: `admin@pecuaria.co` responde HTTP 500
`ERROR_INTERNO` al iniciar sesión en TEST, y ni Ingeniero ni Productor tienen
fincas asignadas en TEST, lo que limita el descubrimiento a roles globales.

---

## VALIDACIÓN DEL ACTOR

| Validación | Resultado |
| --- | --- |
| Productor autenticado | **Sí** — `POST /sesiones/` HTTP 200 |
| Identidad confirmada | `m2m.nuevo@ejemplo.com`, `id_usuario: 35` (`GET /usuarios/me`) |
| Rol Productor confirmado | **Sí** — `nombre_rol: "Productor"` |
| Estado de cuenta | `Activo` (descarta un 403 por `CUENTA_NO_ACTIVA`) |
| Permisos sobre el recurso 12 (sensores) | `[2]` — solo lectura (`GET /sesiones/me/permisos`) |
| Permiso de creación (acción 1) | **Ausente** |
| Roles autorizados por RF-24 | Ingeniero de Campo · Administrador |
| Productor pertenece a los roles autorizados | **No** |
| Endpoint correcto | `POST /configuracion/sensores/7/calibrar`, protegido por `require_permission(12, 1)` |
| Payload funcionalmente válido | **Sí** — dispositivo activo, sensor asociado, área vigente, valor interior al rango |
| HTTP obtenido | **403** |
| 403 originado por RBAC | **Sí** — `error_code: ACCESO_DENEGADO` |
| Persistencia | **No** |

El token del Productor vivió únicamente en memoria del proceso. Ninguna
contraseña ni token se escribió en artefactos.

---

## EJECUCIÓN

Un único POST, ejecutado con Newman y la sesión del Productor. Presupuesto de
la reevaluación: 1 POST inicial + 1 reintento justificado; **se consumió 1 de 2**
y no hubo reintento porque el primer intento fue concluyente.

```
POST /configuracion/sensores/7/calibrar
{
  "id_dispositivo_iot": 3,
  "id_infraestructura": 3,
  "valor_referencia": "10.0000",
  "ganancia": "1.0000",
  "offset": "10.0000",
  "fecha_calibracion": "2026-09-13T02:30:06.753Z",
  "observaciones": "QA TC-M09-148 REEVALUACION V2 G77-REEVAL-V2-20260912-211848"
}
```

Respuesta:

```
HTTP 403
{
  "error_code": "ACCESO_DENEGADO",
  "message": "Acceso denegado. Su rol no tiene permisos para realizar esta operación.",
  "fields": [],
  "timestamp": "2026-09-13T02:30:09.257602+00:00"
}
```

Aserciones: **11 de 11 correctas, 0 fallidas.**

**El 403 es RBAC real, no de infraestructura.** La respuesta es un JSON de la
aplicación con el contrato de error propio del backend (`error_code`, `message`,
`fields`, `timestamp` del servidor), no la página de error del proxy — el mismo
proxy responde `404 page not found` en texto plano cuando la petición no llega a
la aplicación, como se observó en el esquema HTTP. El código
`ACCESO_DENEGADO` lo emite `require_permission(12, 1)` en
`src/shared/rbac.py:100` tras comprobar que el rol carece del permiso, y se
distingue del otro 403 de esa misma dependencia (`CUENTA_NO_ACTIVA`), descartado
porque la cuenta está `Activo`. Tampoco es 401: la sesión era válida. No hubo
CSRF, URL incorrecta ni gateway intermedio: la URL invocada es exactamente el
endpoint del contrato.

---

## PERSISTENCIA

| Evidencia | HISTORY_BEFORE_V2 | HISTORY_AFTER_V2 | Cambió |
| --- | --- | --- | --- |
| Total de calibraciones del sensor 7 | 0 | 0 | No |
| IDs presentes | [] | [] | No |
| Registros nuevos | — | ninguno | No |
| Registros atribuibles al Productor (id_usuario 35) | — | ninguno | No |
| Registros históricos alterados | — | ninguno | No |
| Registros históricos desaparecidos | — | ninguno | No |
| ID de calibración devuelto por la respuesta | — | ninguno | No |

Ambas lecturas se hicieron con `GET /configuracion/sensores/7/calibraciones`
usando el actor autorizado de solo lectura. El POST del Productor no creó
calibración alguna.

---

## COMPARACIÓN V1 VS V2

| Aspecto | Evaluación anterior | Evaluación V2 |
| --- | --- | --- |
| Actor | Productor y Contador (ninguno pudo autenticar) | Productor |
| Rol confirmado | No verificable, sin sesión | Sí — `Productor`, cuenta `Activo` |
| HTTP esperado | 403 | 403 |
| HTTP obtenido | 403 **en el login** (cuenta desactivada); POST no ejecutado | **403 en el POST**, `ACCESO_DENEGADO` |
| Payload válido | Preparado, no enviado | Sí — enviado y válido salvo el rol |
| Persistencia | No (no hubo POST) | No |
| POST ejecutados | 0 de 2 | 1 de 2 |
| Dispositivo / sensor / área | 1 / 3 / 1 | 3 / 7 / 3 (redescubiertos) |
| Resultado | Rechazado (BLOCKED) | **APROBADO** |

---

## ORIGEN DEL FALLO

| Origen | V1 | V2 |
| --- | --- | --- |
| Producto (defecto funcional) | No demostrado | **No**: el control RBAC funciona como exige RF-24 |
| Automatización / error de prueba | No | No |
| Entorno TEST | **Sí** — actores no autorizados desactivados | Resuelto para este caso: existe un Productor activo |
| Bloqueo | Sí | No |

El resultado anterior no fue causado por un defecto de Desarrollo ni por un
error de automatización, sino por la ausencia en TEST de una cuenta con rol no
autorizado y sesión posible. Esa condición ya no se presenta.

---

## CATEGORÍA Y EQUIPO RESPONSABLE

No corresponde asignar categoría de defecto en V2: la reevaluación aprueba.

Para trazabilidad histórica, la clasificación del bloqueo anterior se mantiene
como fue registrada en V1: `INFRAESTRUC — Infraestructura / Sistema Externo`,
equipo responsable **Implementación en TEST** (V1 lo dirigió al DBA). Nada de
esto se reasigna a Desarrollo: no hubo defecto de producto en ninguna de las dos
evaluaciones.

---

## ACCIÓN SOBRE INCIDENCIA

La evidencia V1 **no registra ningún ID de incidencia**; su acción fue reportar
el bloqueo al DBA. No se inventa un identificador: si el Registro de Errores
vigente contiene un reporte abierto por ese bloqueo, la acción es
**actualizarlo como desbloqueo verificado por QA**, adjuntando este RUN_ID; si
no existe, queda `ID pendiente de asignación según Registro de Errores vigente`
y basta con dejar constancia del desbloqueo.

- **No** se crea incidencia nueva ni duplicada.
- **No** se reporta a Desarrollo: el 403 RBAC es el comportamiento correcto.
- **No** se elimina evidencia ni tickets anteriores.
- La evaluación V1 se conserva como antecedente y queda referenciada desde V2.
- La severidad no se infiere: no se asigna ninguna, porque no hay defecto en V2.

No se crearon tickets automáticamente (ni Taiga, ni issues, ni PR).

---

## EVIDENCIAS

Todas dentro de `RF-24/TC-M09-G77/EvaluacionV2/RESULTADOS/G77-REEVAL-V2-20260912-211848/`:

| Archivo | Contenido |
| --- | --- |
| `precheck-v2.json` | Preflight, contrato, alcance del Ingeniero y escalado a Administrador, validación del actor negativo, datos redescubiertos, HISTORY_BEFORE y checklist de 14 puntos previa al POST |
| `TC-M09-148-reevaluacion-v2-intento1.json` | Evidencia sanitizada de la ejecución: RUN_ID, actor, rol, autenticación, dispositivo, sensor, área, valor, endpoint, status, código funcional, HISTORY_BEFORE/AFTER, persistencia y resultado |
| `newman/newman-TC-M09-148-reevaluacion-v2-intento1.html` | Reporte Newman htmlextra del único POST |
| `seguridad-evidencias.json` | Resultado del escaneo final de secretos |
| `git-final.json` | Estado de Git de cierre en ambos repositorios |
| `TC-M09-G77_reevaluacion_V2.md` | Este reporte |

Automatización, en `RF-24/TC-M09-G77/EvaluacionV2/`: `helpers.cjs`,
`precheck.cjs`, `run-newman.cjs`,
`TC-M09-G77-reevaluacion-v2.postman_collection.json` y `README.md`.

Ningún artefacto de V1 fue sobrescrito ni eliminado.

---

## SEGURIDAD

- Las contraseñas se pasaron exclusivamente por variables de proceso
  (`TEST_PRODUCTOR_PASSWORD`, `TEST_ENGINEER_PASSWORD`, `TEST_ADMIN_PASSWORD`) y
  no aparecen en colección, entorno versionado, HTML, JSON, Markdown ni logs.
- Los tokens vivieron solo en memoria. El reporte Newman se generó con
  `omitHeaders`, sin datos de entorno y omitiendo la variable `token`; además el
  HTML se saneó tras generarse.
- Escaneo final sobre toda la carpeta `EvaluacionV2/`: **0 contraseñas
  literales, 0 JWT, 0 `Bearer` con valor y 0 `refresh_token` con valor** en
  cualquier archivo. En la evidencia HTML y JSON hay **0 coincidencias** de
  `Authorization`, `Bearer`, `access_token`, `refresh_token`, `password`,
  `cookie` o `jwt`. Las coincidencias restantes están en los `.cjs`, la
  colección, el README y este reporte, y son nombres de variable, patrones de
  redacción, el marcador `{{token}}` o texto descriptivo, nunca valores. Detalle
  por archivo en `seguridad-evidencias.json`.
- No se imprimió ningún valor secreto durante el escaneo.

---

## GIT FINAL

Backend `sgpmp-backend`, rama `qa/juan-esteban-re-evaluacion-M02`, SHA
`ff5f6c9f6161e46c94d3d6f325a7d07d80d84aa0`:

- `git status --short`: 1 entrada, la carpeta `EvaluacionV2/` sin seguimiento.
- `git diff --stat`: **vacío**, ningún archivo rastreado fue modificado.
- `git ls-files --others --exclude-standard`: los archivos nuevos pertenecen en
  su totalidad a `tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G77/EvaluacionV2/`.
- No existen cambios preexistentes ajenos en este repositorio.

Frontend `SGPMP-FRONT-END-PWA`, rama `qa/juan-esteban-re-evaluacion-M02`, SHA
`49966d244673eb44d0be61e7df25c27d460b2c1c`: árbol limpio, sin cambios ni
archivos sin seguimiento. No se tocó.

Controles cumplidos: no hubo commit, push, pull, merge, rebase, reset, clean,
stash, checkout, cambio ni creación de ramas, tags ni PR. No se modificó código
funcional, permisos, roles, usuarios, dispositivos, sensores, áreas, rangos,
infraestructura ni dependencias. No se ejecutó SQL de ningún tipo. No hubo
limpieza de datos. La evaluación V1 permanece intacta.

**La ejecución se detiene aquí para revisión humana.**
