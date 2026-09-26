# INC-M09-33-G32 (#160) e INC-M09-32-G31 (#159) — observabilidad RF-17 ↔ Monitoreo

Issues: `#160` (Monitoreo no expone el umbral efectivo), `#159` (faltan precondiciones TEST).

Ambas quedan **bloqueadas por una misma carencia de correlación cross-módulo**, no por
un defecto funcional del producto (QA las clasifica como BLOCKED, "defecto funcional
confirmado: No").

## El hueco técnico

Monitoreo (M03) resuelve el semáforo histórico a través de `UmbralHistoricoPort`
(`src/telemetry/domain/repositories/umbral_historico_port.py`), cuya implementación
actual es un stub:

- `src/telemetry/infrastructure/adapters/umbral_historico_m09_adapter.py`
  → `obtener_umbral_vigente()` **siempre devuelve `None`** → todo semáforo queda GRIS.

El puerto pide `(tipo_variable: str, id_especie: Optional[int], timestamp)` y devuelve
`{"umbral_min", "umbral_max", "tolerancia_pct"}`. Para resolver el umbral real de M09
hay que cruzar dos fronteras que hoy no existen:

1. **Variable**: M03 expone `tipo_variable` (string) + `categoria_variable`
   (`AMBIENTAL`/`ANIMAL`/`HIDRICA`), mientras M09 resuelve el umbral por
   `id_variable_ambiental` sobre su catálogo `variables_ambientales`
   (Temperatura del agua, pH del agua, Oxígeno disuelto, …). No hay mapeo
   `tipo_variable` ↔ `variables_ambientales` documentado ni persistido.

2. **Especie**: el dashboard/historial no trae `id_especie` de forma fiable. La cadena
   `sensor → activo biológico → especie` (M02) no está correlacionada en las lecturas
   recientes de TEST (solo las de Tilapia Roja traen activo/especie). El propio `#159`
   documenta que no es demostrable.

Además, M09 **no expone umbrales versionados con vigencia temporal** (`fecha_inicio_vigencia`
/ `fecha_fin_vigencia`, RF-59 Restricción 16), que es lo que `UmbralHistoricoPort` supone
para responder "umbral vigente en `timestamp`".

## Qué falta para cerrar (acción coordinada)

| Responsable | Entregable |
|---|---|
| AIoT / M03 | Mapeo `sensor → variable → activo → especie` verificable (canal read-only o API), y una relación `tipo_variable` ↔ `variables_ambientales` de M09. |
| Implementación | Sustituir `UmbralHistoricoM09Adapter` por un adaptador real que consulte `umbral_ambiental_repository.obtener_por_especie_y_variable(id_especie, id_variable_ambiental)`. |
| Implementación | Exponer en `LecturaHistorica`/`EstadoSensorActual` la referencia al umbral efectivo (`id_umbral_ambiental`, `valor_min`, `valor_max`) para satisfacer "Opción 1" del `#160`. |
| Implementación / DBA | Poblar TEST con la combinación `especie→activo→dispositivo→sensor→variable` + usuario con finca (precondiciones de `#159`). |

## Decisión de esta iteración

No se toca código de Monitoreo/M09 para esto: implementar un adaptador real sin el mapeo
de variables ni la correlación de especie produciría una resolución de umbral **incorrecta**
(umbral equivocado para la variable/especie), peor que el GRIS actual. Se deja documentado
el camino exacto para cuando AIoT entregue la correlación.
