# INC-M09-103-G28 — Discrepancia entre RF-17 (numeric(5,2)) y el esquema PostgreSQL (numeric(8,2))

**RF:** RF-17 (CU03 — Configurar Umbrales y Alertas Ambientales). **Grupo:** TC-M09-G28.

## Qué reportó QA

En la reevaluación V2 de TC-M09-G28 (TC-M09-60 precisión, TC-M09-61 persistencia), ambos casos
quedaron **APROBADOS** — sin defecto funcional. Al verificar el esquema real de PostgreSQL TEST
se encontró que `valor_min`/`valor_max` de `umbrales_ambientales` son `numeric(8,2)`, mientras
que RF-17 documenta `numeric(5,2)`. La escala (2 decimales) coincide en ambos; la diferencia es
la precisión total. QA no afirma que exista un defecto — pide confirmar cuál es la definición
oficial y alinear esquema/modelo o documentación según corresponda. También señala que el ORM
usa `Numeric` sin fijar precisión/escala explícita.

## Investigación (Paso 0)

**Verificado contra `sgpmp_dev` real (vía MCP de postgres; mismo esquema que TEST, ambos parten
de la misma cadena de migraciones/DDL):**

```sql
SELECT column_name, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_schema='modulo9' AND table_name IN ('umbrales_ambientales','niveles_alerta_ambientales');
```

- `umbrales_ambientales.valor_min` / `valor_max` → `numeric(8,2)`.
- `niveles_alerta_ambientales.limite_inferior` / `limite_superior` → `numeric(8,2)`.

**`anotaciones/modulo_9/modulo9_generated.py`** — el archivo autogenerado que refleja el
**diseño original de base de datos del equipo de Análisis/BD** (el mismo documento contra el
que `cu03_gaps_bd_rf17.md`, 2026-06-21, detectó y corrigió los 8 gaps de esa fase: `nombre`
NOT NULL+UNIQUE, `descripcion` NOT NULL, falta de `fecha_actualizacion`, falta de UNIQUE
compuesto — todos ya resueltos) **ya declara `Numeric(8, 2)`** para `valor_min`/`valor_max` y
para `limite_inferior`/`limite_superior`, con `server_default` 0/100. No hay ningún commit ni
gap documentado que haya cambiado esto de `(5,2)` a `(8,2)`: el esquema fue `(8,2)` desde el
diseño original de BD, antes de que existiera implementación de CU03.

**Texto completo de RF-17 (versión 1.0, compartido por el usuario el 2026-09-17):** la sección
`Entradas` del RF solo tipifica tres campos —
`id_parametro_ambiental (serial)`, `id_especie (integer)`, `tipo_variable (varchar(20))` — y
**no menciona `valor_min`/`valor_max` con ningún tipo de dato ni precisión numérica**. Ni
`numeric(5,2)` ni `numeric(8,2)` aparecen en ninguna parte del documento narrativo de RF-17.
Esto significa que el `numeric(5,2)` que cita el incidente de QA **no proviene del texto de
RF-17 en sí** — debe originarse en otro artefacto (un diccionario de datos técnico separado,
una ficha de especificación de BD del equipo de Análisis, o una convención propia del equipo de
QA) que no forma parte de este repositorio ni del documento narrativo revisado.

## Conclusión

**`numeric(8,2)` es la definición correcta/intencional**, respaldada por el diseño original de
base de datos del equipo de Análisis (`modulo9_generated.py`, previo a la implementación de
CU03) y por el esquema desplegado en `sgpmp_dev`/`sgpmp_test`.

**No se puede afirmar que "RF-17 esté desactualizado"** porque, contra el texto completo de
RF-17 v1.0 revisado, el documento simplemente no especifica una precisión numérica para
`valor_min`/`valor_max` — no hay una afirmación contradictoria que corregir ahí. La discrepancia
`numeric(5,2)` reportada por QA debe rastrearse hasta la fuente real de donde QA la tomó (no es
RF-17 mismo) para saber si ese otro documento necesita corrección.

**Acción pendiente fuera de este repositorio:** pedirle a QA/Análisis la fuente exacta del
`numeric(5,2)` citado (probablemente un diccionario de datos o ficha técnica aparte de RF-17) y,
si corresponde, alinear ese documento con `numeric(8,2)` — ya confirmado como el valor correcto
por evidencia de diseño de BD y esquema real. No es un archivo versionado en `sgpmp-backend`.

## Fix aplicado en este repositorio

El gap real y corregible desde este repo era el que QA también señaló: el ORM no declaraba la
precisión/escala real de la columna, dejando el modelo desalineado del esquema físico —

- `src/configuration/infrastructure/models/umbral_ambiental_model.py`: `valor_min`/`valor_max`
  pasan de `Numeric` a `Numeric(8, 2)`.
- `src/configuration/infrastructure/models/nivel_alerta_ambiental_model.py`:
  `limite_inferior`/`limite_superior` pasan de `Numeric` a `Numeric(8, 2)`.

No se tocó la base de datos: el esquema físico ya es correcto (`numeric(8,2)`), no hace falta
ninguna migración.

## Pruebas

- `tests -k umbral -m "not integration"`: 11 passed.
- Suite completa `tests/configuration -m "not integration"`: 236 passed.
- Suite completa `tests -m "not integration"`: 687 passed, mismos 2 fallos preexistentes en
  `test_registrar_transferencia_use_case.py` (no relacionados, ya documentados en el repo).

## Alcance

No se afecta TC-M09-60 ni TC-M09-61 (ya aprobados, sin defecto funcional). No se modifica
`numeric(8,2)` en la base de datos porque ya es el valor correcto. La corrección de la
documentación de RF-17 queda pendiente del equipo de Análisis.
