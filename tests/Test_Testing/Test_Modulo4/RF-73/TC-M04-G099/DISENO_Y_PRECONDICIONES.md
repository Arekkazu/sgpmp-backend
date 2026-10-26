# DISENO Y PRECONDICIONES — TC-M04-G099

## Identificación del Caso
- Caso: TC-M04-G099
- Módulo: Módulo 4 — Predicción e IA (RF-73: Auditoría de eventos de predicción)
- Foco: Consistencia Temporal y Corrección de Timestamp (Eventos futuros o desordenados)
- Herramienta: Postman / Newman

## Subcasos Cubiertos
1. TC-M04-305: Corrección automática de timestamp en eventos con marca temporal en el futuro o desordenada cronológicamente dentro del mismo flujo (correlacion_id).

## Diagnóstico y Mapeo Técnico
- Endpoint de verificación: GET /prediccion/auditoria (filtro por correlacion_id).
- Endpoint de ingesta esperado: POST /prediccion/auditoria/eventos (contrato esperado).
- Modelo de BD: modulo4.eventos_auditoria_m04.
- Enums actuales: tipo_evento en el backend contempla eventos de ciclo de vida de predicción (INFERENCIA_SOLICITADA, MODELO_ACTIVADO, etc.), pero no incluye formalmente `TIMESTAMP_CORREGIDO`.

## Limitaciones Críticas y Fase Separada
1. TC-M04-305 (Manipulación del reloj / Ingesta con timestamp forzado):
   - Actualmente, todos los eventos de auditoría son emitidos internamente por el dominio utilizando `datetime.now(timezone.utc)` del servidor central de FastAPI.
   - No existe un endpoint REST de ingesta pública de eventos de auditoría que admita un payload con `timestamp_evento` configurable por el cliente.
   - Además, manipular el reloj del servidor central de TEST afectaría a todos los módulos y usuarios concurrentes.
   - El caso se entrega construido contra el contrato esperado: simulación de envío con `timestamp_evento` futuro y desordenado en POST /prediccion/auditoria/eventos.

## FASE SEPARADA — CONTROL DE RELOJ Y EMULACIÓN
- Requisito: Capacidad de alterar el reloj o inyectar eventos con timestamps anómalos desde un broker o microservicio emulado.
- Entorno: Mock server o instancia aislada donde se pueda modificar el reloj del sistema operativo (libfaketime o NTP spoofing en contenedor Docker de testing).
- Verificación requerida:
  1. Envío de evento con timestamp T + 1 hora.
  2. Ajuste automático a T_server (timestamp_evento <= now()).
  3. Generación y almacenamiento de evento secundario con tipo_evento = TIMESTAMP_CORREGIDO y severidad = WARNING.

## Hallazgos y Discrepancias
- [DISCREPANCIA]: El enum `tipo_evento` en la base de datos no incluye `TIMESTAMP_CORREGIDO`. Debe añadirse en la migración de Alembic correspondiente cuando se implemente la ingesta externa.

## PENDIENTES DE DESARROLLO
| Subcaso | Elemento / Endpoint | Contrato Esperado | Responsable |
|---|---|---|---|
| TC-M04-305 | Endpoint de ingesta de auditoría | POST /prediccion/auditoria/eventos aceptando timestamp_evento opcional | Backend Lead (M04) |
| TC-M04-305 | Enum TIMESTAMP_CORREGIDO | Extensión del enum de tipo_evento y severidad WARNING | Backend Lead / DBA |

## Bloqueo por diseño (2026-10-25)
- Feature RF-73 E7 no implementado en M04.
- registrar() no acepta timestamp_evento ni origen_dato.
- TIMESTAMP_CORREGIDO no existe en código ni BD (0 eventos).
- Evidencia: diagnóstico read-only 2026-10-25.
- Veredicto: BLOQUEADO_POR_DISENO.
- El test es negativo honesto (documenta el bloqueo).

