# TC-M09-G52 (TC-M09-103, TC-M09-104) — Reglas de desactivación de área productiva

**RF-20 / CU-04 — Gestionar Infraestructura Productiva**
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
