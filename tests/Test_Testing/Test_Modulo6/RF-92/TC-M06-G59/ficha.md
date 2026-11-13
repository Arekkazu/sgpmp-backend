# TC-M06-G59 — RF-92

Fuente: `RF-92_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-01 (TC-92-001 a TC-92-007). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Generación del informe en estado BORRADOR con todas las secciones obligatorias (CA-1, CA-5): las 9 secciones de los Párrafos 40 a 57 presentes, versión asignada, presentación al Contador en M08, informe filtrado por especie sin omitir secciones, y estado BORRADOR no descargable.

### TC-92-001 — Generar el informe para un período CERRADO con datos consolidados
- **Tipo:** Funcional / positivo · **Prioridad:** Crítica · **Ejecutable:** Sí, con escritura (o sobre un BORRADOR existente); la presentación en M08 no se puede comprobar.
- **Pasos:** «TC-92-001 Generar informe sobre el periodo CERRADO [escritura]»; «TC-92-001/004/007 Informe BORRADOR con las 9 secciones».
- **Esperado (matriz):** estado BORRADOR, versión asignada y presentación al Contador en M08.

### TC-92-002 — Verificar la presencia de la sección [Párr. 41] descripción de activos por especie y categoría
- **Tipo:** Funcional / cumplimiento · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** sin petición automatizada (ver Ejecutable).

### TC-92-003 — Verificar la presencia y contenido de la sección [Párr. 48] precios de referencia por especie, fecha y fuente
- **Tipo:** Funcional / cumplimiento · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** sin petición automatizada (ver Ejecutable).

### TC-92-004 — Verificar que las 9 secciones de los Párrafos 40 a 57 están presentes en el informe generado
- **Tipo:** Funcional / cumplimiento · **Prioridad:** Crítica · **Ejecutable:** Sí.
- **Pasos:** «TC-92-001/004/007 Informe BORRADOR con las 9 secciones».

### TC-92-005 — Generar el informe filtrado por especie
- **Tipo:** Funcional / positivo · **Prioridad:** Alta · **Ejecutable:** No aplica: el API no recibe filtro_especie.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** que incluya solo los activos de esa especie manteniendo todas las secciones.

### TC-92-006 — Verificar que la sección [Párr. 49] de riesgos está siempre presente con fuente trazable
- **Tipo:** Funcional / cumplimiento · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** sin petición automatizada (ver Ejecutable).

### TC-92-007 — Verificar que el informe recién generado queda en estado BORRADOR y no es descargable
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Sí.
- **Pasos:** «TC-92-001/004/007 Informe BORRADOR con las 9 secciones»; «TC-92-007 Un BORRADOR no se descarga».

## Ejecución automatizada
- Colección: `tc_m06_g59.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G59.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Las peticiones marcadas **[escritura]** crean o cambian datos: corren **dentro del sandbox transaccional de TEST** (cabecera X-Test-Run-Id) y al final se revierten con DELETE /test-control/runs/{id}. Requieren `--env-var permitir_escritura=SI` y `--env-var sandbox_secret=...` (secreto que da el DBA); la colección comprueba que el sandbox esté activo y, si no, omite esas peticiones.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
