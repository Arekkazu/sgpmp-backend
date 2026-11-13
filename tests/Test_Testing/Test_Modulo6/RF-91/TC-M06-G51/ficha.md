# TC-M06-G51 — RF-91

Fuente: `RF-91_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-05 (TC-91-027 a TC-91-030). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Verificación del precio de referencia y su fuente (Proceso 8, FA-2): CADENA_COMPLETA con MERCADO_ACTIVO o UPRA, y con ESTIMADA solo si existe aprobación registrada del Contador en RF-89; sin esa aprobación, CADENA_INCOMPLETA con alerta.

### TC-91-027 — Precio de referencia con fuente MERCADO_ACTIVO
- **Tipo:** Funcional / positivo · **Prioridad:** Alta · **Ejecutable:** Sí (sobre líneas con precio MERCADO_ACTIVO).
- **Pasos:** «TC-91-027..030 Nivel 3: precio documentado y fuente ESTIMADA con aprobacion».
- **Esperado (matriz):** CADENA_COMPLETA.

### TC-91-028 — Precio de referencia con fuente UPRA
- **Tipo:** Funcional / positivo · **Prioridad:** Media · **Ejecutable:** Sí (sobre líneas con precio UPRA).
- **Pasos:** «TC-91-027..030 Nivel 3: precio documentado y fuente ESTIMADA con aprobacion».
- **Esperado (matriz):** CADENA_COMPLETA.

### TC-91-029 — Precio con fuente ESTIMADA y aprobación registrada del Contador en RF-89
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí (sobre líneas con precio ESTIMADA).
- **Pasos:** «TC-91-027..030 Nivel 3: precio documentado y fuente ESTIMADA con aprobacion».
- **Esperado (matriz):** CADENA_COMPLETA.

### TC-91-030 — Precio con fuente ESTIMADA sin aprobación del Contador
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Sí (sobre líneas con precio ESTIMADA).
- **Pasos:** «TC-91-027..030 Nivel 3: precio documentado y fuente ESTIMADA con aprobacion».
- **Esperado (matriz):** CADENA_INCOMPLETA y alerta para que el Contador apruebe el precio en RF-89.

## Ejecución automatizada
- Colección: `tc_m06_g51.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G51.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Las peticiones marcadas **[escritura]** crean o cambian datos: corren **dentro del sandbox transaccional de TEST** (cabecera X-Test-Run-Id) y al final se revierten con DELETE /test-control/runs/{id}. Requieren `--env-var permitir_escritura=SI` y `--env-var sandbox_secret=...` (secreto que da el DBA); la colección comprueba que el sandbox esté activo y, si no, omite esas peticiones.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
