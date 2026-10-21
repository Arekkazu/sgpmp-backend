# TC-M03-G106 — RF-58 / CU04 (disponibilidad)

Caso original: **TC-M03-206**. La disponibilidad del servicio de monitoreo (`GET /iot/monitoreo/dashboard`) debe ser **≥ 99,0 %** durante el periodo observado. Hay que documentar:
- la duración exacta del periodo;
- los intervalos de disponibilidad e indisponibilidad;
- el porcentaje obtenido.

La matriz pide una herramienta de monitoreo o *uptime*. Aquí se usa una sonda en Node, sin Newman ni Cypress.

## Sonda

- **Duración:** obligatoria con `--duracion` (por ejemplo, `24h`). La matriz no fija el periodo y no se asume ninguno.
- **Intervalo:** 60 s por defecto (`--intervalo`). El tiempo límite de respuesta es de 10 s.
- **Sesión:** una sola sesión del **Ingeniero de Campo** fuera del sandbox. Es el efecto aceptado `sesion-persistente`: un login con su notificación. Solo se renueva si el token deja de ser válido.
- **Cada sondeo:** un `GET` dentro de **su propio RUN de sandbox**, cerrado inmediatamente. No persisten escrituras (por ejemplo, `ultimo_acceso`) ni se mantiene una transacción abierta durante horas. Los sondeos son secuenciales.
- **Evidencia:** se guarda de forma incremental. Con Ctrl+C, el RUN queda INTERRUMPIDO y conserva lo medido.

| Clase | Cuándo |
| --- | --- |
| DISPONIBLE | HTTP 200 con el contrato del dashboard (`sensores`, `resumen_unidades`, `total`) en ≤ 10 s |
| NO_DISPONIBLE | 5xx, tiempo límite, conexión rechazada o reiniciada, o 200 sin el contrato |
| NO_VERIFICABLE | 401, 403 o 429; sandbox saturado o sin eco; fallo de red del propio cliente (DNS o red inalcanzable) |

Cada sondeo cubre el tiempo hasta el siguiente.

## Resultado

- **Disponibilidad mínima:** lo no verificable cuenta como caído.
- **Disponibilidad máxima:** lo no verificable cuenta como disponible.

| Condición | Resultado propuesto |
| --- | --- |
| Mínima ≥ 99,0 % | APROBADO |
| Máxima < 99,0 % | RECHAZADO |
| Lo no verificable podría cambiar el resultado | BLOQUEADO (indeterminado) |
| Periodo interrumpido | BLOQUEADO |

No hay umbrales inventados: el único criterio es el 99,0 % de la matriz.

## Decisiones QA pendientes

- **Duración del periodo:** obligatoria al ejecutar.
- **Intervalo y tiempo límite:** 60 s y 10 s por defecto.
- **Sonda dentro del sandbox:** mide el servicio a través del middleware de sandbox. Una caída del propio sandbox se clasifica como NO_VERIFICABLE solo si se identifica (saturado o sin eco).
- **Ubicación:** la sonda corre en el equipo QA. Una medición desde la infraestructura (Prometheus, Grafana) requeriría acceso que hoy no existe.

## Uso

```
node ejecutar_tc_m03_g106.mjs --validar-local
node --test validar_local_g106.mjs
node ejecutar_tc_m03_g106.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login,sesion-persistente --duracion 24h [--intervalo 60s]
```

La ejecución solo procede con autorización de Desarrollo y `QA_AUTORIZADO=SI`. V1 se guarda en `RESULTADOS/<RUN_ID>/` y V2 y siguientes en `EvaluacionVN/RESULTADOS/<RUN_ID>/`, con informe Markdown y `evidencia.json` con todos los sondeos.
