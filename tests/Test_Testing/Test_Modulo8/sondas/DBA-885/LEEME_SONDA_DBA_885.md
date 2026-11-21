# Sonda DBA-885 (M08)

| Fecha | Autor | Qué se hizo |
|---|---|---|
| 2026-11-20 | Juan Sebastian Gutierrez | Sonda de solo lectura para verificar en TEST el pedido al DBA sobre el activo 885 |
| 2026-11-20 | Juan Sebastian Gutierrez | v2: `-IdFincaA` (184), porque la ficha del 885 no trae `id_finca`, y bandeja de 360 días (máximo 366). La corrida v1 (`sonda-20261120-080641`) dejó los puntos 10, 11 y 13 sin verificar por esos dos fallos de la sonda |

**Qué es:** una colección de Newman (16 peticiones) y su runner. Consulta por la API, con la cuenta de Veterinario (`TEST_VET_*`) y dentro del sandbox, cada punto del pedido de `claude/PEDIDO_DBA_M08.md`.

**Cómo funciona:**
- Solo hace GET, salvo el login y el cierre del sandbox.
- Al final hace rollback.
- No usa `/test-control/query` ni se conecta a la base de datos.

**No es un caso de prueba:** esta carpeta no es `TC-`, así que el scanner no la lee.

## Salida

Todo va a `evidencias\sonda-<ts>\`:

- `puntos_dba_885.txt`: un renglón por punto, con uno de estos estados:
  - CUMPLE
  - PARCIAL
  - NO_CUMPLE
  - NO_VERIFICABLE
  - REVISAR (requiere leer el dato crudo)
- `sonda_dba_885.txt`: todas las trazas.
- `consola_sonda_dba_885.txt`
- `resumen_sonda_dba_885.txt`
- `escaneo_secretos_sonda_dba_885.txt`

## Cobertura del pedido

**Puntos que se verifican por API:**

| Punto | Qué se consulta |
|---|---|
| 1 | Fase activa (`/fases`) |
| 2 | Tres eventos sanitarios con hora exacta y su distancia a la inferencia |
| 3 | Hora en la fecha del evento |
| 4 | Activo de otra finca: 403 |
| 7 | Las inferencias citadas siguen existiendo |
| 9 | Cuatro valoraciones esperadas y tres sin valorar |
| 10 | Activo EN_TRATAMIENTO con 2 o más inferencias en la finca |
| 11 | Activo de baja o cerrado con 2 o más inferencias en la finca |
| 12 | Parámetros de M09 (si el Veterinario tiene acceso) |
| 13 | Conflicto en 32985675 |
| 14 | Alerta ligada a 511a6d66 |
| 15 | Inferencias de más de 12 y de 24 meses |

**Puntos que no se verifican:**

| Punto | Motivo |
|---|---|
| 5, 6 | Son preguntas y no datos |
| 8 | Requiere listar usuarios |
| 16, 17 | Son opcionales y dependen del día de la corrida |

## Uso

PowerShell 5.1, desde esta carpeta:

```
.\ejecutar_sonda_dba_885.ps1
```

Exit codes:

| Código | Significado |
|---|---|
| 0 | Sonda completa |
| 2 | Configuración |
| 3 | ABORT |
| 4 | Secretos |
| 5 | Cierre del sandbox |
