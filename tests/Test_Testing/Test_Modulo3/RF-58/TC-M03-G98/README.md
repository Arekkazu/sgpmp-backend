# TC-M03-G98 — RF-58 / CU04

Caso original: TC-M03-191. El ejecutor descubre mediante `GET /iot/alertas` una unidad con exactamente tres alertas reales `ACTIVA`, de severidad `CRITICO`, `ALTA` y `MEDIA`, en sensores distintos y con activo biológico. Newman comprueba en `GET /iot/monitoreo/dashboard/{id_infraestructura}` el total, la lista ordenada, el tipo, la variable, el tiempo transcurrido y el enlace directo al activo. La preparación es de solo lectura: no altera alertas ni configuraciones existentes.

Validación local: `node ejecutar_tc_m03_g98.mjs --validar-local` y `node --test validar_local_g98.mjs`.

Ejecución futura, únicamente con autorización de Desarrollo y QA: `node ejecutar_tc_m03_g98.mjs --ejecutar --ambiente TEST --autorizacion REF-DESARROLLO --tipo evaluacion --aceptar-efectos notificacion-login`.

Dependencia: el contrato actual de `POST /iot/alertas` solo acepta `LEVE`, `MODERADO` y `CRITICO`; no permite preparar `ALTA` y `MEDIA` de manera oficial. Si en TEST no existen tres alertas fuente elegibles, el escenario queda bloqueado por datos. El dashboard actual publica un contador, pero todavía no expone la lista agregada; esa estructura permanece como aserción funcional para la ejecución autorizada, sin cambiar la matriz. V1 usa `RESULTADOS`; V2+ usa `EvaluacionVn/RESULTADOS`.
