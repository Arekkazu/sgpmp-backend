# TC-M09-G141 — Resultado

**TC-M09-287 y TC-M09-G141: BLOQUEADO / NO VERIFICABLE.** RUN_ID: run-20261007-102458. Ambiente: TEST; prueba local: NO.

## Decisión

El segundo cálculo VISION no se ejecutó. Faltan dos precondiciones comprobadas: TEST no publica una operación VISION y el RUN disponible de TC-M09-275 no creó una L1 verificable. Por eso no se alcanzó el oráculo de reemplazo de vigencia.

## Entorno y contrato

Newman consultó `GET https://api.inmero.co/back-sigab-test/openapi.json` y terminó correctamente; un GET Python obtuvo HTTP 200. Pytest confirmó que el OpenAPI permaneció estable en la lectura posterior. Se examinaron 210 rutas, 77 POST y 305 esquemas. Ninguna operación declara VISION, `modo_calibracion` o `ventana_observacion`.

El `POST /configuracion/sensores/{id_sensor}/calibrar` existente corresponde a **SENSOR, Flujo D**. Su body no describe una calibración VISION con área y ventana; usarlo cambiaría el caso bajo prueba. Método/ruta/schema/security/respuestas VISION: **no publicados**.

Hash SHA-256 del OpenAPI: `3c5399809538cc403904725612dc20072bbc2c964eb10c8ad7f802731d21eed8`. Rama: `qa/juan-esteban-rf24-v2`; HEAD: `30ddd72144102a60af006b265a20cb18c1c72c85`; origin/test: `30ddd72144102a60af006b265a20cb18c1c72c85`; divergencia: `0	0`. Estado Git previo completo en `evidencia.json`.

## Precondición L1

La fuente preferida es TC-M09-275. Se revisaron 1 RUN(s) con evidencia de ese caso. El RUN `run-20261007-100743` quedó `BLOQUEADO / NO VERIFICABLE` y no ejecutó un POST VISION. No hay en esa fuente una L1 creada y vigente que pueda usarse aquí.

Esto **no prueba que en la BD TEST no exista ninguna línea base**: no se consultó la persistencia porque la operación VISION ya faltaba. Tampoco se sustituyó silenciosamente TC-275 por otra supuesta L1. A1, especie, identificador de L1 y su vigencia PRE quedan **no verificados**. La matriz pide revaluar primero TC-275 cuando VISION esté disponible.

## Ventana posterior W2

La prueba requería una ventana posterior a la de L1, cerrada, con al menos N observaciones VISION aptas de una cámara activa asociada al área. Sin contrato VISION ni L1 validada, no se descubrió N, no se creó W2 y no se contaron observaciones. Inicio/fin, IDs y cantidad apta: **no evaluados**, no cero medido.

## Segundo disparo

El actor previsto era el Ingeniero de Campo. Como no había ruta VISION ni precondiciones de L1/W2, no se inició sesión para ejecutar este caso y no se envió POST. HTTP esperado cuando el escenario sea válido: cualquier **2xx**. HTTP obtenido ahora: **no observable**. No se hicieron escrituras de setup ni SQL.

## Reemplazo de vigencia

El oráculo principal sería observar **L1 vigente antes** y, tras el cálculo W2, **L2/W2 vigente y L1 ya no vigente** para el mismo par área/especie. Aquí no existe snapshot PRE/POST de una ejecución VISION, así que L1 sigue vigente: **no verificable**; L2 vigente: **no verificable**; correlación con W2: **no verificable**.

RF-24 no exige que L1 permanezca físicamente como historial ni que L2 tenga un ID distinto si la implementación reemplaza in-place. Esos aspectos no se convierten en fallos de este RUN.

## Incidencia

**INCIDENCIA REQUERIDA: NO, con la evidencia disponible.** El caso está bloqueado antes del segundo cálculo y no hay confirmación de que VISION/M03 ya debiera estar entregado en TEST. No se observó un reemplazo incorrecto que justifique un bug de Desarrollo, AIoT o DBA.

Grupo: TC-M09-G141. Caso: TC-M09-287. Resultado: BLOQUEADO / NO VERIFICABLE. Esperado: operación VISION, L1 vigente de TC-275, W2 posterior con observaciones suficientes y segundo cálculo 2xx que deja L2 vigente. Obtenido: operación VISION no publicada y TC-275 previo bloqueado sin L1 publicada. Causa de una eventual incidencia de entrega: por determinar hasta conocer el hito formal. Grupo responsable, Type, Severity y Priority: no se asignan a una incidencia no abierta. Evidencia: `evidencia.json`, `newman.html`, `pytest.xml`.

## Conclusión

TC-M09-287 y G141 quedan **BLOQUEADOS / NO VERIFICABLES**. Primero debe existir VISION en TEST y revaluarse TC-M09-275 para obtener una L1 vigente trazable; después podrán construirse W2 y comprobarse el reemplazo de vigencia. No se evaluó conservación histórica de L1.
