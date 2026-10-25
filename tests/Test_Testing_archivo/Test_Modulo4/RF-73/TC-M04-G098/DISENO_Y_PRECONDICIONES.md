# DISENO Y PRECONDICIONES — TC-M04-G098

## Identificación del Caso
- Caso: TC-M04-G098
- Módulo: Módulo 4 — Predicción e IA (RF-73: Auditoría de eventos de predicción)
- Foco: Disponibilidad (99.5%) y Rendimiento a Gran Escala (50M de registros)
- Herramienta: k6

## Subcasos Cubiertos
1. TC-M04-054: Disponibilidad del subsistema de auditoría >= 99.5%.
2. TC-M04-055: Tiempo de respuesta en consultas de auditoría P95 <= 2000 ms sobre 50 millones de eventos.

## Diagnóstico y Mapeo Técnico
- Endpoint de verificación: GET /prediccion/auditoria (con filtros fecha_desde, fecha_hasta, pagina, por_pagina).
- Endpoint proxy de salud: GET /health.
- Modelo de BD: modulo4.eventos_auditoria_m04.
- SLA definido en RF-73: Disponibilidad 99.5% y latencia P95 <= 2.0 s en consultas históricas masivas.

## Limitaciones Críticas y Fase Separada
1. TC-M04-054 (Disponibilidad >= 99.5%):
   - La disponibilidad contractual (99.5%) se computa matemáticamente sobre ventanas de medición de semanas o meses (ej. 30 días = máximo ~3.6 horas de downtime).
   - En una prueba de sandbox de <120 segundos es físicamente imposible certificar un SLA del 99.5% a largo plazo.
   - En sandbox se implementa una prueba k6 de ventana corta (~35 segundos, tasa de error < 0.5%) que valida la ausencia de caídas inmediatas del servicio.
2. TC-M04-055 (Consulta <= 2 s sobre 50M de eventos):
   - Generar o mantener 50,000,000 de registros en el sandbox transaccional violaría las restricciones de espacio y el límite temporal de 120 s por corrida.
   - Requiere un entorno de base de datos dedicado y precargado sintéticamente.
   - Además, la tabla `modulo4.eventos_auditoria_m04` no cuenta actualmente con particionamiento declarativo por rango de fecha en las migraciones de Alembic (`[DISCREPANCIA] Arquitectónica`).
   - En sandbox, k6 ejecuta la consulta con filtros en el rango permitido (10 a 18 oct 2026) sobre el catálogo actual para validar que la firma HTTP y la estructura cumplan con el SLA en carga moderada.

## FASE SEPARADA — DISPONIBILIDAD Y VOLUMEN
- Infraestructura Requerida:
  - Cluster PostgreSQL dedicado con 50,000,000 de registros en `modulo4.eventos_auditoria_m04`.
  - Particionamiento mensual/semanal por `fecha_evento` implementado en base de datos.
  - Agente de monitoreo continuo (Prometheus + Grafana / CloudWatch) para cálculo de Uptime en ventana de 30 días.
- Procedimiento en Fase Separada:
  1. Ejecución de suite k6 distribuida consultando rangos históricos de diversas antigüedades.
  2. Medición estadística de percentiles P50, P90, P95 y P99.
  3. Comprobación estricta de P95 <= 2000 ms.

## Hallazgos y Discrepancias
- [DISCREPANCIA]: Ausencia de particionamiento declarativo en PostgreSQL para la tabla `modulo4.eventos_auditoria_m04`. Con 50 millones de registros sin particionamiento, el rendimiento de los índices B-Tree se degradará considerablemente con el tiempo.

## PENDIENTES DE DESARROLLO
| Subcaso | Elemento / Endpoint | Contrato Esperado | Responsable |
|---|---|---|---|
| TC-M04-054 | Endpoint de métricas de Uptime | GET /metrics o GET /health/uptime con porcentaje histórico | DevOps / SRE |
| TC-M04-055 | Particionamiento en BD de auditoría | Partición declarativa por rango de fecha en tabla `eventos_auditoria_m04` | Backend / DBA Lead |
| TC-M04-055 | Entorno de prueba masiva (50M) | Base de datos staging con 50 millones de registros de predicción precargados | DevOps / QA Performance |
