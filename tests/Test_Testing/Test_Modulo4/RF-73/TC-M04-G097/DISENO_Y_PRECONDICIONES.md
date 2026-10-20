# DISENO Y PRECONDICIONES — TC-M04-G097

## Identificación del Caso
- Caso: TC-M04-G097
- Módulo: Módulo 4 — Predicción e IA (RF-73: Auditoría de eventos de predicción)
- Foco: Resiliencia del Subsistema de Auditoría — Reintentos Automáticos de Persistencia
- Herramienta: Postman / Newman

## Subcasos Cubiertos
1. TC-M04-053: Reintento puntual de persistencia antes de activación de mecanismo de contingencia.

## Diagnóstico y Mapeo Técnico
- Endpoint de verificación: GET /prediccion/auditoria
- Tipo de evento analizado: AUDITORIA_FALLA_PERSISTENCIA / AUDITORIA_FALLBACK_ACTIVADO
- Modelo de BD: modulo4.eventos_auditoria_m04
- Comportamiento Nominal: En operación regular o recuperación automática transparente (N reintentos con backoff exponencial), el evento se almacena con éxito y NO se emite alarma de falla de persistencia.

## Limitación Crítica y Fase Separada
La inyección de fallos puntuales y transitorios a nivel de capa de persistencia (desconexión repentina de BD por 200 ms, timeout inducido por proxy o fallo de driver) no puede ser provocada desde la capa de API HTTP externa sin perturbar el entorno compartido de TEST.
Por tanto, el subcaso TC-M04-053 se diseña contra contrato esperado y se ejecuta en sandbox como verificación de ausencia de fallos espurios, derivándose la prueba de mutación/inyección a una fase aislada.

## FASE SEPARADA — RESILIENCIA
- Requisito: Inyección controlada de fallas transitorias de persistencia.
- Entorno requerido: Infraestructura dedicada (Staging o contenedor aislado con Toxiproxy o Chaos Mesh).
- Protocolo:
  1. Interrumpir la conexión a PostgreSQL durante la emisión de un evento de predicción.
  2. Verificar en logs y métricas los 3 reintentos automáticos con backoff exponencial.
  3. Restaurar conexión antes del agotamiento de reintentos; verificar persistencia final sin evento de falla.
  4. Agotar reintentos intencionalmente; verificar generación y persistencia local/buffer de evento de contingencia.

## Hallazgos de Nomenclatura y Discrepancias
- [DISCREPANCIA]: En la especificación se referencia `AUDITORIA_FALLA_PERSISTENCIA`, mientras que en el catálogo funcional del módulo se menciona `AUDITORIA_FALLBACK_ACTIVADO`. Se documenta como ambigüedad a estandarizar por el equipo de arquitectura.

## PENDIENTES DE DESARROLLO
| Subcaso | Elemento / Endpoint | Contrato Esperado | Responsable |
|---|---|---|---|
| TC-M04-053 | Inyección de fallas en repositorio | Toxiproxy / Chaos injection hook en capa repository | DevOps / Backend Lead |
| TC-M04-053 | Endpoint de estado del buffer de auditoría | GET /prediccion/auditoria/buffer-status -> 200 OK | Backend Lead (Módulo 4) |
