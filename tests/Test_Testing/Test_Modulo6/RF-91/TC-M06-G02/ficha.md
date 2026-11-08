# TC-M06-G02 — RF-91

Fuente: `RF-91_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-02 (TC-91-005 a TC-91-010). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Cardinalidad de lecturas IoT por evento (CA-3, CA-4, FA-1): basta con que una lectura tenga apto_para_nic41 = true para alcanzar CADENA_COMPLETA; si ninguna lo tiene, si el array viene vacío o si la lectura no existe, el resultado es CADENA_INCOMPLETA con alerta al Contador.

### TC-91-005 — Evento con 3 lecturas IoT de las cuales solo 1 tiene apto_para_nic41 = true
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Sí (sobre líneas existentes).
- **Pasos:** «TC-91-005/006/007 Basta una lectura apta para el nivel 1».
- **Esperado (matriz):** CADENA_COMPLETA.

### TC-91-006 — Evento con 3 lecturas IoT, todas con apto_para_nic41 = true
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí (sobre líneas existentes).
- **Pasos:** «TC-91-005/006/007 Basta una lectura apta para el nivel 1».
- **Esperado (matriz):** CADENA_COMPLETA.

### TC-91-007 — Evento con 2 de 3 lecturas marcadas
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Media · **Ejecutable:** Sí (sobre líneas existentes).
- **Pasos:** «TC-91-005/006/007 Basta una lectura apta para el nivel 1».
- **Esperado (matriz):** CADENA_COMPLETA.

### TC-91-008 — Asiento IOT_DIRECTO cuyas 3 lecturas tienen apto_para_nic41 = false
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Sí, si TEST tiene cadenas IOT_DIRECTO incompletas.
- **Pasos:** «TC-91-008/009 Sin lecturas aptas: CADENA_INCOMPLETA, PENDIENTE_TRAZABILIDAD y nivel 1 como eslabon fallido»; «TC-91-008 Alerta al Contador con el eslabon fallido (evento WARNING)».
- **Esperado (matriz):** CADENA_INCOMPLETA, estado PENDIENTE_TRAZABILIDAD y alerta al Contador con el eslabón fallido.

### TC-91-009 — Asiento IOT_DIRECTO con ids_lectura_iot vacío
- **Tipo:** Negativo / validación · **Prioridad:** Alta · **Ejecutable:** Sí, si TEST tiene cadenas IOT_DIRECTO sin lecturas.
- **Pasos:** «TC-91-008/009 Sin lecturas aptas: CADENA_INCOMPLETA, PENDIENTE_TRAZABILIDAD y nivel 1 como eslabon fallido».
- **Esperado (matriz):** CADENA_INCOMPLETA por ausencia del Nivel 1.

### TC-91-010 — Asiento IOT_DIRECTO que referencia una lectura inexistente en RF-53
- **Tipo:** Negativo / validación · **Prioridad:** Alta · **Ejecutable:** No aplica: el API no recibe ids_lectura_iot; las lecturas se buscan por dispositivo y fecha.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** CADENA_INCOMPLETA.

## Ejecución automatizada
- Colección: `tc_m06_g02.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G02.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
