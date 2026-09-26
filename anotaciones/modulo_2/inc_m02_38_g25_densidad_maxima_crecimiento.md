# INC-M02-48-G25 — Densidad máxima por especie en RF-36

**RF:** RF-36 — Gestión poblacional de activos biológicos.

## Resultado del reanálisis

La corrección anterior de INC-M02-38-G25 infería el límite como
`infraestructuras.capacidad_maxima / superficie`. La reevaluación v3 confirmó
que esa interpretación no cumple el contrato:

- `capacidad_maxima` es el cupo físico de una infraestructura;
- RF-36 exige una densidad biológica máxima configurada en M09 por especie;
- todas las capacidades de las infraestructuras de `sgpmp_dev` están en `NULL`;
- M09 no tenía un atributo que representara `densidad_maxima_por_especie`.

Además, `cantidad_medida` en un evento de crecimiento describe la muestra. No
reemplaza `cantidad_actual`: RF-36 establece que la población cambia únicamente
por ingresos y bajas.

## Corrección

La revisión Alembic `7abae1ee50f6` (`v5.3.0`) agrega a
`modulo9.especies`:

```text
densidad_maxima_por_especie NUMERIC(10,4) NULL
```

El valor debe ser mayor a cero cuando se configura. Las especies existentes
quedan inicialmente en `NULL`; no se inventan límites biológicos.

El campo se incorporó a los contratos de registro, edición y consulta de
especies de M09. Si se omite al editar, conserva su valor; si se envía `null`,
lo elimina de forma explícita.

M02 aplica una política única:

```text
densidad_actual = cantidad_actual / superficie
```

La política se valida en:

- registro inicial de un lote poblacional;
- evento de crecimiento;
- transferencia a otra infraestructura.

Resultados controlados:

```text
409 DENSIDAD_MAXIMA_SUPERADA
422 DENSIDAD_MAXIMA_NO_CONFIGURADA
422 SUPERFICIE_INFRAESTRUCTURA_INVALIDA
```

`capacidad_maxima` sigue validándose de manera independiente cuando aplica,
pero ya no se usa como sustituto del límite biológico por especie.

## Precondiciones de prueba

Para obtener el `409`, QA debe:

1. configurar en M09 una densidad máxima positiva para la especie del lote;
2. usar un lote activo con fase productiva activa;
3. preparar `cantidad_actual / superficie` por encima del límite;
4. registrar el evento de crecimiento con una medición válida.

Cambiar únicamente `cantidad_medida` no puede producir el `409`, porque no
modifica la población del lote. El lote 345 de la colección v3 tampoco alcanza
esta regla mientras no tenga una fase activa: primero responde
`422 SIN_FASE_ACTIVA`.

## Base oficial

La inspección de `sgpmp_dev` se realizó en modo lectura. La cuenta
`member_dev` no es propietaria de `modulo9.especies` y PostgreSQL rechazó la
prueba transaccional del DDL antes de efectuar cambios. La migración se validó
mediante la generación SQL offline de Alembic y deberá ejecutarla una cuenta
con privilegios durante el despliegue.
