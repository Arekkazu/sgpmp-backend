# TC-M06-G114 — Informe de inspección de preparación (TC-M06-43)

## Objetivo

Verificar si los registros de costos existentes en TEST permiten comprobar RF-90 y RF-94: exactamente un evento de auditoría por cada registro de costo y la relación entre evento, costo, activo y período contable.

## Ambiente inspeccionado

- Ambiente: `https://api.inmero.co/api-sgpmp-test`
- Fase: inspeccion_preparacion_solo_lectura
- Generado: 2026-11-13T01:54:08.146038+00:00
- Escrituras: ninguna (solo GET + POST /sesiones/).

## Antecedentes

- Incidente: INC-M06-330-G86 / #1017
- PR: #1024 (merged en dev; desplegado en TEST)

## Registros consultados

| ID costo | Origen | Encontrado | Activo | Período | Monto | Naturaleza |
|---|---|---|---:|---:|---:|---|
| 4453 | G113 | True | 1569 | 220 | 150000.0000 | MANTENIMIENTO |
| 4454 | G113 | True | 1570 | 220 | 300000.0000 | MANTENIMIENTO |
| 4455 | G113 | True | 1571 | 220 | 450000.0000 | MANTENIMIENTO |
| 4448 | G110_antecedente | True | 1569 | 220 | 150000.0000 | MANTENIMIENTO |

## Consultas realizadas

- `GET /openapi.json` (contrato de `/finanzas/auditoria`).
- `GET /finanzas/costos?id_periodo_contable=220`.
- `GET /finanzas/costos?id_activo_biologico=1569`.
- Por cada costo: `GET /finanzas/auditoria?tipo_evento=COSTO_REGISTRADO&id_referencia={id}&formato=TECNICO|LEGIBLE`.
- Smoke de filtros `origen_registro` e `id_usuario` cuando el evento los expone.

### Filtros PR #1024 en OpenAPI

- `id_usuario`: presente
- `origen_registro`: presente
- `id_referencia`: presente

## Eventos encontrados y comparación

### Costo 4453

- Eventos TECNICO: 1
- Eventos LEGIBLE: 1
- Evento: id=19671, ref=4453, activo=1569, periodo=220, monto=150000.0000, actor=USUARIO, origen=REPOSITORIO

| Validación | Resultado |
|---|---|
| costo_existe | OK |
| exactamente_un_evento_tecnico | OK |
| exactamente_un_evento_legible | OK |
| id_referencia_coincide | OK |
| activo_coincide | OK |
| periodo_coincide | OK |
| monto_coincide | OK |
| naturaleza_en_payload_o_costo | OK |
| actor_exclusivo_usuario_o_sistema | OK |
| usuario_costo_coincide_actor | OK |
| tipo_evento_costo_registrado | OK |

### Costo 4454

- Eventos TECNICO: 1
- Eventos LEGIBLE: 1
- Evento: id=19672, ref=4454, activo=1570, periodo=220, monto=300000.0000, actor=USUARIO, origen=REPOSITORIO

| Validación | Resultado |
|---|---|
| costo_existe | OK |
| exactamente_un_evento_tecnico | OK |
| exactamente_un_evento_legible | OK |
| id_referencia_coincide | OK |
| activo_coincide | OK |
| periodo_coincide | OK |
| monto_coincide | OK |
| naturaleza_en_payload_o_costo | OK |
| actor_exclusivo_usuario_o_sistema | OK |
| usuario_costo_coincide_actor | OK |
| tipo_evento_costo_registrado | OK |

### Costo 4455

- Eventos TECNICO: 1
- Eventos LEGIBLE: 1
- Evento: id=19673, ref=4455, activo=1571, periodo=220, monto=450000.0000, actor=USUARIO, origen=REPOSITORIO

| Validación | Resultado |
|---|---|
| costo_existe | OK |
| exactamente_un_evento_tecnico | OK |
| exactamente_un_evento_legible | OK |
| id_referencia_coincide | OK |
| activo_coincide | OK |
| periodo_coincide | OK |
| monto_coincide | OK |
| naturaleza_en_payload_o_costo | OK |
| actor_exclusivo_usuario_o_sistema | OK |
| usuario_costo_coincide_actor | OK |
| tipo_evento_costo_registrado | OK |

### Costo 4448

- Eventos TECNICO: 1
- Eventos LEGIBLE: 1
- Evento: id=18854, ref=4448, activo=1569, periodo=220, monto=150000.0000, actor=USUARIO, origen=REPOSITORIO

| Validación | Resultado |
|---|---|
| costo_existe | OK |
| exactamente_un_evento_tecnico | OK |
| exactamente_un_evento_legible | OK |
| id_referencia_coincide | OK |
| activo_coincide | OK |
| periodo_coincide | OK |
| monto_coincide | OK |
| naturaleza_en_payload_o_costo | OK |
| actor_exclusivo_usuario_o_sistema | OK |
| usuario_costo_coincide_actor | OK |
| tipo_evento_costo_registrado | OK |

## Integridad

- Eventos G113: 3
- Sin duplicados por referencia: True
- Sin duplicados de id_evento: True
- Costos sin evento: []
- Huérfanos en muestra: []

## Hallazgos actuales

- No se observaron fallas en las validaciones de los costos 4453/4454/4455.

## Limitaciones

- No se ejecutaron escrituras ni se crearon costos nuevos.
- No se usó `GET /activos-biologicos/auditoria` (auditoría M02).
- El costo 4448 se consultó solo como antecedente de G110.

## Dictamen de preparación

**PREPARADO**

Los costos 4453/4454/4455 de G113 permiten comprobar integralmente TC-M06-43 sin generar un nuevo costo. Usarlos como evidencia de G114.

