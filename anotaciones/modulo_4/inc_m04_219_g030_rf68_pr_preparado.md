# RF-68 — Exigir cobertura mínima del 60 % de inferencias · INC-M04-219-G030

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| Restricción de validación, E8 y CA-10: no ejecutar con menos del 60 % de activos con inferencias recientes | Con 55 % calculaba Fs y ejecutaba NORMAL; con 45 % ejecutaba DEGRADADO sin Fs | Ambos escenarios responden 422 ERROR_DATOS_INSUFICIENTES |
| Conservar trazabilidad del intento rechazado | La cobertura insuficiente podía generar un resultado | RF-73 registra el rechazo y sus conteos, sin crear resultado ni alerta |
| Verificar cobertura reciente | Una caché anterior podía devolverse antes de comprobarla | La validación ocurre antes de reutilizar la caché |

Referencias: [#854](https://github.com/Arekkazu/sgpmp-backend/issues/854), INC-M04-219-G030, RF-68 E8/CA-10 y RFC-009. No se suministraron IDs adicionales de historia, tareas o épica.

El usuario confirmó aplicar el mínimo obligatorio del 60 % a inferencias individuales, priorizando la restricción de validación/E8/CA-10 frente al comportamiento contradictorio de E1/CA-5. Se conserva el camino poblacional por score_anomalia.

## Causa raíz

El dominio utilizaba un mínimo de 0.50 para calcular Fs. Por debajo de ese valor continuaba sin factor sanitario, siguiendo E1. No existía el rechazo del mínimo del 60 % definido en E8.

El caso de uso consultaba además la caché antes de verificar la cobertura de la solicitud.

## Cambios implementados

- Aplicar cobertura individual mínima de 0.60, sin redondear antes de comparar.
- Contar únicamente salidas entre cero y 30 minutos de antigüedad, con una última salida reciente por ID de individuo.
- Rechazar la cobertura insuficiente antes de calcular o reutilizar una caché.
- Registrar ERROR_DATOS_INSUFICIENTES en RF-73 con conteo reciente, total, cobertura observada y mínimo requerido.
- Mantener la ausencia de resultados nuevos y alertas RF-57 en ese rechazo.
- Conservar score_anomalia de RFC-009, los demás motivos de degradación y el contrato de éxito existente.
- Actualizar la documentación OpenAPI y la regresión que antes esperaba el comportamiento de E1.

## Migración

No requiere migración. Se reutilizan tablas, enum de auditoría, RLS y permisos existentes.

## Contrato resultante

POST /prediccion/riesgo-contagio, total_activos_lote=20:

| Inferencias recientes | Cobertura | Respuesta |
|---:|---:|---|
| 9 | 45 % | 422 ERROR_DATOS_INSUFICIENTES |
| 11 | 55 % | 422 ERROR_DATOS_INSUFICIENTES |
| 12 | 60 % | 201; ejecuta el cálculo |

Una caché válida conserva HTTP 200. Un score poblacional válido conserva el cálculo RFC-009 sin exigir inferencias individuales. No se reescriben resultados históricos.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contrato RF-68/RFC-009 | 71 | 0 | 0 |
| HTTP con PostgreSQL 18 real, JWT/RBAC/RLS | 17 | 0 | 0 |
| Total distinto | 88 | 0 | 0 |

Cobertura: rechazo de 45/50/55 %, 60 % exacto y superior, vigencia de 30 minutos, datos futuros/obsoletos, individuos repetidos, score poblacional, caché válida/legacy/vencida, auditoría persistida, ausencia de resultados y alertas, permisos/finca y rollback tras flush.

La integración observa sgpmp_app sin superusuario ni BYPASSRLS durante el rechazo. No se desactivan restricciones, triggers ni RLS. Las salidas RF-66 son entradas sintéticas controladas; estas pruebas no ejecutan el motor RF-66 real. Se conserva una advertencia preexistente de TestClient/httpx.

## Integración con sgpmp_dev

Inspección oficial exclusivamente de lectura: esquema, evento, privilegios y RLS/FORCE RLS. member_dev no pudo consultar permisos ni alembic_version; no se presume su contenido ni una revisión desplegada.

La integración se ejecutó en la base exclusiva local sgpmp_g43_test, migrada desde cero a 67e33de11180, con TEST_ROL_APP=sgpmp_app. No se ejecutó DDL/DML oficial ni se desplegó la rama.

## Dependencias y pendientes

- Reflejar en la ficha funcional y QA la prioridad del mínimo del 60 % confirmada por el usuario.
- Conservar la compatibilidad del contrato actual: total opcional derivado de las salidas recientes e IDs opcionales. Para medir cobertura del lote real, el emisor debe enviar el inventario completo; no se incorpora una consulta automática de población/inferencias a M02/RF-66.
- #852 y #853 son cambios independientes que no se incorporan en esta rama. Al integrarlos deben preservarse sus ajustes de umbrales y densidad histórica, verificando antes su estado actual.
- Pendiente desplegar y reejecutar TC-M04-G030 en TEST autorizado.

## Alcance del commit

Alcance de la entrega: 3 archivos de producción, 3 de pruebas y 2 informes. Cabeceras de seguimiento actualizadas; archivos ajenos y evidencias temporales .pytest_cache/g43_* excluidos. Commit y push autorizados por el usuario para #854. El PR se entrega como texto para revisión.

## Revisión contra dev

Rama fix/inc-m04-219-g030-cobertura-rf66-rf68 creada desde dev actualizado a e94232b5086bc1232a77a9f1a625225165eb9a49. La comparación corresponde únicamente a esta corrección y sus pruebas/informes.
