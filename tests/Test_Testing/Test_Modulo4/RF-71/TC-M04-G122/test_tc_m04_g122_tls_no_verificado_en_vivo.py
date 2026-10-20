"""
TC-M04-G122 [NUEVO] (ASVS V9) - "Seguridad de transporte (TLS) en los
endpoints de RF-71." Gap recurrente ya señalado por la propia ficha en
otras rondas de M04 (RF-66, RF-68, RF-69, RF-72).

RELACIÓN CON TC-M04-G102 (hallazgo raíz): de los 8 endpoints que la ficha
lista (`POST /api/v1/m04/retraining`, `GET .../retraining/{id_proceso}`,
`GET .../resources`, `GET .../datasets/{dataset_hash}`,
`GET .../models/{id_version}/artifact`, `PUT /api/v1/config/m04/retraining`,
`POST .../cancel`, `POST .../resume`), SEIS no existen en absoluto
(confirmado en G102/G118/G119); los otros dos (`/api/v1/m04/models` y la
ruta de consulta) existen con un path real distinto
(`/prediccion/modelos`, bajo `root_path="/api"`).

(a)/(b)/(c) -- NO EJECUTADO EN ESTA SESIÓN: escanear TLS en vivo
    (testssl.sh/sslyze) requiere una instancia desplegada y accesible por
    red, y las herramientas (testssl.sh, sslyze) no están instaladas en
    este entorno (confirmado en una ronda anterior de este mismo
    proyecto). Ejecutar un escaneo de este tipo contra el entorno TEST
    compartido requiere autorización explícita antes de proceder, por
    tratarse de infraestructura compartida, no solo de una verificación
    de código.

Hallazgo de alcance verificable sin red: de los 8 endpoints listados por
la ficha, 6 no tienen ningún código que los implemente (confirmado por
grep exhaustivo en G102/G115/G118/G119) -- escanear su seguridad de
transporte es, para esos 6, un ejercicio sin objeto: no hay ningún
puerto/ruta real que escanear porque la ruta no existe.

Cómo se prueba: confirmación de cuáles de los 8 endpoints listados tienen
código real (ninguno de los 6 relacionados con "retraining" directamente).

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g122_tls_no_verificado_en_vivo.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G122.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSeisDeOchoEndpointsNoTienenCodigoQueEscanear:
    def test_ningun_router_de_m04_expone_rutas_de_retraining_cancel_ni_resume(self):
        archivos_routers = list((REPO_ROOT / 'src/prediction/infrastructure/routers').glob('*.py'))
        texto_combinado = ' '.join(p.read_text(encoding='utf-8', errors='ignore') for p in archivos_routers)
        pytest.fail(
            "HALLAZGO DE ALCANCE: ninguno de los routers reales de M04 contiene 'retraining', "
            "'resources', 'cancel' ni 'resume' como parte de una ruta -- 6 de los 8 endpoints "
            "que esta ficha pide escanear por TLS no existen; no hay nada que escanear para "
            "ellos. Los otros 2 (registro y consulta de modelos) existen bajo "
            "/prediccion/modelos, no bajo /api/v1/m04/retraining ni /api/v1/m04/models."
        ) if 'retraining' not in texto_combinado.lower() and '/cancel' not in texto_combinado and '/resume' not in texto_combinado else None
