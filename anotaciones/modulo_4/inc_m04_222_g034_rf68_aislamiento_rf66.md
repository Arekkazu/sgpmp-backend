# INC-M04-222-G034 · RF-68 · Aislamiento de salidas RF-66 por lote

## Diagnóstico y alcance confirmado

Issue: [#857](https://github.com/Arekkazu/sgpmp-backend/issues/857). Fecha: 2026-10-30, America/Bogota. Identidad Git consultada: Leandro.

El defecto pertenece a Desarrollo Backend. El caso de uso autorizaba el lote, pero trasladaba toda la lista salidas_rf66 al motor puro. El motor contaba sus probabilidades sin comprobar su origen. Reproducción unitaria antes del cambio: diez salidas propias (tres enfermas) y cinco ajenas enfermas produjeron ocho enfermos, Fs=0.8, P=0.67, ALTO y solicitud de alerta. Evidencia: .pytest_cache/inc857_antes.xml y .log (una regresión fallida esperada antes del arreglo).

RF-68, precondición 5 y proceso 1, exige datos del mismo id_lote. El usuario confirmó filtrar por identidad: id_activo_biologico debe coincidir con id_lote; excluir salidas de otro ID y salidas sin ID. M02 representa cada lote como un activo y no dispone de una relación individuo→lote. Compartir área, especie o finca no acredita pertenencia. No se inventó una relación ni una tabla.

La lista actual puede contener varias observaciones atribuidas al mismo activo/lote; se conserva su agregación existente. Esta corrección no identifica individuos internos de un lote poblacional ni autentica contra RF-66 que las probabilidades suministradas por el cliente hayan sido generadas por un motor real. Esas garantías requerirían un contrato y una relación explícitos.

## Flujo y causa raíz

POST /prediccion/riesgo-contagio → JWT/RBAC recurso 41, acción 5 → acceso del lote mediante ActivoBiologicoPort/ActivoBiologicoM02Adapter → configuración RF-65 → filtro de identidad → huella/caché → calcular_riesgo_contagio → repositorio de resultados → RF-73 → RF-57/RF-63 si corresponde → commit. Los fallos de persistencia conservan rollback en el caso de uso.

La brecha estaba antes de calcular la cobertura, los tiempos y el conteo sanitario. La lógica pura no tiene acceso a M02 y recibía entradas sin aislar. El filtro queda en el caso de uso, antes de reutilizar caché y antes de evaluar frescura, sincronía, cobertura, Fs y calidad. No se introduce SQL en dominio, DTO o router.

## Cambios

- Conservar solo salidas con el mismo ID del lote autorizado, sin consultar ni revelar datos de los lotes descartados.
- Derivar n_enfermos_detectados de las salidas propias vigentes cuando se envía una lista; un agregado enviado por el cliente no reincorpora enfermos ajenos.
- Conservar total_activos_lote recibido; cuando se omite, el motor lo deriva de la lista filtrada, como hacía con su entrada anterior.
- Si una lista no vacía queda sin salidas propias y no se aporta score_anomalia poblacional: HTTP 422 ERROR_DATOS_INSUFICIENTES y evidencia RF-73, sin resultado ni alerta. Una lista originalmente vacía conserva el flujo previo; no se añade un bloqueo global nuevo.
- Conservar el camino poblacional por score_anomalia de RFC-009.
- No mutar el DTO original. La huella utiliza su copia filtrada y el conteo derivado.
- Versionar la huella con version_aislamiento_rf66=1 para no reutilizar resultados calculados antes del filtro. Si un resultado previo no coincide dentro de cinco segundos, se conserva el 429 temporal de esta base; pasado el intervalo se recalcula. No se modifica el historial anterior.
- RF-73 registra aislamiento_rf66: recibidas, conservadas, descartadas_otro_lote y descartadas_sin_identidad, tanto en el cálculo nuevo como en rechazos por datos. No registra IDs ajenos. Los aciertos de caché conservan el comportamiento previo de no crear otro cálculo/evento.
- Documentar en el DTO la identidad usada y el conteo derivado. El campo ID sigue admitiendo omisión en la estructura; una salida sin ID se excluye del cálculo.

## Regresión de alerta propia

La prueba PostgreSQL de ocho salidas propias enfermas reprodujo un fallo adicional ya tratado en las ramas #852/#855/#856: la emisión como Veterinario no confirmaba la evidencia RF-63 y revertía la operación. Esta base de dev aún no tiene ese ajuste. Se incluye únicamente el bloque mínimo de identidad existente como_sistema en el adaptador de alerta, después de autorizar el lote, con restauración de la identidad solicitante.

No se concede BYPASSRLS ni se cambia el rol SQL: sigue siendo sgpmp_app. La regresión comprueba identidad no-servicio al asociar la alerta y existencia de RF-63. No se amplía el alcance de consultas públicas ni permisos de otros lotes.

## Base de datos y RBAC

Inspección oficial solo en lectura en sgpmp_dev, con SET TRANSACTION READ ONLY por consulta: columnas de M02/RF-66/resultados de contagio, constraints, políticas y RLS. No se encontraron columnas de pertenencia individuo→lote; las coincidencias de nombre fueron identificador_lote en una vista y total_activos_lote en resultados. El usuario member_dev no pudo leer modulo1.permisos ni public.alembic_version (42501); no se presume su contenido o revisión desplegada. Evidencia: .pytest_cache/inc857_preflight.json.

No se necesita migración: se utilizan los IDs y tablas existentes. No se ejecutó DDL/DML oficial ni se desplegó la rama. Alembic local conserva una única head 6bd01d026ac4.

Integración local: PostgreSQL 18, base exclusiva sgpmp_inc857_test creada desde cero y migrada hasta esa head. Se provisionaron privilegios de prueba para las consultas existentes; se conservaron constraints, triggers, políticas RLS/FORCE. HTTP usa TEST_ROL_APP=sgpmp_app, sin superusuario/BYPASSRLS. La siembra y las aserciones se ejecutan con el administrador de la base local, separadas de las peticiones. El fixture conserva una transacción exterior y convierte commits en savepoints.

## Pruebas finales

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias RF-68, aislamiento y RFC-009 | 60 | 0 | 0 |
| HTTP/PostgreSQL 18 con JWT/RBAC/RLS | 15 | 0 | 0 |
| Total distinto | 75 | 0 | 0 |

Unitarias: tests/prediction/test_inc_m04_222_aislamiento_rf66.py, test_rf68_riesgo_contagio.py y test_rfc009_taxonomia_paradigma.py. Integración: tests/integration/test_inc_m04_222_aislamiento_rf66_integration.py.

Cobertura: tres propios enfermos y cinco ajenos; identidad omitida; conteo agregado contaminado; total omitido; cobertura sin inflación; timestamps ajenos viejos/desfasados; rechazo sin propios; score poblacional; caché filtrada e invalidación de huellas anteriores; no mutación del DTO; riesgo propio ALTO; alertas reales y RF-63; restauración del solicitante; rollback tras flush de resultado, auditoría y alerta; otro lote en la misma área; lotes de otras fincas accesibles y no accesibles; JWT/RBAC/aislamiento; lectura posterior por GET.

Las inferencias son entradas sintéticas del contrato; no se ejecutó un clasificador RF-66 real ni QA en TEST desplegado. Se conserva una advertencia preexistente de TestClient/httpx. Hubo errores de preparación inicial del fixture local (nombre de finca con dígitos y orden de montaje de routers); se corrigieron en las pruebas, sin desactivar restricciones. Los permisos de SELECT de especies se completaron solo en el aprovisionamiento local. Las corridas intermedias no se suman al total.

Evidencias ignoradas: .pytest_cache/inc857_unit.xml/.log, inc857_pg.xml/.log, inc857_verificacion.json, inc857_migraciones.log, inc857_preflight.json. Shim fcntl exclusivo del lanzador de Windows, sin cambio de producción.

## Archivos y trazabilidad

Tres archivos de producción (caso de uso, DTO y adaptador de alertas), tres de pruebas (dos nuevos y el fixture unitario existente) y dos informes: ocho archivos. Los seis archivos de código tienen una fila INC-M04-222-G034/RF-68 con fecha real y la identidad Git consultada, conservando filas previas.

Rama fix/inc-m04-222-g034-aislamiento-rf66-rf68 desde dev actualizado a 3af2d9cf45e831d1aec999a01a5ee57969803414. No parte de #856. Commit y push del código, pruebas e informes autorizados por el usuario para #857. No se solicitó publicar un PR.

## Dependencias y pendientes

- Desplegar en entorno autorizado y reejecutar TC-M04-G034 con IDs explícitos coincidentes. Los clientes que enviaban salidas anónimas deben proporcionar el ID del lote.
- No se corrigen retroactivamente los resultados contaminados ni se cierran alertas históricas automáticamente. Revisarlos y recalcular con autorización operativa cuando corresponda.
- Integrar conservando las correcciones independientes #852 (umbrales), #853 (densidad histórica), #854 (mínimo 60 %), #855 (recálculo ante cambios) y #856 (MVP). No están incluidas en esta base; no se incorporaron sus implementaciones completas.
- El filtro debe preceder cobertura y caché en todos los perfiles al integrar. Conservar la cobertura mínima confirmada de #854 también en MVP; esta rama mantiene la cobertura de la base y no duplica ese cambio independiente.
- Al resolver conflictos, mantener una sola envoltura de identidad en el adaptador y todas las filas de seguimiento. Conservar el aviso E10 PARCIAL incorporado en #856.
- Una relación real individuo→lote y sus cambios históricos requieren definición funcional/M02 antes de aceptar como propios IDs distintos al lote. No se dedujo pertenencia por finca, área o atributos JSON.

## Cierre local

Se eliminó exclusivamente sgpmp_inc857_test y se verificó que las demás bases locales permanecieran intactas. Se detuvo el clúster iniciado para la tarea. Se conservaron scripts, logs y evidencias ignoradas. Evidencia: .pytest_cache/inc857_cierre_bd.log.
