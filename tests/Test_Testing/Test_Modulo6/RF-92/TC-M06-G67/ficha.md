# TC-M06-G67 — RF-92

Fuente: `RF-92_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-09 (TC-92-052 a TC-92-055). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Secciones BLOQUEADAS por error crítico en un RF fuente (Restricción 6): un error que impida completar una sección OBLIGATORIA la marca como BLOQUEADA con referencia explícita al RF fuente y al error, e impide la aprobación hasta su corrección; un error en una sección de revelación voluntaria genera solo ADVERTENCIA.

### TC-92-052 — Error crítico en RF-86 que impide completar una sección obligatoria
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Bloqueado: requiere provocar un error crítico en RF-86 (inyección de fallo no disponible).
- **Pasos:** «TC-92-052..055 El informe expone el estado de cada seccion (BLOQUEADA / ADVERTENCIA)».
- **Esperado (matriz):** que la sección quede BLOQUEADA con referencia al RF fuente y al error, y que la aprobación quede impedida.

### TC-92-053 — Error en RF-91 con asientos no VERIFICADOS
- **Tipo:** Negativo / integración · **Prioridad:** Alta · **Ejecutable:** Bloqueado: requiere asientos sin verificar en un período ya cerrado.
- **Pasos:** «TC-92-052..055 El informe expone el estado de cada seccion (BLOQUEADA / ADVERTENCIA)».
- **Esperado (matriz):** que la sección afectada quede BLOQUEADA.

### TC-92-054 — Error en una sección de revelación voluntaria
- **Tipo:** Funcional / flujo alterno · **Prioridad:** Alta · **Ejecutable:** Bloqueado: requiere provocar un error en una sección voluntaria.
- **Pasos:** «TC-92-052..055 El informe expone el estado de cada seccion (BLOQUEADA / ADVERTENCIA)».
- **Esperado (matriz):** ADVERTENCIA al Contador sin impedir la aprobación.

### TC-92-055 — Intentar aprobar un informe que tiene una sección BLOQUEADA
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Parcial: se comprueba si el contrato expone el estado de las secciones; sin él la aprobación no puede impedirse.
- **Pasos:** «TC-92-052..055 El informe expone el estado de cada seccion (BLOQUEADA / ADVERTENCIA)».
- **Esperado (matriz):** rechazo de la aprobación.

## Ejecución automatizada
- Colección: `tc_m06_g09.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G67.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
