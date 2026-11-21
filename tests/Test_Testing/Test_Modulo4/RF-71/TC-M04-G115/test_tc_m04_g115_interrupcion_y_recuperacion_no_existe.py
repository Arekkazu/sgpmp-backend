"""
TC-M04-G115 (RF-71 v2.0 E8/CA-16/RNF-13/RNF-14/RFC-009, CU-11) -
"Interrupción, recuperación y reanudación." La v2.0 corrige el número de
fases (7, no 6) y añade (g) sobre revalidación de la ventana de 72h en
CALIBRACION_EN_SITIO.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existen
`POST .../retrainings/{id}/cancel` ni `.../resume`; `CALIBRACION_EN_SITIO`
no existe como entrada reconocida en ningún punto del sistema (G106).

(a)-(f) -- HALLAZGO ÚNICO: no existe ningún mecanismo de checkpoint,
    reanudación por fase ni detección de "datos ya no válidos". No hay
    ningún endpoint de cancelación/reanudación en ningún router.
(g) RFC-009, revalidar la ventana de 72h si vence durante la pausa --
    HALLAZGO DE ALCANCE: no evaluable -- no existe pausa, no existe
    reanudación, y `CALIBRACION_EN_SITIO` no es un trigger reconocido
    por `sp_iniciar_ciclo_reentrenamiento` (confirmado en G106).

Cómo se prueba: grep exhaustivo de "cancel"/"resume"/"reanudar"/
"checkpoint" en todos los routers de M04.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g115_interrupcion_y_recuperacion_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G115.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoExisteCancelacionNiReanudacion:
    @pytest.mark.parametrize('termino', ['cancel', 'resume', 'reanudar', 'checkpoint'])
    def test_termino_no_existe_en_ningun_router_de_m04(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src/prediction/infrastructure/routers').glob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        pytest.fail(
            f"HALLAZGO: '{termino}' no existe en ningun router de M04 (encontrados: "
            f"{archivos or 'ninguno'})."
        ) if not archivos else None


class TestSubCasoGCalibracionNoTieneNiPausaQueRevalidar:
    def test_calibracion_en_sitio_no_es_trigger_valido(self):
        archivo = REPO_ROOT / 'alembic/baseline/esquema_baseline.sql'
        texto = archivo.read_text(encoding='utf-8', errors='ignore')
        bloque = texto[texto.index('CREATE PROCEDURE modulo4.sp_iniciar_ciclo_reentrenamiento'):]
        bloque = bloque[:bloque.index('ALTER PROCEDURE modulo4.sp_iniciar_ciclo_reentrenamiento')]
        pytest.fail(
            "HALLAZGO (g): sp_iniciar_ciclo_reentrenamiento no reconoce 'CALIBRACION_EN_SITIO' "
            "como trigger valido (solo PROGRAMADO/MANUAL/DEGRADACION) -- no hay ningun proceso "
            "de calibracion que pudiera pausarse ni cuya ventana de 72h pudiera revalidarse."
        ) if "WHEN 'CALIBRACION_EN_SITIO'" not in bloque else None
