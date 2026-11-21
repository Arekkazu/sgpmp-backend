# Preparaci?n ORD-G42-007 ? TC-M06-G42

Estado: PREPARADO LOCALMENTE. Sin TEST, sin RUN nuevo y sin veredicto de producto. Casos TC-M06-021/022/023; RF-87 v1.1. Se conserv? el or?culo de la fila TC-M06-G42 de `tests/Test_Testing/Test_Modulo6/Casos_Prueba(Modulo6Agrup).csv`.

## Cambios y sustituciones

- `lib/contrato.mjs:26-63`: validaci?n anticipada de presencia y tipo de campos declarados, incluyendo objetos y listas; registro de rutas de campos extra sin sus valores. `LECTURA_FUERA_CONTRATO` solo en ensayo local; TEST tolera campos extra. Las respuestas JSON exitosas GET/POST/DELETE se comprueban antes de usarse; login comprueba token.
- `g42.mjs:30,32,57`: `enviar()` y `login()` registran `campos_extra_observados` en `resultado.json`; no se aborta el RUN por extras.
- `g42.mjs:42`: `registrarPrecio` reemplaza `return {...base, precio_unitario}` por selecci?n expl?cita de `id_especie`, `categoria`, `fuente`, `id_metrica_produccion` y `precio_unitario`.
- `lib/g42_core.mjs:33`: `evaluar022` reemplaza `key({...l, numero_id_tributaria:nit})` por clave construida expl?citamente de `nit`, `tipo_hecho` e `id_especie`.
- `g42.mjs:62`: la comparaci?n del cierre fallido reemplaza `{http,...cierre8.data}` por campos expl?citos; las l?neas excluidas del cierre se proyectan a `{id_linea,tipo_hecho}` antes de guardarlas.
- `g42.mjs:63`: el resumen de comprobantes reemplaza `[...cB,...cC]` por `cB.concat(cC)` y proyecta cada comprobante a los campos usados.
- `pruebas/g42_escenarios.test.mjs:20-36`: fixture enriquecido con columnas de activos, per?odos, precios, comprobantes, costos, c?lculos, mediciones y variaciones. Se inyectan dos campos desconocidos en cada objeto de cada respuesta JSON, a cualquier profundidad; los 18 escenarios se ejecutan con y sin inyecci?n y mantienen el veredicto esperado. Se agreg? `campos_extra_reales`.
- `pruebas/g42_local.test.mjs:10-11`: comprueba `CAMPO_AUSENTE`, `TIPO_INVALIDO`, tolerancia del RUN, lectura estricta del ensayo y detecci?n de spread sobre una respuesta instrumentada.

## Contrato y fuentes revisadas

`pruebas/contrato_g42.json`: se declararon `unidad_medida`, `evidencia` y `estado` en GET `/finanzas/precios`, con `src/financial_valuation/infrastructure/repositories/precio_repository.py:18-24`, `src/financial_valuation/domain/services/precios.py:23-36` y `src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:30-34`. `id_especie`, `categoria`, `fuente`, `id_metrica_produccion` y `precio_unitario`, le?dos por el ejecutor, ya estaban declarados. `fecha_cierre` se corrigi? a `datetime|null` y `ultimo_cierre` admite `null` por `periodo_repository.py:19-20` y `m06_router.py:295-299`. `id_linea` y `tipo_evidencia` admiten `null` por el LEFT JOIN de `valoracion_repository.py:309-322`.

Tambi?n se consultaron en solo lectura los SELECT de `valoracion_repository.py:249-329`, `costo_repository.py:18-24`, `asiento_repository.py:18-21`, `periodo_repository.py:118-123`, `auditoria_financiera_repository.py:66-76`, el dataclass `contabilidad.py:16-25` y el retorno de cierre en `ejecutar_cierre_periodo_use_case.py:286-302`. No se consult? TEST. La revisi?n de `g42.mjs` y `lib/` no encontr? lecturas necesarias de campos sin declarar; las enumeraciones restantes operan sobre estructuras locales o sobre el detalle flexible RF-93, que se valida aparte con el or?culo del caso.

## Validaci?n local

- `node --check g42.mjs` y `node --check pruebas/g42_escenarios.test.mjs`: OK.
- `node g42.mjs --comprobar`: OK; una colecci?n Newman vigente y rutas presentes.
- `node pruebas/g42_local.test.mjs`: 37/37 OK.
- `node pruebas/g42_escenarios.test.mjs`: 18 escenarios ? 2 variantes OK (36/36); Newman real ?nicamente en loopback y RUN temporales fuera del grupo, eliminados al finalizar.
- `.venv/Scripts/python.exe pruebas/g42_dto.test.py`: 1/1 OK.

## SHA-256

| Archivo | SHA-256 |
| --- | --- |
| `g42.mjs` | `3c7652351547eddec1f009adb62d6bbe457979456cb59343d665d89addb20191` |
| `lib/g42_core.mjs` | `3c97a4becead4b70d49dda1f554123633d0c990aa677d0db5e05a6634bb6580f` |
| `lib/contrato.mjs` | `4bf95ca1a5d767f915fa714ef72829c3515c448358579ae75f18af6ad2ccb3f3` |
| `pruebas/contrato_g42.json` | `0412019f12954d77ef8beb30b47a96217790abf62a44ed0d4aeb0421705c976d` |
| `pruebas/g42_local.test.mjs` | `a68226a8d9bb2b7e79f5b21deedda6278d5e854a388ab7073351fd125b34d552` |
| `pruebas/g42_escenarios.test.mjs` | `a843f5db4175bcca7f857c52374ec1de7631634e6c18ca3ab5e490ce735e2b55` |
| `README.md` | `ab78aae3f1bfb127318108b5d1eddae55f7d4beb9be23844d43ad49fa1f724ae` |

## Riesgo y siguiente acci?n

El comportamiento en TEST y los veredictos de producto siguen sin comprobarse. Un nuevo intento V1 exige autorizaci?n particular del lanzador externo, acceso controlado a TEST, revisi?n de efectos remotos y evidencia real de rollback. No se modificaron los RUN 195322 ni 200920 ni `registro_qa.mjs`.
