# TC-M03-079

Solo este caso.

## Identificador y nombre

- **ID:** TC-M03-079 (G44)  
- **Nodo pytest:** `test_cortes_severidad_porcentual_en_edge[TC-M03-079]`  
- **Archivo:** `test_tc_m03_g44.py` líneas 20–26  
- **Nombre (script / `rf55_preparacion`):** cortes 9.9 / 10 / 10.1 / 24.9 / 25 / 25.1 % con `umbral_max` conocido; LEVE ≤10 %, MODERADO 10–25 %, CRÍTICO >25 %

## RF y caso de uso

RF-55.1 / CU-02. El script indica que **conservar severidad de un DTO no calcula el porcentaje** (eso sería RF-56). No se reasignó.

## Objetivo y precondiciones

Calcular severidad porcentual **en el Edge**. Precondiciones: umbral_max en el nodo, desviación medida, clasificador firmware.

## Datos de prueba

Literales de matriz embebidos: `CORTES_SEVERIDAD_PCT = (9.9, 10.0, 10.1, 24.9, 25.0, 25.1)`. No se aplicaron a un dispositivo. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g44.py::test_cortes_severidad_porcentual_en_edge[TC-M03-079]
```

## Resultado esperado / obtenido

Esperado: cortes de severidad en firmware, inclusividad de 10 % y 25 % definida.  
Obtenido: SKIPPED (`rf55_preparacion.py:62`). El propio helper anota: inclusividad 10 y 25 **pendiente de Desarrollo**; **no está en src/**.

- 2026-10-25T15:46:07.535957-05:00 → 15:46:08.732337-05:00  
- Proceso 1.196 s; pytest **1 skipped in 0.09s**; EXIT=0  

## Estado

**BLOQUEADO** (SKIPPED). Doble dependencia: clasificador Edge **e** regla de inclusividad no implementada en backend.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`

## Discrepancia

G44 parametriza 079 y 096 con el **mismo** texto de skip. La matriz original no está como archivo en el repo; no se diferenció el CA de 079 vs 096 en el script. No se corrigió.

## Siguiente acción

AIOT: cálculo % vs umbral_max. Backend/QA: decidir inclusividad en 10 % y 25 %. No usar copia de `severidad` del DTO como evidencia de este CA.
