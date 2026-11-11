# TC-M06-G04 — RF-91

Fuente: `RF-91_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-04 (TC-91-019 a TC-91-026). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Coherencia semántica de la cadena (CA-7, Restricción 6, Proceso 9): el evento debe ser el que generó la variación en RF-86, las lecturas deben pertenecer al activo del asiento con la escala correcta, y las fechas de lectura, evento y variación deben ser consistentes entre sí.

### TC-91-019 — Asiento cuyo id_evento_biologico corresponde al evento que generó la variación en RF-86
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí (sobre líneas existentes).
- **Pasos:** «TC-91-019/021 Cadena verificada con evento y lecturas del mismo activo».
- **Esperado (matriz):** CADENA_COMPLETA.

### TC-91-020 — Asiento cuyo id_evento_biologico existe pero NO corresponde al evento que generó la variación en RF-86
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Parcial: requiere sembrar una línea con evento ajeno; se revisan las pendientes existentes.
- **Pasos:** «TC-91-020/022 Evento ajeno o lecturas de otro activo no se dan por buenos».
- **Esperado (matriz):** CADENA_INCOMPLETA.

### TC-91-021 — Lecturas IoT que pertenecen al activo biológico del asiento
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí (sobre líneas existentes).
- **Pasos:** «TC-91-019/021 Cadena verificada con evento y lecturas del mismo activo».
- **Esperado (matriz):** CADENA_COMPLETA.

### TC-91-022 — Lecturas IoT que pertenecen a otro bovino distinto del referenciado en el asiento
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Parcial: requiere lecturas de otro activo sembradas.
- **Pasos:** «TC-91-020/022 Evento ajeno o lecturas de otro activo no se dan por buenos».
- **Esperado (matriz):** CADENA_INCOMPLETA.

### TC-91-023 — Asiento sobre activo POBLACIONAL cuya lectura ambiental procede de un galpón distinto
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Bloqueado: requiere un activo POBLACIONAL con lectura de otro galpón; el código no compara galpón.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** CADENA_INCOMPLETA.

### TC-91-024 — Lectura IoT con fecha posterior al evento biológico que sustenta
- **Tipo:** Negativo / valores límite · **Prioridad:** Alta · **Ejecutable:** Bloqueado: requiere datos con fechas manipuladas; el código acepta lecturas hasta 1 h después del evento.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** detección de incoherencia temporal.

### TC-91-025 — Evento biológico con fecha posterior a la variación de valor razonable
- **Tipo:** Negativo / valores límite · **Prioridad:** Alta · **Ejecutable:** Bloqueado: requiere datos con fechas manipuladas; el código no compara evento contra variación.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** detección de incoherencia temporal.

### TC-91-026 — Lectura, evento y variación con el mismo timestamp exacto
- **Tipo:** Valores límite · **Prioridad:** Media · **Ejecutable:** Bloqueado: el RF no define el comportamiento esperado.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** un comportamiento definido y documentado.

## Ejecución automatizada
- Colección: `tc_m06_g04.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G04.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Las peticiones marcadas **[escritura]** crean o cambian datos: corren **dentro del sandbox transaccional de TEST** (cabecera X-Test-Run-Id) y al final se revierten con DELETE /test-control/runs/{id}. Requieren `--env-var permitir_escritura=SI` y `--env-var sandbox_secret=...` (secreto que da el DBA); la colección comprueba que el sandbox esté activo y, si no, omite esas peticiones.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
