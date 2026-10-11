# INC-M02-99-G97 — RF-51: rango fuera del ciclo de vida en indicadores

**Issue:** #247
**Endpoint:** `GET /activos-biologicos/{id_activo}/indicadores`

## Causa raíz

`ConsultarIndicadoresDTO` solo validaba `tipo_indicador` y el orden
`fecha_inicio <= fecha_fin`. Ni el DTO, ni `ConsultarIndicadoresUseCase`, ni
`IndicadoresRepository.calcular_indicadores` contrastaban el rango solicitado
contra el ciclo de vida real del activo (nacimiento, inicio de ciclo, baja o
cierre). El repositorio usaba las fechas únicamente como filtro de eventos,
por lo que un rango fuera de la vida del activo simplemente no encontraba
eventos y devolvía `disponible: true` con valores en cero, sin advertencia.

## Fix

`ConsultarIndicadoresUseCase._validar_rango_dentro_del_ciclo_de_vida`
(ejecutada después de resolver el activo y antes de calcular indicadores):

- `fecha_inicio` no puede ser anterior a `detalle_individual.fecha_nacimiento`
  (si aplica) ni a `activo.fecha_inicio_ciclo`.
- `fecha_fin` no puede ser posterior a la fecha del último cambio de estado
  cuando el activo está en `BAJA` o `CERRADO` (nuevo método de solo lectura
  `HistoricoEstadoRepository.obtener_ultimo_cambio`).
- Ambas violaciones lanzan `ValidationError(code='RANGO_FUERA_DE_CICLO_VIDA')`
  → HTTP 400, antes de tocar el cálculo de indicadores.

Sin cambios de esquema de BD — toda la información ya existía en
`activos_biologicos`, `detalles_activos_individuales` e
`historicos_estados_activos`.

## Archivos

- `src/biological_assets/domain/repositories/historico_estado_repository.py` — nuevo método `obtener_ultimo_cambio`
- `src/biological_assets/infrastructure/repositories/historico_estado_repository.py` — implementación
- `src/biological_assets/application/use_cases/gestion/consultar_indicadores_use_case.py` — validación + nueva dependencia `historico_repo`
- `src/biological_assets/infrastructure/routers/activo_biologico_router.py` — inyecta `historico_repo` en el use case
- `tests/biological_assets/test_consultar_indicadores_use_case.py` — nuevo
- `anotaciones/modulo_2/curls_m02_cu12_indicadores_datos.md` — nuevo caso de error E-05

## Verificación

- `pytest tests/biological_assets/` — 62 passed (58 existentes + 4 nuevos).
- Regresión cubierta: rango totalmente dentro del ciclo de vida sigue
  devolviendo 200 sin cambios; activo sin histórico de cambio de estado no
  bloquea por dato ausente.

## Fuera de alcance

El issue #246 (misma familia RF-51, outliers/indicadores inválidos
publicados como válidos) es un defecto distinto y se atiende en un PR
separado.
