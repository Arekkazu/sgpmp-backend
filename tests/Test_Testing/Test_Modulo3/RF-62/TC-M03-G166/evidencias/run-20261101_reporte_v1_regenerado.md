# Informe de Regeneración y Verificación de V1 JSON — TC-M03-G166

**Fecha:** 2026-11-01  
**Caso:** TC-M03-G166 (RF-62 v2.0)  
**Ambiente:** TEST  

---

## 1. Identificación y Trazabilidad de Artefactos

| Artefacto | Ruta | SHA-256 |
| :--- | :--- | :--- |
| **V1 Original (Respaldo)** | `evidencias/run-20261022_reporte_v1_original/resultado_TC-M03-G166_original.json` | `3B960577D6189FCC4C28DAF4D4235A56091E3E79D95D0A2EE445C1D06AD454BD` |
| **V1 Regenerado** | `resultados/resultado_TC-M03-G166.json` | `3B960577D6189FCC4C28DAF4D4235A56091E3E79D95D0A2EE445C1D06AD454BD` |
| **Evidencia Primaria (XML V1)** | `resultados/resultado_TC-M03-G166.xml` | `061C071E99E8CAEA790487B8A01F4CDDF4D501B429B670F7F8B44FB969858FAA` |
| **Evidencia HTML V1** | `resultados/resultado_TC-M03-G166.html` | `4BBEB0ECB3C632A78C064475001B9E46DAB92C472997CCC65A9990FF683C4507` |

---

## 2. Motivo
Verificación y regeneración del formato consolidado JSON estandarizado para consumo del pre-commit scanner del QA Dashboard, garantizando que:
1. La estructura contenga exactamente las claves `{"tc", "summary", "checkpoints"}`.
2. Cada uno de los 106 checkpoints posea `estado ∈ {"OK", "FALLA"}`.
3. El bloque `summary` compute honestamente el veredicto histórico `RECHAZADO` (100 OK, 6 FALLA, 5 XFAIL, 1 SKIP).

---

## 3. Verificación de Integridad
- El archivo fuente primario `resultado_TC-M03-G166.xml` (JUnit XML) permaneció estrictamente intacto (`SHA: 061C071E...`).
- La regeneración mediante `generar_json_resultado.py --suffix ""` produjo un resultado determinista idéntico bit a bit, confirmando la validez del conversor parametrizado.
- Ninguna evidencia histórica de ejecución ni suite de pruebas fue modificada.

