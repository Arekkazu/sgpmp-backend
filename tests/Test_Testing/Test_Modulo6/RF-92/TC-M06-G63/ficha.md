# TC-M06-G63 — RF-92

Fuente: `RF-92_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-05 (TC-92-025 a TC-92-029). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Precios de referencia y activos valorados por costo (Párr. 48 y 54, FA-3): la sección de precios lista especie, fecha, fuente y evidencia documental de RF-89; los activos sin mercado activo se incluyen con descripción, razón de imposibilidad y rango de RF-88 con advertencia visible; y las ausencias en el RF fuente se reflejan en lugar de omitirse.

### TC-92-025 — Verificar que la sección [Párr. 48] lista especie, fecha, fuente y evidencia documental tal como están registradas en RF-89
- **Tipo:** Funcional / cumplimiento · **Prioridad:** Alta · **Ejecutable:** Sí (sobre el informe APROBADO existente).
- **Pasos:** «TC-92-025..029 Precios de referencia y activos al costo».

### TC-92-026 — Precio de RF-89 sin evidencia documental registrada
- **Tipo:** Negativo / integración · **Prioridad:** Alta · **Ejecutable:** Sí, si hay precios sin evidencia.
- **Pasos:** «TC-92-025..029 Precios de referencia y activos al costo».
- **Esperado (matriz):** que el informe lo refleje y no lo omita en silencio.

### TC-92-027 — Activo sin mercado activo valorado por costo
- **Tipo:** Funcional / flujo alterno · **Prioridad:** Alta · **Ejecutable:** Sí, si hay activos al costo.
- **Pasos:** «TC-92-025..029 Precios de referencia y activos al costo».
- **Esperado (matriz):** la sección [Párr. 54] con descripción, razón de imposibilidad y rango estimado de RF-88, con advertencia visible.

### TC-92-028 — Activo valorado por costo sin rango estimado registrado en RF-88
- **Tipo:** Negativo / integración · **Prioridad:** Alta · **Ejecutable:** Sí, si hay activos al costo.
- **Pasos:** «TC-92-025..029 Precios de referencia y activos al costo».
- **Esperado (matriz):** que el informe lo refleje como dato faltante.

### TC-92-029 — Período sin activos valorados por costo
- **Tipo:** Funcional / flujo alterno · **Prioridad:** Media · **Ejecutable:** Sí.
- **Pasos:** «TC-92-025..029 Precios de referencia y activos al costo».
- **Esperado (matriz):** que la sección [Párr. 54] se declare como sin contenido, no que desaparezca.

## Ejecución automatizada
- Colección: `tc_m06_g63.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G63.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
