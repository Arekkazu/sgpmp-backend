# ORD-G42-009 — preparación local

Estado: corrección QA preparada localmente. No se consultó TEST, no se creó RUN y no hay veredicto nuevo del producto. Los RUN anteriores permanecen intactos.

## Oráculo y alcance consultados

Se leyó la fila `TC-M06-G42` de `tests/Test_Testing/Test_Modulo6/Casos_Prueba(Modulo6Agrup).csv` y RF-87 v1.1, CA-4, CA-9 y CA-10 en `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo6.md:1489-1712`. Se conservan los oráculos de TC-M06-021, 022 y 023: asiento por los cuatro tipos y ejecutor/timestamp, comprobante por titular/tipo/especie con CSV/PDF e inmutabilidad, y costos de mantenimiento como gasto sin aumentar el valor razonable.

Inventario local revisado: `g42.mjs` es el único ejecutor; `G42.postman_collection.json` es la colección Newman vigente; `lib/contrato.mjs` y `lib/g42_core.mjs` son módulos activos; `pruebas/contrato_g42.json`, `g42_local.test.mjs`, `g42_escenarios.test.mjs`, `g42_dto.test.py`, `newman_hijo.mjs` y `registro_qa.mjs` son apoyo vigente; `README.md` describe su uso. No hay Cypress requerido por esta fila API. No se movieron duplicados ni evidencias históricas.

## Corrección

- `revisar()` comprueba solo la forma superior de listas y objetos. El Proxy valida tipos y presencia al leer un campo declarado; los elementos de una lista se envuelven al acceder a su índice. Los campos extra se registran como observación al envolver un objeto usado, sin recorrer sus hijos ajenos. Un campo obligatorio leído y ausente, o un tipo inválido leído, sigue fallando explícitamente. Los campos marcados `?` admiten ausencia según el contrato existente.
- En `SIN_ESCRITURAS`, rollback comprueba `DELETE 200` y relectura `GET /finanzas/periodos` con HTTP 200 y cuerpo de lista, sin instrumentar el contrato. Con escrituras se mantienen las comparaciones poscierre y la validación perezosa.
- `numero_id_tributaria` de períodos admite `null` por la observación del RUN indicado en la orden; esta divergencia frente al `str` de `domain/entities/contabilidad.py:18` queda documentada, no se interpreta como cambio del oráculo. `fecha_cierre` ya admitía `null` según `contabilidad.py:23` y `periodo_repository.py:65`. `ultimo_cierre` puede ser `null` porque `periodo_repository.py:124-130` devuelve `Optional[dict]`; sus campos `fecha_fin` e `id_usuario_ejecutor` pueden estar sin completar en una ejecución en curso o fallida. `id_cierre` admite `null` defensivamente dentro de esa estructura; el caso G42 sigue exigiendo ID y fecha válidos en el cierre exitoso.
- La nulabilidad existente de `depreciacion_acumulada` corresponde al `LEFT JOIN` de `valoracion_repository.py:250-269`; `id_linea` y `tipo_evidencia` de variaciones, al `LEFT JOIN` de `valoracion_repository.py:309-319`. `id_especie` y `subtipo_costo` de líneas figuran `Optional` en `domain/entities/contabilidad.py:65-66,87`. `fecha_vencimiento` e `id_metrica_produccion` de precios figuran `Optional` en `domain/services/precios.py:23-29`. Las columnas de costos consultadas en `costo_repository.py:17-29` no justifican cambiar a nulos los identificadores y montos exigidos de un costo seleccionado. Se agregaron estas citas al contrato donde correspondía.

## Recorridos revisados

En `g42.mjs` y `lib/` se revisaron: `campo()` y `porId()`; `permisosFaltantes()`; `idsPeriodo()` y rollback; `asignarMatriz()`; `vigente()` y filtros de precios; `cerrar()` y el mapeo de prevalidación; `verificarInmutabilidad()`; `resumen21()`; selección de períodos, activos y precios al preparar la línea base; filtros de líneas, variaciones, mediciones, costos, auditoría y notificaciones; `evaluar021/022/023()` y `buscarDesglose()` en `g42_core.mjs`; `sanear()`, `JSON.stringify()` y los registros de observaciones. Los recorridos de listas globales solo usan claves de selección antes de leer datos del registro elegido; los listados por período se consumen como datos de ese período. `sanear()` recibe cuerpos de escritura o error, no las listas GET instrumentadas. `JSON.stringify()` serializa objetos de resultado o cuerpos ya preparados; no inspecciona por sí mismo una lista GET ajena para validar sus campos.

El fixture añade períodos de otro titular con NIT nulo y fechas irregulares, activos ajenos con campos nulos y precios de otra especie con monto de otro tipo. La inyección se limita a los tres listados globales donde esas entidades pueden aparecer; los endpoints acotados por período o activo mantienen su semántica. La prueba `lista ajena irregular no se valida completa` falla si vuelve la validación estricta de todos los elementos. Se agregó el escenario `datos_ajenos_irregulares`.

## Validación local

`node --check` de ejecutor, contrato y escenarios: correcto. `node g42.mjs --comprobar`: correcto; colección de 8 solicitudes y Newman 6.2.2 detectado. `node pruebas/g42_local.test.mjs`: 38/38. `node pruebas/g42_escenarios.test.mjs`: 19 escenarios por dos variantes, 38/38; incluye los 18 originales con y sin inyección, el escenario nuevo y rollback `SIN_ESCRITURAS` verificado en dos escenarios. `g42_dto.test.py`: 1/1. Estas pruebas emplearon exclusivamente loopback temporal; sus salidas no constituyen evidencia de TEST.

SHA-256 de archivos modificados:

| Archivo | SHA-256 |
| --- | --- |
| `g42.mjs` | `d07912522f517c6e269476252267e48602e6d4e57df852f4218b1fc2618ba45b` |
| `lib/contrato.mjs` | `083d322a3e4e1d3f99ca1d3493a4370ec046564991269c742efe86fc356c585a` |
| `pruebas/contrato_g42.json` | `2b203019cbd8db276b2b9478c27eefce5590ffced3d4050fecda98614510116d` |
| `pruebas/g42_local.test.mjs` | `f14f7fe34d0c3a25988d96401f8b1ca121ef2042b46dceb44177c0c2962253ee` |
| `pruebas/g42_escenarios.test.mjs` | `e5e617119e80786b360452cc1dcc953afa83263745db12a22462459b5f36693a` |

Próxima acción: el lanzador externo, con autorización humana específica, puede hacer un reintento V1 en TEST y conservar todas las evidencias reales bajo su nuevo RUN. Los efectos remotos potenciales de cierres, avisos y rollback requieren esa autorización; este trabajo no los ejecutó.
