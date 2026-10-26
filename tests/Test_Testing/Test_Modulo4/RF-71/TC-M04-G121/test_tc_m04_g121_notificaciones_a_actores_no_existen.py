"""
TC-M04-G121 (RF-71 v2.0 CA-6/Fase 7/Salida 6/RFC-009, CU-17) -
"Notificaciones a los actores." La v2.0 añade (f): notificación por
vencimiento de calibración y por auditorías de RF-24 incompletas.

Código bajo prueba: búsqueda exhaustiva de cualquier llamada a un sistema
de notificaciones desde `src/prediction/`.

HALLAZGO ÚNICO, que invalida los 7 subescenarios: `RegistrarVersionModeloUseCase`
nunca notifica a nadie. Un grep exhaustivo de "notificacion" en todo
`src/prediction/` solo encuentra una coincidencia, en
`alerta_patologica_model.py` (sistema de alertas clínicas RF-57, dominio
distinto).

(a)-(e) -- HALLAZGO: sin cambios respecto a la ronda anterior.
(f) RFC-009, notificación por vencimiento de calibración / auditorías de
    RF-24 incompletas -- HALLAZGO AGRAVADO: no solo no existe ninguna
    notificación -- tampoco existe el concepto de "vencimiento de
    calibración" ni "auditorías de RF-24" con ese significado en el
    código real (el RF-24 real es calibración de ganancia/offset de
    sensor, sin concepto de auditoría ni vencimiento).
(g) Deduplicación -- NO EVALUABLE: no hay notificaciones que deduplicar.

Cómo se prueba: grep exhaustivo de "notificacion" en src/prediction/ +
confirmación de que el RF-24 real no tiene concepto de vencimiento.

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
            f"{archivos_con_match!r} -- pertenecen a RF-57, no a RF-71/RF-69."
        ) if archivos_con_match else None


class TestSubCasoFVencimientoDeCalibracionNoExisteComoConcepto:
    def test_calibracion_real_no_tiene_concepto_de_vencimiento_ni_auditoria(self):
        archivo = REPO_ROOT / 'src/configuration/domain/entities/calibracion.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (f): el RF-24 real (Calibracion) no tiene ningun campo de vencimiento ni "
            "de auditoria -- es un registro puntual de ganancia/offset de sensor, sin fecha de "
            "expiracion ni estado de auditoria que pudiera disparar una notificacion."
        ) if 'vencimiento' not in texto.lower() and 'auditoria' not in texto.lower() else None
