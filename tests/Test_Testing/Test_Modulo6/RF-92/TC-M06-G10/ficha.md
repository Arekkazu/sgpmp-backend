# TC-M06-G10 — RF-92

Fuente: `RF-92_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-10 (TC-92-056 a TC-92-063). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Versionado, archivado automático, aprobación y rechazo (CA-7, FA-4, Restricciones 3 y 4, Fase 3): formato {AAAA}-{NP}-V{NV} con NP en convención Q y M y NV de dos dígitos, archivado automático de la versión anterior al aprobar, registro de id_aprobacion, usuario y timestamp, publicación en M08 con evento en RF-94, y rechazo con razón documentada obligatoria.

### TC-92-056 — Verificar que la versión asignada sigue el formato {AAAA}-{NP}-V{NV} para un período trimestral
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí, si hay un período trimestral.
- **Pasos:** «TC-92-056..058 Formato de version de todos los informes».

### TC-92-057 — Verificar el formato de versión para un período MENSUAL (ej. 2026-M03-V1) y uno ANUAL
- **Tipo:** Funcional / valores límite · **Prioridad:** Alta · **Ejecutable:** Sí (sobre los informes existentes).
- **Pasos:** «TC-92-056..058 Formato de version de todos los informes».

### TC-92-058 — Generar la versión 10 del mismo período
- **Tipo:** Funcional / valores límite · **Prioridad:** Media · **Ejecutable:** Bloqueado: requiere generar 10 versiones del mismo período.
- **Pasos:** «TC-92-056..058 Formato de version de todos los informes».
- **Esperado (matriz):** que el formato admita dos dígitos en NV.

### TC-92-059 — Aprobar una versión existiendo una versión anterior APROBADA
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Sí, con escritura (aprobar un segundo informe).
- **Pasos:** «TC-92-059/060 Aprobar el BORRADOR y archivar el anterior [escritura]».
- **Esperado (matriz):** que la anterior pase automáticamente a ARCHIVADO.

### TC-92-060 — Aprobar la primera versión del informe
- **Tipo:** Funcional / positivo · **Prioridad:** Crítica · **Ejecutable:** Sí.
- **Pasos:** «TC-92-060 El APROBADO registra aprobador y fecha»; «TC-92-059/060 Aprobar el BORRADOR y archivar el anterior [escritura]».
- **Esperado (matriz):** registro de id_aprobacion, id_usuario_aprobador y timestamp_aprobacion, y cambio a APROBADO.

### TC-92-061 — Verificar que tras la aprobación el informe queda publicado en M08 y se registra INFORME_REVELACIONES_APROBADO en RF-94
- **Tipo:** Integración / auditoría · **Prioridad:** Alta · **Ejecutable:** Parcial: el evento de auditoría sí; la publicación en M08 no existe en este backend.
- **Pasos:** «TC-92-061 INFORME_REVELACIONES_APROBADO en la auditoria».

### TC-92-062 — Rechazar el BORRADOR con razón documentada
- **Tipo:** Funcional / flujo alterno · **Prioridad:** Alta · **Ejecutable:** Sí, si existe un informe RECHAZADO.
- **Pasos:** «TC-92-062 El RECHAZADO guarda su razon».
- **Esperado (matriz):** estado RECHAZADO con la razón registrada.

### TC-92-063 — Intentar rechazar sin razón documentada
- **Tipo:** Negativo / validación · **Prioridad:** Alta · **Ejecutable:** Sí.
- **Pasos:** «TC-92-063 Rechazar sin razon -> 422 (no escribe)»; «TC-92-063 Rechazar con razon de 1 caracter -> 422 (no escribe)».
- **Esperado (matriz):** que la operación se impida.

## Ejecución automatizada
- Colección: `tc_m06_g10.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G10.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Las peticiones marcadas **[escritura]** crean o cambian datos en TEST: solo corren con `--env-var "permitir_escritura=SI"`. Sin esa variable se omiten.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
