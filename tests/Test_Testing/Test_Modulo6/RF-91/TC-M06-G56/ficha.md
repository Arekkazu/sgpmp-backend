# TC-M06-G56 — RF-91

Fuente: `RF-91_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-10 (TC-91-049 a TC-91-055). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Cierre de período, exclusión autorizada e inmutabilidad (CA-6, CA-8, Restricciones 1, 2 y 4): ningún asiento PENDIENTE_TRAZABILIDAD entra al cierre ni al comprobante salvo exclusión autorizada por el Contador y registrada en RF-94; la cadena de períodos cerrados no puede modificarse ni completarse retroactivamente, ni por API ni en base de datos.

### TC-91-049 — Ejecutar el cierre de un período cuyos asientos están todos VERIFICADOS
- **Tipo:** Funcional / positivo · **Prioridad:** Alta · **Ejecutable:** Requiere autorización de Coordinación: ejecutar un cierre real es irreversible; se cubre solo la prevalidación.
- **Pasos:** «TC-91-049/050 Prevalidacion del cierre del periodo ABIERTO».
- **Esperado (matriz):** que el cierre proceda.

### TC-91-050 — Ejecutar el cierre con un asiento PENDIENTE_TRAZABILIDAD sin autorización
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Sí, si el período ABIERTO tiene líneas pendientes (el 409 se produce antes de cerrar).
- **Pasos:** «TC-91-049/050 Prevalidacion del cierre del periodo ABIERTO»; «TC-91-050 Cerrar con lineas pendientes sin autorizacion -> 409 (no cierra)».
- **Esperado (matriz):** bloqueo del cierre.

### TC-91-051 — Ejecutar el cierre con exclusión autorizada por el Contador
- **Tipo:** Funcional / flujo alterno · **Prioridad:** Crítica · **Ejecutable:** Requiere autorización de Coordinación: cierre real con exclusión.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** que proceda y que la exclusión quede registrada en RF-94.

### TC-91-052 — Intentar autorizar una exclusión con un rol distinto del Contador
- **Tipo:** Seguridad / autorización · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** «TC-91-052 prod autoriza exclusion y cierra -> 403»; «TC-91-052 vet autoriza exclusion y cierra -> 403»; «TC-91-052 adm autoriza exclusion y cierra -> 403»; «TC-91-052 revfis autoriza exclusion y cierra -> 403»; «TC-91-052 ext autoriza exclusion y cierra -> 403».
- **Esperado (matriz):** 403.

### TC-91-053 — Intentar modificar la cadena de un asiento de período cerrado vía API
- **Tipo:** Seguridad / integridad · **Prioridad:** Crítica · **Ejecutable:** Sí.
- **Pasos:** «TC-91-053 No existe operacion para modificar la cadena -> 404/405».
- **Esperado (matriz):** rechazo y registro del intento.

### TC-91-054 — Intentar re-verificar un asiento perteneciente a un período ya cerrado
- **Tipo:** Negativo / integridad · **Prioridad:** Alta · **Ejecutable:** Sí, si TEST tiene un período CERRADO.
- **Pasos:** «TC-91-054 Re-verificar periodo CERRADO -> 422»; «TC-91-054 Cerrar de nuevo un periodo CERRADO -> 409».
- **Esperado (matriz):** rechazo.

### TC-91-055 — Ejecutar UPDATE directo sobre la cadena con el usuario de base de datos de la aplicación
- **Tipo:** Seguridad / integridad · **Prioridad:** Crítica · **Ejecutable:** Bloqueado: requiere acceso directo a la base de datos de TEST.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** denegación por permisos del motor.

## Ejecución automatizada
- Colección: `tc_m06_g56.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G56.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Administrador, Contador, Productor, Veterinario, Revisor Fiscal, Externo AgroFusion (auditor externo).
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
