# CU08 — Gaps BD y RBAC — RF-42 (Eventos Reproductivos)

Fecha de análisis: 2026-06-29

---

## Tabla analizada: `modulo2.eventos_reproductivos`

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'modulo2' AND table_name = 'eventos_reproductivos'
ORDER BY ordinal_position;
```

| Columna               | Tipo         | Nullable original | Nullable tras fix |
|-----------------------|--------------|-------------------|-------------------|
| id_evento_reproductivo| integer      | NO (PK, FK)       | NO                |
| categoria             | USER-DEFINED | NO                | NO                |
| id_padre              | integer      | **NO**            | **YES** ← gap     |
| resultado             | varchar      | NO                | NO                |
| numero_cria           | integer      | NO (default 0)    | NO                |
| id_madre              | integer      | YES               | YES               |

---

## Gap encontrado: `id_padre NOT NULL`

**Problema:** El RF-42 establece que `id_padre` (semental) es obligatorio solo para
eventos de tipo `servicio` e `inseminacion`. Para `diagnostico`, `parto`, `aborto`
y `nacimiento` el padre es opcional o no aplica.

La columna estaba definida como `NOT NULL`, lo que impedía registrar esos eventos.

**Decisión:** Hacer la columna nullable. La obligatoriedad de `id_padre` para
`servicio`/`inseminacion` se valida en el use case, no en la DB.

**DDL aplicado (2026-06-29):**
```sql
ALTER TABLE modulo2.eventos_reproductivos
  ALTER COLUMN id_padre DROP NOT NULL;
```

---

## RBAC — sin gaps

El recurso 29 (`activos_biologicos`) con acción 1 (C) ya tenía permisos activos para:
- admin (id_permiso=163)
- prod  (id_permiso=165)
- vet   (id_permiso=176)

No se requirieron inserciones adicionales en `modulo1.permisos`.
