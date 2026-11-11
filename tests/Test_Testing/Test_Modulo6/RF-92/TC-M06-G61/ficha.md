# TC-M06-G61 — RF-92

Fuente: `RF-92_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-03 (TC-92-012 a TC-92-017). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Métodos y supuestos de valoración por activo y datos insuficientes (CA-3, CA-9, Párr. 47, FA-5): fuente del precio, tasa de descuento cuando aplica y supuestos de crecimiento, producción y condición corporal recuperados de RF-82, RF-83, RF-88 y RF-89; cuando un RF fuente no los persiste, alerta al Contador y marcado granular de 'datos insuficientes' sin bloquear la generación.

### TC-92-012 — Verificar que el informe revela para cada activo la fuente del precio recuperada de RF-89
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí (sobre el informe APROBADO existente).
- **Pasos:** «TC-92-012..017 Metodos y supuestos por activo».

### TC-92-013 — Verificar que el informe revela la tasa de descuento cuando aplica, recuperada de RF-83
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** «TC-92-012..017 Metodos y supuestos por activo».

### TC-92-014 — Verificar que el informe revela los supuestos de crecimiento, producción esperada y condición corporal por activo
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** «TC-92-012..017 Metodos y supuestos por activo».

### TC-92-015 — Activo cuyo RF-83 no tiene supuestos persistidos
- **Tipo:** Negativo / flujo alterno · **Prioridad:** Crítica · **Ejecutable:** Sí, si algún activo no tiene supuestos.
- **Pasos:** «TC-92-012..017 Metodos y supuestos por activo».
- **Esperado (matriz):** alerta al Contador y la sección marcada como 'datos insuficientes' para ese activo específico, sin bloquear la generación.

### TC-92-016 — Ningún activo del período tiene supuestos persistidos
- **Tipo:** Negativo / flujo alterno · **Prioridad:** Alta · **Ejecutable:** Sí, si ningún activo tiene supuestos.
- **Pasos:** «TC-92-012..017 Metodos y supuestos por activo».
- **Esperado (matriz):** que el informe se genere con toda la sección marcada y alerta al Contador.

### TC-92-017 — Activo con tasa de descuento aplicable pero no registrada en RF-83
- **Tipo:** Negativo / flujo alterno · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** «TC-92-012..017 Metodos y supuestos por activo».
- **Esperado (matriz):** marcado de dato insuficiente para ese campo.

## Ejecución automatizada
- Colección: `tc_m06_g61.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G61.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
