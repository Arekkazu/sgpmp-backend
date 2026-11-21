# TC-M06-G114 / TC-M06-43 — APROBADO

**Caso:** TC-M06-G114  
**Subcaso:** TC-M06-43 — APROBADO  
**RF:** RF-90, RF-94  
**Ambiente:** TEST  
**Dictamen:** APROBADO  
**Aprobados:** 1/1  

## Alcance

Validación integral de la trazabilidad de costos registrados y sus movimientos contables,
usando exclusivamente los costos 4453, 4454 y 4455 de G113. No se crearon costos nuevos.

## Resultado

Se verificó la trazabilidad integral de los costos 4453/4454/4455: exactamente un evento COSTO_REGISTRADO por costo, con correspondencia de activo, período, monto, naturaleza y actor USUARIO 141 (RF-90 / RF-94).

## Validaciones

| Validación | Resultado |
|---|---|
| costo_4453_existe | OK |
| costo_4453_un_evento_tecnico | OK |
| costo_4453_un_evento_legible | OK |
| costo_4453_id_referencia | OK |
| costo_4453_activo | OK |
| costo_4453_periodo | OK |
| costo_4453_monto | OK |
| costo_4453_naturaleza | OK |
| costo_4453_actor_usuario_141 | OK |
| costo_4453_evento_esperado | OK |
| costo_4453_tipo_evento | OK |
| costo_4454_existe | OK |
| costo_4454_un_evento_tecnico | OK |
| costo_4454_un_evento_legible | OK |
| costo_4454_id_referencia | OK |
| costo_4454_activo | OK |
| costo_4454_periodo | OK |
| costo_4454_monto | OK |
| costo_4454_naturaleza | OK |
| costo_4454_actor_usuario_141 | OK |
| costo_4454_evento_esperado | OK |
| costo_4454_tipo_evento | OK |
| costo_4455_existe | OK |
| costo_4455_un_evento_tecnico | OK |
| costo_4455_un_evento_legible | OK |
| costo_4455_id_referencia | OK |
| costo_4455_activo | OK |
| costo_4455_periodo | OK |
| costo_4455_monto | OK |
| costo_4455_naturaleza | OK |
| costo_4455_actor_usuario_141 | OK |
| costo_4455_evento_esperado | OK |
| costo_4455_tipo_evento | OK |
| sin_duplicados_ni_huerfanos | OK |
| rf90_costos_existentes_trazables | OK |
| rf94_auditoria_m06_por_id_referencia | OK |

## Conclusión

TC-M06-G114 queda **APROBADO**. Requerimientos verificados: RF-90 y RF-94.
