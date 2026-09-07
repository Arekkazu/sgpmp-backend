# TC-M09-G26 — RF17, integridad referencial, unicidad y catálogo predefinido

Responsable del grupo Juan Esteban. Solo TEST real. No ejecutar G22, G23, G24 ni
G25 desde aquí. No iniciar G27. Grupo de API: **sin Cypress**.

Ejecución `run-20260906` concluida. Decisión general: **APROBADO**.
TC-M09-57 APROBADO · TC-M09-58 APROBADO · TC-M09-65 APROBADO. Sin defectos que
reportar a Desarrollo. Queda una **observación de contrato** sin impacto funcional
para el dueño del requisito: actualizar el resultado esperado de TC-M09-65 en la
matriz (400 → 404) y unificar el criterio de código para referencias inexistentes.
Consultar `RESULTADOS/run-20260906/TC-M09-G26_resultado.md`.

| Caso | GIVEN | WHEN | THEN |
|---|---|---|---|
| TC-M09-57 A | Admin autorizado, variable activa del catálogo, rango y niveles válidos | POST con `id_especie` ausente del catálogo completo | 422 `ESPECIE_INACTIVA` sobre `id_especie`, sin persistencia |
| TC-M09-57 B | Igual, con una especie real cuyo `es_activo` es false | POST con esa especie | Mismo rechazo y ausencia de persistencia |
| TC-M09-58 | Existe una configuración ACTIVA para una combinación especie+variable | POST con la misma especie y la misma variable, todo lo demás válido | 409 `UMBRAL_DUPLICADO` y una sola configuración después, la original |
| TC-M09-65 | Especie activa, payload sin otra invalidez | POST con `id_variable_ambiental` entero ausente del catálogo | Rechazo específico por catálogo, sin umbral y **sin crear la variable** |

## Contrato revisado una sola vez (solo lectura)

- Especie inexistente **o** inactiva → `BusinessRuleError('ESPECIE_INACTIVA')` →
  **422**, con `field = id_especie`. Coincide con RF-17.
- Duplicado → `ConflictError('UMBRAL_DUPLICADO')` → **409**. Coincide con RF-17.
  La unicidad se consulta **sin filtrar por `es_activo`**.
- Variable fuera del catálogo → `NotFoundError('VARIABLE_AMBIENTAL_NO_ENCONTRADA')`
  → **404**. La matriz/RF declaraba **400**: la discrepancia se ejecutó y registró
  primero con el oráculo de la matriz (intento 1, assertion fallida) y solo después
  se corrigió la assertion, tras el análisis documentado en el informe
  (`CONTRACT_REQUIREMENT_MISMATCH` y `DECISIÓN SOBRE TC-M09-65`). El oráculo **no**
  se cambió en silencio.
- La variable se envía como **ID entero** (FK al catálogo). El `tipo_variable` de la
  matriz académica no existe en el contrato real, así que no se envía «Radiación».
- Orden de validación: especie → variable → niveles → rangos → unicidad. Cada
  payload debe superar todas las reglas anteriores para llegar a la suya.
- `GET /configuracion/especies` devuelve el catálogo **completo** con `total`
  (`solo_activas=false` por defecto): sirve para demostrar que un ID no existe. No
  hay endpoint `GET especies/{id}`.

## Trampa de aislamiento en TC-M09-58

Los umbrales heredados de TEST guardan rangos como `0.00 – 100.00` que exceden los
límites físicos de su propia variable. Copiar esos valores en el POST duplicado
dispararía `RANGO_FISICO_INVALIDO` (400) **antes** de la comprobación de unicidad y
daría un rechazo por la regla equivocada. El payload usa un rango propio dentro de
los límites físicos, con niveles contiguos, para llegar realmente al 409.

## Datos

Descubiertos dinámicamente antes de cada original: permisos, catálogo completo de
especies con su estado, catálogo de variables activas con límites físicos, umbrales
existentes y su estado. Ningún ID fijo: el ID de especie inexistente y el de
variable ausente se calculan con un salto sobre el máximo del catálogo y se
demuestra su ausencia antes del POST. Para TC-M09-58 se reutiliza una configuración
activa preexistente: **no se crea ningún prerequisito**.

## Requisitos y ejecución

Ya instalados, no se instala nada: Newman 6.2.2 y `newman-reporter-htmlextra`
1.23.1. G26 no usa Cypress.

Variables de proceso: `TEST_ADMIN_EMAIL`, `TEST_ADMIN_PASSWORD`, `G26_RUN_ID`,
`G26_CASE` (`TC-M09-57` | `TC-M09-58` | `TC-M09-65`) y `G26_VARIANTE`
(`inexistente` | `inactiva` para TC-M09-57; `intento1` | `intento2` para los otros
dos). La contraseña nunca se escribe en un archivo.

```
NODE_PATH=<npm root -g>  node run-newman.cjs      # una invocación = un original
NODE_PATH=<npm root -g>  node verificar-cierre.cjs # GET final + escaneo de secretos
```

Máximo **2 POST por original**; en TC-M09-57 los consumen sus dos variantes
funcionales, así que **no dispone de reintento**. El runner rechaza por diseño un
tercer POST y sobrescribir la evidencia de una ejecución ya registrada. No se
reintenta un PASS. Si un dato inválido llegara a persistir, o si el POST creara una
variable de catálogo: detener sin limpiar.

## Evidencia

`RESULTADOS/<G26_RUN_ID>/` con el JSON sanitizado por ejecución, los datos y
preflight, la verificación final de solo lectura, el escaneo de secretos, el estado
de Git y el informe; los HTML reales de htmlextra en
`RESULTADOS/<G26_RUN_ID>/newman/`. Los archivos de TC-M09-57 se nombran por variante
(`inexistente`, `inactiva`) y no `intento1`/`intento2`, para no confundirlas con
reintentos.

Estado inicial: ambas ramas en `qa/juan-esteban-m09`. SHAs locales: backend
`adc3932b9f0293a76ebec7e89ed877274791b6a1`, frontend
`966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`. SHA desplegado no confirmado.

Discrepancia de responsable detectada entre caso agrupado e individual; para esta
ejecución se siguió la asignación del grupo TC-M09-G26. La matriz no fue modificada.
