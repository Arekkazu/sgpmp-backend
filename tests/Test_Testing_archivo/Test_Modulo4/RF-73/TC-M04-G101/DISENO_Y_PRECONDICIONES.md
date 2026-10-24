# DISENO Y PRECONDICIONES — TC-M04-G101

## Identificación del Caso
- Caso: TC-M04-G101
- Módulo: Módulo 4 — Predicción e IA (RF-73: Auditoría de eventos de predicción)
- Foco: Seguridad de Transporte (TLS 1.2+, Redirección HTTP->HTTPS, ASVS V9)
- Herramienta: Postman / Newman (Parte A) + testssl.sh (Parte B — Fase Separada)

## Subcasos Cubiertos
1. TC-M04-308: Exigencia de transporte seguro TLS en todas las comunicaciones del subsistema de auditoría:
   - Redirección obligatoria o rechazo de tráfico HTTP plano (301, 308, 400, 426).
   - Presencia de encabezados Strict-Transport-Security (HSTS).
   - Inhabilitación de protocolos y cifrados obsoletos (TLS 1.0, TLS 1.1, suites débiles).

## Arquitectura de Ejecución: División Parte A / Parte B
El subcaso se estructura formalmente en dos etapas:

### Parte A — Ejecutable en Newman / CI
- Invocación deliberada sobre `http://api.inmero.co/back-sigab-test/` (puerto 80 plano) para los endpoints clave de auditoría:
  - `GET /prediccion/auditoria`
  - `GET /prediccion/auditoria/{id_evento}`
  - `GET /prediccion/auditoria/exportar`
- Aserta:
  - Ninguna respuesta entrega datos sensibles en texto plano sin redirección previa (status nunca 200 directo sin HSTS/upgrade).
  - Presencia obligatoria de cabecera HSTS (`Strict-Transport-Security: max-age=...`) en las respuestas HTTPS.

### Parte B — FASE SEPARADA (testssl.sh)
- Requisito: Herramienta externa `testssl.sh` ejecutada contra el endpoint SSL público.
- Comando:
  `testssl.sh --severity HIGH --protocols --cipher-per-proto https://api.inmero.co/back-sigab-test/`
- Asertos esperados en auditoría de seguridad:
  - Protocolos TLS 1.0 y 1.1: NOT offered / disabled.
  - Protocolos TLS 1.2 y TLS 1.3: offered / enabled.
  - Cifrados vulnerables (RC4, DES, 3DES, EXPORT, NULL, anon): NOT offered.
  - Certificado SSL válido y no revocado.

## PENDIENTES DE DESARROLLO
| Subcaso | Elemento / Endpoint | Contrato Esperado | Responsable |
|---|---|---|---|
| TC-M04-308 | Escaneo criptográfico testssl.sh | Reporte formal sin vulnerabilidades de transporte (TLS 1.2+, sin cifrados débiles) | DevOps / SecOps |
| TC-M04-308 | HSTS estricto | Cabecera `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` | DevOps / Infraestructura |
