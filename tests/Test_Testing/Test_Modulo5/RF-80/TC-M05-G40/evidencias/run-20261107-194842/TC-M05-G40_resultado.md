# Resultado de Prueba: TC-M05-G40
## Resiliencia ante Caída de Auditoría, Cola y Latencia (RF-80)

- **ID Caso:** TC-M05-G40 (TC-M05-095 / Agrupado: TC-M05-031)
- **Veredicto:** Rechazado (3/4 OK, 1 Fallas)
- **Fecha:** 2026-11-07 19:48:55 (America/Bogota)
- **Duración:** 11.35 s

### Métricas de Latencia Observadas (POST /suministros/costeo-directo)
- **Muestras registradas:** 20
- **Latencia Mínima:** 128.68 ms
- **Latencia Mediana (p50):** 140.09 ms
- **Latencia Percentil 95 (p95):** 250.02 ms
- **Latencia Máxima:** 250.02 ms

### Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
| 1 | T00 Admin Conteo inicial, creacion de activo y muestreo de latencia (20 peticiones) | HTTP 200 en auditoria base, HTTP 201 en activo QA y 20 suministros exitosos con medicion de latencia | HTTP 200 en auditoria base, HTTP 201 en activo QA y 20 suministros exitosos con medicion de latencia | OK |
| 2 | A01 Presencia de cola persistente M05-M12 con capacidad para 100.000 eventos (TC-M05-095 / 031) | Cola persistente o outbox implementada para desacoplamiento y resiliencia ante caidas de M12 (CA-9 / RNF-08) | AssertionError: DEFECTO_PRODUCTO (RF-80 Restr. 3 / CA-9 / RNF-08 / TC-M05-095 / 031): La especificacion exige una cola persistente entre M05 y M12 con capacidad configurable de hasta 100.000 eventos para garantizar la resiliencia ante caidas de M12. El backend carece de cola/buffer persistente o tabla outbox (la persistencia es directa y sincronica en modulo5.auditorias_suministros). | FALLA |
| 3 | T98 Admin Cierre ordenado de sandbox Administrador y rollback | HTTP 200 con confirmacion de rollback exitoso | HTTP 200 con confirmacion de rollback exitoso | OK |
| 4 | T99 Admin Verificacion de inocuidad tras corrida Administrador | Conteo final de auditoria identico al conteo inicial | Conteo final de auditoria identico al conteo inicial | OK |

### Diagnóstico de Fallas (Defecto de Producto)
- **Falla en A01 (TC-M05-095 / 031 - RF-80 Restr. 3 / CA-9 / RNF-08):**
  La especificación exige una cola persistente o buffer de desacoplamiento entre M05 y M12 con capacidad configurable de hasta 100.000 eventos para garantizar la resiliencia ante caídas del repositorio de auditoría o de M12.
  En la arquitectura actual de backend, no existe cola en memoria persistente, broker externo (RabbitMQ/Kafka) ni tabla outbox; la persistencia es directa y sincrónica en `modulo5.auditorias_suministros`.

### Cobertura No Ejecutada Declarada
- **Inyección de fallas en M12 / Caída forzada de repositorio:** No ejecutable en sandbox sin alterar el cluster de BD o servicios externos.
- **Alertas de saturación de cola al 90% y 100%:** No ejecutable debido a la inexistencia de la cola/buffer persistente.
- **Política de retención FIFO de 48 horas:** No ejecutable debido a la inexistencia de la cola/buffer persistente.
- **Límite de degradación <= 50 ms respecto a línea base sin auditoría:** No medible de forma comparativa, ya que en el producto actual la auditoría está fuertemente acoplada en la transacción de suministro y no existe un switch o baseline sin auditoría.
