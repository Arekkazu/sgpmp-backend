# TC-M06-G49 — RF-91

Fuente: `RF-91_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-03 (TC-91-011 a TC-91-018, TC-91-071). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Matriz de niveles obligatorios por tipo_evidencia_origen (CA-2, FA-3, Proceso 2): cada uno de los 5 tipos exige exactamente los niveles definidos, se verifica la cadena completa y la ausencia de un nivel obligatorio, y las lecturas informadas en tipos que no las requieren se ignoran sin rechazo.

### TC-91-011 — Asiento REGISTRO_MANUAL con auditoría RF-52 presente
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Sí (sobre líneas REGISTRO_MANUAL existentes).
- **Pasos:** «TC-91-011..018 Niveles obligatorios por tipo de evidencia (oraculo de la matriz)».
- **Esperado (matriz):** VERIFICADO sin exigir Nivel 1 y sin alerta de IoT faltante.

### TC-91-012 — Asiento EVENTO_SANITARIO con auditoría RF-73 vinculada al activo y cubriendo la fecha del evento
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Sí (sobre líneas EVENTO_SANITARIO existentes).
- **Pasos:** «TC-91-011..018 Niveles obligatorios por tipo de evidencia (oraculo de la matriz)».
- **Esperado (matriz):** VERIFICADO sin ids_lectura_iot.

### TC-91-013 — Asiento REGISTRO_MANUAL que informa ids_lectura_iot
- **Tipo:** Funcional / flujo alterno · **Prioridad:** Media · **Ejecutable:** No aplica: el API no recibe ids_lectura_iot.
- **Pasos:** «TC-91-011..018 Niveles obligatorios por tipo de evidencia (oraculo de la matriz)».
- **Esperado (matriz):** que las lecturas se ignoren sin alterar el resultado ni provocar rechazo.

### TC-91-014 — Asiento EVENTO_SANITARIO sin id_auditoria_m04
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí (sobre líneas EVENTO_SANITARIO existentes).
- **Pasos:** «TC-91-011..018 Niveles obligatorios por tipo de evidencia (oraculo de la matriz)».
- **Esperado (matriz):** CADENA_INCOMPLETA.

### TC-91-015 — Asiento VARIACION_PRECIO
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Sí (sobre líneas VARIACION_PRECIO existentes).
- **Pasos:** «TC-91-011..018 Niveles obligatorios por tipo de evidencia (oraculo de la matriz)».
- **Esperado (matriz):** que solo se exijan id_precio_referencia y el Nivel 4, alcanzando VERIFICADO sin evento biológico ni lecturas.

### TC-91-016 — Asiento CIERRE_PERIODO
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí (sobre líneas CIERRE_PERIODO existentes).
- **Pasos:** «TC-91-011..018 Niveles obligatorios por tipo de evidencia (oraculo de la matriz)».
- **Esperado (matriz):** que solo se exijan la validación de RF-87 y el Nivel 4.

### TC-91-017 — Asiento IOT_DIRECTO al que le falta el Nivel 1
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí (sobre líneas IOT_DIRECTO existentes).
- **Pasos:** «TC-91-011..018 Niveles obligatorios por tipo de evidencia (oraculo de la matriz)».
- **Esperado (matriz):** CADENA_INCOMPLETA por nivel obligatorio ausente.

### TC-91-018 — Asiento REGISTRO_MANUAL al que le falta el Nivel 2
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí (sobre líneas REGISTRO_MANUAL existentes).
- **Pasos:** «TC-91-011..018 Niveles obligatorios por tipo de evidencia (oraculo de la matriz)».
- **Esperado (matriz):** CADENA_INCOMPLETA.

### TC-91-071 — Asiento derivado de un servicio veterinario o de una inseminación. Según la guía son gasto del período sin línea de asiento: aparecen en Costos y en el Estado de resultados pero NO en Trazabilidad
- **Tipo:** Negativo / alcance · **Prioridad:** Crítica · **Ejecutable:** Sí.
- **Pasos:** «TC-91-071 Servicio veterinario e inseminacion no generan lineas de trazabilidad».
- **Esperado (matriz):** que queden fuera del alcance de la verificación de cadena y no generen PENDIENTE_TRAZABILIDAD.

## Ejecución automatizada
- Colección: `tc_m06_g49.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G49.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Las peticiones marcadas **[escritura]** crean o cambian datos: corren **dentro del sandbox transaccional de TEST** (cabecera X-Test-Run-Id) y al final se revierten con DELETE /test-control/runs/{id}. Requieren `--env-var permitir_escritura=SI` y `--env-var sandbox_secret=...` (secreto que da el DBA); la colección comprueba que el sandbox esté activo y, si no, omite esas peticiones.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
