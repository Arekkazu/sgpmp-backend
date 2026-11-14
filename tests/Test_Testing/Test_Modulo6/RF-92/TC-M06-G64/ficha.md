# TC-M06-G64 — RF-92

Fuente: `RF-92_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-06 (TC-92-030 a TC-92-036). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Entradas manuales del Contador y sección de riesgos (Párr. 53, 55 y 49, CA-5): compromisos y activos pignorados reflejados íntegros, declaracion_sin_novedad generando la declaración expresa de inexistencia, rechazo de las combinaciones contradictorias, y sección de riesgos siempre presente con sus tres categorías y fuente trazable incluso sin eventos.

### TC-92-030 — Ingresar compromisos vigentes y verificar que se reflejan íntegros en la sección [Párr. 53]
- **Tipo:** Funcional / positivo · **Prioridad:** Alta · **Ejecutable:** Sí, con escritura.
- **Pasos:** «TC-92-030/031 Generar con compromisos y pignorados [escritura]»; «TC-92-030 El compromiso se refleja integro».

### TC-92-031 — Ingresar activos pignorados y verificar que se reflejan íntegros en la sección [Párr. 55]
- **Tipo:** Funcional / positivo · **Prioridad:** Alta · **Ejecutable:** Sí, con escritura (mismo patrón que TC-92-030).
- **Pasos:** «TC-92-030/031 Generar con compromisos y pignorados [escritura]».

### TC-92-032 — Enviar declaracion_sin_novedad = true con ambos arrays vacíos
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí (sobre el informe existente).
- **Pasos:** «TC-92-032/035/036 Declaracion y riesgos en el informe existente».
- **Esperado (matriz):** que las secciones se generen con la declaración expresa de inexistencia.

### TC-92-033 — Enviar ambos arrays vacíos SIN declaracion_sin_novedad
- **Tipo:** Negativo / validación · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** «TC-92-033 Sin elementos ni declaracion -> 422 (no escribe)».
- **Esperado (matriz):** un comportamiento definido: rechazo o solicitud de la declaración.

### TC-92-034 — Enviar declaracion_sin_novedad = true junto con elementos en los arrays
- **Tipo:** Negativo / validación · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** «TC-92-034 Declaracion sin novedad junto con compromisos -> rechazo».
- **Esperado (matriz):** rechazo por contradicción.

### TC-92-035 — Verificar la sección de riesgos con eventos en las tres categorías: climáticos, sanitarios y de mercado, cada uno con su fuente identificada
- **Tipo:** Funcional / integración · **Prioridad:** Alta · **Ejecutable:** Sí (sobre el informe existente).
- **Pasos:** «TC-92-032/035/036 Declaracion y riesgos en el informe existente».

### TC-92-036 — Período sin eventos en una o en ninguna categoría de riesgo
- **Tipo:** Funcional / flujo alterno · **Prioridad:** Alta · **Ejecutable:** Sí (sobre el informe existente).
- **Pasos:** «TC-92-032/035/036 Declaracion y riesgos en el informe existente».
- **Esperado (matriz):** que las categorías se declaren como sin eventos, sin desaparecer de la sección.

## Ejecución automatizada
- Colección: `tc_m06_g64.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G64.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Las peticiones marcadas **[escritura]** crean o cambian datos: corren **dentro del sandbox transaccional de TEST** (cabecera X-Test-Run-Id) y al final se revierten con DELETE /test-control/runs/{id}. Requieren `--env-var permitir_escritura=SI` y `--env-var sandbox_secret=...` (secreto que da el DBA); la colección comprueba que el sandbox esté activo y, si no, omite esas peticiones.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
