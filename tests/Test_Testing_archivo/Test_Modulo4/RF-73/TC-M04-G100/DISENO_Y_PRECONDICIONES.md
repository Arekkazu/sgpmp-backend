# DISENO Y PRECONDICIONES — TC-M04-G100

## Identificación del Caso
- Caso: TC-M04-G100
- Módulo: Módulo 4 — Predicción e IA (RF-73: Auditoría de eventos de predicción)
- Foco: Aislamiento del Subsistema de Auditoría y Retención Mínima (>= 365 días)
- Herramienta: Postman / Newman

## Subcasos Cubiertos
1. TC-M04-306: Aislamiento de auditoría — Procesos de negocio (inferencia RF-66, OTA RF-70, versionado RF-71) continúan operando sin interrupción ante una caída del bus/repositorio de auditoría (RF-63).
2. TC-M04-307: Política de retención de registros — Garantía de retención legal y operativa mínima >= 365 días y prohibición de purgas anticipadas (< 365 días).

## Diagnóstico y Mapeo Técnico
- Endpoint de verificación de salud: GET /health.
- Endpoint de configuración esperado: GET /prediccion/auditoria/configuracion.
- Mecanismo de persistencia en código: `src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py`.
- Mecanismo de contingencia existente: `_escribir_fallback(data)` genera un log local `audit_fallback_M04_<YYYYMMDD>.log` cuando la base de datos no responde, evitando bloquear al invocador de negocio.

## Limitaciones Críticas y Fase Separada
1. TC-M04-306 (Aislamiento ante caída):
   - Detener intencionalmente el servicio o componente de auditoría no es una operación viable por API en el entorno compartido de TEST.
   - Requiere un entorno de caos/infraestructura para matar el proceso de auditoría o bloquear el puerto de base de datos mientras se ejecutan inferencias de predicción.
2. TC-M04-307 (Retención >= 365 días):
   - La retención suele estar delegada a políticas de backup, lifecycle en S3/MinIO o particiones de base de datos con TTL.
   - No existe actualmente un endpoint de administración que exponga el parámetro `retention_days` o un comando REST de purga de auditoría.
   - Se diseña contra el contrato esperado: verificación de política >= 365 días y rechazo de cualquier purga inferior a un año.

## FASE SEPARADA — AISLAMIENTO DE INFRAESTRUCTURA
- Requisito: Caída forzada del bus/repositorio de auditoría.
- Protocolo:
  1. Detener el contenedor de PostgreSQL o bloquear la tabla `eventos_auditoria_m04`.
  2. Disparar petición de inferencia en `POST /prediccion/inferencias/`.
  3. Verificar que la inferencia responde 200 OK con el resultado del modelo (el proceso de negocio no se aborta).
  4. Verificar que se activa el mecanismo `_escribir_fallback()` escribiendo en disco el archivo de contingencia.

## Hallazgos y Discrepancias
- El código backend actual ya implementa el aislamiento arquitectónico mediante `_escribir_fallback`, evitando propagar excepciones de persistencia hacia el caso de uso principal.
- Falta formalizar el endpoint administrativo de consulta de retención `GET /prediccion/auditoria/configuracion`.

## PENDIENTES DE DESARROLLO
| Subcaso | Elemento / Endpoint | Contrato Esperado | Responsable |
|---|---|---|---|
| TC-M04-306 | Modo de prueba degradado / Flag de auditoría | Header o flag para simular fallo de auditoría en pruebas de integración | DevOps / Backend Lead |
| TC-M04-307 | Endpoint de configuración de retención | GET /prediccion/auditoria/configuracion -> { retention_days: 365 } | Backend Lead (M04) |
| TC-M04-307 | Bloqueo estricto de purga | Prohibición explícita de DELETE o purgas con antigüedad < 365 días | Backend Lead / DBA |
