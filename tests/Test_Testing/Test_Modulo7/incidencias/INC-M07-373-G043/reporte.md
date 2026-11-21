# INC-M07-373-G043 · RF-101 · Nombre de cliente externo duplicado se acepta (sin 409)

> Numeración **provisional** (373): confirmar el consecutivo con la líder de pruebas / Taiga antes de publicar.

## Título (GitHub y Taiga)

`[INC-M07-373-G043][RF-101] Nombre de cliente externo duplicado se registra con HTTP 201 en lugar de rechazarse con 409`

## Cuerpo del issue (pegar igual en GitHub y en Taiga)

[TC-M07-G043][RF-101] Nombre de cliente externo duplicado se registra con HTTP 201 en lugar de rechazarse con 409

Incidencia: INC-M07-373-G043
Módulo: M07
RF: RF-101 (Entradas `nombre`, FA-8)
Caso: TC-101-004
RUN: RUN-G043-V1-20261118-115824
Ambiente: TEST
Equipo responsable: Desarrollo Backend (con decisión de Análisis; DBA si requiere migración)
Repositorio: Backend
Categoría: Unicidad
Severidad: Baja
Prioridad: Normal
Evaluador: Julian Badillo

### Problema

Al registrar un cliente externo con el mismo `nombre` que uno ya existente, la API lo crea (`HTTP 201`, estado `ACTIVO`) en lugar de rechazarlo.

RF-101 define el campo `nombre` como único (Entradas: «Nombre del cliente (p. ej. `AGROFUSION`). Único.») y FA-8 exige: «Nombre de cliente duplicado → 409».

La unicidad sí se aplica al campo `codigo`: registrar un `codigo` repetido responde `HTTP 409`. El nombre visible no tiene restricción.

### Caso reproducido

1. Cliente existente: id 6, `codigo = QA_M07_AAEF`, `nombre = "QA_M07_AAEF (cliente de pruebas QA-M07)"`.
2. `POST /integracion/clientes` con un `codigo` nuevo (`QA_M07_INC373_A`), un `identificador_publico` nuevo y el **mismo `nombre`** del cliente 6.

Resultado: `HTTP 201`, cliente creado en estado `ACTIVO`. El conteo de clientes pasó de 18 a 19 dentro del run.

Control: mismo `POST` con el `codigo` del cliente 6 → `HTTP 409` (`RECURSO_DUPLICADO`).

La reproducción se hizo dentro de un run del sandbox y se revirtió con rollback. No quedó ningún cliente creado en TEST.

### Resultado esperado

- Registro con un `nombre` ya existente rechazado con `HTTP 409`.
- Ningún cliente creado.
- El mensaje indica que el `nombre` ya existe y el campo `nombre`.

### Resultado obtenido

`HTTP 201` y cliente creado con el nombre repetido. El conteo de clientes aumenta.

### Impacto

Severidad: Baja.

- Dos clientes externos pueden mostrarse con el mismo nombre en Integración → Acceso, lo que dificulta a un Administrador distinguir cuál suspender, rotar o revocar.
- No hay exposición de datos ni salto de autenticación: los clientes siguen identificándose por `codigo` e `identificador_publico`, que sí son únicos.

### Causa probable

La causa raíz técnica no está confirmada en TEST.

La lectura del código (`origin/test`) indica que `codigo` y `nombre` son campos distintos y que la única restricción es `uix_cliente_externo_codigo`, sobre `codigo`. En el código, el mapeo de esa restricción lleva el texto «Ya existe un cliente externo con ese nombre», aunque se dispara por `codigo` (la respuesta real del control dice «Ya existe un registro con esos datos», campo `cliente_externo_codigo`).

Es posible que el RF use «nombre» para lo que el modelo llama `codigo` (el ejemplo `AGROFUSION` se parece a un código). Esto debe ser confirmado por Análisis y Desarrollo.

### Acción requerida

1. Análisis: confirmar si el `nombre` visible debe ser único o si el RF se refiere al `codigo`.
2. Si el `nombre` debe ser único: agregar la validación y la restricción (sin distinguir mayúsculas ni espacios sobrantes) y responder `409` con el campo `nombre`; DBA si requiere migración y revisar duplicados ya existentes.
3. Si no debe serlo: corregir el texto de RF-101 (Entradas y FA-8) y el mensaje del mapeo de errores.
4. Desplegar en TEST.
5. Reevaluar TC-101-004 (grupo TC-M07-G043).

### Criterios de aceptación

- Un registro con `nombre` repetido se rechaza con `409` (o el RF queda corregido y alineado con el código).
- La respuesta identifica el campo en conflicto.
- No se crea ningún cliente duplicado.
- El caso de `codigo` repetido sigue respondiendo `409`.
- TC-101-004 aprueba.

### Evidencias

- `evidencias/resultado.json`
- `evidencias/preflight.json`
- `evidencias/contexto_operacion.json`
- `evidencias/reproduccion_nombre_duplicado.json`
- `evidencias/newman/newman-G043.html`

RUN: `RUN-G043-V1-20261118-115824`

### Estado

INC-M07-373-G043 queda abierta y debe ser derivada a Desarrollo Backend, con consulta a Análisis sobre el alcance de la unicidad. La causa raíz permanece como hipótesis hasta su confirmación.

## Atributos personalizados de Taiga

| Atributo | Valor |
|---|---|
| Modulo | M07 |
| RF | RF-101 (FA-8) |
| Codigo de error | Unicidad |
| Equipo responsable | Desarrollo Backend (+ Análisis) |
| Severidad | Baja |
| Tiempo maximo de solucion | Hasta el sábado 21 de noviembre de 2026 (3 días desde el reporte) |
| Fecha de deteccion | 2026-11-18 |
| Fecha limite | 2026-11-21 |
| Evaluador | Julian Badillo |

## Adjuntos (ambas plataformas)

Carpeta `evidencias/` de esta incidencia: `resultado.json`, `preflight.json`, `contexto_operacion.json`, `reproduccion_nombre_duplicado.json` y `newman/newman-G043.html`.

## Retest (2026-11-20)

**Resultado: corregida, retest aprobado.**

- **Corrección:** Nombre de cliente único sin distinguir mayúsculas ni espacios: `409 CLIENTE_DUPLICADO` en `nombre` (#1170, dentro de #1190, rc.80; índice `uq_cliente_externo_nombre`, migración `b4d2f8e61c07`).
- **Verificación:** El nombre repetido (idéntico, en mayúsculas y con espacios sobrantes) responde 409; un nombre nuevo sigue respondiendo 201 (verificacion_nombre_duplicado.json, con rollback). El caso TC-M07-G043 pasa 31 de 31 y el conteo de clientes no cambia.
- **RUN del retest:** `RUN-G043-V2-20261120-105748`
- **Evidencia:** `retest/resultado.json`, `retest/preflight.json`, `retest/verificacion_nombre_duplicado.json`, `retest/comentario_retest.md` y `retest/newman/newman-G043-retest.html`.
