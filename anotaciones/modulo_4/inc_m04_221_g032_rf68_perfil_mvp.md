# INC-M04-221-G032 · RF-68 — Perfil MVP explícito y auditable

Fecha: 2026-10-30. Autor Git consultado: Leandro. Referencia: [#856](https://github.com/Arekkazu/sgpmp-backend/issues/856).

## Definición confirmada

RF-68 describe un modo MVP con pesos por defecto, sin caché y evaluación básica, pero no define cómo activarlo ni qué validaciones extendidas se omiten. modo_ejecucion pertenece a RF-65 y al enum PostgreSQL EDGE/HIBRIDO/SERVIDOR; agregar MVP allí mezclaría perfil de cálculo con lugar de ejecución.

El usuario confirmó:

- perfil_calculo_contagio=ESTANDAR|MVP en RF-65, con ESTANDAR por defecto y MVP exclusivo de MODELO_RIESGO_CONTAGIO.
- Conservar modo_ejecucion=EDGE|HIBRIDO|SERVIDOR.
- MVP usa pesos base 0.5/0.3/0.2 y no utiliza caché.
- Mantener JWT/RBAC, RLS, auditoría y controles obligatorios. No inventar qué validaciones se omiten; una simplificación adicional requiere definición funcional separada.

Se revisaron ambas copias de los requisitos M04 y la issue en GitHub, sin comentarios adicionales al momento de la consulta.

## Reproducción y causa raíz

POST /prediccion/motor-ia con modo_ejecucion=MVP era rechazado por MODO_EJECUCION_INVALIDO. Ese rechazo del lugar de ejecución se conserva: la activación correcta utiliza el nuevo perfil independiente.

La configuración, su historial, DTO y ORM no tenían un campo de perfil. Tampoco existía una rama RF-68 que seleccionara pesos por defecto y evitara la caché. La regresión nueva de activación falló antes del cambio porque la entidad carecía de perfil_calculo_contagio; evidencia en .pytest_cache/inc856_antes.xml/log.

## Persistencia y migración

Revisión nueva c31f8a6d920e, dependiente de 6bd01d026ac4:

1. Agrega perfil_calculo_contagio VARCHAR(20) NOT NULL DEFAULT ESTANDAR en modulo4.configuraciones_motor_ia y modulo4.configuracion_ia_log.
2. Define restricciones de catálogo y exclusividad de MVP para MODELO_RIESGO_CONTAGIO en ambas tablas.
3. Actualiza mediante CREATE OR REPLACE la función existente modulo4.fn_rf65_log_configuracion_motor para copiar OLD.perfil_calculo_contagio al historial.
4. Conserva el OID, propietario, SECURITY DEFINER, search_path y triggers existentes. No se modifican RLS, FORCE RLS, permisos, enums de despliegue ni protecciones append-only.
5. La revisión inversa restaura la función anterior y elimina únicamente columnas/restricciones nuevas.

Las configuraciones y registros de historial previos se interpretan como ESTANDAR mediante el DEFAULT. No se ejecutan UPDATE/DELETE de filas históricas ni se desactiva su protección.

La migración debe aplicarse antes del backend que mapea la nueva columna. Activar MVP solo después de completar el despliegue de ese backend. El downgrade elimina la información de perfil y vuelve al contrato anterior; no se aplicó en una base oficial.

## Flujo de configuración

El DTO admite el campo nuevo. El caso de uso valida catálogo, tipo de modelo, umbrales, pesos, ventana, nodos cuando corresponda y concurrencia optimista existentes.

En MVP, pesos personalizados válidos se normalizan a 0.5/0.3/0.2 antes de guardar. Pesos inválidos siguen rechazándose; el DTO no se modifica. La configuración visible, el historial, RF-73 y el payload de sincronización reflejan los valores realmente guardados.

Crear y actualizar propagan el perfil a la entidad, ORM y repositorio. Cambiarlo incrementa config_version y conserva el estado anterior mediante el trigger. Una edición con versión obsoleta conserva HTTP 412.

Omitir el campo conserva el valor por defecto ESTANDAR del contrato de configuración; al editar una configuración MVP, el cliente debe enviar el perfil que desea guardar.

## Flujo de cálculo

- RF-68 carga el perfil vigente de RF-65.
- MVP evita completamente reutilización de caché y el bloqueo previo de cinco segundos: cada solicitud válida crea un resultado y devuelve HTTP 201, incluso si las entradas son idénticas a las de dos segundos antes.
- Los pesos base aplicados son 0.5/0.3/0.2, también de forma defensiva ante una configuración MVP escrita por otro canal. No se cambian fórmula, clasificación ni mínimos sanitarios existentes.
- Si falta un factor, se conserva la renormalización proporcional y confianza_baja establecidas en RF-68. Por tanto, los pesos finales pueden diferir de los pesos base cuando el cálculo es degradado; no se inventa un factor ausente para mantener una suma ficticia.
- ESTANDAR conserva pesos configurables y el comportamiento de su base. Al cambiar de perfil no se reutiliza un resultado del perfil anterior ni se aplica el bloqueo de frecuencia por esa transición.
- perfil_calculo_contagio es independiente del modo_ejecucion de la respuesta RF-68, que continúa representando NORMAL/DEGRADADO.
- El perfil y los pesos aplicados quedan en RF-73; el perfil también se conserva en variables_ambientales_snap. Los snapshots legados sin perfil se leen como ESTANDAR, sin reescribirlos ni presentar el perfil como variable ambiental.

## Aviso de calidad E10

Se probó también la repetición de seis cálculos MVP degradados. El aviso ALERTA_CALIDAD_DATOS usaba ADVERTENCIA como resultado_operacion, valor ajeno al enum existente, y terminaba en respaldo. Se corrigió a PARCIAL conservando severidad WARNING. La nueva prueba verifica seis resultados, el aviso E10 persistido con el perfil y el conteo correctos, y ninguna alerta operativa. No se cambia el umbral de seis ejecuciones ni se agrega otro catálogo. Evidencia previa: .pytest_cache/inc856_e10_antes.xml/log.

## Alertas y seguridad

Se conserva la emisión o consolidación RF-57 para ALTO con confianza normal, y la prohibición de alerta automática con confianza baja. Se incluye el ajuste mínimo de identidad de servicio ya identificado en #852/#855: como_sistema alrededor de la emisión automática, después de autorizar el lote, con restauración del solicitante.

No se asigna una identidad nueva ni se amplían permisos globales. Las solicitudes conservan sgpmp_app, sin superusuario/BYPASSRLS. La consolidación de una alerta existente y las auditorías RF-63/RF-73 participan en la misma transacción del cálculo.

Los fallos reales tras resultado, auditoría o alerta revierten la operación nueva y conservan el cálculo anterior. No se omiten restricciones ni evidencia para obtener un resultado exitoso.

## Contrato de activación

POST /prediccion/motor-ia, con los demás parámetros válidos de RF-65:

    tipo_modelo: MODELO_RIESGO_CONTAGIO
    modo_ejecucion: SERVIDOR
    perfil_calculo_contagio: MVP

Luego POST /prediccion/riesgo-contagio dos veces con el mismo cuerpo y dos segundos de diferencia:

- Ambas respuestas HTTP 201, desde_cache=false.
- IDs de resultado diferentes y dos eventos RF-73.
- perfil_calculo_contagio=MVP y pesos base 0.5/0.3/0.2.

modo_ejecucion=MVP continúa produciendo 422 MODO_EJECUCION_INVALIDO. Perfil desconocido responde 422 PERFIL_CALCULO_CONTAGIO_INVALIDO y MVP para otro modelo responde 422 PERFIL_MVP_NO_APLICA.

## Inspección oficial e integración

La inspección oficial fue únicamente de lectura: current_database=sgpmp_dev, current_user=member_dev y transaction_read_only=on. Se verificó la ausencia del perfil en configuración/historial, columnas reales, restricciones, índices, funciones y triggers. Las tablas inspeccionadas conservan RLS/FORCE RLS y los roles API consultados no son superusuarios ni BYPASSRLS.

member_dev no pudo consultar modulo1.permisos ni public.alembic_version (42501); no se presume su contenido ni una revisión desplegada. No se ejecutó DDL/DML oficial.

La integración utilizó sgpmp_inc856_test local, PostgreSQL 18, migrada desde cero a c31f8a6d920e, con TEST_ROL_APP=sgpmp_app. Los grants de preparación se limitaron a esa base local; la API mantiene solo SELECT sobre el historial y el trigger usa su propietario existente.

## Pruebas finales

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias/contrato RF-65, RF-68, RFC-009 y DEV-09, cuatro archivos | 92 | 0 | 0 |
| Integración HTTP/PostgreSQL y migración transaccional, dos archivos | 22 | 0 | 0 |
| Total distinto | 114 | 0 | 0 |

Evidencias: .pytest_cache/inc856_unit.xml/log e inc856_pg.xml/log. No se suman corridas repetidas, lanzadores interrumpidos ni el diagnóstico fallido previo. Se conserva una advertencia preexistente de TestClient/httpx en las corridas finales.

Cobertura: activación separada, defaults y pesos personalizados, entradas idénticas a cero/dos segundos, caché ESTANDAR, transiciones de perfil y versiones, historial real y auditoría, compatibilidad de snapshot legado, catálogo SQL, exclusividad por modelo, inmutabilidad, 412, JWT/RBAC/finca, datos obsoletos/sensores insuficientes, alerta real/consolidación, restauración de identidad y rollback.

La prueba de migración ejecuta downgrade/upgrade de la revisión dentro de la transacción exterior de la base local de pruebas: conserva configuraciones e historial previos, comprueba el DEFAULT al añadir las columnas, prueba el trigger y verifica owner, SECURITY DEFINER, search_path y RLS. Ese DDL temporal se revierte al finalizar el fixture. La siembra declara la identidad de un Administrador de prueba real; no se desactiva RLS para que el trigger pase.

Los tests HTTP usan salidas RF-66 sintéticas controladas y reloj explícito; no ejecutan el motor RF-66 real ni certifican un despliegue compartido. El shim fcntl permanece solo en lanzadores de pruebas Windows. Un bloqueo del lanzador unitario en el sandbox se resolvió reiniciándolo con la misma configuración de fakes; no se modificó producción por ese problema.

## Archivos y alcance

14 archivos de producción, una migración nueva, tres archivos nuevos de pruebas y dos informes: 20 archivos en total. Las cabeceras de los 18 archivos de código contienen fecha real, identidad Git consultada y tarea/RF, preservando las filas anteriores.

El perfil se conecta a DTO, caso de uso, entidad, repositorios, ORM, schemas, trigger de historial y auditoría. El commit/rollback permanece en los casos de uso; no se incorpora SQL a entidades o lógica de negocio a routers.

## Base y dependencias

Rama fix/inc-m04-221-g032-perfil-mvp-rf68, creada desde dev actualizado a 3af2d9cf45e831d1aec999a01a5ee57969803414.

Las correcciones #852, #853, #854 y #855 no están incluidas en esa base. Se reutiliza aquí solo el ajuste mínimo de identidad de alerta compartido con #852/#855. Al integrar se deben preservar umbrales, densidad histórica, cobertura mínima del 60 %, recálculo ESTANDAR ante cambios y el bypass de caché exclusivo de MVP, manteniendo un único bloque de identidad y todas las cabeceras.

MVP no constituye una excepción a los controles obligatorios confirmados de esas correcciones. La cobertura del 60 % de #854 debe mantenerse también para MVP al integrar esa rama; esta entrega no duplica su implementación de cobertura.

El payload existente de sincronización incorpora el perfil en configuracion. Las pruebas DEV-09 verifican el contrato con fakes; no se afirma que un firmware real haya recibido o aplicado MVP. En EDGE/HIBRIDO se requiere coordinar la adopción del nuevo campo con IoT. SERVIDOR se verificó mediante HTTP/PostgreSQL.

Pendiente aplicar la migración y desplegar en un entorno autorizado, adaptar el caso QA a la activación confirmada y reejecutar G032. La definición de validaciones extendidas adicionales que podrían omitirse queda separada; no se introdujo un bypass indeterminado.

Commit y push autorizados por el usuario para #856; no se solicitó publicar un PR. Se preservan AGENTS.md y documentos ajenos. Los artefactos temporales .pytest_cache/inc856_* no pertenecen al commit.

## Cierre del entorno local

Se eliminó exclusivamente sgpmp_inc856_test y se verificó que las demás bases locales permanecieran intactas. Se detuvo el clúster iniciado para esta tarea. Evidencia: .pytest_cache/inc856_cierre_bd.log. Se conservaron logs/scripts y la evidencia de diagnóstico fuera del commit.
