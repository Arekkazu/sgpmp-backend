# TC-M02-G78 — Control de acceso a la ficha integral y visibilidad de accesos directos según rol (OWASP API5)

**CU-10B · RF-47 — Ficha Integral del Activo Biológico.**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-131) Rechazar consulta sin permisos · (TC-M02-132) Accesos directos visibles solo según permisos del rol |
| Tipo | Validación / Seguridad — OWASP API5:2023 |
| Herramienta | Pytest |
| Endpoint | `GET /activos-biologicos/{id_activo}/ficha-integral` |
| Responsable | Juan Manuel · Prioridad Media |

## Resultado: TC-M02-131 PASS completo · TC-M02-132 bloqueado (mismo gap ya confirmado en TC-M02-G77)

**4/4 tests PASS.** Detalle completo en `RESULTADOS/TC-M02-G78_resultado.md`.

### Cuentas usadas

- **Contador** (sin ningún permiso sobre `activos_biologicos`, para TC-M02-131): cuenta QA reactivada
  (`tc016.f87178ba.qa@sgpmp-test.com`, dormida desde una prueba de RF-01 anterior) y re-rolada a Contador
  (`id_rol=5`) para esta prueba.
- **Veterinario** (solo lectura, para TC-M02-132): la misma cuenta reactivada y re-rolada en TC-M02-G23
  (`tc020.qa@sgpmp-test.com`), reutilizada aquí. Se le creó una finca propia dedicada (Finca 40) con un activo
  accesible (`id=222`), porque no tenía ninguna finca asignada y sin eso no podía leer ningún activo (RF-25).

### TC-M02-131 — PASS completo

`GET /activos-biologicos/5/ficha-integral` con el token del Contador → **403** `ACCESO_DENEGADO`, y se verificó
explícitamente que la respuesta **no contiene ningún campo del activo** (identificador, especie, raza, eventos,
indicadores, etc.) — solo el sobre de error estándar. Cumple exactamente lo que exige el RF: "Ningún dato del
activo es expuesto."

### TC-M02-132 — bloqueado por el mismo gap de TC-M02-G77, no es un fallo nuevo de control de acceso

Confirmado (control positivo) que el Veterinario **sí** puede leer la ficha de un activo dentro de su alcance
(200). Pero la respuesta **no tiene ningún campo `accesos_directos`** — la Sección 8 que este sub-caso pide
verificar (visibilidad de acciones según permisos del rol) **no existe en absoluto** en la API actual, ya
confirmado en `TC-M02-G77` (TC-M02-127). No hay nada que filtrar por rol porque no hay ninguna lista de accesos
que la API devuelva. Este sub-caso queda **bloqueado**, no fallido: el control de acceso general (RBAC + alcance
por finca) sí funciona correctamente sobre lo que la API expone hoy; simplemente no expone la sección que este
caso necesita para evaluarse.

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Pytest 9.0.3 + `requests`. Fecha de ejecución: 2026-09-10.

### Cómo re-ejecutar

```bash
python -m pytest tests/Test_Testing/Test_Modulo2/RF-47/TC-M02-G78/test_tc_m02_g78_control_acceso_ficha_integral.py -v
```
