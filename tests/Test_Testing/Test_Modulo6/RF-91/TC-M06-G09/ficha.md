# TC-M06-G09 — RF-91

Fuente: `RF-91_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-09 (TC-91-043 a TC-91-048, TC-91-070). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Máquina de estados y contrato de entrada (Descripción, Entradas): solo son posibles las transiciones definidas, y se rechaza con error controlado un asiento inexistente, un UUID malformado, un tipo_evidencia_origen fuera del enumerado o un id_evento_biologico informado en VARIACION_PRECIO.

### TC-91-043 — Intentar verificar un asiento que ya está en estado VERIFICADO
- **Tipo:** Negativo / máquina de estados · **Prioridad:** Alta · **Ejecutable:** Parcial: se comprueba que las líneas VERIFICADO se conservan; el re-intento con escritura está en G07.
- **Pasos:** «TC-91-043 Re-verificar lineas VERIFICADO no las altera (estado ya verificado se conserva)».
- **Esperado (matriz):** rechazo.

### TC-91-044 — Forzar la transición VERIFICADO → PENDIENTE_TRAZABILIDAD
- **Tipo:** Negativo / máquina de estados · **Prioridad:** Alta · **Ejecutable:** Sí, si TEST tiene períodos CERRADO y EN_CIERRE.
- **Pasos:** «TC-91-044 Verificar periodo CERRADO -> 422»; «TC-91-044 Verificar periodo EN_CIERRE -> 422».
- **Esperado (matriz):** rechazo por transición no contemplada.

### TC-91-045 — Verificar un id_asiento_contable inexistente
- **Tipo:** Negativo / validación · **Prioridad:** Media · **Ejecutable:** Sí.
- **Pasos:** «TC-91-045 Verificar periodo inexistente -> 404/422»; «TC-91-045 Cadena de linea inexistente -> 404».
- **Esperado (matriz):** error controlado sin 500.

### TC-91-046 — Enviar UUID malformado en cualquiera de los identificadores de entrada
- **Tipo:** Negativo / validación · **Prioridad:** Media · **Ejecutable:** Sí.
- **Pasos:** «TC-91-046 Periodo no numerico -> 400/422»; «TC-91-046 Linea no numerica -> 400/422»; «TC-91-046 Periodo negativo -> 4xx».
- **Esperado (matriz):** 400/422 sin stack trace.

### TC-91-047 — Enviar tipo_evidencia_origen fuera del enumerado
- **Tipo:** Negativo / validación · **Prioridad:** Alta · **Ejecutable:** No aplica: el API no recibe tipo_evidencia_origen; se comprueba que el campo se ignora sin error.
- **Pasos:** «TC-91-047/048 Campos de entrada ajenos se ignoran sin error».
- **Esperado (matriz):** rechazo por allow-list.

### TC-91-048 — Enviar id_evento_biologico informado en un asiento VARIACION_PRECIO, donde debe ser nulo
- **Tipo:** Negativo / validación · **Prioridad:** Alta · **Ejecutable:** No aplica: el API no recibe id_evento_biologico; se comprueba que el campo se ignora sin error.
- **Pasos:** «TC-91-047/048 Campos de entrada ajenos se ignoran sin error».
- **Esperado (matriz):** rechazo.

### TC-91-070 — Consultar la cadena o lanzar la verificación con un valor inválido en un filtro
- **Tipo:** Negativo / validación · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** «TC-91-070 Lineas con id_periodo_contable=0 -> 400»; «TC-91-070 Lineas con id_periodo_contable no numerico -> 400»; «TC-91-070 Lineas con estado fuera del enumerado -> 400»; «TC-91-070 Lineas sin id_periodo_contable -> 400».
- **Esperado (matriz):** el error de validación 400 con su error_code, nunca un 500 ni una lista vacía.

## Ejecución automatizada
- Colección: `tc_m06_g09.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G09.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Administrador, Contador, Productor, Veterinario, Revisor Fiscal.
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
