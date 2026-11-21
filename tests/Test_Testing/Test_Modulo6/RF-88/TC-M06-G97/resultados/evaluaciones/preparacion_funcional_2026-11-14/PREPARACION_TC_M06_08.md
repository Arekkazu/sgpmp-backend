# Preparación TC-M06-08 — Vida útil obligatoria

**Estado:** **parcialmente preparado** — evidencia de bloqueo en propuesta; POST y camino B no listos sin autorización/datos.

---

## Camino A — Reconocimiento al costo sin vida útil

### Objetivo AC
`POST /finanzas/reconocimientos/{id}` → HTTP **422** + código **`VIDA_UTIL_NO_CONFIGURADA`**.

### Hallazgo en TEST (solo lectura)

| Campo | Valor verificado |
|---|---|
| Activo | **1864** (`QA-RF82-BLOQUEADO`) |
| Especie | Caprino Sin Contable Qa Rf (`id_especie` **595**) |
| `GET .../propuestas/1864` | 200 |
| Bloqueos | 1) `CLASIFICACION_NO_CONFIGURADA` 2) `VIDA_UTIL_NO_CONFIGURADA` |
| `es_confirmable` | `false` |
| Costo adquisición (propuesta) | 1.500.000 |

### Solicitud POST preparada (NO ejecutar sin autorización)

```http
POST /finanzas/reconocimientos/1864
Authorization: Bearer <token_contador>
X-Zona-Horaria: America/Bogota
Content-Type: application/json

{}
```

(Ajustar body si el contrato exige campos; no se ensayó escritura.)

### Riesgo de aserción con el activo 1864

`ConfirmarReconocimientoUseCase` lanza el **primer** bloqueo (`bloqueos[0]`).  
Con la propuesta actual, el POST respondería **422 `CLASIFICACION_NO_CONFIGURADA`**, no `VIDA_UTIL_NO_CONFIGURADA`.

| Uso de 1864 | ¿Cubre AC-08? |
|---|---|
| GET propuesta muestra `VIDA_UTIL_NO_CONFIGURADA` | Evidencia parcial / soporte |
| POST reconocimiento | **No** como fixture limpia del AC |

### Datos que faltan (requieren autorización)

1. Especie de prueba **con clasificación** configurada y **sin** `vida_util_meses`, **o**
2. Activo elegible a costo cuya propuesta tenga **solo** el bloqueo `VIDA_UTIL_NO_CONFIGURADA`.

**No** modificar especies compartidas ni clasificaciones sin autorización explícita.

---

## Camino B — Consulta depreciación sobre histórico sin vida útil

### Objetivo AC
`GET /finanzas/activos/{id}/depreciacion?fecha=…` → **422** `VIDA_UTIL_NO_CONFIGURADA`.

### Hallazgo

Ninguno de los 9 activos al costo inventariados tiene `vida_util_meses` nula.  
No hay fixture histórico autorizada en TEST para este camino.

| Ítem | Estado |
|---|---|
| Registro histórico sin vida + especie sin vida | **No disponible** |
| Creación vía SQL/config | **Prohibida** en esta fase |

---

## Dictamen 08

| Camino | ¿Listo para ejecución? |
|---|---|
| A (POST) | **BLOQUEADO** hasta fixture con único bloqueo `VIDA_UTIL_NO_CONFIGURADA` (o autorización para ajustar especie 595 sin contaminar) |
| A (GET propuesta 1864) | Evidencia de bloqueo **ya observada** (no sustituye el AC del POST) |
| B (GET histórico) | **BLOQUEADO** — sin registro apto |

No se ejecutó POST ni se alteró configuración.
