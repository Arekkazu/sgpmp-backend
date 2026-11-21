# RF-68 — Recalcular inmediatamente ante cambios de entradas · INC-M04-220-G032

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| CA-4: actualizar el riesgo cuando cambia el estado sanitario | Un cambio de Fs dentro de cinco segundos respondía 429 | Recalcula inmediatamente y responde 201 |
| Paso 5.1: reutilizar solo entradas/configuración iguales | La rama de frecuencia impedía procesar entradas diferentes | Los cinco segundos funcionan únicamente como ventana de caché |
| Trazabilidad de cada cálculo nuevo | El segundo cálculo no se ejecutaba ni persistía | Conserva ambos resultados y sus eventos RF-73 |
| Completar el flujo cuando el nuevo riesgo es ALTO | La emisión automática bajo el solicitante podía fallar con 500 al registrar RF-63 | Emite/consolida con la identidad de servicio existente y restaura al solicitante |

Referencias: [#855](https://github.com/Arekkazu/sgpmp-backend/issues/855), INC-M04-220-G032, RF-68 CA-4/paso 5.1, RF-65, RF-57 y RF-63/RF-73.

El usuario confirmó priorizar el recálculo ante cambios sobre el mínimo rígido de cinco segundos. Esto permite superar 12 cálculos/minuto por lote si las entradas cambian; la caché sigue evitando reprocesar entradas idénticas durante su ventana.

## Causa raíz

Después de detectar una huella diferente, el caso de uso lanzaba EJECUCION_CONTAGIO_MUY_FRECUENTE si el último cálculo tenía menos de cinco segundos. La operación terminaba antes del motor y la persistencia.

La validación completa detectó además que las alertas automáticas necesitaban la identidad de servicio para confirmar su evidencia RF-63. Ese ajuste ya estaba preparado en #852, pero no formaba parte del dev usado como base.

## Cambios implementados

- Eliminar el bloqueo por frecuencia para entradas diferentes.
- Mantener caché únicamente si coinciden huella y config_version y la antigüedad está entre cero y menos de cinco segundos.
- Conservar fórmula, validaciones, historial, auditoría y transacción existentes.
- Usar como_sistema solo alrededor de la emisión/consolidación RF-57, tras autorizar el lote, restaurando la identidad del solicitante.
- Documentar el 201 inmediato y retirar el 429 de frecuencia obsoleto en OpenAPI de este POST.
- Actualizar la regresión previa y añadir pruebas del flujo completo.

## Migración

No requiere migración. No modifica tablas, enums, permisos de negocio, RLS, FORCE RLS ni triggers.

## Contrato resultante

POST /prediccion/riesgo-contagio con pesos 0.5/0.3/0.2, Fa=0.875 y Fd=0.80:

| Secuencia | Respuesta |
|---|---|
| Fs=0.20 | 201, P=0.5225 |
| Dos segundos después: Fs=0.45 | 201, P=0.6475, nuevo ID |
| Repetición idéntica del segundo cálculo dentro de cinco segundos | 200, mismo ID; sin persistencia ni auditoría adicional |

Los cambios de ambiente, densidad, score poblacional y versión de configuración también recalculan inmediatamente. A los cinco segundos exactos la caché deja de aplicar. Los datos inválidos siguen rechazándose mediante los errores existentes.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contrato RF-68/RFC-009 | 65 | 0 | 0 |
| HTTP con PostgreSQL 18 real, JWT/RBAC/RLS | 19 | 0 | 0 |
| Total distinto | 84 | 0 | 0 |

Cobertura: caso QA exacto, factores/configuración cambiantes, fronteras de caché, historial independiente, auditoría, datos inválidos, JWT/RBAC/finca, alerta real, consolidación, ausencia de duplicados, restauración de identidad y rollback tras flush o tras generar alerta.

Las solicitudes se ejecutaron con sgpmp_app sin superusuario/BYPASSRLS; no se desactivaron restricciones ni RLS. Las salidas RF-66 son entradas sintéticas; no se ejecutó el motor RF-66 real. La prueba de más de 12 cambios usa fakes/reloj controlado y no constituye una prueba de carga. Se conserva una advertencia preexistente de TestClient/httpx.

## Integración con sgpmp_dev

Inspección oficial exclusivamente de lectura: esquema, índices, restricciones, triggers, enum de auditoría y RLS/FORCE RLS. member_dev no pudo consultar permisos ni alembic_version; no se presume su contenido ni una revisión desplegada.

La integración se ejecutó en sgpmp_g44_test local, migrada desde cero a 6bd01d026ac4, con TEST_ROL_APP=sgpmp_app. No se ejecutó DDL/DML oficial ni se desplegó la rama.

## Dependencias y pendientes

- Reflejar la decisión de frecuencia confirmada en RF-68 y la matriz QA; desplegar y reejecutar G032 en TEST autorizado.
- El ajuste de identidad de alertas coincide parcialmente con #852. Al integrar ambas ramas debe conservarse una sola implementación y ambas filas de seguimiento; los cambios de umbrales de #852 no se incorporan aquí.
- #853 (densidad histórica) y #854 (cobertura del 60 %) son correcciones independientes no incluidas en esta base. Verificar su estado actual antes de integrarlas y preservar sus comportamientos.
- La cola de concurrencia/FIFO y la agregación del historial permanecen fuera del alcance de esta tarea.

## Alcance del commit

Alcance de la entrega: 3 archivos de producción, 3 de pruebas y 2 informes. Cabeceras actualizadas; archivos ajenos y evidencias temporales .pytest_cache/g44_* excluidos. Commit y push autorizados por el usuario para #855. El PR se entrega como texto para revisión.

## Revisión contra dev

Rama fix/inc-m04-220-g032-recalculo-contagio-rf68 creada desde dev actualizado a 3af2d9cf45e831d1aec999a01a5ee57969803414. La comparación corresponde a esta corrección, el ajuste mínimo de identidad requerido por su flujo, pruebas e informes.
