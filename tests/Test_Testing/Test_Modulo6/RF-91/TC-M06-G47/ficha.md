# TC-M06-G47 — RF-91

Fuente: `RF-91_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-01 (TC-91-001 a TC-91-004, TC-91-069). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Verificación exitosa de la cadena IOT_DIRECTO en sus 4 niveles (CA-1): resultado CADENA_COMPLETA, transición a VERIFICADO, navegación completa de la cadena, coherencia de id_variacion_valor_razonable con RF-86 y registro del evento en RF-94.

### TC-91-001 — Verificar un asiento IOT_DIRECTO con los 4 niveles completos
- **Tipo:** Funcional / positivo · **Prioridad:** Crítica · **Ejecutable:** Sí, con escritura (la verificación cambia el estado de las líneas).
- **Pasos:** «TC-91-001 Verificar la cadena del periodo ABIERTO [escritura]»; «TC-91-001/002/004 Cadena IOT_DIRECTO VERIFICADA con 4 niveles navegables».
- **Esperado (matriz):** resultado_verificacion = CADENA_COMPLETA y transición del asiento a VERIFICADO.

### TC-91-002 — Navegar la cadena de un asiento VERIFICADO
- **Tipo:** Funcional / positivo · **Prioridad:** Crítica · **Ejecutable:** Sí.
- **Pasos:** «TC-91-001/002/004 Cadena IOT_DIRECTO VERIFICADA con 4 niveles navegables».
- **Esperado (matriz):** recorrer los 4 niveles: lectura de sensor → evento biológico → variación de valor → asiento.

### TC-91-003 — Comprobar que cada verificación queda registrada en RF-94 con todos los identificadores de la cadena y el resultado
- **Tipo:** Auditoría · **Prioridad:** Crítica · **Ejecutable:** Sí.
- **Pasos:** «TC-91-003 Cada verificacion queda en la auditoria con resultado e identificadores».

### TC-91-004 — Verificar la coherencia de id_variacion_valor_razonable contra RF-86: el monto, el tipo y el activo biológico referenciado deben coincidir con el asiento
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Parcial: la API expone los ids de la cadena, pero no el monto ni el tipo de la variación de RF-86 para compararlos.
- **Pasos:** «TC-91-001/002/004 Cadena IOT_DIRECTO VERIFICADA con 4 niveles navegables».

### TC-91-069 — Revisar la cadena navegable, las alertas al Contador y la vista del auditor en busca de terminología interna
- **Tipo:** Negativo / presentación · **Prioridad:** Alta · **Ejecutable:** Parcial: se revisan los textos del API; la pantalla y la exportación se revisan a mano.
- **Pasos:** «TC-91-069 Auditoria legible sin terminologia interna».
- **Esperado (matriz):** que ningún texto en pantalla, mensaje ni exportación muestre «RF-xx», «M06», «Módulo N», null, undefined, un identificador como «#123» ni un código en mayúsculas como PENDIENTE_TRAZABILIDAD o CADENA_INCOMPLETA.

## Ejecución automatizada
- Colección: `tc_m06_g47.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G47.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Las peticiones marcadas **[escritura]** crean o cambian datos en TEST: solo corren con `--env-var "permitir_escritura=SI"`. Sin esa variable se omiten.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
