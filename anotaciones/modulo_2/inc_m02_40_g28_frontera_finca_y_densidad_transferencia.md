# INC-M02-40-G28 — Frontera de finca y densidad en transferencia interna de lotes

**RF:** RF-36 (Gestión Poblacional) + RF-48 (Transferencia Interna).
**Endpoint:** `POST /activos-biologicos/{id_activo}/transferencias`.
**Caso QA:** `TC-M02-G28`, dos defectos (`DEF-RF48-01`, `DEF-RF48-02`).

**Relación con INC-M02-41-G28 (issue #201):** el mismo informe de QA
(`TC-M02-G28`) documentó los dos defectos juntos, pero luego se abrieron como
issues individuales — `#200` (`INC-M02-40-G28`) es específicamente
`DEF-RF48-01` (frontera de finca) y `#201` (`INC-M02-41-G28`) es
específicamente `DEF-RF48-02` (recálculo de densidad, mismo lote 130, misma
transferencia Alevinera-01 500 m² → Estanque-01 2500 m², mismo `TC-M02-202`).
No son el mismo defecto entre sí, pero esta rama ya resuelve ambos: `#200`
queda confirmado como ya corregido en `dev` (sección DEF-RF48-01 arriba) y
`#201` es el fix de código real de esta rama (sección DEF-RF48-02). No se
abre una rama ni un PR separado para `INC-M02-41-G28`; el PR de esta rama
cierra los dos issues.

## DEF-RF48-01 — Ausencia de validación de frontera de finca (ya resuelto en `dev`)

**Qué reportó QA (`TC-M02-201`):** transferir el lote `130` de Alevinera-01 (Finca 1) a Canal-Trucha-01 (Finca 2) respondía `201 Created` en vez de rechazar el movimiento entre fincas distintas.

**Investigación (Paso 0):** se verificó `registrar_transferencia_use_case.py` en `dev` antes de tocar nada. La validación **E-08** ya existe:

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

## DEF-RF48-02 — Densidad no se recalculaba tras la transferencia (fix real de este INC)

**Qué reportó QA (`TC-M02-202`):** lote `130` (`cantidad_actual=5`), transferido de Alevinera-01 (500 m², densidad 0.01) a Estanque-01 (2500 m²) — se esperaba `densidad` recalculada a `0.002` y quedó en `0.01`. Confirmado en BD (`sgpmp_test`): `id_infraestructura` y el historial de movimientos se actualizaban correctamente; `modulo2.detalles_activos_biologicos_poblacionales.densidad` nunca se tocaba.

**Verificado que este sí es un gap real en `dev`:** `RegistrarTransferenciaUseCase._execute()` actualiza `activos_biologicos.id_infraestructura` y `historial_infraestructura_activo` con SQL directo, pero nunca toca la tabla de detalle poblacional.

### Fix

`ActivoBiologico` (dominio) gana un método público `recalcular_densidad(superficie)`, extraído de la lógica que ya usaba `aplicar_evento_crecimiento` (mismo cálculo, `cantidad_actual / superficie`, sin tocar nada si no hay superficie configurada — mismo criterio ya establecido para ese caso):

```python
def recalcular_densidad(self, superficie: Optional[Decimal]) -> None:
    self._validar_tipo_poblacional()
    dp = self.detalle_poblacional
    if superficie and superficie > 0:
        cantidad_actual = Decimal(str(dp.cantidad_actual or 0))
        dp.densidad = cantidad_actual / superficie
```

`RegistrarTransferenciaUseCase._execute()`, inmediatamente después de actualizar `id_infraestructura` (paso c) y antes de registrar el movimiento (paso d), para activos `POBLACIONAL`:

```python
if activo.tipo == 'POBLACIONAL' and activo.detalle_poblacional:
    activo.recalcular_densidad(infra_destino.superficie)
    self.db.execute(
        text(
            'UPDATE modulo2.detalles_activos_biologicos_poblacionales '
            'SET densidad = :densidad WHERE id_activo_biologico = :id'
        ),
        {'id': id_activo, 'densidad': activo.detalle_poblacional.densidad},
    )
```

`infra_destino` ya estaba resuelto en memoria desde la validación E-05; no se agregó ninguna consulta nueva. Se sigue el mismo estilo de SQL directo que ya usa el resto del método (no se pasó por el repository/ORM, consistente con cómo este use case ya actualiza `id_infraestructura` e `historial_infraestructura_activo`).

## Pruebas

`tests/biological_assets/test_registrar_transferencia_densidad.py` — 3 casos nuevos, fakes escritos a mano:

- Caso `TC-M02-202`: 5 individuos, de 500 m² (0.01) a 2500 m² → densidad recalculada a `0.002`.
- Activo `INDIVIDUAL` (sin `detalle_poblacional`) → no se ejecuta ningún `UPDATE` de densidad.
- Destino sin `superficie` configurada → la densidad conserva el valor previo (no hay con qué calcularla), sin romper la transferencia.

Suite completa sin regresiones: 664 passed (661 previos + 3 nuevos), mismos 2 fallos preexistentes en `test_registrar_transferencia_use_case.py` (no relacionados, confirmados fallando igual en `origin/dev`).

## Fuera de alcance

- `SIN_INFRAESTRUCTURA_ORIGEN`, `INFRAESTRUCTURA_ORIGEN_INCORRECTA` e `INFRAESTRUCTURA_DESTINO_INVALIDA` responden `400` (`ValidationError`) en vez de `422` — ya señalado como posible defecto en `INC-M02-73-G80` sin confirmar; no se toca aquí.
- Recalcular `densidad` tras un evento de `BAJA` (`aplicar_evento_baja` no la toca) es el mismo patrón de gap, pero no fue parte de este reporte de QA — queda para su propio issue si el equipo decide auditarlo.
- Actualizar el contenedor de `sgpmp_test` a una revisión de `dev` posterior a `df73a16d` (DEF-RF48-01) — responsabilidad de despliegue/DevOps.
