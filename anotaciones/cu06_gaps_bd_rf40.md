# CU06 — Gaps BD y RBAC: RF-40

Fecha de análisis: 2026-06-28

---

## Gap BD: columnas de rango en `modulo9.metricas_produccion`

La tabla `metricas_produccion` no tenía columnas para definir el rango válido de medición por especie, necesario para FA-04 (validar que el valor esté dentro del rango permitido).

**SQL aplicado:**

```sql
ALTER TABLE modulo9.metricas_produccion
    ADD COLUMN valor_min NUMERIC(10,4),
    ADD COLUMN valor_max NUMERIC(10,4);
```

Ambas columnas son **nullable**: si no se configuran rangos para una métrica, la validación de rango se omite (no bloquea el registro).

---

## Decisión: evaluación de avance de fase

El RF-40 especifica una relación `<<extend>>` para la evaluación automática de avance de fase cuando "la nueva condición biológica supera el umbral configurado en M09–RF-17". Sin embargo:

- `modulo9.umbrales_ambientales` (RF-17) solo contiene variables ambientales (temperatura, pH, oxígeno, etc.) — no variables de crecimiento biológico.
- No existe una tabla de umbrales biológicos (peso/talla por fase) en el esquema actual.

**Decisión adoptada**: el avance automático de fase se evalúa usando `ciclos_biologicos.duracion_dias` — si los días transcurridos desde `fecha_inicio` de la fase activa son ≥ a la duración configurada de esa fase, el sistema avanza a la siguiente fase automáticamente al registrar el evento. Si no hay fase siguiente o el avance falla por cualquier razón, el evento se guarda igualmente (el avance de fase es opcional, no bloquea el registro).

---

## RBAC — sin gap

El recurso 29 (`activos_biologicos`) ya tiene todos los permisos necesarios. No se requieren cambios en `modulo1.permisos`.
