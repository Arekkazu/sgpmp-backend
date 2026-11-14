# TC-M06-G65 — RF-92

Fuente: `RF-92_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-07 (TC-92-037 a TC-92-043, TC-92-082, TC-92-084). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Bloqueo sobre períodos no cerrados y validación del contrato de entrada (FA-1, Restricción 1, Entradas): HTTP 422 sin informe parcial para períodos ABIERTO y EN_CIERRE, y rechazo controlado sin 500 ante identificador inexistente, enumerados inválidos, filtro inexistente y entradas manuales con campos ausentes o montos negativos.

### TC-92-037 — Intentar generar el informe sobre un período ABIERTO
- **Tipo:** Negativo / validación · **Prioridad:** Crítica · **Ejecutable:** Sí, si TEST tiene un período ABIERTO.
- **Pasos:** «TC-92-037 Conteo inicial de versiones (periodo ABIERTO)»; «TC-92-037 Generar sobre periodo ABIERTO -> 422»; «TC-92-037 Sin informe parcial (conteo igual)».
- **Esperado (matriz):** HTTP 422 con mensaje descriptivo y sin informe parcial.

### TC-92-038 — Intentar generar el informe sobre un período EN_CIERRE
- **Tipo:** Negativo / validación · **Prioridad:** Crítica · **Ejecutable:** Sí, si TEST tiene un período EN_CIERRE.
- **Pasos:** «TC-92-038 Generar sobre periodo EN_CIERRE -> 422».
- **Esperado (matriz):** HTTP 422.

### TC-92-039 — Intentar generar el informe para un id_periodo_contable inexistente
- **Tipo:** Negativo / validación · **Prioridad:** Media · **Ejecutable:** Sí.
- **Pasos:** «TC-92-039 Periodo inexistente -> 404/422»; «TC-92-039 Periodo no numerico -> 400/422»; «TC-92-039 Informe inexistente -> 404».
- **Esperado (matriz):** error controlado sin 500.

### TC-92-040 — Enviar tipo_periodo fuera del enumerado MENSUAL / TRIMESTRAL / ANUAL
- **Tipo:** Negativo / validación · **Prioridad:** Media · **Ejecutable:** No aplica: el API no recibe tipo_periodo (sale del período).
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** rechazo por allow-list.

### TC-92-041 — Enviar formato_salida fuera del enumerado PDF_A1 / EXCEL_UPRA
- **Tipo:** Negativo / validación · **Prioridad:** Media · **Ejecutable:** Sí (adaptado al parámetro formato de la descarga).
- **Pasos:** «TC-92-041 Descarga en formato ajeno -> 400».
- **Esperado (matriz):** rechazo.

### TC-92-042 — Enviar filtro_especie con un identificador inexistente
- **Tipo:** Negativo / validación · **Prioridad:** Media · **Ejecutable:** No aplica: el API no recibe filtro_especie.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** rechazo o informe vacío con comportamiento definido.

### TC-92-043 — Enviar compromisos o pignorados con campos obligatorios ausentes o montos negativos
- **Tipo:** Negativo / validación · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** «TC-92-043 Compromiso con descripcion vacia -> 400»; «TC-92-043 Compromiso sin descripcion -> 400»; «TC-92-043 Compromiso con monto negativo -> 400»; «TC-92-043 Pignorado sin entidad acreedora -> 400»; «TC-92-043 Pignorado con activo 0 -> 400».
- **Esperado (matriz):** rechazo controlado.

### TC-92-082 — Enviar un valor inválido en filtro_especie o en el rango de fechas del período
- **Tipo:** Negativo / validación · **Prioridad:** Alta · **Ejecutable:** No aplica: el API no recibe filtro_especie ni rango de fechas.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** el error de validación 400 con su error_code, nunca un 500 ni un informe vacío sin explicación.

### TC-92-084 — Intentar generar el informe sin la cadena de datos previos completa: sin titular tributario con NIT y DV, sin matriz contable o sin porcentajes de costos de venta por especie
- **Tipo:** Negativo / precondiciones · **Prioridad:** Alta · **Ejecutable:** Parcial: se comprueba el bloqueo por falta de entradas manuales; los datos previos faltantes (NIT, matriz, costos de venta) requieren preparar una finca.
- **Pasos:** «TC-92-084 Periodo CERRADO sin entradas manuales -> 422».
- **Esperado (matriz):** que el período no llegue a cerrarse y que, por tanto, el informe no pueda generarse, con el mensaje que identifique el dato faltante.

## Ejecución automatizada
- Colección: `tc_m06_g65.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G65.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Administrador, Contador, Productor, Revisor Fiscal.
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
