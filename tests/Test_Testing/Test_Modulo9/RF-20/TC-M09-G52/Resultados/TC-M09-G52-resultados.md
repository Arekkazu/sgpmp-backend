# TC-M09-G52 (TC-M09-103, TC-M09-104, TC-M09-260) — Activación y desactivación de área productiva

**RF-20 v1.1 / CU-04 — Gestionar Infraestructura Productiva**

## Estado vigente — reevaluación 2026-10-06 (RF-20 v1.1, RFC-009)

**Resultado: PASA**: 20 requests, 40 assertions, 0 failed. Un sub-escenario del 260 queda
**pendiente de aclarar con Análisis**, como indica la ficha. Se registra lo observado sin darlo
por fallido.

| Sub-caso | Antes → operación → después | Resultado |
|---|---|---|
| TC-M09-103 | Área 166 sin dependencias: activa → `PATCH /desactivar` `200` → relectura `es_activo: false` | ✅ PASA |
| TC-M09-104 | Área 167 con un lote ACTIVO de 25 animales alojado (M02): activa → `422 INFRAESTRUCTURA_CON_DEPENDENCIAS` (*"…tiene dispositivos y/o activos biológicos asociados. Debe desvincular o trasladar los recursos antes de desactivar la infraestructura."*) → relectura sigue activa | ✅ PASA |
| TC-M09-260 (especie activa, modelo coherente) | Área 166 (inactiva tras el 103, especie A + `MODELO_AVES`) → `PATCH /reactivar` `200` → relectura activa, conserva especie A y `MODELO_AVES` | ✅ PASA |
| TC-M09-260 (especie inactivada después) | Área 168 (especie B + `MODELO_PORCINOS`) desactivada; luego especie B desactivada en RF-15 → `PATCH /reactivar` **`200`** → relectura: área **activa** con la especie B inactiva | ⏸️ PENDIENTE DE ACLARAR |

**Lo observado en el escenario pendiente:** `ReactivarInfraestructuraUseCase` solo valida que el
área exista, que esté inactiva y que su finca esté activa. No revalida la especie ni la coherencia
especie↔modelo, así que el área vuelve a quedar activa apuntando a una especie inactiva. Para
comparar, al registrar y al editar un área con cambio de especie, el sistema sí rechaza una
especie inactiva (`422 ESPECIE_INVALIDA`, ver G49). Si Análisis define que la reactivación debe
rechazarse en este caso, esto pasa a ser un defecto.

Sobre "respetar la coherencia y las dependencias" en la reactivación: las dependencias no aplican,
porque un área solo puede estar inactiva si se desactivó sin dependencias (TC-M09-104). La
coherencia del modelo tampoco se puede romper mientras el área está inactiva: el fix `258ceca2`
impide cambiar el `tipo_modelo` de una especie si deja áreas incoherentes, activas o inactivas.
El único hueco es el de la especie inactiva.

Cambios en la colección (reescrita):
- La versión anterior usaba áreas compartidas de TEST (`id=10`, que esa misma corrida dejó
  desactivada, así que no era repetible; e `id=1` como área con dependencias). Ahora crea su
  propia finca, dos especies, tres áreas y un lote de activos biológicos como dependencia
  operativa. No usa dispositivos IoT: el lote basta para disparar la regla, que revisa
  dispositivos **o** activos.
- Se agregaron los dos escenarios del TC-M09-260.

La auditoría de la reactivación como `UPDATE` se verifica en TC-M09-G53, según la ficha.

Evidencia: `Resultados/reporte-TC-M09-G52.html` (Newman htmlextra, 2026-10-06).

---

## Evaluación anterior (RF-20 v1.0): histórico

**Estado del caso: PASA** (7 requests, 13 assertions, 0 failed) — pero en el camino de
seleccionar los datos de prueba se encontró un **bug real**, documentado abajo.

`DesactivarInfraestructuraUseCase` no toca `modulo9.tipos_area`, así que este caso **no**
está afectado por el gap de `TC-M09-G48/NOTA_BLOQUEO.md`.

## Resultado por sub-caso

| Sub-caso | Verificación | Resultado |
|---|---|---|
| TC-M09-103 | Área sin dependencias (`id=10`, "Invernadero Norte") → `PATCH .../desactivar` → `200`, `es_activo: false`, confirmado con relectura independiente | ✅ |
| TC-M09-104 | Área con dependencias activas (`id=1`, "Estanque-01") → `422 INFRAESTRUCTURA_CON_DEPENDENCIAS`, sin alterar su estado | ✅ |

## Bug encontrado durante la selección de datos (no bloquea este caso, pero es real)

El primer candidato elegido para "sin dependencias" fue `id=6` ("Piscina-Cam-01"), porque
`modulo9.vw_rf20_dependencias_infraestructuras` la reportaba con `dispositivos_activos = 0`
y no tiene activos biológicos — es decir, pasaba el chequeo que usa
`InfraestructuraDependencyAdapter.tiene_dependencias_activas()`.

Al intentar desactivarla, la API devolvió `500 Internal Server Error`:
```json
{"error_code":"ERROR_INTERNO","message":"Error inesperado en base de datos", ...}
```

Reproducido directamente contra Postgres (fuera de la app) para confirmar la causa exacta:

```
InternalError: AREA_IN_USE: El área "Piscina-Cam-01" tiene 0 dispositivo(s) activo(s) y
3 sensor(es) asociado(s). Desvincule los recursos antes de desactivar la infraestructura.
CONTEXT: PL/pgSQL function modulo9.trg_fn_infraestructura_no_desactivar_en_uso() line 19
```

**Causa raíz:** hay dos capas de defensa para esta regla, y usan criterios distintos:

- **Aplicación** (`InfraestructuraDependencyAdapter`, consulta `vw_rf20_dependencias_infraestructuras`):
  cuenta dispositivos IoT con `dispositivos_iot.es_activo = TRUE`. Un área con sensores
  asociados a dispositivos **inactivos** pasa este chequeo (cuenta 0).
- **Trigger de BD** (`trg_fn_infraestructura_no_desactivar_en_uso`): cuenta filas en
  `modulo9.sensores_areas_asociadas` con `tiene_estado = TRUE` (asociación vigente),
  **sin mirar si el dispositivo enlazado está activo o no**. Un área con 3 asociaciones
  vigentes (aunque a dispositivos inactivos) la bloquea.

Como la aplicación no anticipa este caso, la excepción del trigger no está mapeada en
`src/shared/db_error_translator.py` y cae en la rama genérica (`InfrastructureError` /
`ERROR_INTERNO`, 500) en vez de devolver el mismo `422 INFRAESTRUCTURA_CON_DEPENDENCIAS`
que la aplicación usa para los demás casos de dependencia. El usuario final vería un error
genérico de servidor en un flujo que en realidad es un rechazo de regla de negocio válido.

**Impacto:** cualquier intento de desactivar un área con sensores asociados a dispositivos
inactivos (probablemente un escenario real y no infrecuente — un sensor puede quedar
"vigente" en la asociación aunque su dispositivo se haya desactivado) sale como 500 en vez
de 422. No bloquea el caso de prueba (se evitó el escenario cambiando de área), pero es un
defecto de la aplicación que vale la pena reportar aparte.

## Cómo reproducir

```sql
UPDATE modulo9.infraestructuras SET tipo = 'estanque', es_activo = false
WHERE id_infraestructura = 6;
-- ERROR: AREA_IN_USE: ... 3 sensor(es) asociado(s) ...
```
o vía API: `PATCH /configuracion/infraestructuras/6/desactivar` con un administrador
autenticado.
