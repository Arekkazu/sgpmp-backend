# TC-M06-G42 — RF-87 v1.1

## Preparación V2, ronda 3 — ORD-G42-020

Se leyó la fila TC-M06-G42 de `Casos_Prueba(Modulo6Agrup).csv` (casos 021–023, RF-87, CA-4, CA-9 y CA-10), `AGENTS.md`, los archivos activos de este grupo y el RUN V2 `RUN-G42-V2-20261113-010212` en solo lectura. Del backend se consultaron realmente mediante `git show origin/test` `src/financial_valuation/application/use_cases/configuracion/guardar_asignacion_cuenta_use_case.py`, `src/financial_valuation/infrastructure/routers/m06_router.py` y `src/financial_valuation/infrastructure/repositories/configuracion_contable_repository.py`. No se modificó Git ni código de producto. El grupo conserva un ejecutor, una colección Newman y ninguna prueba Cypress porque estos casos son API; no se retiraron archivos ni pruebas.

La línea preexistente 1431 del período 241 era DEPRECIACION_ACTIVO_COSTO/UNICO, especie 39, sin subtipo. En el RUN previo quedó PENDIENTE_CUENTA pese a estar cubierta por una asignación genérica: el ejecutor omitía el POST. El caso de uso solo llama a `resolver_pendientes` al guardar una asignación por POST. El router ofrece POST y DELETE para la matriz; POST sobre una combinación específica existente desactiva esa asignación e inserta otra. En un RUN autorizado, el ejecutor guardará una asignación específica para la especie pendiente con exactamente las cuentas de la cobertura genérica. Si la cobertura ya es específica, la guardará de nuevo con las mismas cuentas. Registrará el nuevo ID para verificar rollback, exigirá `lineas_resueltas >= 1` y leerá la prevalidación del 241 antes de cualquier otra escritura de preparación del 021. Una respuesta sin resolución o una prevalidación aún bloqueada termina NO_CONCLUYENTE con diagnóstico y DELETE. Los oráculos de los tres casos se conservan literalmente.

La prueba local reproduce una línea pendiente con cobertura genérica que no se resuelve solo por existir esa cobertura. También prueba cobertura específica y respuesta `lineas_resueltas: 0`; conserva el resto de escenarios. La ronda 3 requiere aprobación expresa del responsable QA antes de despachar el ejecutor a TEST. En esta fase no se consultó TEST ni se creó RUN en el grupo; el ejemplo se genera únicamente en `%TEMP%/g42-verificar-ejemplo`.

## Preparaci?n V2 ? ORD-G42-018

Fuentes le?das en esta ronda: fila 385 de `tests/Test_Testing/Test_Modulo6/Casos_Prueba(Modulo6Agrup).csv`; archivos activos de este grupo; `EvaluacionV2/Resultados/RUN-G42-V2-20261113-004229/resultado.json`, `preflight.json` e informe. No se abrieron rutas de c?digo backend ni un `AGENTS.md` f?sico en esta carpeta; se aplicaron las instrucciones AGENTS.md suministradas en la orden.

El ejecutor can?nico `g42.mjs` mantiene los tres casos TC-M06-021, 022 y 023 y la colecci?n Newman vigente. En esta ronda solo se prepararon archivos locales; no se consult? TEST ni se cre? un RUN. El per?odo 219 de NIT-B figura CERRADO con cierre 43 COMPLETADO en el RUN anterior y ya no es requisito ni se consulta. El 022 usa los comprobantes de 241 (NIT-D, bovino) y 220 (NIT-C, caprino y equino), con descargas `descargas/comprobantes-241.csv` y `descargas/comprobantes-220.csv`. Se conserva el or?culo de la fila 385 de `Casos_Prueba(Modulo6Agrup).csv`.

El preflight registra estado, ?ltimo cierre y prevalidaci?n de ambos per?odos; recorre los dos antes de abortar y re?ne los motivos en `diagnostico_preflight.motivos`. Para la l?nea 1431 `DEPRECIACION_ACTIVO_COSTO/UNICO`, especie 39, solo acepta un par de cuentas de otra especie o asignaci?n gen?rica del mismo tipo, sentido y subtipo. Si no existe referencia, termina NO_CONCLUYENTE sin escrituras del escenario. Tras el POST a matriz comprueba que `puede_cerrar=true` antes del cierre 241.

Hay tres cierres previstos: 241, 220 y diciembre de NIT-C. El escenario conforme usa 156 solicitudes locales simuladas; con el pendiente resoluble usa 157. El l?mite vigente es 300 solicitudes y 1800 segundos. Si falla el cierre 241, el 023 puede continuar desde 220; el 022 queda NO_CONCLUYENTE por faltar el comprobante del 241. El 021 solo se rechaza con evidencia de un RUN TEST autorizado. Newman, DELETE 200 y lecturas poscierre son necesarios para la oficialidad.

Validaci?n local: `node --check g42.mjs`, `node g42.mjs --comprobar`, `node pruebas/g42_local.test.mjs`, `node pruebas/g42_escenarios.test.mjs` y `pruebas/g42_dto.test.py`. Con `G42_EJEMPLO=SI`, el escenario conforme deja el RUN simulado y `capacidades.json` en `%TEMP%/g42-verificar-ejemplo`. Ese RUN es un fixture local, no evidencia TEST. Si el proceso hijo falla por EPERM en un sandbox, se documenta y no se atribuye ejecuci?n.

Las secciones siguientes describen la automatización V1 histórica. Sus referencias al período 8 y al bovino 945 no son instrucciones vigentes para V2.

Automatización API para TC-M06-021, TC-M06-022 y TC-M06-023. El oráculo se conserva de la fila `TC-M06-G42` de `Casos_Prueba(Modulo6Agrup).csv` y de `ORD-G42-001`. La consulta del código sirve para construir cuerpos y leer respuestas; no cambia los resultados esperados.

## Inventario activo

| Archivo | Función |
| --- | --- |
| `g42.mjs` | Ejecutor canónico, barreras de autorización, flujo en serie, evidencias, informe y rollback. |
| `lib/g42_core.mjs` | Comparaciones decimales y oráculos 021–023. |
| `lib/contrato.mjs`, `pruebas/contrato_g42.json` | Contrato de respuestas, lecturas instrumentadas y citas de código. |
| `G42.postman_collection.json`, `pruebas/newman_hijo.mjs` | Colección vigente y Newman hijo con reportes saneados. |
| `pruebas/registro_qa.mjs` | Validador local del registro QA externo. |
| `pruebas/g42_local.test.mjs`, `pruebas/g42_escenarios.test.mjs`, `pruebas/g42_dto.test.py` | Decisiones, escenarios con Newman real en loopback y DTO Pydantic reales. |
| `preparacion_ORD-G42-001.md` | Informe local de preparación, sin RUN. |

G42 estaba vacía. Se revisaron en solo lectura G41 (`g41.mjs`, librería, contrato, colección, pruebas, README y dependencias); G38 (`g38.mjs`, DTO y ruta M02); G39 (`g39.mjs`, origen y factura RF-90). No hay duplicados ni legado en G42. No hay Cypress: los tres casos son solo API.

## Validación local

Desde esta carpeta: `node --check g42.mjs`; `node g42.mjs --comprobar`; `node pruebas/g42_local.test.mjs`; `node pruebas/g42_escenarios.test.mjs`. Desde la raíz del repositorio: `.venv\Scripts\python.exe tests\Test_Testing\Test_Modulo6\RF-87\TC-M06-G42\pruebas\g42_dto.test.py`.

El ejecutor exige contexto del lanzador en `Resultados/RUN-G42-V1-.../` o `EvaluacionVN/Resultados/RUN-G42-VN-.../`, `QA_AUTORIZADO=SI`, host TEST exacto, credenciales suministradas externamente y Newman instalado. La fase `preparar` solo ejecuta los comandos locales anteriores. Los ensayos integrales usan únicamente loopback y borran sus RUN temporales fuera de G42.

Los tres períodos se prevalidan antes de escribir. El 8 admite lineas sin trazabilidad solo si sus ids ya estaban en la linea base del periodo 8; se registran ambas prevalidaciones, las lineas excluidas y las variaciones omitidas. Una linea creada por el RUN excluida falla 021. Si falla el cierre 8, 021 se rechaza; G32 solo se reutiliza con HTTP 500, paso 3 y auditoria coincidente. Los otros fallos generan incidencia G42. Los casos 022/023 continuan. Si falla 219, 023 continúa desde 220. El informe oficial se genera únicamente dentro del RUN y concuerda con `resultado.json`.

El runner usa la fecha de Bogota y comprueba antes de escribir que caiga dentro de 219 y 220 y antes de diciembre de 2026. Costos, facturas y precios usan esa fecha. El PDF se valida en memoria por HTTP, Content-Type, tamano, SHA-256 y cabecera %PDF; solo se guarda el CSV saneado. El límite es 260 solicitudes y 1800 segundos; los cierres no se reintentan. Newman, un DELETE 200 y las lecturas poscierre son necesarios para que el resultado sea oficial.

## Riesgos de producto por verificar en TEST

Para 021, la preparación lee `GET /finanzas/activos/{id}` de cada bovino ACTIVO a valor razonable de la finca de NIT-A (período 8), en orden de id. El contrato declara `activo.id_dispositivo_iot: integer|null` según `src/financial_valuation/infrastructure/adapters/activo_financiero_m02_adapter.py:22-62`. Se elige el primero sin IoT que tenga ficha y métrica PESO/kg aptas para ambos pesajes y precio aplicado coincidente con la simulación. La elección y los descartes quedan en `resultado.json` y en el informe del RUN. Sin candidato, los casos quedan NO_CONCLUYENTE con `SIN_BOVINO_SIN_IOT` y no hay escrituras. El rollback compara los eventos del bovino elegido. La línea TB del RUN sigue sin poder excluirse.

Observación RF-91 sin veredicto: un activo con dispositivo IoT y pesaje manual deja la línea TB en `PENDIENTE_TRAZABILIDAD` si no hay telemetría apta en las 24 h previas. Esta preparación no crea telemetría.

- `src/financial_valuation/domain/services/consolidacion.py:125-140` y `src/financial_valuation/application/services/reportes.py:29-40` acumulan `costos_mantenimiento` sin desglose por subtipo en la lectura revisada. Clasificación: `DEFECTO_FUNCIONAL_CANDIDATO` para 023; la comprobación pública lee el detalle de RF-93 y sus `componentes`.
- Las variaciones de pérdida pueden almacenar signo negativo mientras las líneas contables presentan magnitud positiva. El oráculo suma importes exactos por tipo y sentido, comparando la magnitud de la pérdida con su línea.
- Los avisos de cierre y de precio pueden persistir fuera del sandbox. El informe registra únicamente los avisos observados; su eliminación no se declara como parte del rollback.

## Contrato ORD-G42-007

Las respuestas JSON exitosas se validan por presencia y tipo de cada campo declarado. Los campos adicionales se anotan en `campos_extra_observados` de `resultado.json`; el RUN los tolera y el ensayo local detecta cualquier lectura de ellos por el Proxy. El fixture incluye columnas reales de los SELECT y ejecuta los escenarios con y sin dos campos desconocidos inyectados en cada objeto de respuesta. Las sustituciones y citas constan en `preparacion_ORD-G42-007.md`.
