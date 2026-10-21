# TC-M03-G107 — RF-58 / CU04 (control de acceso)

Casos originales:
- **TC-M03-207**: BOLA entre granjas (OWASP API1).
- **TC-M03-208**: rol sin permiso de lectura (OWASP API5).
- **TC-M03-209**: registro en bitácora de los accesos denegados (ASVS V7).

Herramientas: **Newman** para 207 y 208 en ambas rutas del dashboard; el ejecutor en Node evalúa 209 sobre esos mismos rechazos.

## Escenario construido en el sandbox (APIs oficiales)

- **Granja A:** con acceso del **Ingeniero de Campo** (creada con su `id_usuario`) y una unidad con sensor y lectura, que es su vista legítima.
- **Granja B:** sin acceso del Ingeniero, con unidad, sensor, lectura y una **alerta activa**. Son los datos que no deben exponerse.
- **Rol sin permiso:** la primera cuenta QA cuyo rol no tiene el permiso activo (recurso 33, Leer). Se comprueba con `GET /roles/{id_rol}/permisos` y no con el propio dashboard.
- **Precondiciones `[PRE]`:**
  - el Ingeniero está autorizado en A y no en B;
  - la unidad B es un identificador válido con datos;
  - el Ingeniero ve su propia unidad;
  - existe la cuenta sin permiso.

## Aserciones

| Caso | Ruta `?id_infraestructura=` y ruta `/dashboard/{id}` |
| --- | --- |
| 207 | API-207-01: la respuesta no expone nombres ni identificadores de la granja B en ningún nivel del JSON (unidad, granja, sensor, alerta) · API-207-02: el acceso es denegado (respuesta 4xx). El código concreto se registra como INFO, porque la matriz no lo fija. |
| 208 | API-208-01: HTTP 403 · API-208-02: mensaje de acceso no autorizado, sin lecturas ni datos de ninguna granja |
| 209 | API-209-01 (rol sin permiso) y API-209-02 (granja ajena): cada rechazo producido en 207 y 208 tiene **su propio registro** con fecha, usuario, unidad solicitada y motivo |

Para 209 se consultan inmediatamente las bitácoras RF-10 (`/auditoria/`) e IoT (`/iot/auditoria`), desde un ancla temporal del servidor.

**Testigo positivo:** la bitácora RF-10 debe reflejar eventos del propio RUN (el inicio de sesión del Ingeniero). Si no los refleja, o no se puede consultar, la ausencia de registros no se interpreta y el resultado es BLOQUEADO.

## Decisiones QA y dependencias

- **«Unidad no asignada» (API-209-03): REQUIERE DECISIÓN QA.** El producto delimita el alcance por granja (`usuarios_fincas`) y no existe asignación de unidades a usuarios, así que el escenario no se distingue de «granja ajena». Mientras no se defina, 209 no puede aprobarse. Sus otros dos rechazos sí se evalúan y pueden rechazar.
- **207 con HTTP 200 sin datos:** cumple «no expone», pero no «es denegado». La nota de la matriz excluye solo el código *específico*. Si QA considera que una respuesta vacía equivale a denegación, API-207-02 debe pasar a INFO.
- **209 depende del producto:** la nota de la matriz advierte que no se encontró auditoría propia del monitoreo. Si el registro llega a ser asíncrono (post-commit), el testigo positivo evita un falso rechazo.

## Aislamiento, rollback y veredicto

- **Aislamiento:** el testigo es el INSERT del dispositivo de la granja A en `auditoria.logs_dml`. Se exige 1 dentro del RUN, 0 fuera y 0 tras el rollback.
- **Peticiones** secuenciales.
- **Veredicto por caso:**
  - RECHAZADO: un `[ASSERT]` incumplido con respuesta real y sin `[PRE]` fallido en su ruta o caso.
  - BLOQUEADO: precondiciones, entorno o automatización.

## Uso

```
node ejecutar_tc_m03_g107.mjs --validar-local
node --test validar_local_g107.mjs
node ejecutar_tc_m03_g107.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
```

La ejecución solo procede con autorización de Desarrollo y `QA_AUTORIZADO=SI`. V1 se guarda en `RESULTADOS/<RUN_ID>/` y V2 y siguientes en `EvaluacionVN/RESULTADOS/<RUN_ID>/`, con informe Markdown y `evidencia.json`.
