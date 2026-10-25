# TC-M03-096

Solo este caso.

## Identificador y nombre

- **ID:** TC-M03-096 (G44)  
- **Nodo pytest:** `test_cortes_severidad_porcentual_en_edge[TC-M03-096]`  
- **Archivo:** `test_tc_m03_g44.py` (mismo `parametrize` que 079)  
- **Nombre:** mismos cortes porcentuales de severidad en Edge que declara el script para G44

## RF y caso de uso

RF-55.1 / CU-02.

## Objetivo y precondiciones

Igual que el cuerpo compartido del test: desviaciones en 9.9–25.1 % con umbral_max conocido. Motor Edge ausente. Inclusividad 10 %/25 % no está en `src/`.

## Datos de prueba

`CORTES_SEVERIDAD_PCT` en `rf55_preparacion.py`. No ejecutados contra hardware. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g44.py::test_cortes_severidad_porcentual_en_edge[TC-M03-096]
```

## Resultado esperado / obtenido

Esperado: severidad LEVE/MODERADO/CRÍTICO según % en el nodo. Obtenido: SKIPPED.

- 2026-10-25T15:46:08.735362-05:00 → 15:46:09.904418-05:00  
- Proceso 1.169 s; pytest **1 skipped in 0.08s**; EXIT=0  

## Estado

**BLOQUEADO** (SKIPPED).

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`

## Discrepancia

El script no distingue el objetivo de 096 respecto de 079 (mismo mensaje). Matriz de diseño no versionada aquí. No se reescribió el script.

## Siguiente acción

Confirmar con QA qué CA exclusivo tiene 096. Luego firmware + regla de inclusividad.
