# TC-M06-G66 — RF-92

Fuente: `RF-92_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-08 (TC-92-044 a TC-92-051). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Validación de consistencia entre fuentes y continuidad con justificación (CA-8, FA-2, Proceso 3): los cuatro cuadres definidos contra RF-86/RF-93, RF-82/RF-83 y M02, RF-90 y RF-89; una diferencia superior a ±0,01 COP genera ALERTA_CONSISTENCIA y ERROR_CONSISTENCIA en RF-94; el Contador puede continuar con justificación documentada obligatoria y el informe nunca queda bloqueado permanentemente.

### TC-92-044 — Validar el cuadre entre la suma de variaciones de RF-86 y el resultado_neto de RF-93 con datos consistentes
- **Tipo:** Funcional / positivo · **Prioridad:** Alta · **Ejecutable:** Sí (sobre el informe existente).
- **Pasos:** «TC-92-044..049/050 Alertas de consistencia y justificacion en el informe».

### TC-92-045 — Diferencia de exactamente 0,01 COP entre RF-86 y RF-93
- **Tipo:** Funcional / valores límite · **Prioridad:** Crítica · **Ejecutable:** Bloqueado por datos: requiere sembrar una diferencia exacta de 0,01 COP. RF-92 paso 3a exige ±0,01 COP entre RF-86 y RF-93; el código no hace ese cuadre (solo concilia el rollforward con tolerancia de 1 COP): posible defecto a confirmar con datos.
- **Pasos:** «TC-92-044..049/050 Alertas de consistencia y justificacion en el informe».
- **Esperado (matriz):** que NO se genere alerta por estar dentro de la tolerancia.

### TC-92-046 — Diferencia de 0,011 COP entre RF-86 y RF-93
- **Tipo:** Negativo / valores límite · **Prioridad:** Crítica · **Ejecutable:** Sí, si el informe existente tiene alertas.
- **Pasos:** «TC-92-044..049/050 Alertas de consistencia y justificacion en el informe»; «TC-92-046 Continuar con alertas deja ERROR_CONSISTENCIA en la auditoria».
- **Esperado (matriz):** ALERTA_CONSISTENCIA al Contador y ERROR_CONSISTENCIA en RF-94.

### TC-92-047 — Validar el cuadre entre el total de activos de RF-82/RF-83 y el inventario de M02 al cierre
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Bloqueado por datos. RF-92 paso 3b exige este cuadre y el código no lo implementa: posible defecto a confirmar con datos.
- **Pasos:** «TC-92-044..049/050 Alertas de consistencia y justificacion en el informe».

### TC-92-048 — Validar el cuadre entre los costos de RF-90 y los costos consolidados en RF-93
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Bloqueado por datos. RF-92 paso 3c exige este cuadre y el código no lo implementa: posible defecto a confirmar con datos.
- **Pasos:** «TC-92-044..049/050 Alertas de consistencia y justificacion en el informe».

### TC-92-049 — Validar que los precios de RF-89 usados en RF-83/RF-84 coinciden con los registrados
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Bloqueado por datos. RF-92 paso 3d exige este cuadre y el código no lo implementa: posible defecto a confirmar con datos.
- **Pasos:** «TC-92-044..049/050 Alertas de consistencia y justificacion en el informe».

### TC-92-050 — Continuar la generación marcando la inconsistencia como 'pendiente de resolución' con justificación documentada
- **Tipo:** Funcional / flujo alterno · **Prioridad:** Alta · **Ejecutable:** Sí (sobre el informe existente).
- **Pasos:** «TC-92-044..049/050 Alertas de consistencia y justificacion en el informe».
- **Esperado (matriz):** que el informe se genere con la marca visible.

### TC-92-051 — Intentar continuar sin justificación documentada
- **Tipo:** Negativo / flujo alterno · **Prioridad:** Alta · **Ejecutable:** Sí, con escritura (si las alertas desaparecieron, la petición crearía un informe).
- **Pasos:** «TC-92-051 Continuar con justificacion de 1 caracter -> 409 [escritura si no hay alertas]».
- **Esperado (matriz):** que la opción se rechace.

## Ejecución automatizada
- Colección: `tc_m06_g66.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G66.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
