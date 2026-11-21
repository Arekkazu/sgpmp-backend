# INC-M07-378-G019 · RF-96 · Comodín en la matriz contable de TEST deja inalcanzable `LINETYPE_NO_CATALOGADO`

> Numeración **provisional** (378, continúa la serie 373-377): confirmar el consecutivo con la
> líder de pruebas / Taiga antes de publicar.

## Título (GitHub y Taiga)

`[INC-M07-378-G019][RF-96] La matriz contable real de TEST tiene un comodín que vuelve inalcanzable LINETYPE_NO_CATALOGADO`

## Cuerpo del issue (pegar igual en GitHub y en Taiga)

[TC-M07-G019][RF-96] La matriz contable real de TEST tiene un comodín que vuelve inalcanzable LINETYPE_NO_CATALOGADO

Incidencia: INC-M07-378-G019
Módulo: M07
RF: RF-96 (catálogo de LineType/cuentas, `_exigir_catalogo()`)
Caso: TC-M07-G019
Ambiente: TEST
Equipo responsable: DBA / Análisis de datos de prueba (no es un defecto de código)
Repositorio: Datos de TEST (`modulo6`/`modulo7`, matriz contable)
Categoría: DATOS_PRUEBA
Severidad: Media
Prioridad: Normal
Evaluador: Julian Badillo

### Problema

El bug original de G019 (el `LineType` no se validaba contra la matriz contable real) ya está
**corregido en código** — confirmado contra `dev` (release v8, 2026-11-20): `_exigir_catalogo()`
ya rechaza con `LINETYPE_NO_CATALOGADO` cuando corresponde, confirmado por prueba unitaria
(`RF-96/TC-M07-G019`). Pero en los **datos reales de TEST**, ese bloqueo nunca llega a dispararse
en la práctica.

### Caso reproducido

`GET /finanzas/configuracion` (matriz contable compartida, cualquier titular) muestra que las
únicas filas con `tipo_hecho=CONSUMO_INSUMO`/`sentido=UNICO` — exactamente las que usa
`linetypes_catalogados()` para el catálogo de Compras — tienen `subtipo_costo=null`:

```json
{"tipo_hecho": "CONSUMO_INSUMO", "sentido": "UNICO", "subtipo_costo": null, "...": "..."}
```

No existe ninguna fila específica por `subtipo_costo` (`ALIMENTO`/`MEDICAMENTO`/`MANO_OBRA`/
`VETERINARIO`) para esa combinación. Por diseño de `_exigir_catalogo()` (`None in catalogados` →
pasa), un `subtipo_costo=null` en la matriz actúa como comodín: **cualquier** valor real de
`subtipo_costo` en un costo pasa la validación sin excepción.

**Control registrado en vivo (2026-11-20/21, con autorización explícita del usuario):** costo
real `id_registro_costo=4589` (titular 901444215, activo 2550, `subtipo_costo=MEDICAMENTO`,
`COMPRA_PROVEEDOR`, factura `QA-CTRL-G019-01`) se registró sin ningún error en el período 628
(noviembre 2026, en ese momento ABIERTO) — confirma en vivo que M06 (RF-90) lo acepta sin
objeciones, como predice el comodín.

### Resultado esperado

La matriz contable de TEST debería tener filas específicas (no comodín) para cada `subtipo_costo`
real que CA-3/CA-5 de RF-96 esperan poder rechazar, de modo que `LINETYPE_NO_CATALOGADO` sea
alcanzable en una prueba real contra TEST.

### Resultado obtenido

La única fila disponible para `CONSUMO_INSUMO`/`UNICO` es un comodín (`subtipo_costo=null`), así
que ningún costo real de ese tipo puede disparar `LINETYPE_NO_CATALOGADO` en TEST hoy.

### Impacto

Severidad: Media (ajustable a Baja si Análisis confirma que producción tiene filas específicas y
el comodín es exclusivo de los datos de prueba).

- El fix de G019 no puede terminar de confirmarse de punta a punta contra TEST (código correcto,
  pero sin dato real que lo ejercite) — quedó pendiente llegar hasta la exportación AAEF
  (requiere cerrar el período 628, acción no autorizada en esta sesión).
- Si producción tuviera el mismo patrón de comodín, la validación de catálogo de RF-96 no
  protegería nada ahí tampoco — **no confirmado**, solo una hipótesis a verificar por Análisis/DBA.

### Causa probable

No confirmada. Es consistente con que la matriz contable de TEST se haya sembrado antes de que
RF-96 definiera subtipos específicos, usando un comodín general en vez de filas por subtipo.

### Acción requerida

1. DBA / Análisis: confirmar si producción tiene filas específicas por `subtipo_costo` para
   `CONSUMO_INSUMO`/`UNICO`, o si también usa un comodín.
2. Si RF-96 espera poder rechazar subtipos no catalogados en la práctica: agregar a la matriz de
   TEST al menos una fila específica (p. ej. solo `ALIMENTO`/`MANO_OBRA` catalogados) para que
   `MEDICAMENTO`/`VETERINARIO` puedan probarse como rechazados.
3. Una vez agregada esa fila, cerrar el período 628 (o uno nuevo) y reconsultar `vista-previa`
   para confirmar que el costo 4589 (o uno nuevo con un subtipo fuera de catálogo) sale como se
   espera.
4. Reevaluar TC-M07-G019 de punta a punta contra TEST.

### Criterios de aceptación

- La matriz contable de TEST tiene al menos una combinación `tipo_hecho`/`sentido` con
  `subtipo_costo` específico (no comodín) para RF-96.
- Un costo con un `subtipo_costo` fuera de esa lista es rechazado con `LINETYPE_NO_CATALOGADO` en
  una corrida real contra TEST, de punta a punta hasta la exportación AAEF.
- Queda documentado si producción comparte o no el patrón de comodín.

### Evidencias

- `tests/Test_Testing/Test_Modulo7/RF-97-Verificacion-Live/ficha.md` (sección "G019 — hallazgo de
  configuración real en TEST").
- Costo real registrado: `id_registro_costo=4589` (título 901444215, período 628) — queda como
  evidencia viva en la base de datos de TEST, no revertido (por decisión explícita del usuario).
- `tests/Test_Testing/Test_Modulo7/RF-96/TC-M07-G019/` (prueba unitaria que confirma el fix de
  código correcto).

### Estado

INC-M07-378-G019 queda abierta y debe ser derivada a DBA / Análisis de datos de prueba. No
requiere ningún cambio de código (el código ya está corregido) — es una decisión sobre los datos
de TEST.

## Atributos personalizados de Taiga

| Atributo | Valor |
|---|---|
| Modulo | M07 |
| RF | RF-96 (catálogo LineType/cuentas) |
| Codigo de error | DATOS_PRUEBA |
| Equipo responsable | DBA / Análisis |
| Severidad | Media |
| Tiempo maximo de solucion | Hasta el martes 24 de noviembre de 2026 (3 días desde el reporte) |
| Fecha de deteccion | 2026-11-20 (control registrado 2026-11-20/21) |
| Fecha limite | 2026-11-24 |
| Evaluador | Julian Badillo |

## Adjuntos (ambas plataformas)

`RF-97-Verificacion-Live/ficha.md` (sección G019) y la carpeta `RF-96/TC-M07-G019/` (prueba
unitaria del fix de código).
