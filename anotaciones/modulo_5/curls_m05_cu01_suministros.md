# CURLs — M05 CU01: Gestión de Suministros (RF-75, RF-76)

Base URL (local, sin proxy): `http://localhost:8000`
(En producción el proxy antepone `/api`.)

Autenticación: header `Authorization: Bearer <TOKEN>`.
Roles de los tokens en los ejemplos: `<ADMIN>` (rol 1), `<PROD>` (rol 2), `<VET>` (rol 3).

RBAC: recurso `consumo_alimentos` = 47, `medicamentos` = 48. Acciones C=1, R=2, D=4.

---

## Flujo 1 — Registrar consumo de alimento (RF-75) · Productor/Veterinario/Administrador

```bash
curl -X POST http://localhost:8000/suministros/consumo-alimentos \
  -H "Authorization: Bearer <ADMIN>" -H "Content-Type: application/json" \
  -d '{
    "id_activo_biologico": 5,
    "id_tipo_alimento": 1,
    "fecha_consumo": "2026-07-29",
    "hora_suministro": "08:00",
    "cantidad_alimento": 10.5,
    "observaciones": "primer suministro"
  }'
```
Respuesta esperada `201`:
```json
{
  "id_consumo_alimeto": 27, "id_activo_biologico": 5, "id_tipo_alimento": 1,
  "tipo_alimento": "test", "tipo_unidad": "kg", "cantidad_suministrada": "10.500",
  "costo_unitario": "1.0000", "costo_total": "10.5000",
  "consumo_por_individuo_kg": null, "estado_registro": "VALIDADO", "id_usuario": 1
}
```
Notas:
- `costo_total` y la auditoría los genera la BD (triggers). El costo usa el precio del
  **catálogo** `tipos_alimentos` (por eso no se envía `costo_unitario`).
- Para activos **POBLACIONAL** el sistema calcula `consumo_por_individuo_kg =
  cantidad_alimento / cantidad_actual`.

Errores posibles:
- `404 ACTIVO_NO_ENCONTRADO` — el activo no existe (FA-02).
- `422 ACTIVO_ESTADO_INVALIDO` — el activo no está ACTIVO (E1).
- `422 CICLO_NO_ABIERTO` — el activo no tiene ciclo productivo abierto.
- `422 TIPO_ALIMENTO_NO_ENCONTRADO` / `TIPO_ALIMENTO_INACTIVO` — catálogo inválido.
- `400 FECHA_FUTURA` — fecha de consumo futura (E2).
- `400 FECHA_ANTERIOR_A_FASE` — fecha anterior al inicio de la fase productiva (E3).
- `422 POBLACIONAL_SIN_CANTIDAD` — POBLACIONAL con cantidad_actual 0/NULL (E7).
- `409 CONSUMO_DUPLICADO` — ya existe VALIDADO con misma (activo, fecha, hora, tipo) (E8).
- `403 ACCESO_DENEGADO` — rol sin permiso C sobre recurso 47 (FA-13).

---

## Flujo 2 — Anular consumo VALIDADO (RF-75) · Veterinario/Administrador

```bash
curl -X POST http://localhost:8000/suministros/consumo-alimentos/27/anulacion \
  -H "Authorization: Bearer <VET>" -H "Content-Type: application/json" \
  -d '{"justificacion_anulacion": "Registro erroneo: cantidad mal ingresada por el operario"}'
```
Respuesta esperada `200`: el registro con `estado_registro: "ANULADO"`,
`justificacion_anulacion` y `fecha_hora_anulacion` poblados.

Errores posibles:
- `404 CONSUMO_NO_ENCONTRADO` — no existe.
- `400 JUSTIFICACION_INSUFICIENTE` — justificación < 20 caracteres (E6).
- `409 CONSUMO_YA_ANULADO` — un ANULADO no puede reactivarse ni re-anularse (FA-11).
- `403 ACCESO_DENEGADO` — rol sin permiso D sobre recurso 47 (p.ej. Productor).

---

## Flujo 3 — Consultar/buscar consumos (RF-75)

```bash
curl "http://localhost:8000/suministros/consumo-alimentos?id_activo_biologico=5&estado_registro=VALIDADO" \
  -H "Authorization: Bearer <ADMIN>"
```
Filtros opcionales: `id_activo_biologico`, `fecha_desde`, `fecha_hasta`, `tipo_alimento`,
`estado_registro`. Respuesta `200`: `{ "total": N, "items": [ ... ] }`.

---

## Flujo 4 — Registrar aplicación de medicamento (RF-76) · Veterinario/Administrador

```bash
curl -X POST http://localhost:8000/suministros/medicamentos \
  -H "Authorization: Bearer <VET>" -H "Content-Type: application/json" \
  -d '{
    "id_activo_biologico": 5,
    "nombre_medicamento": "Oxitetraciclina",
    "fecha_aplicacion": "2026-07-29",
    "hora_aplicacion": "08:00",
    "via_administracion": "INTRAMUSCULAR",
    "dosis_aplicada": 5,
    "unidad_dosis": "ml",
    "periodo_retiro_dias": 7,
    "motivo_aplicacion": "Tratamiento antibiotico preventivo",
    "costo_unitario": 1200,
    "nombre_veterinario": "Dra. Ana Ruiz",
    "id_evento_sanitario": null
  }'
```
Respuesta esperada `201`:
```json
{
  "medicamento": {
    "id_registro_medicamento": 14, "id_activo_biologico": 5,
    "nombre_medicamento": "Oxitetraciclina", "via_aplicacion": "IM",
    "cantidad": "5.000", "fecha_fin_retiro": "2026-08-05",
    "costo_total_medicamento": "6000.0000", "estado_registro": "VALIDADO",
    "id_usuario_veterinario": 3
  },
  "fecha_fin_retiro_vigente": "2026-08-05",
  "mensaje": "El medicamento fue registrado correctamente. El período de retiro vigente del activo se extiende hasta 2026-08-05."
}
```
Notas:
- `via_administracion` acepta `ORAL, INTRAMUSCULAR, INTRAVENOSA, SUBCUTANEA, TOPICA,
  INTRAMAMARIA`; se persiste el código de BD (`IM`, `IV`, `SC`, …).
- Si `periodo_retiro_dias > 0`: `fecha_fin_retiro = fecha_aplicacion + periodo_retiro_dias`
  y el activo pasa a **EN_TRATAMIENTO** vía RF-44 (módulo 2), en la misma transacción.
- Múltiples tratamientos simultáneos (E11): cada uno es independiente; el
  `fecha_fin_retiro_vigente` es el **MAX** de todos los VALIDADOS; el activo se mantiene
  EN_TRATAMIENTO.
- Para POBLACIONAL se calcula `dosis_por_individuo = dosis_aplicada / cantidad_actual`.

Errores posibles:
- `404 ACTIVO_NO_ENCONTRADO` — el activo no existe.
- `422 ACTIVO_ESTADO_INVALIDO` — el activo no está ACTIVO ni EN_TRATAMIENTO (E1/E11).
- `422 CICLO_NO_ABIERTO` — sin ciclo productivo abierto (E7).
- `400 FECHA_FUTURA` / `FECHA_ANTERIOR_A_CICLO` — fecha inválida (E2/E3).
- `400 VIA_ADMINISTRACION_INVALIDA` — vía fuera del dominio (FA-06).
- `422 EVENTO_SANITARIO_INVALIDO` — `id_evento_sanitario` inexistente o de otro activo (E12).
- `422 POBLACIONAL_SIN_CANTIDAD` — POBLACIONAL sin cantidad_actual (E7 pobl.).
- `409 MEDICAMENTO_DUPLICADO` — VALIDADO con misma (activo, medicamento, fecha, hora) (E13).
- `403 ACCESO_DENEGADO` — rol sin permiso C sobre recurso 48 (p.ej. Productor).

---

## Flujo 5 — Anular aplicación de medicamento (RF-76) · Veterinario/Administrador

```bash
curl -X POST http://localhost:8000/suministros/medicamentos/14/anulacion \
  -H "Authorization: Bearer <VET>" -H "Content-Type: application/json" \
  -d '{"justificacion_anulacion": "Medicamento aplicado por error, dosis incorrecta registrada"}'
```
Respuesta `200`: registro con `estado_registro: "ANULADO"`.

Errores posibles:
- `404 MEDICAMENTO_NO_ENCONTRADO` — no existe.
- `400 JUSTIFICACION_INSUFICIENTE` — justificación < 20 (E9).
- `409 MEDICAMENTO_YA_ANULADO` — ya anulado (E8).
- `403 ACCESO_DENEGADO` — rol sin permiso D sobre recurso 48.

> La reversión del estado del activo a ACTIVO tras vencer el período de retiro es
> responsabilidad del scheduler de RF-44 (fuera del alcance de CU-01).

---

## Flujo 6 — Consultar/buscar medicamentos (RF-76)

```bash
curl "http://localhost:8000/suministros/medicamentos?id_activo_biologico=5&estado_registro=VALIDADO" \
  -H "Authorization: Bearer <VET>"
```
Filtros opcionales: `id_activo_biologico`, `fecha_desde`, `fecha_hasta`, `estado_registro`.
Respuesta `200`: `{ "total": N, "items": [ ... ] }`.

---

## Notas
- Los registros son **inmutables**: no hay endpoint de edición; para corregir se anula y se
  crea uno nuevo (RF-75 R5 / RF-76 R5, reforzado por triggers BEFORE UPDATE).
- La auditoría (`modulo5.auditorias_suministros`) se genera por triggers de la BD; no se
  invoca desde la aplicación.
- Los costos (`costo_total`, `costo_total_medicamento`) los calcula la BD y se devuelven en
  la respuesta tras releer el registro.
