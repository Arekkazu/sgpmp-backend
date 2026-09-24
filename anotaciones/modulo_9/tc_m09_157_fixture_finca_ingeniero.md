# TC-M09-157-G82 — Fixture de finca en DEV (RF-25)

## Bloqueo reportado

Issue #305: ninguna de las credenciales de prueba disponibles en DEV tenía una finca
propia asignada, por lo que no era posible demostrar `GET /configuracion/fincas/{id}`
→ 403 sobre una finca ajena (TC-M09-157).

## Verificación de backend

`ConsultarFincasUseCase.obtener()` (src/configuration/application/use_cases/fincas/consultar_fincas_use_case.py:19-31)
ya aplica el alcance correcto: 404 si la finca no existe, 403 (`FINCA_NO_AUTORIZADA`) si
existe pero `finca.id_usuario != id_usuario_filtro`. No había ningún defecto de código,
solo faltaba el dato de prueba.

## Fixture aplicado (solo aditivo, ninguna fila existente fue modificada)

Se insertó una finca nueva en `sgpmp_dev` asignada al usuario `ingeniero@pecuaria.co`
(id_usuario=4, credencial ya usada por QA — ver issue #306):

| id_finca | nombre | id_usuario |
|---|---|---|
| 14 | Finca Alcance Propio Ingeniero Pruebas | 4 |

## Cómo ejecutar TC-M09-157 con esto

- Login con `ingeniero@pecuaria.co`.
- **Finca A (propia):** `GET /configuracion/fincas/14` → 200.
- **Finca B (ajena):** cualquier finca existente no asociada al usuario 4, ej.
  `GET /configuracion/fincas/1` (pertenece al usuario 2) → 403 `FINCA_NO_AUTORIZADA`.

No se reasignó ninguna finca existente ni se tocaron otros usuarios.
