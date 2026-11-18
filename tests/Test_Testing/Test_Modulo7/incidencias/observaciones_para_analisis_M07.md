# Observaciones de RF-95 y RF-101 para Análisis (no son incidencias)

Resultados de las pruebas TC-M07-G001 a G006 y G042 a G047 contra TEST (18-nov-2026) que **no se publican como incidencia** porque el comportamiento coincide con una decisión de diseño documentada en el código o con una tolerancia razonable. Se dejan por escrito para que Análisis confirme o actualice el RF.

| # | Caso | RF | Observación | Evidencia | Propuesta |
|---|---|---|---|---|---|
| O-1 | TC-M07-G003 (TC-95-010) | RF-95 5.4 / FA-3 | El token de canal se acepta hasta `exp + 30 s`: usado a los 310 s (TTL 300 s) respondió 200 y a los 340 s respondió 401. `verify_token_canal` aplica la tolerancia de reloj `JWT_LEEWAY_SECONDS` (30 s por defecto). El RF no la menciona. | `Resultados/resultado_TC-M07-G003.html` (corrida con `-Ttl`) | Documentar los 30 s de tolerancia en RF-95 y RF-SSO02. |
| O-2 | TC-M07-G046 (TC-101-013) | RF-101 (Descripción) | `GET /integraciones/agrofusion/roles` responde 200 **sin token**, solo con id y nombre de cada rol. El código lo documenta: «AgroFusion lo llama sin autenticación, así que se limita por IP» (30 por minuto). RF-101 dice que los demás endpoints autentican con el token de canal. | `Resultados/resultado_TC-M07-G046.html` | Registrar en el RF que `GET_ROLES` es público por contrato de AgroFusion. |
| O-3 | TC-M07-G004 (TC-95-013) | RF-95 FA-5 | Datos de preparación indicaban `ACCESO_DENEGADO` para el Productor sin permiso. El Gateway responde `PERMISO_INSUFICIENTE`, que es lo que pide el RF (el caso aprobó). `ACCESO_DENEGADO` corresponde a la vista previa. | `Resultados/resultado_TC-M07-G004.html` | Sin acción; aclarar en la guía de datos de prueba. |
| O-4 | TC-M07-G001/G005/G006 | RF-95 / RF-98 | La versión ACTIVA del contrato en TEST cambió durante la semana (hoy 3.0; 2.1 DEPRECADO; 2.0 INACTIVO) por las pruebas de RF-98. Las colecciones leen la versión activa al iniciar. | `evidencias/preflight.json` de cada incidencia | Coordinar con quien ejecuta RF-98 para no cambiar el contrato durante las corridas de RF-95. |

## Fuera de alcance de esta ejecución

- RF-95: RF-102 caído (CA-10), errores 5xx sin información interna (CA-11), delegación (CA-12), `TAMANO_EXCEDIDO` (20 MB), tiempo agotado (FA-10), `TRAZABILIDAD_INCOMPLETA`, `CONTRATO_NO_ACTIVO` y los requisitos de rendimiento. Requieren dobles de prueba o inyección de fallos (no disponibles en TEST).
- RF-101: comparación en tiempo constante (5.3), validación ≤ 20 ms (RNF-101.2), consistencia entre instancias (RNF-101.3) y rollback cuando falla la auditoría. TC-101-016 (migración de AGROFUSION sin variables de entorno) es manual.
