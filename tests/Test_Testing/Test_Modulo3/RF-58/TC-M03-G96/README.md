# TC-M03-G96 — TC-M03-187

**Oráculo literal (matriz, RF-58/CU04):** «El estado de conectividad presentado por el monitoreo utiliza exclusivamente uno de los valores definidos por RF-58 (ONLINE, OFFLINE o SIN_SEÑAL); no se exponen valores diferentes al catálogo establecido.» La matriz pide las tres condiciones: conectado, desconectado y sin señal. Fuente: `Casos_Prueba(Modulo3 Agrupado).csv`, fila G96 (Windows-1252). RF-58: `Especificacion-Requerimientos-Modulo3.md:4923,5160`. RF-60: línea 6336; no define la correspondencia entre sus cinco estados internos y los tres valores de RF-58.

Una sola comprobación API `API-187-01`; no hay UI. Se leen respuestas públicas del Productor con Newman; no se crean sensores ni lecturas, ni se usa SQL. Un valor con significado ajeno al catálogo, null o campo ausente en una respuesta 200 con eco basta para RECHAZADO. APROBADO exige ver los tres valores y completar la paginación de cada unidad recorrida. Si faltan condiciones, BLOQUEADO por datos; 5xx BLOQUEADO; sin respuesta NO_CONCLUYENTE. Variantes ortográficas como `SIN_SENAL` se reconocen por significado y quedan anotadas con el texto exacto.

Orden de unidades: 1, 268, 337 (historial G93 con INACTIVO/ACTIVO), y hasta tres más halladas con un GET acotado de fincas del Productor y hasta dos GET de infraestructuras. No se consulta el dashboard global. Se detiene al hallar un valor fuera del catálogo o después de completar una unidad con los tres valores observados.

## Presupuesto único para la SOL futura

`lib/g96_presupuesto.cjs`: hasta 3 lecturas de descubrimiento, 12 páginas de dashboard (`por_pagina=50`), total 15 GET dentro del RUN, 1 DELETE de cierre y 600 segundos (prevalidación 30 s, login 30 s, descubrimiento 90 s, Newman 390 s y cierre 30 s, con 30 s de margen). Máximo 6 unidades, de ellas 3 adicionales. El informe generado toma estos límites del mismo módulo.

## Contrato del lanzador

`node g96.mjs --capacidades` y `node g96.mjs --comprobar` son locales. `node pruebas/g96.test.mjs` ejecuta regresiones. `node pruebas/g96_ensayo.mjs` inicia una API loopback y ejecuta el runner completo con cinco modos sintéticos; no usa TEST. Salida esperada exacta:

```text
catalogo_ok APROBADO OFICIAL
fuera_catalogo RECHAZADO OFICIAL
cobertura_incompleta BLOQUEADO NO_OFICIAL
error5xx BLOQUEADO NO_OFICIAL
sin_respuesta NO_CONCLUYENTE NO_OFICIAL
G96 ensayo 5/5
```

Para TEST, únicamente el lanzador externo crea `Resultados/RUN-G96-V1-<timestamp>/contexto_operacion.json` y llama `node g96.mjs --operacion evaluar --version 1 --intento 1 --run-id ... --autorizacion ... --contexto ...` con autorización particular. V2 requiere `reevaluar` y decisión explícita. El runner carga `.env.qa` solo al ejecutar TEST; `--comprobar` y el ensayo no lo leen.

La sesión del Productor se inicia antes del RUN: puede registrar último acceso, auditoría, notificaciones y cierre de sesiones previas. Las lecturas del dashboard dentro del RUN pueden provocar correo RF-58 E7 por sensores GRIS sin umbral no desactualizados. El cierre verifica bitácora de solo GET con eco y DELETE 200; no presume reversión de efectos externos. El código backend de referencia `origin/test` es `5b46ca00a0ba92774f8e3d4b9eeaeec169344f17`; el oráculo se juzga sobre TEST desplegado.
