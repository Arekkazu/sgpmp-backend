# TC-M06-G53 — RF-91

Fuente: `RF-91_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-07 (TC-91-035 a TC-91-038). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Re-verificación de asientos PENDIENTE_TRAZABILIDAD (CA-5, FA-4): resuelto el eslabón en RF-62 o en RF-89, la re-ejecución lleva el asiento a VERIFICADO y lo hace elegible para el cierre; sin resolver permanece pendiente, y todo intento queda registrado en RF-94.

### TC-91-035 — Re-verificar un asiento PENDIENTE_TRAZABILIDAD tras corregir la lectura IoT en RF-62
- **Tipo:** Funcional / flujo alterno · **Prioridad:** Crítica · **Ejecutable:** Requiere corregir la lectura en RF-62 entre las dos verificaciones (paso manual).
- **Pasos:** «TC-91-035..037 Primera verificacion del periodo ABIERTO [escritura]»; «TC-91-035..037 Re-verificacion sin cambios: las pendientes siguen pendientes [escritura]».
- **Esperado (matriz):** transición a VERIFICADO y elegibilidad para el cierre.

### TC-91-036 — Re-verificar un asiento PENDIENTE_TRAZABILIDAD tras aprobar el precio ESTIMADA en RF-89
- **Tipo:** Funcional / flujo alterno · **Prioridad:** Alta · **Ejecutable:** Requiere aprobar el precio en RF-89 entre las dos verificaciones (paso manual).
- **Pasos:** «TC-91-035..037 Primera verificacion del periodo ABIERTO [escritura]»; «TC-91-035..037 Re-verificacion sin cambios: las pendientes siguen pendientes [escritura]».
- **Esperado (matriz):** transición a VERIFICADO.

### TC-91-037 — Re-verificar sin haber corregido el eslabón faltante
- **Tipo:** Negativo / flujo alterno · **Prioridad:** Alta · **Ejecutable:** Sí, con escritura.
- **Pasos:** «TC-91-035..037 Primera verificacion del periodo ABIERTO [escritura]»; «TC-91-035..037 Re-verificacion sin cambios: las pendientes siguen pendientes [escritura]».
- **Esperado (matriz):** que el asiento permanezca en PENDIENTE_TRAZABILIDAD.

### TC-91-038 — Comprobar que cada intento de re-verificación queda registrado en RF-94, incluidos los que no cambian el estado
- **Tipo:** Auditoría · **Prioridad:** Alta · **Ejecutable:** Sí, con escritura.
- **Pasos:** «TC-91-038 Cada intento queda en la auditoria, tambien los que no cambian el estado».

## Ejecución automatizada
- Colección: `tc_m06_g53.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G53.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Las peticiones marcadas **[escritura]** crean o cambian datos en TEST: solo corren con `--env-var "permitir_escritura=SI"`. Sin esa variable se omiten.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
