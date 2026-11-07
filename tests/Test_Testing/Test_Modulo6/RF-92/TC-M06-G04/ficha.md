# TC-M06-G04 — RF-92

Fuente: `RF-92_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-04 (TC-92-018 a TC-92-024). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Cuadre matemático del rollforward por activo individual y agregado (CA-4, Párr. 50): valor_inicio + compras + nacimientos + producción − ventas − bajas − cosechas ± variaciones = valor_cierre, con coherencia del número de activos y con la sumatoria individual coincidiendo exactamente con la agregación por especie y por categoría.

### TC-92-018 — Verificar el cuadre del rollforward para un activo sin movimientos: valor_inicio = valor_cierre ± variaciones
- **Tipo:** Funcional / cálculo · **Prioridad:** Alta · **Ejecutable:** Sí (sobre los activos del informe).
- **Pasos:** «TC-92-018..024 Cuadre del rollforward (APROBADO)»; «TC-92-018..024 Cuadre del rollforward (BORRADOR)».

### TC-92-019 — Verificar el cuadre para un activo con todos los tipos de movimiento: compras, nacimientos, producción, ventas, bajas y cosechas
- **Tipo:** Funcional / cálculo · **Prioridad:** Crítica · **Ejecutable:** Sí, si algún activo tiene todos los movimientos.
- **Pasos:** «TC-92-018..024 Cuadre del rollforward (APROBADO)»; «TC-92-018..024 Cuadre del rollforward (BORRADOR)».

### TC-92-020 — Activo nacido dentro del período, sin valor inicial
- **Tipo:** Funcional / valores límite · **Prioridad:** Crítica · **Ejecutable:** Sí, si hay nacimientos en el período.
- **Pasos:** «TC-92-018..024 Cuadre del rollforward (APROBADO)»; «TC-92-018..024 Cuadre del rollforward (BORRADOR)».
- **Esperado (matriz):** que la ecuación cuadre con valor_inicio = 0 y el nacimiento como movimiento.

### TC-92-021 — Activo dado de baja dentro del período, sin valor de cierre
- **Tipo:** Funcional / valores límite · **Prioridad:** Crítica · **Ejecutable:** Sí, si hay bajas en el período.
- **Pasos:** «TC-92-018..024 Cuadre del rollforward (APROBADO)»; «TC-92-018..024 Cuadre del rollforward (BORRADOR)».
- **Esperado (matriz):** que la ecuación cuadre con valor_cierre = 0.

### TC-92-022 — Verificar que el número de activos al inicio y al cierre es coherente con los movimientos registrados
- **Tipo:** Funcional / cálculo · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** «TC-92-018..024 Cuadre del rollforward (APROBADO)»; «TC-92-018..024 Cuadre del rollforward (BORRADOR)».

### TC-92-023 — Verificar que la sumatoria de los rollforward individuales coincide exactamente con el rollforward agregado por especie
- **Tipo:** Funcional / cálculo · **Prioridad:** Crítica · **Ejecutable:** Sí.
- **Pasos:** «TC-92-018..024 Cuadre del rollforward (APROBADO)»; «TC-92-018..024 Cuadre del rollforward (BORRADOR)».

### TC-92-024 — Verificar la agregación del rollforward a nivel de categoría
- **Tipo:** Funcional / cálculo · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** «TC-92-018..024 Cuadre del rollforward (APROBADO)»; «TC-92-018..024 Cuadre del rollforward (BORRADOR)».

## Ejecución automatizada
- Colección: `tc_m06_g04.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G04.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
