# INC-M09-06-G15 — Normalización de tipos históricos de métricas RF-16

## Desvío confirmado

`PATCH /configuracion/metricas/{id}/desactivar` respondía `500 ERROR_INTERNO` para la
métrica 1 de TEST. La fila histórica almacenaba `tipo_medicion='manual'`, pero el dominio
RF-16 solo admite `PESO`, `VOLUMEN`, `LONGITUD`, `CONTEO` y `OTRO`.

`SqlAlchemyMetricaProduccionRepository._a_entidad()` intentaba construir
`TipoMedicion('manual')` y lanzaba `ValueError` antes de que
`SqlAlchemyDependenciaMetricaRepository` comprobara los cuatro eventos productivos asociados.
El diagnóstico y la expectativa `HTTP 422` del equipo de QA son correctos.

## Causa histórica

Antes de RF-16, `tipo_medicion` describía el método de obtención (`manual` o `calculada`).
RF-16 reutilizó la columna para representar la magnitud. La migración `192872fafd40` agregó
`chk_metricas_tipo_medicion` como `NOT VALID`, por lo que protegía escrituras nuevas pero no
normalizaba ni rechazaba las filas anteriores.

La clasificación ya estaba documentada por el proyecto:

| ID | Métrica histórica | Valor anterior | RF-16 |
| --- | --- | --- | --- |
| 1 | Peso promedio individual | `manual` | `PESO` |
| 2 | Biomasa total | `calculada` | `PESO` |
| 3 | Tasa de mortalidad | `calculada` | `OTRO` |
| 4 | Factor de conversión alimenticia | `calculada` | `OTRO` |
| 5 | Densidad de siembra | `manual` | `OTRO` |
| 6 | Tasa de crecimiento específico | `calculada` | `OTRO` |
| 7 | Consumo de alimento diario | `manual` | `OTRO` |
| 8 | Supervivencia acumulada | `calculada` | `OTRO` |
| 14 | Talla tilapia | `TALLA` | `LONGITUD` |

## Corrección

La revisión Alembic `9a5de7d9973f` fue creada con el mensaje requerido:

```text
v5.3.0_rf16_normalizar_tipos_medicion_legacy
```

La migración:

- aplica la clasificación histórica de los indicadores globales;
- convierte otros valores `manual`/`calculada` según su unidad de medida;
- convierte `TALLA` a `LONGITUD`;
- canonicaliza valores válidos escritos con espacios o minúsculas;
- alinea `tipo_dato` (`NUMERICO` o `ENTERO`) en las filas corregidas;
- detiene el despliegue si encuentra un valor desconocido, sin reinterpretarlo silenciosamente;
- crea el CHECK si falta y ejecuta `VALIDATE CONSTRAINT` al finalizar.

No se agregó `MANUAL` al enum porque no es una magnitud y hacerlo mantendría dos conceptos
distintos dentro de la misma columna.

## Validación

En `sgpmp_dev`, la métrica 1 tenía cuatro eventos productivos. Dentro de una transacción
exterior se aplicó exactamente el DML de la migración y se ejecutó el endpoint con sus
repositorios reales:

```text
Antes:               CONTEO / ENTERO / activa
Normalizada:          PESO / NUMERICO / activa
PATCH /desactivar:    422 METRICA_CON_REGISTROS
Dependencias:         4
Después del endpoint: PESO / NUMERICO / activa
Después del rollback: CONTEO / ENTERO / activa
```

La conexión `member_dev` no es propietaria de la tabla (`owner=dba`), por lo que la prueba
oficial ejecutó el DML y la regla HTTP pero no el `ALTER TABLE ... VALIDATE`. La prueba de
integración automatizada ejecuta la revisión completa mediante `MigrationContext` en una base
de pruebas con permisos de propietario y comprueba que el CHECK quede validado.

No quedaron cambios ni datos de prueba en la base oficial.
