# Resultados TC-M06-G104

## Dictamen general del grupo

**APROBADO CON ALCANCE DELIMITADO**

| Elemento | Resultado |
|---|---|
| TC-M06-25 | APROBADO |
| TC-M06-26 | APROBADO |
| TC-M06-29 | APROBADO (alcance delimitado, RF-89 v1.2) |
| CA-8 / FA-5 (aviso diario Contador) | Pendiente — validación complementaria |
| G104 completo | **No** (mientras CA-8 siga pendiente) |

Fuente de verdad: `estado_oficial_G104.json`.  
Informe consolidado: `INFORME_FINAL_G104.html`.

## Estructura (tres evaluaciones cronológicas)

```
resultados/
├── README.md
├── INFORME_FINAL_G104.html
├── estado_oficial_G104.json
├── primera_evaluacion/     # 2026-11-08 — ejecución inicial
├── segunda_evaluacion/     # 2026-11-10 — aprobación 25/26; 29 preparado
└── tercera_evaluacion/     # 2026-11-13 — lectura TC-29, RF-89 v1.2, dictamen
```

### Primera evaluación (2026-11-08)

Ejecución inicial de solo lectura en TEST. TC-M06-25 y TC-M06-26 quedaron **BLOQUEADOS** (sin precio futuro registrado). TC-M06-29 quedó en **REQUIERE ACLARACIÓN** bajo criterios RF-89 v1.0 (`SIN_PRECIO_VIGENTE` / RF-88).

### Segunda evaluación (2026-11-10)

TC-M06-25 y TC-M06-26 **APROBADOS**. TC-M06-29 **PREPARADO, PENDIENTE DE FECHA** (vencimiento del precio 492 el 2026-11-10; comprobación a partir del 11). Incluye soporte de preparación del escenario.

### Tercera evaluación (2026-11-13)

Verificación de lectura del escenario 492/544/1644, aplicación operativa de **RF-89 v1.2**, dictamen **APROBADO con alcance delimitado** para TC-M06-29, antecedente histórico de rechazo v1.0 y registro de **CA-8 pendiente**.

## Documentación principal (carpeta padre)

- `../criterios_tc_m06_29_rf89_v1_2.md`
- `../procedimiento_verificacion_lectura_tc_m06_29.md`
- `../ejecutar_tc_m06_g104.py`

Material de trabajo no publicado: `../_archivo_trabajo_local/` (excluido por `.gitignore`).
