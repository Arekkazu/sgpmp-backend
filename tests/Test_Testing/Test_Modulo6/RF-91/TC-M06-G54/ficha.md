# TC-M06-G54 — RF-91

Fuente: `RF-91_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-08 (TC-91-039 a TC-91-042, TC-91-072). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Distinción entre eslabón ausente e indisponibilidad del módulo fuente (Restricción 7): si RF-62, RF-52 o RF-63 no responden por timeout, error 5xx o fallo de red, el asiento permanece en VERIFICACION_PENDIENTE y el intento fallido queda en RF-94; PENDIENTE_TRAZABILIDAD no se asigna por indisponibilidad temporal.

### TC-91-039 — RF-62 no responde por timeout durante la verificación
- **Tipo:** Negativo / resiliencia · **Prioridad:** Crítica · **Ejecutable:** Bloqueado: la verificación consulta la misma base de datos; no hay servicio remoto que simular (WireMock/Toxiproxy) y una caída real en TEST está prohibida.
- **Pasos:** «TC-91-039..041 El estado VERIFICACION_PENDIENTE existe en el contrato».
- **Esperado (matriz):** que el asiento permanezca en VERIFICACION_PENDIENTE y no pase a PENDIENTE_TRAZABILIDAD.

### TC-91-040 — RF-52 devuelve HTTP 503 durante la verificación
- **Tipo:** Negativo / resiliencia · **Prioridad:** Crítica · **Ejecutable:** Bloqueado: misma razón.
- **Pasos:** «TC-91-039..041 El estado VERIFICACION_PENDIENTE existe en el contrato».
- **Esperado (matriz):** VERIFICACION_PENDIENTE y registro del intento fallido.

### TC-91-041 — RF-63 inalcanzable por fallo de red
- **Tipo:** Negativo / resiliencia · **Prioridad:** Alta · **Ejecutable:** Bloqueado: misma razón.
- **Pasos:** «TC-91-039..041 El estado VERIFICACION_PENDIENTE existe en el contrato».
- **Esperado (matriz):** VERIFICACION_PENDIENTE.

### TC-91-042 — Comprobar que el intento fallido por indisponibilidad queda registrado en RF-94 con la causa de infraestructura
- **Tipo:** Auditoría · **Prioridad:** Alta · **Ejecutable:** Bloqueado: no se puede provocar la falla; solo se comprueba que la consulta existe.
- **Pasos:** «TC-91-042 Intentos fallidos por infraestructura en la auditoria».

### TC-91-072 — Verificar la cadena de un asiento inmediatamente después de registrar el hecho en Activos biológicos, antes de que haya corrido el proceso de fondo
- **Tipo:** Negativo / resiliencia · **Prioridad:** Crítica · **Ejecutable:** Manual: registrar un hecho en Activos biológicos y verificar a los 0, 30, 60 y 90 s (con escritura).
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** que no se declare CADENA_INCOMPLETA de forma prematura: la medición tarda hasta 1 minuto y el Contador puede forzarla con «Calcular medición ahora».

## Ejecución automatizada
- Colección: `tc_m06_g54.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G54.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
