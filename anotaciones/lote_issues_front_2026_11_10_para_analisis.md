# Cambios del 10-11-2026 para Análisis

Para: @miguelortiz13 (Análisis). Copia: @SamuelPR21 (DBA, por la migración).

Este documento resume lo que se cambió para cerrar 14 issues del repositorio del frontend. Para cada cambio dice qué RF toca, qué se decidió y qué falta que Análisis confirme o lleve al texto del RF.

## 1. Lo que necesita una decisión de Análisis

| # | Tema | RF | Qué se hizo | Qué falta confirmar |
|---|------|----|-------------|----------------------|
| 1 | Densidad máxima por etapa | RF-16, RF-36, RFC-012 | Cada etapa admite su propio máximo, que se suma al de la especie. Se aplica el más estricto. | Si se acepta como cambio menor de RF-16 y RF-36, o si va como RFC. Ver la sección 3. |
| 2 | Especie sin densidad | RF-36, RFC-012 | Se mantiene el 422 de RFC-012: sin densidad de especie no entra nadie al área. | #394 pedía «no bloquear si no hay máximo». Se respetó RFC-012. Si Análisis prefiere no bloquear, hay que cambiar RFC-012. |
| 3 | Activos sin precio en el cierre | RF-87 FA-2 y CA-5, RF-88 v2.0 | Decisión por activo entre excluirlo o estimarlo con el último precio conocido. | El texto de RF-87 FA-2 todavía dice que el activo pasa a costo con RF-88. RF-88 v2.0 (RFC-024) lo prohíbe por NIC 41 ¶31. Hay que alinear el texto de RF-87. |
| 4 | Ciclos productivos | RF-16, RF-37 | Ya estaban pedidos, pero no implementados. Se construyeron. | Que el texto de RF-16 diga explícitamente que el ciclo productivo es la secuencia ordenada de etapas. Ver la sección 2. |

## 2. Ciclos productivos con sus fases (#512)

**RF:** RF-16 (etapas por especie, M09) y RF-37 (fases del ciclo productivo del activo, M02). Lo bloqueado eran RF-75 y RF-76 (registro de alimento y de medicamento, M05).

**Problema.** RF-75 y RF-76 exigen que el activo tenga un ciclo productivo abierto (RF-37). RF-37 dice que las fases salen de RF-16 y siguen «una secuencia lógica definida en RF-16 mediante un orden o flujo configurado». Las tablas existían, pero no había forma de crear esa secuencia. Por eso «Cambiar fase» decía que la especie no tenía ciclos, y M05 rechazaba todo registro.

**Qué se hizo.**
- Backend: `GET/POST /configuracion/ciclos-productivos` y `PUT/DELETE /configuracion/ciclos-productivos/{id}`.
- Front: Configuración › Por especie › **Ciclos productivos**.
- El ciclo tiene un nombre, único en la especie, y una lista ordenada de etapas activas de esa especie, sin repetir. El orden en que se guardan es la secuencia estándar que usa RF-37.
- La duración del ciclo es la suma de las duraciones de sus etapas.
- Si algún animal o lote ya pasó por el ciclo, solo se le puede cambiar el nombre y no se puede eliminar. Sus fases son la historia de esos activos.
- Permisos: los mismos de las etapas (recurso `ciclos_biologicos`): Administrador y Veterinario crean, editan y eliminan.
- Sin migración.

**Para el texto de RF-16.** Sugerencia: «Un ciclo productivo es una secuencia ordenada de etapas activas de la especie. Una vez que un activo ha pasado por él, sus fases no se modifican.»

**Mensajes de M05.** El 422 decía «El activo 767 no tiene un ciclo productivo activo», con el id interno. Ahora nombra el activo por su identificador.

## 3. Densidad máxima por etapa (#391, #392, #393, #394)

**RF:** RF-16 (configuración por especie y etapa) y RF-36 (gestión poblacional). Toca la regla de RFC-012 (RF-15, densidad por especie y capacidad del área).

**Qué se hizo.**
- Cada etapa admite:
  - `densidad_maxima`: animales por m², mayor que 0 y hasta 200.
  - `biomasa_maxima`: kg por m², mayor que 0. Opcional.
  - `aviso_preventivo_pct`: 80, 85, 90 o 95; 90 por defecto.
- Configura Administrador y Veterinario (`PATCH /configuracion/ciclos/{id}/densidad`), con concurrencia optimista y auditoría en la auditoría de etapas. Un valor fuera de rango responde 400.
- Productor, Ingeniero de Campo y Contador reciben permiso de **lectura** de etapas: ven la tabla sin poder editarla, como pide #392.
- **Cómo se combina con RFC-012.** La capacidad del área por la densidad de las especies sigue igual. La densidad de la etapa es un límite adicional para el lote que está en esa fase. Gana el más estricto.
- **Validación (RF-36, RF-48).** Un ingreso de individuos o una transferencia que deje al lote por encima del máximo de su etapa responde 422 y dice cuántos animales caben. Una etapa sin densidad configurada no bloquea nada.
- **La biomasa máxima es informativa.** Se muestra en la ficha, pero no bloquea operaciones. Ningún issue pidió bloquear por biomasa.
- **Ficha del lote.** Devuelve el estado de densidad, el máximo que aplica y de dónde sale (etapa o especies del área), el porcentaje, la superficie, la capacidad y el cupo disponible.
- **Estados:**
  - `OK`: dentro del límite.
  - `AVISO`: el lote llegó al porcentaje de aviso.
  - `EXCEDE`: supera el máximo.
  - `SIN_CONFIGURAR`: ni la etapa ni la especie tienen máximo.
- **Listado de activos.** La columna Densidad muestra ese estado para cada lote.
- Front: pestaña **Densidad máxima** en Configuración › Por especie, columna Densidad en el listado y barra de densidad en los datos del lote. Los estados se dicen con texto e ícono, no solo con color.
- **Migración `143fa2eda4fc`.** Tres columnas en `modulo9.ciclos_biologicos` con sus CHECK, más los tres permisos de lectura, resueltos por nombre. Requiere autorización del DBA.

**Decisiones a confirmar.**
1. Si la densidad por etapa entra como cambio menor de RF-16 y RF-36 o necesita RFC, porque amplía lo que fijó RFC-012.
2. RFC-012 bloquea si la especie no tiene densidad, y #394 pedía no bloquear. Se mantuvo RFC-012.
3. La validación por etapa aplica al ingreso y a la transferencia. En el registro inicial el lote todavía no tiene fase, así que solo aplica la capacidad del área.

## 4. Decisión por activo sin precio en el cierre (#589)

**RF:** RF-87 FA-2 y CA-5. Contexto: RF-88 v2.0 y RF-83 v1.2 (RFC-024).

**Problema.** QA pidió poder decidir activo por activo y no con dos opciones generales. RF-87 FA-2 dice «solicita confirmación explícita de que **cada uno** cumple…». Pero la opción que describe es pasar el activo al costo con RF-88, y RF-88 v2.0 dice que un activo a valor razonable nunca pasa al costo (NIC 41 ¶31).

**Qué se hizo.** Cada activo sin precio tiene su propia decisión: **excluirlo** del cierre, con lo que pasa al período siguiente, o **estimarlo** con el último precio conocido, según RF-83 v1.2. Ninguno pasa al costo. El cierre se habilita cuando todos los activos tienen decisión. El backend recibe `activos_estimados` y rechaza con 400 un activo que no esté en la lista de los que no tienen precio. Sin migración.

**Para el texto de RF-87.** Reemplazar en FA-2 y CA-5 «incluirlos con RF-88 (método de costo)» por «incluirlos con el último precio conocido como estimación (RF-83 v1.2)», y dejar explícito que la decisión es por activo.

## 5. Errores corregidos, sin cambio de RF

Quedan aquí para la trazabilidad.

| Issue | RF | Corrección |
|-------|----|------------|
| #548 | RF-86 | El panel de medición mostraba «Medido» para un activo con un evento suspendido. Nuevo `GET /finanzas/periodos/{id}/eventos-pendientes`, y el panel marca «Medición pendiente» con su motivo. |
| #589 A | RF-87 CA-12 | La verificación previa del cierre lista cada asiento sin trazabilidad con su activo y el eslabón que falta. |
| #526 | RF-77 | El PDF de gastos ahora trae el nombre del activo, el desglose mensual o semanal y la nota de tendencia. Un logo que falta responde 404 y no 500. |
| #511 | RF-74 | Una corrida del cálculo nocturno del ICA que quedaba colgada tras un reinicio bloqueaba las siguientes. Ahora se interrumpe al arrancar. El 500 de «Calcular ahora» se corrige en #1070. |
| #510 | RF-89 | Si confirmar la desviación del precio fallaba, el error no se mostraba en el formulario. |
| #509, #510 | RF-82 a RF-89 | El 500 al guardar venía de un permiso de base de datos (pgcrypto). Lo resolvió #953, ya en dev. |
| #470, #472, #467 | RF-58, RF-68 | Ya estaban resueltos antes del lote. Se cerraron. |

## 6. Orden de los PRs para llegar a la versión del front

Backend primero, porque el front llama endpoints nuevos.

| Paso | Repositorio | PR | Base | Contenido | Requisito |
|------|-------------|----|------|-----------|-----------|
| 1 | backend | #1070 | `dev` | Lote M05/M06 integrado: 15 migraciones y RLS de M05/M06 | Autorización del DBA |
| 2 | backend | #1071 | rama de #1070 | Este lote. Migración `143fa2eda4fc`, que va detrás de `4fa0e24ea021` | Autorización del DBA. Mergear después de #1070 |
| 3 | frontend | #591 | `dev` | Lote M06 del front integrado | Backend de #1070 desplegado |
| 4 | frontend | #592 | rama de #591 | Este lote | Backend de #1071 desplegado |

Después del merge en `dev`, se promueve a `test` igual que siempre: backend con `alembic upgrade head`, y luego el front.

**Acciones de ambiente en TEST, aparte de los PRs:**
- Un Administrador debe interrumpir la corrida 62 del cálculo ICA, colgada desde el 10-11. Si no, el cálculo nocturno sigue bloqueado hasta que se despliegue #1071.
- Hay que definir `LOGOS_STORAGE_PATH` sobre un volumen persistente, escribible por el usuario 1000, y volver a subir el logo de la finca 1. Hoy se guarda en `/tmp` y se pierde en cada despliegue.
- QA necesita un ciclo productivo con fases para probar M05 de punta a punta. Ahora lo puede crear desde la pantalla.
