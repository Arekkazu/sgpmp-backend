# Planes de prueba de flujo multiespecie

Un archivo por especie. El paradigma (poblacional/individual) lo fija el `grupo_manejo` de la especie (`src/shared/tipo_modelo.py`); un area multiespecie solo admite especies del mismo grupo (RF-20 v2.1).

| Cod | Especie | Grupo de manejo | Paradigma | Confianza | Plan |
|---|---|---|---|---|---|
| E1 | Vaca | ESPECIES_GRANDES | INDIVIDUAL | Alta | [plan_E1_vaca.md](plan_E1_vaca.md) |
| E2 | Cerdo | PORCINOS | POBLACIONAL | Alta | [plan_E2_cerdo.md](plan_E2_cerdo.md) |
| E3 | Pollo | AVES | POBLACIONAL | Alta | [plan_E3_pollo.md](plan_E3_pollo.md) |
| E4 | Cachama | ACUICULTURA | POBLACIONAL | Alta | [plan_E4_cachama.md](plan_E4_cachama.md) |
| E5 | Tortuga | ACUICULTURA (propuesta) | POBLACIONAL (decision de QA) | Media: grupo por confirmar | [plan_E5_tortuga.md](plan_E5_tortuga.md) |
| E7 | Avestruz | ESPECIES_GRANDES (propuesta) | INDIVIDUAL (decision de QA) | Media: grupo por confirmar | [plan_E7_avestruz.md](plan_E7_avestruz.md) |

## Combinaciones multiespecie (mismo grupo)

- ACUICULTURA: E4 Cachama + E5 Tortuga.
- ESPECIES_GRANDES: E1 Vaca + E7 Avestruz.
- AVES (E3 Pollo) y PORCINOS (E2 Cerdo): una sola especie de la lista; el policultivo usa una especie de apoyo del catalogo (`Avicola`, `Marranos`).
- Negativo transversal: cualquier par de grupos distintos (p. ej. E3 Pollo + E1 Vaca) -> 422 `GRUPOS_MANEJO_INCOMPATIBLES`.

## Pendientes de confirmar (Desarrollo/analisis)

1. Paradigma decidido por QA el 2026-10-27: E5 Tortuga poblacional y E7 Avestruz individual. Falta confirmar con Desarrollo el `grupo_manejo` que lo produce (propuestos ACUICULTURA y ESPECIES_GRANDES); el catalogo solo tiene 5 grupos.
2. E6 Cocodrilo queda fuera del alcance (decision del 2026-10-27); se conserva el codigo E6 sin plan.
3. Si E5/E7 no se registran como especies del catalogo, los planes quedan sin datos semilla.
4. Las especies reales de TEST (Tilapia, Bovino, Equino...) no tienen `grupo_manejo`; las nuevas deben crearse con grupo.

Los TC se asignan con id `TC-M09-G..`/`TC-M03-G..` al formalizarlos; aqui van como `por asignar`.
