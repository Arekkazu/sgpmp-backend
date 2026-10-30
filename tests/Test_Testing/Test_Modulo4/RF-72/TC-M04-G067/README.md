# TC-M04-G067 — preparación local

RF-72, casos TC-M04-205 a TC-M04-209, solo API. Fuente original: `Actualizacion_Matriz_RF69_RF72/Casos_Prueba(Mod4Agrupfinal)_actualizada.csv`, fila `TC-M04-G067` (Windows-1252, `;`). Se conservan los oráculos: 205 exige cuatro HTTP 422 de estado no válido; 206 exige rechazo del estado ausente indicando el campo y sin persistencia; 207 y 208 exigen dos HTTP 422 de diagnóstico obligatorio cada uno; 209 exige cuatro HTTP 201 en resultados distintos. Decisión QA de 2026-10-29: 206 con HTTP 400 completo puede aprobarse con observación porque RF-72 no fija código para la ausencia. No se comprueba conservación de diagnósticos en 209.

Referencias RF-72: dominio 4070–4072; obligatoriedad 4074–4078; entradas 4162–4163; validación de fase 5 4199–4200; E3 4248–4252; E4 4254–4258; CA-3 4363; CA-4 4365. RFC-009 exige inferencias de modelo INDIVIDUAL.

## Ejecución preparada

`node g067.mjs --capacidades`, `node g067.mjs --comprobar`, `node pruebas/g067_env.test.mjs` y `node pruebas/g067_ensayo.mjs` son locales. El ensayo usa exclusivamente un servidor loopback y carpetas temporales. Un RUN real requiere contexto de operación y autorización del lanzador externo; este grupo no lo ejecuta por sí mismo en la fase preparar.

El ejecutor carga `.env.qa` sin imprimir valores. Requiere los nombres `SIGAB_API_TEST_BASE`, `QA_SANDBOX_SECRET`, `QA_VETERINARIO_EMAIL`, `QA_COMMON_PASSWORD`; `QA_AUTORIZADO=SI` debe venir del proceso. Preflight verifica colección y Newman (30 s) antes de cualquier petición. Login veterinario: 120 s; demás peticiones: 30 s; duración máxima: 900 s. Presupuesto exacto máximo: **260 solicitudes** = 1 login + 4 páginas de activos + 128 páginas de historial de descubrimiento + 8 versiones + 1 catálogo + 26 POST (13 originales y hasta 13 reemplazos) + 39 páginas de historial de verificación + 13 auditorías + 1 DELETE + 39 páginas de historial poscierre.

La semilla externa prevista contiene 14 resultados libres de `MODELO_ESPECIES_MEDIANAS` versión 43 para el activo 885, especie 220. Se necesitan cuatro resultados distintos para 209, uno libre compartido para rechazos, uno reservado para `correcto` y reemplazos si un intento persiste o el dato no es apto. Los diagnósticos usan patologías activas 8–14; se excluye 7. Orden: 209, 207, 208, 206, 205; `correcto` se envía al final. Si un rechazo persiste, se reserva ese resultado y se usa otro libre para que el siguiente caso no falle por duplicado. Nunca se modifica la semilla.

Los 13 POST evaluados se ejecutan en una sola invocación de Newman y una iteración de colección, con solicitudes ordenadas y un posible reemplazo de resultado distinto por subcaso. No hay reintentos de la misma petición. El ejecutor usa HTTP, cuerpo y tiempo reales de Newman, con eco de `X-Test-Run-Id`. Login, descubrimiento, historial, auditoría, DELETE y lecturas poscierre usan fetch. Se guardan un único `newman-G067.json` y `newman-G067.html` saneados en `newman/`, junto con `resultado.json`, `preflight.json` y un único informe Markdown dentro del RUN. El presupuesto máximo sigue siendo 260 solicitudes. La ausencia de respuesta exige conciliación; la aceptación indebida exige comprobar historial y auditoría. El DELETE se intenta siempre después de iniciar el RUN, y el rollback se declara verificado solo tras lecturas públicas poscierre.

## Efectos para una SOL futura

Login; lecturas de descubrimiento; cuatro retroalimentaciones válidas y su auditoría; nueve intentos esperados como rechazo sin persistencia; posibles registros indebidos, incluso `correcto`, revertidos por DELETE; lecturas poscierre que pueden crear `HISTORIAL_CONSULTADO` fuera del sandbox. Sin correos ni archivos remotos; la semilla no se altera. TEST y el RUN requieren autorización humana particular.

## Lectura de código local

Se consultó `origin/test` en `src/prediction/infrastructure/dto/registrar_retroalimentacion_dto.py`, `src/prediction/domain/entities/retroalimentacion_clinica.py`, `src/prediction/application/use_cases/retroalimentacion/registrar_retroalimentacion_use_case.py`, `src/prediction/infrastructure/routers/retroalimentacion_clinica_router.py`, `src/shared/error_handlers.py`, `src/shared/errors.py` y `src/shared/base_dto.py`. Las divergencias previsibles de 205 son candidatas, no veredictos: solo un RUN autorizado en TEST puede confirmar un RECHAZADO.
