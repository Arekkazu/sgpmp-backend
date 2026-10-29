# TC-M03-G98 — TC-M03-191

Preparación local de la automatización API de RF-58/CU04. No se ha consultado TEST ni creado un RUN.

**Oráculo literal de la matriz (fila G98, Windows-1252):** «HTTP 200. Se devuelve el total de alertas activas y la lista ordenada por severidad con CRITICO primero, indicando tipo de alerta, variable afectada y tiempo transcurrido, con navegación al detalle del activo biológico afectado.» Datos de la matriz: alertas activas CRITICO, ALTA y MEDIA en sensores distintos de una unidad. RF-58 Salida 2 está en `Especificacion-Requerimientos-Modulo3.md:5400-5407`; CA-11 en `:5531-5532`. RF-57 define `CRITICO > MODERADO > LEVE` en `:3785` y `LEVE | MODERADO | CRITICO` en `:4547`. La diferencia de nombres con la matriz queda documentada; se aceptan por separado el catálogo RF-57 y la escala literal CRITICO/ALTA/MEDIA de la matriz, sin inferir equivalencia entre escalas.

Una sola comprobación obligatoria `API-191-01`, sin UI. `GET /iot/monitoreo/dashboard/{id_infraestructura}` debe devolver un panel con total y lista, elementos con tipo, variable, tiempo transcurrido y enlace o identificador del activo, en orden descendente con CRITICO primero. Se aceptan nombres de campo equivalentes explícitos y se registran los nombres reales. El contador por unidad y los campos aislados del sensor no son un panel. La falta de panel en respuesta 200 con eco es RECHAZADO incluso si la lista debería estar vacía. Panel presente sin severidades mixtas es BLOQUEADO por datos. 5xx es BLOQUEADO; sin respuesta o sin eco es NO_CONCLUYENTE. APROBADO requiere panel completo, al menos dos severidades y orden válido.

El ejecutor consulta primero las unidades 1, 268 y 337; añade hasta tres candidatas desde una lectura de fincas y hasta dos de infraestructuras visibles al Productor. Newman recorre páginas por unidad hasta hallar alertas activas o agotar 12 páginas; no usa el dashboard global ni crea datos. Se detiene al hallar la primera unidad con alertas. El primer RUN autorizado puede probar el incumplimiento aunque no existan alertas activas: el total y la lista exigidos deben estar presentes. Referencias de código leídas: backend `origin/test 5b46ca00a0ba92774f8e3d4b9eeaeec169344f17`; frontend `origin/test 81058af57d5d80d523fb5225f8eab48e0307ba85`. Su divergencia es `DEFECTO_FUNCIONAL_CANDIDATO`, sin veredicto de TEST.

## Presupuesto para la SOL futura

Fuente única: `lib/g98_presupuesto.cjs`. Máximo 3 GET de descubrimiento + 12 GET del dashboard (`por_pagina=50`) = **15 GET** dentro del RUN, 1 DELETE de cierre y **600 s**. Login Productor antes del RUN. Las lecturas llevan `X-Test-Run-Id` y `X-Sandbox-Secret` con eco obligatorio; sin refresh ni inactividad intencional. El cierre solo verifica bitácora de GET con eco y DELETE 200. El login puede registrar último acceso, auditoría, notificaciones y cierre de sesiones; las lecturas del dashboard pueden generar correo RF-58 E7 por sensores GRIS sin umbral no desactualizados. No se presume reversión de efectos externos.

## Comandos locales

`node g98.mjs --capacidades` y `node g98.mjs --comprobar` no leen `.env.qa`. `node pruebas/g98.test.mjs` ejecuta regresiones locales. `node pruebas/g98_ensayo.mjs` ejecuta el runner completo contra loopback y valida `resultado.json` contra la emulación del registro QA. Salida esperada exacta:

```text
panel_ok APROBADO OFICIAL
sin_panel RECHAZADO OFICIAL
orden_incorrecto RECHAZADO OFICIAL
panel_sin_mixtas BLOQUEADO NO_OFICIAL
error5xx BLOQUEADO NO_OFICIAL
sin_respuesta NO_CONCLUYENTE NO_OFICIAL
G98 ensayo 6/6
```

En TEST, solo el lanzador externo crea `Resultados/RUN-G98-V1-<timestamp>/contexto_operacion.json` y llama `node g98.mjs --operacion evaluar --version 1 --intento 1 --run-id ... --autorizacion ... --contexto ...` con autorización particular. V2 requiere `reevaluar` y decisión explícita. El runner carga `.env.qa` solo en esa ejecución. Un único informe oficial, `resultado.json` y reportes Newman reales quedan bajo el RUN creado por el lanzador.
