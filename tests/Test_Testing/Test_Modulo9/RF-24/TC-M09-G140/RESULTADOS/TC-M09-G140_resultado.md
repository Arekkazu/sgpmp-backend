# TC-M09-G140 — Resultado

Informe único del grupo. Cubre sus tres casos y los dos RUN, uno por ambiente.

## Decisión general

**Resultado del grupo: BLOQUEADO / NO VERIFICABLE**

| Caso | Ambiente | Resultado | Motivo |
|---|---|---|---|
| TC-M09-284 | TEST | BLOQUEADO / NO VERIFICABLE | TEST no publica ninguna operación VISION: compuerta de ejecutabilidad en 0/10. No hay fuente formal de observaciones ni línea base que comparar. |
| TC-M09-285 | TEST | BLOQUEADO / NO VERIFICABLE | Misma causa primaria. Además, ε, el máximo de iteraciones y la regla exacta de refinamiento no son consultables desde ninguna fuente formal. |
| TC-M09-286 | LOCAL AISLADO | BLOQUEADO / NO VERIFICABLE | El artefacto de la rama no contiene la implementación VISION: compuerta previa en 0/8. No se levantó laboratorio para una función inexistente. |

**POST VISION ejecutados: 0** de los 5 planificados (3 en TEST, 2 en LOCAL). No se creó ningún
dato en TEST, no se ejecutó SQL sobre TEST y no se levantó ningún laboratorio local.

## Entorno y RUN

**Rama:** qa/juan-esteban-rf24-v2
**Commit:** 30ddd72144102a60af006b265a20cb18c1c72c85

| Componente | Ambiente | RUN_ID | Evidencia |
|---|---|---|---|
| TC-M09-284 y TC-M09-285 | TEST — https://api.inmero.co/back-sigab-test | `run-test-20261007-142538` | `RESULTADOS/run-test-20261007-142538/evidencia.json` · `pytest.xml` |
| TC-M09-286 | LOCAL AISLADO (no levantado) | `run-local-20261007-142538` | `RESULTADOS/run-local-20261007-142538/evidencia.json` · `pytest.xml` |

Los RUN se separan porque los ambientes son distintos; no son reintentos. Sobre TEST solo se
ejecutó `GET /openapi.json`, sin credenciales y sin escrituras. No existe `backend.log` del
componente local porque no se levantó ningún backend.

## Ejecutabilidad VISION

La decisión se apoya en dos verificaciones empíricas independientes, una por ambiente.

### En TEST — el contrato desplegado

| # | Punto de la compuerta | Resultado |
|---|---|---|
| 1 | Operación VISION publicada | **NO** |
| 2 | Fuente formal de observaciones / vector VISION | **NO** |
| 3 | Componentes numéricos del vector identificados | **NO** |
| 4 | Vínculo cámara → área → observación | **NO** |
| 5 | `apto_para_ia` consultable por flujo formal | **NO** |
| 6 | Mínimo N consultable | **NO** |
| 7 | Persistencia de línea base verificable | **NO** |
| 8 | ε consultable | **NO** |
| 9 | Máximo de iteraciones consultable | **NO** |
| 10 | Regla de refinamiento suficientemente definida | **NO** |

**Cumplidos: 0 de 10.**

En las **210 rutas** del contrato, `VISION` **no aparece como palabra ni una sola vez**. Todas
las coincidencias de la subcadena vienen de "pro**visión**":

```text
ProvisionNic41Response · /suministros/nic41/{id_provision} · corregir_provision_suministros_nic41
CorregirProvisionDto   · ConsultaVersionesProvisionResponse
```

Contarlas habría producido un falso positivo de ejecutabilidad, así que la compuerta cuenta la
palabra como token. Tampoco existe enum alguno con `VISION`, ni ruta de `vision`, `baseline`,
`linea-base`, `observacion`, `vector` o `comportamiento`.

El DTO del registro de calibración lo confirma:

```text
RegistrarCalibracionDTO
  properties: id_dispositivo_iot, id_infraestructura, valor_referencia,
              ganancia, offset, fecha_calibracion, observaciones
  required  : id_dispositivo_iot, id_infraestructura, fecha_calibracion
  declara modo_calibracion: NO
```

Sin `modo_calibracion` no hay forma de solicitar la modalidad.

`apto_para_ia` sí existe, pero solo dentro de `TelemetriaCalidadSchema` —calidad de la telemetría
de sensores: índice de calidad, clasificación, flags, límites físicos— y **ningún endpoint lo
expone**: 0 operaciones lo devuelven o lo aceptan. No se asume que sea el vector de comportamiento
VISION por llevar ese campo; el caso exige una entidad con cámara, área, timestamp y componentes.

Ausentes en todo el contrato: `linea_base`, `baseline`, `ventana_observacion`,
`vector_comportamiento`, `p5`, `p95`, `winsoriz`, `percentil`, `epsilon`, `max_iter`,
`refinamiento` y `convergencia`. Por tanto **N, ε y el máximo de iteraciones no son consultables
desde ninguna fuente formal**, y no se inventaron valores.

### En el artefacto — la implementación de la rama

| Pieza requerida | Presente |
|---|---|
| Operación VISION | **NO** |
| `modo_calibracion` | **NO** |
| Persistencia de línea base VISION | **NO** |
| Algoritmo de refinamiento | **NO** |
| Configuración de máximo de iteraciones | **NO** |
| Configuración de ε | **NO** |
| Fuente del vector VISION | **NO** |
| Percentiles p5/p95 o winsorización | **NO** |

**Presentes: 0 de 8.**

Se verificó además el esquema real con las migraciones aplicadas al día (`78f6f579b5ba`): no hay
ninguna tabla ni columna de línea base VISION, ε, iteraciones, percentiles ni convergencia. Las
tablas cuyo nombre contiene la subcadena son `modulo5.provision_nic41`,
`modulo6.revisiones_reconocimiento` y `modulo4.observaciones_clinicas` —provisión, revisión y
observaciones clínicas veterinarias—, ninguna relacionada con VISION.

### Tres falsos positivos descartados

Conviene dejarlos registrados, porque darlos por buenos habría llevado a montar un laboratorio
para una función inexistente:

1. **"provisión" y "revisión"** contienen la subcadena "vision". Por eso la compuerta de TEST
   cuenta la palabra como token.
2. **`CAMARA_VISION` y `ATRIBUTOS_VISION`** —en
   `alembic/versions/cf12e716a4ec_...taxonomia_camara_auditoria.py` y en
   `registrar_dispositivo_iot_use_case.py`— son el **tipo de dispositivo cámara** y sus atributos
   (resolución, fps, área de cobertura) al registrar un dispositivo IoT. No hay operación de
   calibración VISION asociada.
3. **"línea base"** —en `b5d81f27ac93_rf10_campos_completos_indices_baseline.py`, dentro del
   mensaje `IMMUTABLE_RECORD: La linea base de integridad no puede ser modificada`— es el
   **baseline de integridad de RF-10** (`modulo1.integridad_baseline`), no la línea base del
   Flujo F.

Una primera pasada de la compuerta local contó 2 de 8 piezas por los puntos 2 y 3. Se afinó para
descartarlos de forma explícita y registrarlos en la evidencia, y el recuento real quedó en 0/8.

## TC-M09-284 — etapa 1, filtrado de `apto_para_ia = false`

**Resultado: BLOQUEADO / NO VERIFICABLE.**

Sin operación VISION ni entidad de observación no puede construirse por flujo formal el conjunto
K de observaciones aptas ni el conjunto M de no aptas, ni obtenerse las dos líneas base que el
oráculo debía comparar componente por componente.

**Impedimento adicional, concreto y persistente.** El caso pide áreas gemelas con
`tipo_modelo_asignado = POBLACIONAL`, y el contrato no admite ese valor para infraestructuras:

```text
tipo_modelo_asignado ∈ { MODELO_AVES, MODELO_PORCINOS, MODELO_ACUICULTURA,
                         MODELO_ESPECIES_MEDIANAS, MODELO_ESPECIES_GRANDES,
                         MODELO_RIESGO_CONTAGIO }
```

`POBLACIONAL` es el tipo del **activo biológico** (`INDIVIDUAL | POBLACIONAL`), no el modelo
asignado al área. Aunque VISION existiera, la precondición del caso tendría que reformularse.

**POST VISION: 0 de 2** (corrida K y corrida K+M). No se crearon áreas gemelas ni observaciones.

## TC-M09-285 — etapas 2 y 3, p5/p95 y refinamiento

**Resultado: BLOQUEADO / NO VERIFICABLE**, por la misma causa primaria.

- **ε:** no consultable desde ninguna fuente formal.
- **max_iter:** no consultable.
- **Lectura DESCARTE:** no calculable sobre datos reales (no hay dataset ni línea base).
- **Lectura WINSORIZACIÓN:** ídem.
- **Interpretación observada:** ninguna; no hubo ejecución.

Incluso si VISION existiera, este caso arrastra dos dependencias documentales no resueltas hoy
por ninguna fuente formal disponible para QA: ε y el máximo de iteraciones, y la regla exacta de
refinamiento —qué mediana se calcula, sobre qué conjunto, cómo se actualiza el conjunto o el
centro en cada iteración, cómo se mide el cambio relativo, qué ocurre con el cero y qué
comparación representa convergencia—.

El oráculo externo `oracle_vision.py` queda preparado y, por diseño, se niega a suplir lo que el
requisito no define:

- calcula **las dos** lecturas admitidas de la etapa 2 sin elegir entre ellas;
- `refinar()` exige una `EspecificacionRefinamiento` formal —estimador, actualización del
  conjunto, medida del cambio relativo, tratamiento del cero, criterio de convergencia, ε,
  `max_iter` y su fuente— y levanta `EspecificacionIncompleta` si falta cualquiera. El código del
  producto no cuenta como requisito;
- `percentil_robusto()` solo devuelve un valor si es **invariante** entre `lower`, `higher`,
  `nearest`, `midpoint` y `linear`; si no lo es, levanta `PercentilAmbiguo`.

Esa ambigüedad documental **no es un defecto del producto** y se reporta aparte, como
`Type = question`.

**POST VISION: 0 de 1.**

## TC-M09-286 — etapa 3, no convergencia (LOCAL)

**Resultado: BLOQUEADO / NO VERIFICABLE.**

La compuerta previa al laboratorio quedó en 0 de 8 piezas, así que **no se levantó ningún
laboratorio**: no se creó base, no se aplicaron migraciones, no se sembraron datos, no se tocó
configuración y no se ejecutó ningún POST. El paquete lo prohíbe expresamente, y tampoco se
construyeron mocks para simular VISION.

Ninguno de los eslabones obligatorios del caso es alcanzable:

```text
baseline previa válida        -> no hay operación VISION que la produzca
max_iter = 1                  -> no existe configuración de máximo de iteraciones que modificar
dataset no convergente        -> sin regla de refinamiento no puede demostrarse la no convergencia
POST VISION -> 422            -> no hay operación que invocar
auditoría FALLIDA             -> no hay etapa de refinamiento que falle
baseline previa conservada    -> no hay baseline
restauración de configuración -> no hubo configuración alterada
```

Al no haber tocado configuración, no quedó nada que restaurar ni ningún harness abierto. No se
reutilizó el laboratorio ni el volumen de ningún otro grupo.

**POST VISION: 0 de 2** (baseline previa de setup y caso objetivo).

## Presupuesto de operaciones

```text
POST VISION planificados: 5   (3 en TEST: K, K+M, dataset p5/p95 · 2 en LOCAL: setup y objetivo)
POST VISION ejecutados:   0
Escrituras en TEST:       ninguna
SQL sobre TEST:           ninguno
Laboratorio local:        no levantado
```

## Incidencias

### Incidencia 1 — ausencia de la funcionalidad VISION

**INCIDENCIA REQUERIDA:** SÍ
**Grupo responsable:** AIoT
**Grupo:** TC-M09-G140
**Casos:** TC-M09-284, TC-M09-285 y TC-M09-286
**Ambiente:** TEST y artefacto de la rama
**Resultado:** BLOQUEADO

**Motivo:** RF-24 v2.0 define la modalidad VISION y el cálculo automático de línea base del
Flujo F, pero no existe nada de eso: ni en el contrato desplegado en TEST ni en la rama
`qa/juan-esteban-rf24-v2`.

**Esperado:** una operación VISION publicada, una fuente formal de observaciones/vector de
comportamiento con cámara, área, timestamp, componentes y `apto_para_ia`, y configuración
consultable de N, ε y máximo de iteraciones, con persistencia de línea base verificable.

**Obtenido:** 0 de 10 puntos de ejecutabilidad en TEST y 0 de 8 piezas en el artefacto.
`VISION` no aparece como palabra en las 210 rutas; `modo_calibracion` no está en el DTO de
calibración; `apto_para_ia` no se expone en ningún endpoint y pertenece a la calidad de
telemetría de sensores, no a un vector de comportamiento.

**Causa raíz:** la cadena VISION no está implementada de extremo a extremo. Lo que falta primero
es la dependencia de origen: no hay vectores de comportamiento, ni fuente cámara-observación, ni
pipeline VISION en M03, ni aptitud VISION.

Se asigna a **AIoT** porque el criterio del paquete reserva ese grupo exactamente para la
ausencia confirmada de esas cuatro piezas, y las cuatro están confirmadas. No se asigna a
**Desarrollo**, cuyo criterio aplica cuando la operación RF-24 VISION no existe *aun teniendo* las
dependencias de M03, y aquí tampoco existen; conviene dejarlo dicho: en cuanto la fuente VISION
de M03 esté disponible, la ausencia de la operación RF-24 VISION pasaría a Desarrollo. No se
asigna a **DBA**: no hay migración VISION implementada y sin aplicar. No se usa **Por
determinar**, porque la evidencia sí permite situar el origen.

**Type:** bug
**Severity:** Important
**Priority:** High

Important/High porque bloquea por completo los tres casos del grupo y deja sin cobertura una
etapa del requisito; no Critical porque no hay pérdida de datos ni fallo de una función en
producción.

**Evidencia:** `RESULTADOS/run-test-20261007-142538/evidencia.json` (compuerta 0/10 y búsqueda en
el contrato) · `RESULTADOS/run-local-20261007-142538/evidencia.json` (compuerta 0/8 y falsos
positivos descartados) · los `pytest.xml` de ambos RUN.

### Incidencia 2 — ambigüedad de especificación del Flujo F

**INCIDENCIA REQUERIDA:** SÍ, como aclaración documental
**Incidencia de producto:** NO
**Grupo responsable:** Por determinar (documental; corresponde a quien custodia RF-24 v2.0)
**Casos:** TC-M09-285, y TC-M09-286 en lo relativo a la no convergencia

**Motivo:** aunque VISION se implemente, el oráculo exacto de TC-M09-285 no es construible
mientras tres puntos no se cierren contractualmente:

1. **Descarte vs winsorización.** El RF denomina la etapa "winsorización" pero también describe
   descartar los valores fuera de p5/p95. Son dos algoritmos distintos con resultados distintos.
2. **Método de interpolación de percentiles.** Sin definirlo, p5 y p95 pueden variar entre
   `lower`, `higher`, `nearest`, `midpoint` y `linear`.
3. **Regla exacta de refinamiento**, en los términos detallados en TC-M09-285.

**Type:** question · **Severity:** Normal · **Priority:** Normal

No se reporta como defecto del producto: es una definición pendiente. Se mantiene separada de la
incidencia 1 porque su causa es distinta —documental, no de implementación— y porque sobrevivirá
a la implementación de VISION si no se aclara.

## Evidencias

```text
RESULTADOS/
├── TC-M09-G140_resultado.md                  este informe, único del grupo
├── run-test-20261007-142538/
│   ├── evidencia.json    compuerta de 10 puntos, búsqueda VISION en el contrato, falsos
│   │                     positivos por subcadena, DTO de calibración, exposición de
│   │                     apto_para_ia, configuración del algoritmo e impedimento de áreas gemelas
│   └── pytest.xml
└── run-local-20261007-142538/
    ├── evidencia.json    compuerta de 8 piezas con sus archivos, falsos positivos descartados,
    │                     baseline no-VISION identificado y presupuesto en cero
    └── pytest.xml
```

## Conclusión

**TC-M09-G140 queda BLOQUEADO / NO VERIFICABLE**, con sus tres casos bloqueados.

El bloqueo es de **disponibilidad de la funcionalidad**, no un incumplimiento observado del
producto: no se llegó a ejecutar ninguna operación VISION porque no existe ninguna que ejecutar.
La revisión previa de la rama, que el paquete aportaba solo como contexto, quedó confirmada
empíricamente por dos vías independientes —el contrato desplegado en TEST y el artefacto de la
rama con su esquema migrado—, y en ambas con cuidado de no dejarse engañar por las coincidencias
de subcadena de "provisión", "revisión", `CAMARA_VISION` y la línea base de integridad de RF-10.

No se usaron mocks, no se ejecutó SQL sobre TEST, no se crearon datos para forzar la
ejecutabilidad y no se levantó un laboratorio local para una función inexistente.

La automatización queda lista para la reevaluación: ambas compuertas aprobarán automáticamente en
cuanto VISION esté disponible, y `oracle_vision.py` ya calcula las dos lecturas admitidas sin
elegir entre ellas. Para desbloquear el grupo hacen falta la implementación VISION y la
aclaración documental de la incidencia 2.
