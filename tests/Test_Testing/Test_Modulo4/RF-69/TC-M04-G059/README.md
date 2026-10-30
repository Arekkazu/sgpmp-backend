# TC-M04-G059 · preparación local

Orden `ORD-G059-001`; RF-69 v2.1; casos TC-M04-161 a TC-M04-165. Solo API. Esta carpeta empezó con `.gitkeep`; no había ejecutor, colección, spec, config, diagnóstico, README ni dependencia local. G058 se leyó como plantilla, sin modificar sus archivos ni evidencias. No hay Cypress porque los cinco casos son API.

## Oráculo y decisiones QA

La fila `TC-M04-G059` de `Casos_Prueba(Mod4Agrupfinal)_actualizada.csv` (Windows-1252, `;`) conserva: APROBADO solo sale manualmente a ACTIVO; ACTIVO solo pasa automáticamente a DEPRECADO al activar otra versión; DEPRECADO y RECHAZADO son terminales; no hay deprecación directa; el campo de estado no declarado en PATCH de notas no cambia el estado. La matriz remite a TC-M04-161–165 y enumera 14 combinaciones. El CSV de Módulo 3 se consultó y no contiene G059; para este grupo rige la matriz de Módulo 4 citada por la orden.

RF-69 v2.1: transiciones válidas y prohibición de reactivar, líneas 1811–1839; Restricción 6, 1887–1888; activación manual y deprecación atómica, 2070–2087; E4 HTTP 409, 2177–2181; E5, 2183–2192; CA-5, 2297–2300; CA-6, 2302–2305; CA-7, 2307–2311; CA-8, 2313–2315. RFC-015 C3, citado en la matriz, excluye OTA previa como precondición. La falta de evento propio del intento de reactivación se documenta como observación por la decisión QA sobre FA-08.

Cada vía prohibida se intenta por PUT y PATCH sobre `/prediccion/modelos/{id}`. Cuando el destino es ACTIVO desde DEPRECADO o RECHAZADO, también se usa POST `/{id}/activar`, cuyo HTTP debe ser 409. Cualquier 4xx de PUT/PATCH con estado intacto es conforme; 2xx sin cambio se documenta; cambio de estado o 5xx rechaza el caso. PATCH `/notas` con `estado_version` puede ignorar el campo o rechazar el cuerpo 4xx, siempre con estado intacto. En R se reenvían métricas corregidas con el mismo `id_proceso_rf71`: R debe conservar estado, métricas y detalle; un registro nuevo o 4xx es conforme, 5xx o modificación de R no lo es. La persistencia se acredita con GET y listado, sin SQL. La auditoría compara eventos `VERSION_*` e ignora `HISTORIAL_CONSULTADO`.

| Caso | Origen | Destinos prohibidos | Vías |
|---|---|---|---|
| 161 | APROBADO | RECHAZADO, DEPRECADO, EN_VALIDACION | PUT y PATCH por destino |
| 162 | ACTIVO | APROBADO, RECHAZADO, EN_VALIDACION | PUT y PATCH por destino |
| 163 | DEPRECADO | APROBADO, ACTIVO, RECHAZADO, EN_VALIDACION | PUT y PATCH por destino; también POST `/activar` para ACTIVO |
| 164 | RECHAZADO | APROBADO, ACTIVO, DEPRECADO, EN_VALIDACION | PUT y PATCH por destino; también POST `/activar` para ACTIVO |

Son 3 + 3 + 4 + 4 = **14 combinaciones**. El caso 165 añade POST `/{id}/deprecar` y PATCH `/{id}/estado`, seguidos de la activación válida de V2.

## Diseño y fuentes consultadas

`origin/test` consultado por Git de lectura: `daefc3a5`; el despliegue TEST no se verificó. En `src/prediction/infrastructure/routers/version_modelo_router.py:42-47,80,116,141,168` solo se declaran POST registro, GET listado, GET id, PATCH notas y POST activar; PUT/PATCH en id y deprecación directa carecen de ruta declarada (404/405 previstos). `src/prediction/infrastructure/dto/registrar_notas_version_dto.py:4-5` declara solo `notas_validacion`; `src/shared/base_dto.py:21-23` no configura `extra`, por lo que aplica el valor predeterminado de Pydantic. `src/prediction/domain/entities/version_modelo.py:150-179,196-211` devuelve conflicto de activación desde estados terminales/ACTIVO y rechaza notas repetidas; no condiciona la primera nota al estado. `src/prediction/application/use_cases/versiones_modelo/activar_version_modelo_use_case.py:29-95` hace deprecación dentro de activar y registra eventos solo tras éxito; no aparece llamada OTA en esa ruta. `src/prediction/infrastructure/routers/version_modelo_router.py:47-77` fija 201 APROBADO y 200 RECHAZADO. `src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py:111-187` crea entidad nueva, evalúa métricas y avisa solo si queda RECHAZADO. `src/prediction/infrastructure/models/version_modelo_model.py:39` y `alembic/baseline/esquema_baseline.sql:24709,39411-39415` muestran `id_proceso_rf71` sin unicidad declarada para `versiones_modelos`; su respuesta al reenvío queda por observar en TEST, no se presupone. La ausencia de auditoría para intentos fallidos se infiere de `activar_version_modelo_use_case.py:37-38,73-92`, no se afirma como observación TEST.

Orden: registrar V1/V2/V3 APROBADAS y R RECHAZADA; notas y activar V1; 165 comprueba deprecación directa y activa V2; 162 usa V2 ACTIVO; 163 usa V1 DEPRECADO; 164 usa R; 161 usa V3 al final. Si falla activar V2, 162 continúa sobre V1 aún ACTIVO. V3 y R son independientes. El caso que muta un estado por defecto se rechaza con la lectura posterior; los restantes continúan con sus precondiciones comprobadas.

## Presupuesto y efectos para autorización posterior

Camino completo normal: **100 solicitudes**. Si el reenvío crea otra versión, una lectura poscierre adicional: **101**. Si el primer PATCH de notas de V1 rechaza el campo extra, se registra la nota sin ese campo: **101**. Ambos caminos juntos: **102**, límite declarado. Duración máxima 900 s; logins y registros 120 s; resto 30 s. Newman solo registra versiones; el ejecutor hace el resto por API. El ensayo usa servidor `127.0.0.1` y directorios temporales fuera de esta carpeta.

Posibles efectos en TEST que requieren autorización particular: cuatro versiones de BD más una si el reenvío crea otra; notas, dos activaciones válidas, intentos rechazados, historial y auditoría, sujetos al sandbox; cuatro o cinco ONNX en `MODELOS_STORAGE_PATH` y posible respaldo RF-73 fuera de rollback; un correo irreversible por cada destinatario con permiso 43/3 al registrar R RECHAZADA (otro solo si el reenvío crease una versión RECHAZADA); dos logins previos; lecturas poscierre. Activar no distribuye OTA según la ruta revisada. El informe solo se genera al evaluar un RUN autorizado y se conserva dentro de su RUN; preparar no crea RUN ni resultados ficticios.

Validación local: `node --check g059.mjs`, `node pruebas/g059_env.test.mjs`, `node g059.mjs --capacidades`, `node g059.mjs --comprobar`, `node pruebas/g059_ensayo.mjs`. El ensayo debe terminar `OK G059: 34/34 modos; presupuesto 100; registro QA fiel` si todos los modos pasan.
