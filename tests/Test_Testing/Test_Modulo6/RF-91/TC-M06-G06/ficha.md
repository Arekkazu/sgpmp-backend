# TC-M06-G06 — RF-91

Fuente: `RF-91_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-06 (TC-91-031 a TC-91-034). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Verificación de los registros de auditoría de los módulos fuente (Proceso 5, 6 y 7): RF-52 para IOT_DIRECTO y REGISTRO_MANUAL, RF-63 para IOT_DIRECTO, y RF-73 vinculado al activo y cubriendo la fecha del evento para EVENTO_SANITARIO.

### TC-91-031 — Asiento REGISTRO_MANUAL sin id_auditoria_m02 en RF-52
- **Tipo:** Negativo / integración · **Prioridad:** Alta · **Ejecutable:** Sí (sobre líneas REGISTRO_MANUAL existentes).
- **Pasos:** «TC-91-031..034 La cadena registra la verificacion de las auditorias fuente (RF-52, RF-63, RF-73)».
- **Esperado (matriz):** CADENA_INCOMPLETA.

### TC-91-032 — Asiento IOT_DIRECTO sin id_auditoria_m03 en RF-63
- **Tipo:** Negativo / integración · **Prioridad:** Alta · **Ejecutable:** Sí (sobre líneas IOT_DIRECTO existentes).
- **Pasos:** «TC-91-031..034 La cadena registra la verificacion de las auditorias fuente (RF-52, RF-63, RF-73)».
- **Esperado (matriz):** CADENA_INCOMPLETA.

### TC-91-033 — Auditoría RF-73 existente pero que NO cubre la fecha del evento sanitario
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Bloqueado: requiere una auditoría RF-73 con fecha manipulada.
- **Pasos:** «TC-91-031..034 La cadena registra la verificacion de las auditorias fuente (RF-52, RF-63, RF-73)».
- **Esperado (matriz):** CADENA_INCOMPLETA.

### TC-91-034 — Auditoría RF-73 vinculada a un activo biológico distinto del asiento
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Bloqueado: requiere una auditoría RF-73 de otro activo.
- **Pasos:** «TC-91-031..034 La cadena registra la verificacion de las auditorias fuente (RF-52, RF-63, RF-73)».
- **Esperado (matriz):** CADENA_INCOMPLETA.

## Ejecución automatizada
- Colección: `tc_m06_g06.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G06.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Las peticiones marcadas **[escritura]** crean o cambian datos: corren **dentro del sandbox transaccional de TEST** (cabecera X-Test-Run-Id) y al final se revierten con DELETE /test-control/runs/{id}. Requieren `--env-var permitir_escritura=SI` y `--env-var sandbox_secret=...` (secreto que da el DBA); la colección comprueba que el sandbox esté activo y, si no, omite esas peticiones.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
