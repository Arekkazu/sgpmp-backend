# Narrativa de Diseño y Ejecución — TC-M04-G097

## Resumen Ejecutivo
El grupo TC-M04-G097 evalúa la capacidad de resiliencia del pipeline de auditoría de predicción ante fallos transitorios en el repositorio de base de datos.
El diseño asegura que el sistema aplique reintentos transparentes antes de activar contingencias o reportar pérdidas de trazabilidad.

## FASE SEPARADA — RESILIENCIA
Por definición arquitectónica y de seguridad operativa, una prueba de inyección de fallos de persistencia no debe ejecutarse en el ambiente compartido de TEST vía API pública.
La suite actual incluye:
1. Verificación del estado nominal del subsistema mediante consulta autenticada.
2. Comprobación de que no existan eventos espurios de falla de persistencia (`AUDITORIA_FALLA_PERSISTENCIA` o `AUDITORIA_FALLBACK_ACTIVADO`) generados indebidamente en corridas normales.
3. Teardown transaccional garantizado con rollback en sandbox.
La prueba de inyección destructiva queda delegada a la fase de pruebas de caos en infraestructura aislada.

## Hallazgos de Dominio
- Ambigüedad entre los eventos de auditoría `AUDITORIA_FALLA_PERSISTENCIA` y `AUDITORIA_FALLBACK_ACTIVADO`. Se recomienda unificar la máquina de estados de contingencia del subsistema de auditoría.
