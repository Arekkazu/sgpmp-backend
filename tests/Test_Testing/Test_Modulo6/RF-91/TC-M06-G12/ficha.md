# TC-M06-G12 — RF-91

Fuente: `RF-91_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-12 (TC-91-064 a TC-91-068). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Rendimiento y retención (RNF-91-01 a RNF-91-04): verificación individual en ≤ 2 segundos; verificación masiva del período en ≤ 5 minutos para hasta 1.000 activos, medida también con la composición de tipos más costosa; 50 consultas simultáneas del API de auditores sin degradación; y cadena de períodos cerrados disponible tras simular la retención de 10 años.

### TC-91-064 — Medir la verificación individual de un asiento
- **Tipo:** Rendimiento · **Prioridad:** Alta · **Ejecutable:** Parcial: se mide la consulta de la cadena; el API no verifica una línea sola.
- **Pasos:** «TC-91-064 Consulta de la cadena de una linea en <= 2 s (10 mediciones)».
- **Esperado (matriz):** que se complete en ≤ 2 segundos.

### TC-91-065 — Ejecutar la verificación masiva de todos los asientos del período antes del cierre
- **Tipo:** Rendimiento · **Prioridad:** Alta · **Ejecutable:** Sí, con escritura, pero con el volumen que tenga TEST (no 1.000 activos).
- **Pasos:** «TC-91-065/068 Verificacion masiva del periodo ABIERTO en <= 5 min [escritura]».
- **Esperado (matriz):** ≤ 5 minutos para períodos de hasta 1.000 activos.

### TC-91-066 — Ejecutar 50 consultas simultáneas sobre el API de trazabilidad para auditores externos
- **Tipo:** Rendimiento · **Prioridad:** Alta · **Ejecutable:** Requiere k6 y visto bueno: 50 consultas simultáneas sobre el TEST compartido.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** que no haya degradación de rendimiento.

### TC-91-067 — Consultar la cadena de un asiento de período cerrado tras simular el envejecimiento conforme a la retención de 10 años
- **Tipo:** No funcional / retención · **Prioridad:** Alta · **Ejecutable:** Bloqueado: requiere simular 10 años de antigüedad en la base de datos.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** disponibilidad íntegra.

### TC-91-068 — Ejecutar la verificación masiva sobre un período con mezcla de los 5 tipos de evidencia
- **Tipo:** Rendimiento · **Prioridad:** Alta · **Ejecutable:** Sí, con escritura, con la mezcla de tipos que tenga TEST.
- **Pasos:** «TC-91-065/068 Verificacion masiva del periodo ABIERTO en <= 5 min [escritura]».
- **Esperado (matriz):** que el tiempo total respete la cota con la composición más costosa.

## Ejecución automatizada
- Colección: `tc_m06_g12.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G12.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Las peticiones marcadas **[escritura]** crean o cambian datos: corren **dentro del sandbox transaccional de TEST** (cabecera X-Test-Run-Id) y al final se revierten con DELETE /test-control/runs/{id}. Requieren `--env-var permitir_escritura=SI` y `--env-var sandbox_secret=...` (secreto que da el DBA); la colección comprueba que el sandbox esté activo y, si no, omite esas peticiones.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
