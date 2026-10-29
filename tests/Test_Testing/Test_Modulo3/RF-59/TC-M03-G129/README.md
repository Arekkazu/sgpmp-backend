# TC-M03-G129 — RF-59 / CU04 (autorización por granja, recurso y rol)

Casos originales: **TC-M03-258, 259, 260 y 261**. Cubren OWASP API1 (autorización a nivel de objeto) y API5 (a nivel de función) sobre `GET /iot/monitoreo/historial` y `GET /iot/monitoreo/historial/exportar`.

Herramientas:
- **Newman**, con una única petición parametrizada que recorre la matriz actor × endpoint × recurso × comprobación mediante `iterationData`.
- **Node**, que orquesta, prepara el escenario, elige actores por permisos y busca en las bitácoras de auditoría.

No hay Pytest: la parametrización de Newman cubre la suite propuesta por la matriz sin duplicar herramientas. Tampoco Cypress: la matriz exige el control en el backend.

## Escenario construido en el sandbox (APIs oficiales)

| Elemento | Detalle | Caso |
| --- | --- | --- |
| Granja A | Acceso del Ingeniero de Campo (creada con su `id_usuario`, sin tocar sus asignaciones); unidad A con sensor y lecturas | Recursos autorizados (258) |
| Granja B, unidad B1 | Sin acceso del Ingeniero; sensor, lecturas y **alerta activa** | 258 |
| Granja B, unidad B2 | Sensor, lecturas y **activo biológico INDIVIDUAL** | 259 (sensor, activo y unidad) |
| Identificador de control `2147480000` | Comprobado como inexistente (404) por un actor autorizado | 259 |

**Ámbito del Ingeniero:** se verifica que ve la granja A y no la B. Conserva sus granjas reales, así que «acceso exclusivo a A» se interpreta como «sin acceso a B». Una cuenta QA con solo A requeriría crear o reasignar cuentas, y eso no se hace.

## Cómo se garantiza que los recursos ajenos existen

- **Con un actor autorizado (el Administrador, cuyo permiso de lectura también se comprueba):**
  - obtiene el historial de B1, del sensor B2 y de la unidad B2, y cada respuesta debe contener las lecturas del recurso;
  - obtiene la ficha del activo B2;
  - las fichas de unidad y sensor responden 200.
- Sin esas pruebas, la variante queda BLOQUEADA, nunca aprobada: un recurso inexistente aprobaría de forma artificial.
- **Identificador de control:** debe responder 404 en unidad, sensor y activo.

## Autorización por objeto y por rol

- **Por objeto (258 y 259):**
  - el actor tiene permiso de lectura (comprobado con `/roles/{id_rol}/permisos`) y acceso a A, así que cualquier denegación se debe al ámbito y no al rol;
  - el control previo confirma que ve su propia unidad.
- **Por función (260 y 261):** los actores se eligen por sus **permisos reales** del recurso 34 (acción 2, Leer; acción 5, Ejecutar), nunca por el nombre de la cuenta:
  - 260 necesita una cuenta con lectura y sin ejecución, y se confirma además que su consulta del historial responde 200;
  - 261 necesita una cuenta autenticable y sin lectura.

  Si no existe una cuenta QA con ese perfil, el caso queda BLOQUEADO con esa dependencia.

## Aserciones

| Caso | Aserción |
| --- | --- |
| 258 | API-258-01: no se entregan lecturas, total, estadísticas ni rango real de datos de B · API-258-02: no se exponen nombres ni identificadores de B (unidad, sensor, granja, alerta) en ningún nivel · API-258-03: el intento queda registrado en la auditoría. **Sin código HTTP impuesto.** |
| 259 (SENSOR, ACTIVO, UNIDAD) | API-259-01: no devuelve información del recurso ajeno · API-259-02: la respuesta con el identificador ajeno es **indistinguible** de la de un identificador inexistente (mismo estado y mismo cuerpo normalizado), así que no revela existencia ni características |
| 260 | API-260-01: **HTTP 403**, sin aceptar 200, 401, 404 ni 503 · API-260-02: sin archivo, enlace ni identificador de descarga · API-260-03: el intento rechazado queda registrado |
| 261 | API-261-01: acceso denegado (no se entrega un historial; un 200 con resultado vacío no cuenta como denegación) · API-261-02: sin lecturas, estadísticas, alertas ni metadatos. **Sin código HTTP impuesto.** |

**Comparación del eco de la petición:** el campo `filtros_aplicados` repite los parámetros enviados y se excluye de la búsqueda de exposición y de la comparación.

## Auditoría (258 y 260)

- **Fuentes:** las bitácoras oficiales RF-10 (`/auditoria/`) y RF-63 (`/iot/auditoria`), consultadas con la cuenta de preparación desde un ancla temporal del servidor, con hasta 3 búsquedas.
- **Requisitos de cada registro:**
  - es **del actor** (otros usuarios y el propio login quedan fuera);
  - identifica el recurso (la unidad B1 en 258, la exportación en 260);
  - trae fecha y motivo.
- **Testigo positivo:** la bitácora debe mostrar eventos del actor en el propio RUN.
  - Si no se puede consultar o no los muestra, se bloquea **solo** la aserción de auditoría, que tiene variante propia (`GRANJA_AUDITORIA` / `EXPORTAR_AUDITORIA`). Las de denegación conservan su resultado.
  - Si se puede consultar y falta el registro, se propone RECHAZADO con evidencia.
- **No confundir:** `auditoria.logs_dml` es solo el testigo de aislamiento del sandbox (1 dentro, 0 fuera, 0 tras el rollback).

## Dependencias reales

- **259 ACTIVO:** el contrato actual del historial **no tiene filtro `id_activo_biologico`**. La aserción se conserva, y un `[PRE]` dinámico comprueba si el filtro aparece en `filtros_aplicados`; mientras no aparezca, la variante queda BLOQUEADA. `id_unidad_productiva` de la matriz corresponde a `id_infraestructura` en el contrato.
- **Auditoría de accesos denegados:** el control RBAC actual no registra los rechazos (nota de la matriz). Con el testigo cumplido, su ausencia es evidencia de incumplimiento.
- **Cuentas QA:** las de 260 y 261 deben existir con esos perfiles de permisos.
- **M08:** no bloquea 260, porque el permiso se valida antes del servicio de exportación.

## Uso

```
node ejecutar_tc_m03_g129.mjs --validar-local
node --test validar_local_g129.mjs
node ejecutar_tc_m03_g129.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
```

La ejecución solo procede con autorización de Desarrollo y `QA_AUTORIZADO=SI`. V1 se guarda en `RESULTADOS/<RUN_ID>/` y V2 y siguientes en `EvaluacionVN/RESULTADOS/<RUN_ID>/`.
