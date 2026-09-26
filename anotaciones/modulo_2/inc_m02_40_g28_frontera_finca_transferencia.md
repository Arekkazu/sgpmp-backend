# INC-M02-40-G28 — Ausencia de validación de frontera de finca en transferencia interna

**RF:** RF-36 (Gestión Poblacional) + RF-48 (Transferencia Interna).
**Endpoint:** `POST /activos-biologicos/{id_activo}/transferencias`.
**Caso QA:** `TC-M02-G28` / `TC-M02-201` (`DEF-RF48-01`).

**Relación con INC-M02-41-G28 (issue #201):** el mismo informe de QA
(`TC-M02-G28`) documentó dos defectos juntos — `DEF-RF48-01` (este ticket) y
`DEF-RF48-02` (recálculo de densidad, título de `INC-M02-41-G28`/#201). No son
el mismo defecto: este (`#200`) ya estaba resuelto en `dev` sin necesidad de
código; `#201` sí requirió un fix real y tiene su propia rama/PR
(`fix/rf36-inc-m02-41-g28-densidad-transferencia`), para que cada issue tenga
su propia trazabilidad formal.

## Qué reportó QA

`TC-M02-201`: transferir el lote `130` de Alevinera-01 (Finca 1) a Canal-Trucha-01 (Finca 2) respondía `201 Created` en vez de rechazar el movimiento entre fincas distintas.

## Investigación (Paso 0)

Se verificó `registrar_transferencia_use_case.py` en `dev` antes de tocar nada. La validación **E-08** ya existe:

```python
infra_origen = self.infra_port.obtener_activa(dto.infraestructura_origen_id)
if (
    infra_origen is not None and infra_origen.id_finca is not None
    and infra_destino.id_finca is not None
    and infra_destino.id_finca != infra_origen.id_finca
):
    raise BusinessRuleError(code='DESTINO_OTRA_FINCA', ...)
```

Introducida por el commit `df73a16d` ("fix(rf48): validar alcance por finca tambien en el POST de transferencia"), fechado **2026-09-12** — posterior a la ejecución de QA (2026-09-08/09) contra `sgpmp_test`. Mismo patrón que `INC-M02-39-G27`: el entorno de TEST corría una revisión anterior. **No se requiere cambio de código para este defecto.**

Cobertura de prueba ya existente en `dev` para esta regla: `tests/biological_assets/test_registrar_transferencia_e08_finca.py` (`test_rechaza_destino_de_otra_finca`).

## Conclusión

Este ticket se cierra por verificación/documentación — el defecto reportado ya no existe en `dev`.

## Fuera de alcance

- `DEF-RF48-02` (recálculo de densidad) — ver `INC-M02-41-G28`, tiene su propia rama y PR.
- `SIN_INFRAESTRUCTURA_ORIGEN`, `INFRAESTRUCTURA_ORIGEN_INCORRECTA` e `INFRAESTRUCTURA_DESTINO_INVALIDA` responden `400` en vez de `422` — ya señalado como posible defecto en `INC-M02-73-G80` sin confirmar; no se toca aquí.
- Actualizar el contenedor de `sgpmp_test` a una revisión de `dev` posterior a `df73a16d` — responsabilidad de despliegue/DevOps.
