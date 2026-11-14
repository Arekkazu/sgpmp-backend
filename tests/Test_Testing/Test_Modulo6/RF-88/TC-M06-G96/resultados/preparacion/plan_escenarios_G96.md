# TC-M06-G96 — Plan de escenarios (no ejecutado)

## Datos base verificados

- Activo **2126** / valoración **66** / reconocimiento **886** / periodo **411 ABIERTO**
- Costo 10.000.000 · dep 0 · det 0 · libros 10.000.000 · vida útil 100 meses
- Eventos sanitarios: **0**
- Alerta `VALOR_LIBROS_AJUSTADO_A_CERO` en 2126: **0**

## Datos a usar por subcaso (objetivo)

| ID | Dep | Det | Libros | POST clave | Verificación |
|---|---:|---:|---:|---|---|
| 05 | 2.000.000 | 1.000.000 | 7.000.000 | deterioro 1.000.000 (tras dep) | GET activo `valor_contable_por_costo` |
| 06 | 10.000.000 | 0 | 0 | solo depreciación (cierre) | GET activo |
| 07 | 7.000.000 | 5.000.000 | 0 + alerta | deterioro 5.000.000 (tras dep) | GET activo + auditoría `VALOR_LIBROS_AJUSTADO_A_CERO` |

## Precondiciones faltantes antes de autorizar escritura

1. Estrategia para lograr depreciaciones exactas (vida útil / cierres / seed del responsable).  
2. Al menos un `id_evento_sanitario` del activo 2126 (o clones).  
3. Tres baselines independientes **o** reset entre subcasos.  
4. Autorización expresa por subcaso (y, si aplica, para cierre de periodo 411).

## Consultas posteriores estándar

```
GET /finanzas/activos/2126
GET /finanzas/auditoria?tipo_evento=VALOR_LIBROS_AJUSTADO_A_CERO&id_activo_biologico=2126&formato=TECNICO
GET /finanzas/periodos?numero_id_tributaria=901999213
```
