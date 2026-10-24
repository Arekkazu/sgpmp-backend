# Narrativa de Diseño y Ejecución — TC-M04-G101

## Resumen Ejecutivo
El grupo TC-M04-G101 evalúa la postura de seguridad de transporte de datos en tránsito conforme a OWASP ASVS V9 (Comunicaciones Seguras) aplicado a los servicios de auditoría del Módulo 4.

## División Parte A y Parte B (Fase Separada)
1. Parte A (HTTP Redirect / HSTS): Implementada en la suite Newman. Realiza peticiones deliberadas por HTTP plano verificando que el reverse proxy o API Gateway fuerce el redireccionamiento (301/308) o rechace la solicitud insegura. Adicionalmente, verifica la inyección de la directiva `Strict-Transport-Security`.
2. Parte B (testssl.sh — FASE SEPARADA): Dado que el análisis exhaustivo de suites criptográficas, curvas elípticas y versiones de protocolo requiere binarios especializados (OpenSSL / testssl.sh) y toma varios minutos de escaneo de red, se documenta como Fase Separada. El comando y script de automatización quedan preparados en `ejecutar_tc_m04_g101.ps1`.
