# RF-68 — Habilitar el perfil MVP de contagio sin caché · INC-M04-221-G032

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| Poder operar en MVP con pesos base 0.5/0.3/0.2 y sin caché | No existía un mecanismo de activación ni una rama de cálculo MVP | RF-65 configura perfil_calculo_contagio=MVP y RF-68 recalcula cada solicitud válida |
| Distinguir perfil funcional y lugar de ejecución | QA intentaba modo_ejecucion=MVP, incompatible con EDGE/HIBRIDO/SERVIDOR | El perfil queda separado; se conserva el enum de despliegue |
| Mantener trazabilidad de la configuración y evaluación | Configuración e historial carecían del perfil | Perfil versionado en RF-65, historial, snapshot de resultado y RF-73 |

Referencias: [#856](https://github.com/Arekkazu/sgpmp-backend/issues/856), INC-M04-221-G032, RF-68 modo MVP, RF-65/DEV-36 y DEV-09, RF-57/RF-63/RF-73.

El usuario confirmó el campo separado, ESTANDAR por defecto, MVP exclusivo de MODELO_RIESGO_CONTAGIO y conservación de los controles obligatorios. No se interpreta “sin validaciones extendidas” como permiso para desactivar controles sin definirlos.

## Causa raíz

modo_ejecucion expresa EDGE/HIBRIDO/SERVIDOR. El rechazo de MVP en ese campo era coherente con su contrato, pero faltaba un perfil independiente que activara la simplificación descrita en RF-68.

DTO, entidad, persistencia, historial y cálculo no tenían soporte para ese perfil.

## Cambios implementados

- Agregar perfil_calculo_contagio=ESTANDAR|MVP a RF-65, exclusivo de contagio para MVP y versionado con config_version.
- Guardar los pesos base MVP 0.5/0.3/0.2; pesos personalizados válidos se normalizan al activar MVP y los inválidos siguen rechazándose.
- Evitar caché y el bloqueo de frecuencia en MVP; cada solicitud válida crea un resultado.
- Conservar ESTANDAR, controles obligatorios, degradación y ajuste proporcional si falta un factor.
- Exponer el perfil independientemente de NORMAL/DEGRADADO, conservándolo en snapshot y auditoría junto con los pesos aplicados.
- Leer snapshots legados sin perfil como ESTANDAR.
- Conservar el aviso E10 tras ejecuciones degradadas: usar resultado_operacion=PARCIAL del enum existente, manteniendo severidad WARNING y su umbral.
- Mantener el flujo real de alertas con identidad de servicio existente y restauración del solicitante.

## Migración

Nueva revisión c31f8a6d920e, dependiente de 6bd01d026ac4:

- Columna perfil_calculo_contagio con DEFAULT ESTANDAR y NOT NULL en configuración e historial.
- Restricciones de catálogo y exclusividad por modelo.
- Actualización de la función existente que copia OLD al historial, conservando owner, SECURITY DEFINER y search_path.
- Downgrade que restaura la función anterior y elimina los campos/restricciones nuevos.

No modifica el enum EDGE/HIBRIDO/SERVIDOR, permisos, RLS, FORCE RLS ni la inmutabilidad del historial. Aplicar la migración antes de desplegar este backend y activar MVP después del despliegue completo.

## Contrato resultante

POST /prediccion/motor-ia, con los demás parámetros válidos:

    tipo_modelo: MODELO_RIESGO_CONTAGIO
    modo_ejecucion: SERVIDOR
    perfil_calculo_contagio: MVP

Dos POST /prediccion/riesgo-contagio idénticos, separados por dos segundos:

- Ambos HTTP 201 y desde_cache=false.
- IDs diferentes, dos resultados y dos eventos RF-73.
- Perfil MVP y pesos base 0.5/0.3/0.2.

Omitir el perfil conserva ESTANDAR. modo_ejecucion=MVP sigue siendo inválido; la activación utiliza el nuevo campo. Si faltan factores, se conserva la renormalización y confianza baja de RF-68.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias/contrato RF-65/RF-68/RFC-009/DEV-09 | 92 | 0 | 0 |
| HTTP/PostgreSQL 18 y migración transaccional | 22 | 0 | 0 |
| Total distinto | 114 | 0 | 0 |

Cobertura: activación, pesos, llamadas idénticas, caché ESTANDAR, transiciones y versiones, historial, snapshot legado, restricciones SQL, inmutabilidad, rollback de migración, owner/RLS, JWT/RBAC/finca, datos insuficientes, alertas y rollback de la operación nueva.

Las solicitudes usan sgpmp_app sin superusuario/BYPASSRLS. No se desactivan RLS ni restricciones. Las inferencias RF-66 son entradas sintéticas; no se ejecuta el motor RF-66 real. Se conserva una advertencia preexistente de TestClient/httpx.

## Integración con sgpmp_dev

Inspección oficial exclusivamente de lectura: ausencia del perfil, columnas, constraints, triggers, propietario y políticas. member_dev no pudo consultar permisos ni alembic_version; no se presume su contenido o revisión desplegada.

La migración y las pruebas se ejecutaron en sgpmp_inc856_test local, desde cero hasta c31f8a6d920e, con TEST_ROL_APP=sgpmp_app. No se ejecutó DDL/DML oficial ni se desplegó la rama.

## Dependencias y pendientes

- Aplicar la migración, desplegar y reejecutar QA con el campo de activación confirmado.
- Coordinar con IoT el consumo del perfil en EDGE/HIBRIDO: solo se verificó el payload DEV-09 con fakes; SERVIDOR se probó por HTTP/PostgreSQL.
- Definir separadamente cualquier validación extendida adicional que se quiera omitir.
- Integrar sin perder las correcciones independientes #852/#853/#854/#855. MVP no exime los controles obligatorios de esas ramas. Conservar el mínimo del 60 % de #854 también en MVP y el recálculo ESTANDAR de #855.
- El bloque de identidad de alertas coincide con parte de #852/#855; mantener una sola implementación y todas las filas de seguimiento.

## Alcance del commit

Alcance de la entrega: 14 archivos de producción, 1 migración, 3 de pruebas y 2 informes. Cabeceras actualizadas; archivos ajenos y evidencias temporales excluidos. Commit y push autorizados por el usuario para #856. El PR se entrega como texto para revisión.

## Revisión contra dev

Rama fix/inc-m04-221-g032-perfil-mvp-rf68 creada desde dev actualizado a 3af2d9cf45e831d1aec999a01a5ee57969803414. La comparación incluye el perfil confirmado, su migración, el ajuste mínimo de identidad necesario para alertas, pruebas e informes.
