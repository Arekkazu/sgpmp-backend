# TC-M06-G57 — RF-91

Fuente: `RF-91_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-11 (TC-91-056 a TC-91-063). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Escala del activo y control de acceso (CA-9, Restricción 5, RFC-018): la verificación alcanza VERIFICADO tanto para un bovino individual con pesaje IoT como para un conjunto de aves POBLACIONAL con telemetría ambiental, detecta la incoherencia de escala, define el comportamiento ante el campo retirado id_lote, y limita al Contador a consulta y al Auditor externo a solo lectura sobre períodos CERRADOS.

### TC-91-056 — Verificar un asiento de bovino individual sustentado en su pesaje IoT
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Requiere un bovino con pesaje IoT y una línea IOT_DIRECTO (dato sembrado).
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** VERIFICADO.

### TC-91-057 — Verificar un asiento de un conjunto de aves (activo POBLACIONAL) sustentado en telemetría ambiental del galpón
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Requiere un lote avícola POBLACIONAL con telemetría ambiental (dato sembrado).
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** VERIFICADO.

### TC-91-058 — Asiento POBLACIONAL cuya variación fue calculada a escala individual
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Requiere una variación individual sobre un activo POBLACIONAL (dato sembrado).
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** CADENA_INCOMPLETA por incoherencia de escala.

### TC-91-059 — Enviar un payload que aún incluye id_lote, campo retirado por RFC-018
- **Tipo:** Negativo / validación · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** «TC-91-059 Payload con id_lote retirado: comportamiento definido sin error».
- **Esperado (matriz):** un comportamiento definido y documentado.

### TC-91-060 — Contador intentando modificar la cadena de trazabilidad
- **Tipo:** Seguridad / autorización · **Prioridad:** Crítica · **Ejecutable:** Sí.
- **Pasos:** «TC-91-060 Contador consulta la cadena (permitido)»; «TC-91-060 Contador intenta modificar la cadena -> 404/405».
- **Esperado (matriz):** 403: el Contador solo puede consultar.

### TC-91-061 — Auditor externo consultando la cadena de un asiento de período CERRADO
- **Tipo:** Seguridad / autorización · **Prioridad:** Alta · **Ejecutable:** Parcial: se comprueba que el auditor externo (Externo AgroFusion) tiene lectura de la cadena; la consulta por M08 no existe en este backend y la línea de un período CERRADO requiere datos.
- **Pasos:** «TC-91-061 Auditor externo tiene lectura de la cadena (404 por id inexistente, no 403)».
- **Esperado (matriz):** acceso de solo lectura permitido.

### TC-91-062 — Auditor externo consultando la cadena de un asiento de período ABIERTO o EN_CIERRE
- **Tipo:** Seguridad / autorización · **Prioridad:** Crítica · **Ejecutable:** Sí, con el auditor externo, si hay líneas en un período ABIERTO.
- **Pasos:** «TC-91-062 Auditor externo consulta cadena de periodo ABIERTO -> 403».
- **Esperado (matriz):** denegación.

### TC-91-063 — Auditor externo intentando iniciar una verificación o alterar un estado
- **Tipo:** Seguridad / autorización · **Prioridad:** Crítica · **Ejecutable:** Sí, con el auditor externo.
- **Pasos:** «TC-91-063 Auditor externo inicia verificacion -> 403».
- **Esperado (matriz):** 403.

## Ejecución automatizada
- Colección: `tc_m06_g57.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G57.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Administrador, Contador, Productor, Veterinario, Revisor Fiscal, Externo AgroFusion (auditor externo).
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
