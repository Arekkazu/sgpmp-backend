# INC-M02-41-G28 — Omisión de recálculo de densidad poblacional tras transferencia interna

**RF:** RF-36 (Gestión Poblacional) + RF-48 (Transferencia Interna).
**Endpoint:** `POST /activos-biologicos/{id_activo}/transferencias`.
**Caso QA:** `TC-M02-G28` / `TC-M02-202` (`DEF-RF48-02`).

**Relación con INC-M02-40-G28 (issue #200):** el mismo informe de QA
(`TC-M02-G28`) documentó dos defectos juntos — `DEF-RF48-01` (frontera de
finca, título de `INC-M02-40-G28`/#200) y `DEF-RF48-02` (este ticket). No son
el mismo defecto: `#200` ya estaba resuelto en `dev` sin necesidad de código
(commit `df73a16d`); este ticket sí requirió un fix de código real. Se separan
en ramas y PRs independientes para que cada issue tenga su propia
trazabilidad formal.

## Qué reportó QA

Lote `130` (`cantidad_actual=5`), transferido de Alevinera-01 (500 m², densidad `0.01`) a Estanque-01 (2500 m², misma finca). Se esperaba `densidad` recalculada a `0.002` (`5 / 2500`) y quedó en `0.01`. Confirmado en BD (`sgpmp_test`): `id_infraestructura` y el historial de movimientos se actualizaban correctamente; `modulo2.detalles_activos_biologicos_poblacionales.densidad` nunca se tocaba.

## Investigación

`RegistrarTransferenciaUseCase._execute()` actualiza `activos_biologicos.id_infraestructura` y `historial_infraestructura_activo` con SQL directo, pero nunca toca la tabla de detalle poblacional — gap real confirmado en `dev`, no un problema de despliegue de TEST.

## Fix

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

`infra_destino` ya estaba resuelto en memoria desde la validación E-05 del use case; no se agregó ninguna consulta nueva. Se sigue el mismo estilo de SQL directo que ya usa el resto del método (no se pasó por el repository/ORM, consistente con cómo este use case ya actualiza `id_infraestructura` e `historial_infraestructura_activo`).

## Pruebas

`tests/biological_assets/test_registrar_transferencia_densidad.py` — 3 casos nuevos, fakes escritos a mano:

- Caso `TC-M02-202`: 5 individuos, de 500 m² (0.01) a 2500 m² → densidad recalculada a `0.002`.
- Activo `INDIVIDUAL` (sin `detalle_poblacional`) → no se ejecuta ningún `UPDATE` de densidad.
- Destino sin `superficie` configurada → la densidad conserva el valor previo (no hay con qué calcularla), sin romper la transferencia.

Suite completa sin regresiones: 664 passed (661 previos + 3 nuevos), mismos 2 fallos preexistentes en `test_registrar_transferencia_use_case.py` (no relacionados, confirmados fallando igual en `origin/dev`).

## Fuera de alcance

- Recalcular `densidad` tras un evento de `BAJA` (`aplicar_evento_baja` no la toca) es el mismo patrón de gap, pero no fue parte de este reporte de QA — queda para su propio issue si el equipo decide auditarlo.
- La validación de frontera de finca (`DEF-RF48-01`) — ver `INC-M02-40-G28`, no forma parte de este ticket.
