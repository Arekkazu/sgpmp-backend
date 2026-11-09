# TC-M06-G39 — RF-86 v2.0

Preparación local de TC-M06-016 y TC-M06-017, solo API. El ejecutor canónico es `g39.mjs`; la colección vigente es `G39.postman_collection.json`. No hay spec Cypress porque la matriz exige únicamente API.

## Oráculos conservados

- TC-M06-016: el intento manual de `CONSUMO_INVENTARIO` devuelve 422 `ORIGEN_RESERVADO_M05` y no crea costo ni línea; `MANO_OBRA_PROPIA` crea una línea `MANO_OBRA_PROPIA/UNICO` conforme a RF-109; `COMPRA_PROVEEDOR` y `SERVICIO_TERCERO` crean costos sin línea. La integración asíncrona M05→M06 no forma parte del caso.
- TC-M06-017: baja por venta y baja por muerte de bovinos distintos. Cada una crea exactamente una línea `BAJA_ACTIVO` por el valor en libros truncado a dos decimales, con sentido `UNICO` o `PERDIDA` y cuentas de RF-109. La venta no crea una línea adicional de ingreso.

El contrato `pruebas/contrato_g39.json` indica las rutas y las citas de código para los campos consumidos. La selección exige tres bovinos individuales ACTIVO reconocidos, período ABIERTO, precio vigente y valor en libros positivo. El costo de 016 usa un activo a valor razonable. Se leen permisos de ambos actores, catálogo, detalles, fichas, matriz, costos y líneas antes de la primera escritura. Un par contable faltante bloquea únicamente el caso afectado.

| Evidencia de contrato | Fuente leída | Uso en G39 |
| --- | --- | --- |
| Catálogo de 16 activos, cinco especies; permisos, configuración, líneas y procesar | `TC-M06-G37/Resultados/RUN-G37-V1-20261108-233956/resultado.json` y `TC-M06-G38/Resultados/RUN-G38-V1-20261109-025651/resultado.json` | Reproducción local del catálogo y de tipos de línea; HTTP y contraste oficial. |
| Costos 201, 422 y GET | `src/financial_valuation/infrastructure/routers/m06_router.py:267-281`, `src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:82-84,126-127,207-233`, `src/financial_valuation/infrastructure/repositories/costo_repository.py:17-26,99-102` | Forma mínima del registro, consulta y `ORIGEN_RESERVADO_M05`. |
| Baja y valor en libros | `src/biological_assets/infrastructure/routers/activo_biologico_router.py:1223-1261`, `src/biological_assets/infrastructure/schema/activo_biologico_schema.py:325-339`, `src/financial_valuation/application/use_cases/valoracion/procesar_eventos_m02_use_case.py:129-160` | `id_eventos` en raíz; BAJA_ACTIVO vinculada al evento y valor truncado. |

La matriz original consultada fue `tests/Test_Testing/Test_Modulo6/Casos_Prueba(Modulo6Agrup).csv`, fila `TC-M06-G39`, reformulada el 2026-11-09. No se encontró un archivo RF-86 independiente dentro de las rutas de lectura del repositorio; el texto de CA-19 y CA-20 y la tabla de tipo_hecho se tomaron de esa fila y de la orden vigente.

## Ejecución

`node g39.mjs --comprobar` solo valida archivos locales. La ejecución TEST corresponde exclusivamente al lanzador externo autorizado; `g39.mjs` exige contexto de RUN y preflight. Los ensayos `principal()` usan loopback y `os.tmpdir()`. Límite: 150 solicitudes, 1800 s. Newman corre en un proceso hijo con `process.execPath`. Los reportes e informe solo se escriben dentro del RUN correspondiente.

## Inventario

Vigentes: `g39.mjs`, `lib/g39_core.mjs`, `G39.postman_collection.json`, `pruebas/contrato_g39.json`, `pruebas/newman_hijo.mjs`, `pruebas/registro_qa.mjs` y pruebas locales. No hay duplicados ni legado en G39. G37 y G38 son referencias de solo lectura.

## Observación de configuración

La matriz conocida de TEST usa `158405` como débito de `MANO_OBRA_PROPIA/UNICO` con política `GASTO`. El oráculo compara con la matriz leída durante el RUN; el informe deja la observación para decisión de QA.
