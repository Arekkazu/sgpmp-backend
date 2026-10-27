# TC-M03-G127 — RF-59 / CU04 (auditoría del historial)

Caso original: **TC-M03-256**. Toda consulta histórica genera un registro de auditoría con usuario, filtros aplicados, rango temporal, cantidad de registros y timestamp. Cuando la operación es una exportación, el registro incluye además el formato.

Herramientas: **Newman** genera las operaciones (como Ingeniero de Campo) y el ejecutor en Node busca y evalúa su registro en las bitácoras. Sin Cypress.

## Variantes

| Variante | Operación | Cuándo se exige |
| --- | --- | --- |
| CONSULTA | `GET /iot/monitoreo/historial` con sensor, unidad, `estado_dato` y periodo conocidos | Siempre |
| EXPORTACION | `GET /iot/monitoreo/historial/exportar` con los mismos filtros y `formato=EXCEL` | Solo cuando la exportación existe (la matriz dice «cuando aplique») |

- **Exportación no disponible:** si responde **503 `M08_NO_DISPONIBLE`**, la variante se registra como INFO, se anota la dependencia de M08 y el resultado del caso se basa en la consulta.
- **Exportación disponible (2xx):** se exige además su registro, incluido el formato.
- **Cualquier otra respuesta** (por ejemplo, 403 o 500): la variante queda BLOQUEADA y el caso no se aprueba.

## Cómo se identifica la auditoría

- **No existe un mecanismo propio de auditoría del historial** en el código actual: ni el caso de uso ni el router registran la consulta. No se inventa ninguna tabla ni endpoint.
- **Fuentes revisadas:** las bitácoras oficiales existentes, **RF-10** (`GET /auditoria/`) y **RF-63** (`GET /iot/auditoria`), consultadas con la cuenta de preparación (Administrador).
- **Ancla temporal:** se toma del servidor antes del login del Ingeniero.
- **Correlación:** un registro solo cuenta si es del Ingeniero y menciona el historial o la exportación, o lleva el sensor del RUN. Se descartan los registros de otros usuarios y los del login.
- **Atributos evaluados** sobre el mejor registro relacionado, recorriendo toda su estructura:
  - usuario;
  - los tres filtros con sus valores;
  - el rango (fecha de inicio y de fin, nunca la marca de tiempo del propio evento);
  - la cantidad, igual al `total` devuelto por la consulta;
  - un timestamp posterior al ancla;
  - el formato, en la exportación.
- **Reintentos:** hasta 3 búsquedas separadas por 10 s.
- **Testigo positivo:** la bitácora RF-10 debe mostrar eventos del propio RUN (el inicio de sesión del Ingeniero). Si no puede consultarse, o no los muestra, la ausencia no se interpreta y el caso queda BLOQUEADO.

| Aserción | Atributo |
| --- | --- |
| API-256-01 | Existe un registro de auditoría de la operación |
| API-256-02 a 06 | Usuario, filtros, rango temporal, cantidad de registros y timestamp |
| API-256-07 | Formato (solo en EXPORTACION) |

## Dependencias

- **Auditoría del historial (RF-59 CA-16):** sin implementar en el código actual. Con el testigo positivo cumplido, la ausencia del registro se propondría como RECHAZADO con evidencia.
- **Posible auditoría post-commit:** si Desarrollo la implementa después del commit (no visible dentro del sandbox), habrá que acordar un mecanismo observable. Los reintentos cubren solo escrituras en sesión separada.
- **M08 (exportación):** pendiente; la variante se activa sola cuando el servicio responda.
- **Escrituras:** no hay SQL de escritura. `auditoria.logs_dml` se usa solo como testigo de aislamiento del sandbox, no como auditoría evaluada.

## Uso

```
node ejecutar_tc_m03_g127.mjs --validar-local
node --test validar_local_g127.mjs
node ejecutar_tc_m03_g127.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
```

La ejecución solo procede con autorización de Desarrollo y `QA_AUTORIZADO=SI`. V1 se guarda en `RESULTADOS/<RUN_ID>/` y V2 y siguientes en `EvaluacionVN/RESULTADOS/<RUN_ID>/`.
