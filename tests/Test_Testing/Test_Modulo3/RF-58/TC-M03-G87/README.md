# TC-M03-G87 — RF-58 Monitoreo Ambiental en Tiempo Real

La fuente de los criterios es la fila `TC-M03-G87` de `Casos_Prueba(Modulo3 Agrupado).csv`. El flujo comprueba:

| Caso | Oráculo de la matriz | Cobertura |
| --- | --- | --- |
| TC-M03-168 | Tras tres lecturas `LECTURA_VALIDA` y una posterior `FUERA_DE_RANGO`, HTTP 200 y `ultimo_valor`, `ultima_unidad` y `ultimo_timestamp_captura` de la última válida. | API (Newman) |
| TC-M03-177 | El Productor conserva la última lectura válida (25) como referencia operativa; la anomalía `FUERA_DE_RANGO` permanece visible mediante ROJO/ícono. | API + UI (Newman y Cypress) |
| TC-M03-178 | `ERROR_CALIBRACION` no es valor ni alerta operativa del Productor y no expone sus datos técnicos; el Ingeniero identifica el error y el detalle para reconocer que requiere calibración. El sensor sigue visible. | API + UI (Newman y Cypress) |

## Estructura vigente

- `g87.mjs`: único ejecutor canónico.
- `G87.postman_collection.json`: única colección Newman vigente.
- `g87.cy.js` y `g87.cypress.config.cjs`: spec y configuración Cypress vigentes.
- `lib/g87_preparacion.mjs`, `lib/g87_seguridad.mjs`, `lib/g87_cierre.mjs`, `lib/g87_cypress_runner.mjs`, `lib/g87_cypress_worker.mjs` y `lib/g87_informe.mjs`: auxiliares del ejecutor.
- `pruebas/`: cuatro suites locales; `Resultados/`: destino de V1, inicialmente vacío.

## Uso

Desde esta carpeta, `node g87.mjs --comprobar` hace comprobaciones locales sin red ni RUN. La ejecución en TEST corresponde exclusivamente al lanzador externo con autorización particular. La invocación heredada `node g87.mjs --autorizacion <ref> [--tipo reintento]` permanece para compatibilidad del ejecutor, con V1 fija. La recuperación directa con `--recuperar` está bloqueada; requiere el contrato del lanzador y permiso propio. Ningún comando de TEST se ejecuta durante la preparación local.

Para preparar una corrección documental sin consultar TEST: `node g87.mjs --regenerar-informe RUN-G87-V1-20261023-145303 --salida _paquete_responsables/TC-M03-G87_resultado.md`. La salida debe ser un Markdown nuevo en la raíz de G87 o en `_paquete_responsables/`; el comando lee las evidencias del RUN, conserva el informe oficial y no escribe en `Resultados/` ni `EvaluacionVn/`. El borrador registra el hash del informe vigente, conserva la trazabilidad de la primera regeneración y toma los metadatos locales del informe histórico, sin consultar Git. Los enlaces relativos de evidencia están preparados para la instalación dentro del RUN.

## Contrato propuesto sigab-qa-ejecutor/1

node g87.mjs --capacidades imprime JSON local, sin red ni autorización: operaciones evaluar, reintentar, reevaluar, recuperar, versiones 1..n. El paquete _paquete_orquestacion/ propone la extensión del lanzador protegido; no está instalada.

Tras instalarse, el lanzador reserva y registra el RUN y escribe contexto_operacion.json antes de invocar:

node g87.mjs --autorizacion <ref> --operacion <evaluar|reintentar|reevaluar|recuperar> --version <n> --intento <k> --run-id <RUN> --contexto <ruta-absoluta> [--run-objetivo <RUN>].

El ejecutor valida argumentos, contexto, grupo, casos y ruta antes de leer credenciales o acceder a TEST. V1 usa Resultados/; V2+ usa EvaluacionV<n>/Resultados/. Recuperación escribe una evidencia aparte dentro del RUN objetivo y no reemplaza resultado.json ni el informe. La utilidad neutra lib/contrato_ejecutor.mjs implementa la validación local para poder copiarla a otro grupo en una orden futura.

Las invocaciones heredadas siguen disponibles para compatibilidad local del ejecutor. Toda operación remota requiere lanzador y autorización específica. El registro persistente, las referencias consumidas y las versiones los administra únicamente el lanzador.

Dependencias de datos a verificar antes de cualquier escritura autorizada: S1, sensor 552, dispositivo 357 en infraestructura 349, especie 126, umbral 70 de 15–30 °C y calibración 68; S2, sensor 77, dispositivo 266, con asociación original al área 328 y sin calibración. El ejecutor comprueba por API las relaciones, el umbral activo, el rango físico, las asociaciones y el cupo; estos IDs son referencias de preparación, no resultados confirmados en esta fase. Si S1 no cumple sus precondiciones, 168 y 177 se bloquean sin impedir la comprobación independiente de 178 cuando S2 sí cumple las suyas.

Suites locales, sin TEST ni red, ejecutadas individualmente desde esta carpeta:

```powershell
node pruebas/validar_flujo_g87.mjs
node pruebas/g87_orden013.test.mjs
node pruebas/validar_orden_g87_005.mjs
node pruebas/validar_orden_g87_007.mjs
node pruebas/contrato_g87.test.mjs
```

## Evidencia de una evaluación autorizada

- V1 por defecto o reintento V1: `Resultados/RUN-G87-V1-<timestamp>/TC-M03-G87_resultado.md`.
- V2 únicamente por decisión expresa de reevaluación: `EvaluacionV2/Resultados/RUN-G87-V2-<timestamp>/TC-M03-G87_reevaluacion_V2.md`.
- Cada RUN guarda `resultado.json`, los reportes Newman JSON/HTML realmente generados en `newman/` y las capturas Cypress reales, si existen, en `cypress/`. Hay un solo Markdown oficial dentro del RUN, sin copia en la raíz de `Resultados/` ni `informe.md`.

El historial de intentos descartados se conserva en la carpeta de coordinación QA.
