# INC-M07-375-G002 · RF-95 · El cuerpo de error no sigue el contrato del RF (`field`)

> Numeración **provisional** (375): confirmar el consecutivo con la líder de pruebas / Taiga antes de publicar.

## Título (GitHub y Taiga)

`[INC-M07-375-G002][RF-95] El cuerpo de error devuelve fields[] y timestamp en lugar de { error_code, message, field }`

## Cuerpo del issue (pegar igual en GitHub y en Taiga)

[TC-M07-G002][RF-95] El cuerpo de error devuelve fields[] y timestamp en lugar de { error_code, message, field }

Incidencia: INC-M07-375-G002
Módulo: M07
RF: RF-95 (Salida: respuesta de error)
Caso: TC-95-005
RUN: RUN-G002-V1-20261118-095350
Ambiente: TEST
Equipo responsable: Desarrollo Backend
Repositorio: Backend
Categoría: HTTP_COM
Severidad: Baja
Prioridad: Normal
Evaluador: Julian Badillo

### Problema

Las respuestas de error del Gateway AAEF cumplen el código HTTP y el `error_code` exigidos, pero el **cuerpo** no tiene la forma que define RF-95.

RF-95 (Salida) establece: «Respuesta de error: `{ "error_code", "message", "field" }`».

### Casos reproducidos

Tres solicitudes sin credenciales (la validación ocurre antes de autenticar):

1. `GET /integracion/aaef/productores/901444215?desde=2026/09/01&hasta=2026-10-31`
2. `GET /integracion/aaef/productores/901444215?desde=2026-09-01` (sin `hasta`)
3. `GET /integracion/aaef/productores/901444215-0?desde=2026-09-01&hasta=2026-10-31` (NIT con dígito de verificación)

Resultado en las tres: `HTTP 400`, `error_code: PARAMETROS_INVALIDOS`, y un cuerpo con estas claves:

`error_code`, `message`, `fields`, `timestamp`

donde `fields` es una lista `[{ "field": "...", "message": "..." }]`. No existe la clave `field`.

### Resultado esperado

Cuerpo de error con `error_code`, `message` y `field` (el parámetro que falló).

### Resultado obtenido

Cuerpo con `error_code`, `message`, `fields[]` y `timestamp`.

### Impacto

Severidad: Baja.

- El código HTTP, el `error_code` y el mensaje legible se cumplen, y la respuesta identifica el parámetro dentro de `fields[0].field`; por eso CA-2 se cumple.
- Un consumidor que programe contra el contrato del RF (leer `field`) no encontrará la clave. Agrofusión muestra estos errores a la persona usuaria (RF-95 5.6), así que el contrato debe ser predecible.
- Es un comportamiento del manejador global de errores, no de un endpoint puntual.

### Causa probable

La causa raíz no está confirmada. La forma observada corresponde al manejador global de errores de la API (`error_code`, `message`, `fields`, `timestamp`), distinto de la que describen RF-95 y la guía del repositorio (`code`, `message`, `field`). Debe ser confirmada por Desarrollo.

### Acción requerida

1. Análisis / Desarrollo: decidir el contrato de error vigente y dejarlo único para RF-95.
2. Alinear el RF-95 (Salida) con el cuerpo real, o ajustar el manejador para incluir `field`.
3. Mantener `error_code`, `message` e identificación del parámetro.
4. Desplegar en TEST.
5. Reevaluar TC-95-005 (grupo TC-M07-G002).

### Criterios de aceptación

- El cuerpo de error trae las claves definidas por el RF-95 (o el RF queda actualizado con el contrato real).
- La respuesta sigue identificando el parámetro que falló.
- Código HTTP y `error_code` no cambian.
- TC-95-005 aprueba.

### Evidencias

- `evidencias/resultado.json`
- `evidencias/preflight.json`
- `evidencias/contexto_operacion.json`
- `evidencias/respuestas_error_400.json`
- `evidencias/newman/newman-G002.json`
- `evidencias/newman/newman-G002.html`

RUN: `RUN-G002-V1-20261118-095350`

### Estado

INC-M07-375-G002 queda abierta y debe ser derivada a Desarrollo Backend. La causa raíz permanece como hipótesis hasta su confirmación.

## Atributos personalizados de Taiga

| Atributo | Valor |
|---|---|
| Modulo | M07 |
| RF | RF-95 (Salida) |
| Codigo de error | HTTP_COM |
| Equipo responsable | Desarrollo Backend |
| Severidad | Baja |
| Tiempo maximo de solucion | Hasta el sábado 21 de noviembre de 2026 (3 días desde el reporte) |
| Fecha de deteccion | 2026-11-18 |
| Fecha limite | 2026-11-21 |
| Evaluador | Julian Badillo |

## Adjuntos (ambas plataformas)

Carpeta `evidencias/` de esta incidencia: `resultado.json`, `preflight.json`, `contexto_operacion.json`, `respuestas_error_400.json` y `newman/newman-G002.html` y `.json`.
