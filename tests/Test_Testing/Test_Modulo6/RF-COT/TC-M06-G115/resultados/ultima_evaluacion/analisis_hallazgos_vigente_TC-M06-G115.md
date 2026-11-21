# TC-M06-G115 — Análisis de hallazgos vigente

**Resultado:** APROBADO 2/2

## Subcasos

| Subcaso | Estado | Evidencia |
|---|---|---|
| TC-M06-44 Contador | APROBADO | cotización 9 · HTTP 201 · evidencia_ejecucion_tc44_contador_TC-M06-G115.json |
| TC-M06-44 Administrador | APROBADO | cotización 10 · HTTP 201 · evidencia_ejecucion_tc44_administrador_TC-M06-G115.json |
| TC-M06-45 Productor | APROBADO | HTTP 403 ACCESO_DENEGADO · evidencia histórica primera evaluación |

## Hallazgos

- Contador (usuario 141): registró cotización 9 sobre activo 1569; referencia 3760000.0000; VR sin cambio; evento COTIZACION_REGISTRADA.
- Administrador (usuario 137): registró cotización 10 sobre el mismo activo (segunda cotización permitida por el caso de uso); cotización 9 intacta; período 220 ABIERTO.
- Productor: denegado en evaluación histórica 2026-11-08; sin incremento de cotizaciones ni eventos.
- Cotizaciones 6 y 7 (#1022) no fueron alteradas.

## SQL

Verificaciones de la ejecución positiva vía GET API. SQL directo no disponible en el entorno de ejecución.

## Conclusión

G115 queda **APROBADO 2/2**. Ambos subcasos (TC-M06-44 y TC-M06-45) están respaldados por evidencia.
