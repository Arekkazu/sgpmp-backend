# INC-M07-374-G047 · RF-101 · Credenciales de clientes sembrados sin formato bcrypt

> Numeración **provisional** (374): confirmar el consecutivo con la líder de pruebas / Taiga antes de publicar.

## Título (GitHub y Taiga)

`[INC-M07-374-G047][RF-101] Credenciales de clientes externos sembrados (ids 1 y 2) guardan un hash de 64 caracteres que no es bcrypt`

## Cuerpo del issue (pegar igual en GitHub y en Taiga)

[TC-M07-G047][RF-101] Credenciales de clientes externos sembrados (ids 1 y 2) guardan un hash de 64 caracteres que no es bcrypt

Incidencia: INC-M07-374-G047
Módulo: M07
RF: RF-101 (Restricción 5.1, RNF-101.1, Postcondiciones)
Caso: TC-101-019
RUN: RUN-G047-V2-20261118-121528
Ambiente: TEST
Equipo responsable: DBA / Implementación (datos de TEST); Desarrollo Backend si el formato proviene de una migración
Repositorio: Backend / Datos de TEST
Categoría: Seguridad (OWASP API2 / ASVS V2.4)
Severidad: Media
Prioridad: Normal
Evaluador: Julian Badillo

### Problema

En `modulo7.identificadores_apis`, las credenciales de los clientes externos **1 (`holi`)** y **2 (`AGROFUSION-PROD-001`)** no están guardadas como hash bcrypt. Se almacenan como cadenas hexadecimales de 64 caracteres.

RF-101 exige: 5.1 «se persiste solo su hash», RNF-101.1 «solo hash con sal» y Postcondiciones «ningún secreto queda en texto plano en BD». Los clientes del 5 en adelante (incluidos los QA_M07_* y los creados por la API) sí guardan bcrypt (`$2b$`, 60 caracteres).

### Caso reproducido

Consulta de solo lectura dentro de un run del sandbox:

`SELECT id_cliente_externo, left(hash_secreto,4), length(hash_secreto), estado FROM modulo7.identificadores_apis`

| Cliente | Credenciales | Formato | Largo |
|---|---|---|---|
| 1 `holi` | 2 (una ACTIVA, una REVOCADA) | no bcrypt | 64 |
| 2 `AGROFUSION-PROD-001` | 1 (ACTIVA) | no bcrypt | 64 |
| 5 al 18 | todas | bcrypt (`$2b$`) | 60 |

La evidencia guarda solo el prefijo de 4 caracteres y el largo; nunca el hash completo.

### Resultado esperado

Toda credencial de cliente guardada como hash bcrypt con sal, sin excepciones.

### Resultado obtenido

Tres credenciales (clientes 1 y 2) con un hash de 64 caracteres hexadecimales.

### Impacto

Severidad: Media (ajustable a Baja si el DBA confirma que son datos de relleno sin uso).

- Con el código actual, la validación usa `bcrypt.checkpw`; con estos valores devuelve falso, por lo que esas credenciales **no pueden autenticar**. No se observó acceso indebido.
- Si el formato corresponde a un hash sin sal (por ejemplo, SHA-256), incumple el requisito de hash con sal de un RF de prioridad Alta/Must.
- El cliente 2 lleva el código `AGROFUSION-PROD-001`: si ese registro se promueve o se usa, la integración real no podría autenticar con él.

### Causa probable

La causa raíz no está confirmada. Los datos parecen haber sido sembrados antes de RF-101 v2.0 (RFC-019), que introdujo el hash bcrypt. Debe ser confirmada por el DBA / Desarrollo.

### Acción requerida

1. DBA / Implementación: confirmar el origen de los registros 1 y 2.
2. Decidir si se eliminan, se revocan o se re-emiten con `POST /integracion/clientes/{id}/rotar` (sin tocar el cliente AGROFUSION real sin coordinar con Desarrollo).
3. Revisar que ningún cliente de PROD tenga credenciales con este formato antes del lanzamiento.
4. Considerar una validación o restricción que impida guardar un hash que no sea bcrypt.
5. Reevaluar TC-101-019 (grupo TC-M07-G047).

### Criterios de aceptación

- `SELECT` sobre `modulo7.identificadores_apis`: todas las filas con prefijo `$2` y largo 60.
- Ningún secreto en claro en BD, auditoría ni respuestas de error (el resto de TC-101-019 ya aprueba).
- TC-101-019 aprueba.

### Evidencias

- `evidencias/resultado.json`
- `evidencias/preflight.json`
- `evidencias/contexto_operacion.json`
- `evidencias/credenciales_formato_hash.json`
- `evidencias/newman/newman-G047.html`

RUN: `RUN-G047-V2-20261118-121528`

### Estado

INC-M07-374-G047 queda abierta y debe ser derivada a DBA / Implementación, con aviso a Desarrollo Backend. La causa raíz permanece como hipótesis hasta su confirmación.

## Atributos personalizados de Taiga

| Atributo | Valor |
|---|---|
| Modulo | M07 |
| RF | RF-101 (5.1, RNF-101.1) |
| Codigo de error | Seguridad (OWASP API2 / ASVS V2.4) |
| Equipo responsable | DBA / Implementación |
| Severidad | Media |
| Tiempo maximo de solucion | Hasta el sábado 21 de noviembre de 2026 (3 días desde el reporte) |
| Fecha de deteccion | 2026-11-18 |
| Fecha limite | 2026-11-21 |
| Evaluador | Julian Badillo |

## Adjuntos (ambas plataformas)

Carpeta `evidencias/` de esta incidencia: `resultado.json`, `preflight.json`, `contexto_operacion.json`, `credenciales_formato_hash.json` y `newman/newman-G047.html`.
