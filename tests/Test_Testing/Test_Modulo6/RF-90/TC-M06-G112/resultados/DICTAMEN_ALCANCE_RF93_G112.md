# Dictamen de alcance — RF-93 respecto de G112

**Fecha:** 2026-11-15  
**Grupo:** TC-M06-G112  
**Decisión:** **B** — RF-93 es un requisito **relacionado**, verificable en un **caso/escenario independiente**; **no** es criterio obligatorio de aprobación de TC-M06-39, TC-M06-40 ni del cierre documental G112 (RF-90 / RF-94).

---

## Fundamento documental

| Fuente | Qué establece |
|---|---|
| Ubicación del grupo | G112 vive bajo `Test_Modulo6/RF-90/TC-M06-G112/` (alcance primario **RF-90**, con traza a RF-109 y RF-94). |
| Subcasos del grupo | `estado_oficial` y preparaciones definen subcasos ejecutables **TC-M06-39** y **TC-M06-40**. |
| Matriz actualizada 2026-11-14 | Criterio **39-X1**: RF-93 / cerrar 220 = **eliminado** como criterio de G112. Criterio **93-X1**: cerrar/usar ER de 220 = **prohibido**. |
| Correcciones técnicas H39-3 | Se eliminó exigir cierre o ER del período **220** para aprobar G112. |
| Sección RF-93 de la misma matriz | Verifica `componentes.inversiones_llevadas_a_gasto` tras **cierre de un período aislado** (no 219/220), alimentado por costos `INVERSION`+`GASTO` (código `consolidacion.estado_resultados`). |
| Suite RF-93 propia | Existe carpeta `tests/Test_Testing/Test_Modulo6/RF-93/` (G71–G82) para el requisito de estado de resultados. |
| Matrices de ejecución 39/40 | TC-39 y TC-40 aprueban con POST + GETs de costo/activo/línea/auditoría; **no** exigen cierre ni ER. |
| Título de cierre solicitado | Cierre documental **RF-90 / RF-94**, no certificación E2E de RF-93. |

## Qué no es RF-93 para G112

- **No es A:** no bloquea la aprobación de los dos subcasos ni el dictamen global G112 de capitalización vs gasto.
- **No es C:** no fue un error de trazabilidad; la relación funcional existe (el GASTO de RF-90 alimenta el componente ER de RF-93), pero su verificación E2E exige operaciones distintas (cierre de período aislado + consulta ER).

## Estado formal de RF-93 en este cierre

| Campo | Valor |
|---|---|
| Estado | `PENDIENTE_CASO_INDEPENDIENTE` |
| Aprobación | **ni APROBADO ni RECHAZADO** |
| Relación con G112 | Consumidor aguas abajo del costo GASTO (p. ej. registro **4497** / período **629**) |
| Prohibición vigente | No cerrar período **220**; no usar ER de 220 como criterio G112 |
| Próximo paso | Caso/escenario independiente con autorización expresa de cierre del período aislado + GET ER `inversiones_llevadas_a_gasto` (o cobertura equivalente en suite RF-93) |

## Confirmación sobre TC-39 y TC-40

TC-M06-39 y TC-M06-40 **no** requieren cerrar el período 220 para su aprobación. Quedan APROBADOS con las evidencias de `ejecucion_tc39_2026-11-15/` y `ejecucion_tc40_2026-11-15/`.
