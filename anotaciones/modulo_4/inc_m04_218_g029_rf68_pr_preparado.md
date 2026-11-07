# RF-68 — Recuperar densidad histórica ante error del sensor · INC-M04-218-G029

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| RF-68 E2 usa el histórico promedio de ocupación de los últimos 30 días cuando falla el sensor de densidad | El DTO rechazaba densidades negativas con HTTP 400, antes del caso de uso | El negativo finito activa la consulta del histórico y permite ejecutar el modelo |
| Fd se obtiene de una densidad válida del mismo lote | No existía lectura histórica; una llamada directa al dominio saturaba el negativo en cero | Se utiliza el promedio temporal de densidades auditadas de M02 y se normaliza por la densidad máxima RF-65 |
| La densidad desconocida conserva el preventivo | El nulo asumía capacidad máxima | El nulo mantiene su comportamiento y no consulta histórico |
| El cálculo conserva trazabilidad | No se registraba una resolución histórica de densidad | Snapshot y RF-73 conservan entrada, valor aplicado, fuente, ventana y cobertura |

Referencias: [#853](https://github.com/Arekkazu/sgpmp-backend/issues/853), INC-M04-218-G029, RF-68 E2 y restricción de dependencia de datos, RF-36/M02 y RF-65. No se suministraron IDs adicionales de historia, tareas o épica.

## Causa raíz

EstimarRiesgoContagioDTO imponía ge=0 en densidad_poblacional. La entrada -5 era rechazada antes de ejecutar E2. El caso de uso tampoco disponía de un puerto para obtener la ocupación histórica.

El snapshot inicial RF-33 no constituye una serie completa de ocupación. Se verificó que el trigger existente de M02 registra densidad y sus cambios en auditoria.logs_dml; esa fuente se reutiliza sin crear tablas alternativas.

## Cambios implementados

- Admitir densidades negativas finitas en el DTO para resolver el error en dominio; mantener rechazo de formatos inválidos, NaN e infinitos.
- Incorporar OcupacionLotePort y su adaptador M02, que lee únicamente densidad, fecha e id del mismo lote visible bajo RLS.
- Calcular el promedio ponderado por duración dentro de los últimos 30 días, según definición funcional confirmada.
- Utilizar el último estado previo al inicio; excluir el futuro y los intervalos sin dato válido, sin inventar cobertura.
- Ante negativo sin histórico útil, usar capacidad máxima preventiva con confianza baja y motivo SIN_HISTORICO_OCUPACION, impidiendo alertas automáticas.
- Conservar la entrada original y la resolución aplicada en contexto_densidad del snapshot y de RF-73.
- Mantener caché, transacciones, normalización, fórmula y pesos existentes.

Un nulo u omisión conserva su preventivo anterior. Cero y positivos no consultan el histórico. Una falla de infraestructura se traduce y propaga; no se presenta como historia vacía.

## Migración

No requiere migración nueva. Se reutilizan el trigger M02, auditoria.logs_dml y variables_ambientales_snap JSONB. No se cambian políticas RLS, permisos de negocio ni identidades de servicio.

## Contrato resultante

POST /prediccion/riesgo-contagio puede responder HTTP 201 ante densidad_poblacional=-5 cuando aplica E2.

Con densidades registradas de 8 y 11 durante 15 días cada una:

- Promedio histórico: (8×15 + 11×15) / 30 = 9.5.
- Densidad máxima RF-65: 15.
- Fd: 9.5 / 15 = 0.6333.

El 9.5 procede de los registros utilizados, no de una constante ni de un valor impuesto para la prueba. Se conserva el esquema público de respuesta y densidad_asumida distingue el uso preventivo. La cobertura real y la fuente quedan en auditoría y snapshot.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contrato RF-68/RFC-009 (3 archivos) | 79 | 0 | 0 |
| HTTP con PostgreSQL 18 real, JWT/RBAC/RLS | 17 | 0 | 0 |
| **Total distinto** | **96** | **0** | **0** |

No se suman ejecuciones repetidas ni la reproducción fallida previa a la corrección. Advertencia preexistente de TestClient/httpx en integración; las corridas finales no tienen fallos ni omisiones.

Cobertura: reproducción del rechazo previo; promedio temporal; frecuencia de cambios; ventana, fronteras y estado previo; registros futuros/de otro lote; estados inválidos; cero y saturación; histórico ausente; nulo/positivo sin consulta; caché; trazabilidad; trigger real; JWT/RBAC/RLS; UTC; errores del puerto y rollback tras flush.

Las fixtures históricas son sintéticas, identificadas como fixture-inc853 y limitadas a la base desechable. Una prueba separada demuestra que el trigger real de M02 genera la fuente. No se modifican registros existentes ni se desactivan restricciones o triggers.

## Integración con sgpmp_dev

Inspección oficial exclusivamente de lectura: fuente, columnas, triggers, restricciones y políticas. Se verificó SELECT existente para los roles de API sobre la fuente técnica. member_dev no puede consultar historial_activos ni permisos/alembic_version; no se presume ausencia de esa tabla ni una revisión desplegada.

La integración se ejecutó en PostgreSQL 18 local, base exclusiva migrada desde cero a 67e33de11180, con TEST_ROL_APP=sgpmp_app, sin superusuario/BYPASSRLS en las solicitudes. No se ejecutó DDL/DML oficial ni se desplegó la rama.

## Dependencias y pendientes

- Requiere la auditoría DML existente de M02 y los permisos SQL ya verificados en la fuente.
- El histórico representa densidades registradas y su tiempo de vigencia, no mediciones físicas retrospectivas. No se rellenan períodos desconocidos; se documenta su cobertura.
- #852 es una corrección independiente de umbrales/contexto de alertas: su commit 831ea427 no estaba en dev al crear esta rama y no se incorpora aquí. Al integrar ambas deben conservarse sus cambios y filas de cabecera.
- Queda desplegar y reejecutar TC-M04-G029 en un sandbox autorizado de TEST.

## Alcance del commit

Alcance de la entrega: 8 archivos de producción, 3 de pruebas y 2 informes. Evidencias y lanzadores .pytest_cache/g42_* excluidos. Se preservan los archivos ajenos. Commit y push autorizados por el usuario para #853. El PR se entrega como texto para revisión.

## Revisión contra dev

Rama fix/inc-m04-218-g029-densidad-historica-rf68 creada desde dev actualizado a e94232b5086bc1232a77a9f1a625225165eb9a49. La comparación corresponde únicamente a esta corrección y sus pruebas/informes.
