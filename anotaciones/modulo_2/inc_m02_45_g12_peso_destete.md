# INC-M02-45-G12 — Falta configuración de `peso_destete` en RF-16

## Qué reportó QA

`TC-M02-014` esperaba que registrar un activo con `atributos_dinamicos:
{"peso_destete": 5}` para la especie 4 (Cachama Blanca) fuera rechazado con
`400` por estar fuera del rango 20–40 kg. Al consultar
`GET /configuracion/metricas?id_especie=4&solo_activas=true` la especie no
tenía ninguna métrica `peso_destete` configurada, así que la regla de rango
no se podía ni ejecutar.

## Diagnóstico

Esto **no es un defecto de código**. RF-16 no exige ninguna métrica
específica por nombre — el admin/veterinario configura las que necesite por
especie (`POST /configuracion/metricas`), y el mecanismo de validación de
rango (`valor_min`/`valor_max`) para `atributos_dinamicos` ya existe
(`RegistrarActivoBiologicoUseCase._validar_atributos_dinamicos`). El gap real
era que nadie había configurado esa métrica concreta para esa especie.

Al intentar aplicar la solución (insertar la métrica) aparecieron dos
bloqueadores preexistentes, ninguno introducido por este cambio:

### 1. Migración `b92f7e1a4c63` sin aplicar en `sgpmp` (dev)

El PR #245 (`fix/rf16-rf33-inc-m02-47-g17-atributos-dinamicos`, mergeado a
`dev` el 2026-09-11) agregó las columnas `tipo_dato`/`es_obligatorio` a
`modulo9.metricas_produccion` vía la migración `b92f7e1a4c63`, pero el
propio PR deja explícito que **no se aplicó a `sgpmp_dev` ni a `pruebas`**.
Sin esa migración, `MetricaProduccionModel` (que ya mapea esas dos columnas
desde ese PR) rompe con "columna no existe" en cualquier query — es decir,
`/configuracion/metricas` y el registro de activos con `atributos_dinamicos`
estaban rotos en `dev` desde que se mergeó ese PR hasta que se aplicó esta
migración.

Se aplicó con `alembic upgrade head` a ambas bases:

```
sgpmp (dev):  fa915f4d113e -> b92f7e1a4c63
pruebas:      56cd2038ff06 -> b92f7e1a4c63  (9 migraciones pendientes, no solo esta)
```

### 2. Datos preexistentes que violaban `chk_metricas_tipo_medicion`

La migración incluye un backfill (`UPDATE ... SET tipo_dato = ...`) que
toca todas las filas de `metricas_produccion`, y eso revalida el CHECK
`chk_metricas_tipo_medicion` (está como `NOT VALID`, así que nunca se había
revalidado contra las filas existentes). En `sgpmp` (dev) había 8 filas con
`tipo_medicion` fuera del dominio válido (`PESO`/`VOLUMEN`/`LONGITUD`/`CONTEO`/`OTRO`),
seguramente datos de antes de que existiera ese CHECK:

| id | nombre | unidad | valor original | corregido a |
|----|--------|--------|-----------------|-------------|
| 1 | Peso promedio individual | g | `manual` | `PESO` |
| 2 | Biomasa total | kg | `calculada` | `PESO` |
| 3 | Tasa de mortalidad | % | `calculada` | `OTRO` |
| 4 | Factor conversión alimenticia (FCR) | ratio | `calculada` | `OTRO` |
| 5 | Densidad de siembra | ind/m² | `manual` | `OTRO` |
| 6 | Tasa de crecimiento específico (SGR) | %/día | `calculada` | `OTRO` |
| 7 | Consumo de alimento diario | kg/día | `manual` | `OTRO` |
| 8 | Supervivencia acumulada | % | `calculada` | `OTRO` |
| 14 | Talla tilapia | cm | `TALLA` | `LONGITUD` |

Se corrigió con `UPDATE` directo (vía MCP postgres) antes de reintentar la
migración. `pruebas` no tenía estas filas (no tiene datos de M09 precargados
más allá de especies base), así que solo necesitó la migración.

`pruebas` también tenía `modulo2.estados_activos_biologicos` completamente
vacío (bloqueaba cualquier registro de activo biológico, no solo esta
prueba) — se sembró con el mismo catálogo de 6 estados que ya existe en
`sgpmp` (`ACTIVO`, `INACTIVO`, `EN_TRATAMIENTO`, `AISLADO`, `CERRADO`,
`BAJA`).

## Configuración aplicada (RF-16, no código)

Insertado en `modulo9.metricas_produccion` de `sgpmp` y `pruebas`:

```sql
INSERT INTO modulo9.metricas_produccion
  (nombre, unidad_medida, tipo_medicion, tiene_estado, id_especie,
   aplica_a_tipo_activo, es_activo, valor_min, valor_max, tipo_dato, es_obligatorio)
VALUES
  ('peso_destete', 'kg', 'PESO', true, 4, 'AMBOS', true, 20, 40, 'NUMERICO', false);
```

Con esto, `POST /activos-biologicos` con `atributos_dinamicos: {"peso_destete": 5}`
para la especie 4 ahora sí encuentra la métrica, compara `5 < 20` y rechaza
el registro con `ATRIBUTO_FUERA_DE_RANGO` — el flujo que pedía TC-M02-014.

**Nota de código HTTP:** el issue esperaba `400`, pero `ATRIBUTO_FUERA_DE_RANGO`
se lanza como `BusinessRuleError` (**422**) en `_validar_atributos_dinamicos`,
igual que el resto de violaciones de rango/tipo de esa misma función — no es
un comportamiento nuevo de esta corrección ni algo que se haya cambiado aquí.
`400` queda reservado para errores de formato (ej. tipo de dato incorrecto a
nivel Pydantic), consistente con la tabla de errores de `CLAUDE.md`.

## Limitación conocida, fuera de alcance de esta issue

El nombre `peso_destete` (snake_case, con `_`) **no se puede crear a través
del endpoint real** `POST /configuracion/metricas`: `RegistrarMetricaDTO`
valida `nombre` contra
`^[A-Za-zÁÉÍÓÚáéíóúÑñ][A-Za-zÁÉÍÓÚáéíóúÑñ0-9 \-()/]*$`, que no admite
guion bajo. La coincidencia entre el nombre de la métrica y la clave del
JSON `atributos_dinamicos` es literal (case-insensitive, sin normalizar
espacios/guiones) en `_validar_atributos_dinamicos`, así que en la práctica
un admin solo puede configurar métricas cuyo nombre matchee exactamente las
claves que use el cliente (p. ej. "Peso Destete" con espacio, si el cliente
también manda esa clave con espacio). RF-16 no prohíbe el guion bajo en el
nombre, así que esta restricción del DTO no viene del RF — es una decisión
de implementación anterior a esta issue. No se modifica aquí (no es lo que
reporta INC-M02-45-G12); si el equipo quiere que los nombres de métrica
sean utilizables como claves JSON de forma consistente, es una issue aparte.
