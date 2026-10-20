"""
TC-M04-G121 (RF-71 CA-6/Fase 7/Salida 6, CU-17) - "Notificaciones a los
actores." Grupo existente de RF-71.

Código bajo prueba: búsqueda exhaustiva de cualquier llamada a un sistema
de notificaciones desde `src/prediction/`.

HALLAZGO ÚNICO, que invalida los 6 subescenarios: `RegistrarVersionModeloUseCase`
(el único punto donde un modelo puede quedar APROBADO/RECHAZADO, ver
TC-M04-G102) nunca notifica a nadie -- ni al veterinario cuando queda
APROBADO, ni al administrador cuando queda RECHAZADO o cuando falla. Un
grep exhaustivo de "notificacion"/"Notificacion" en todo `src/prediction/`
solo encuentra una coincidencia, en `alerta_patologica_model.py`, que
pertenece al sistema de alertas clínicas de RF-57 -- un dominio
completamente distinto al de notificaciones sobre el ciclo de vida de
versiones de modelo que pide esta ficha.

(a) Veterinario notificado cuando RF-69 marca APROBADO -- HALLAZGO: no
    existe ninguna llamada de notificación en el camino de aprobación.
(b) Administrador notificado ante fallo/rechazo/degradación -- HALLAZGO:
    mismo motivo.
(c) Separación de destinatarios (veterinario sin alertas de
    infraestructura) -- NO EVALUABLE: no hay ningún destinatario porque
    no hay ninguna notificación.
(d)/(e) Notificación por cambio de catálogo durante ejecución / por
    drift pospuesto -- NO EVALUABLE, mismos motivos que TC-M04-G108 y
    TC-M04-G104 (ninguno de esos flujos existe).
(f) Deduplicación de fallos repetidos -- NO EVALUABLE: no hay
    notificaciones que deduplicar.

Cómo se prueba: grep exhaustivo de "notificacion" en src/prediction/ e
inspección directa de que `registrar_version_modelo_use_case.py` no
importa ningún servicio de notificaciones.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g121_notificaciones_a_actores_no_existen.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G121.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoExisteNingunaNotificacionDeCicloDeVidaDeModelo:
    def test_registrar_version_no_importa_ningun_servicio_de_notificaciones(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'notificacion' not in texto.lower()

    def test_la_unica_mencion_de_notificacion_en_prediction_es_de_otro_dominio(self):
        archivos_con_match = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src/prediction').rglob('*.py')
            if 'notificacion' in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        pytest.fail(
            f"HALLAZGO: las unicas coincidencias de 'notificacion' en src/prediction/ son "
            f"{archivos_con_match!r} -- pertenecen al sistema de alertas clinicas RF-57 "
            f"(alerta_patologica_model.py), no a notificaciones sobre el ciclo de vida de "
            f"versiones de modelo. No existe ninguna notificacion a veterinario/administrador "
            f"ligada a RF-71/RF-69."
        ) if archivos_con_match else None
