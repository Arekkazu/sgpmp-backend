"""
TC-M03-G151 (RF-60 v1.3/RFC-011 v1.1, CU-18) - "Categoría CAMARA y
estado_calibración." [BLOQUEADO, según la propia ficha].

Código bajo prueba: búsqueda exhaustiva de `CAMARA`/`estado_calibracion`
en todo `src/` y `alembic/`, más inspección de `TipoDispositivoIoT`.

HALLAZGO PRINCIPAL (confirma el bloqueo que la propia ficha ya declara):
`CAMARA`, `CAMARA_VISION` y `estado_calibracion` tienen CERO
coincidencias en todo `src/` y `alembic/`. `TipoDispositivoIoT` no
declara ningún enum cerrado de categorías de dispositivo -- la categoría
es un dato configurable en BD, sin tratamiento especial en código.

(a) Intervalo de heartbeat propio de CAMARA -- BLOQUEADO: no hay
    distinción por categoría de dispositivo en ningún lado.
(b) Cámara sin señal -> algoritmo general -- no es un hallazgo nuevo:
    el algoritmo no distingue categorías (TC-M03-G132).
(c) Cámara con señal pero sin detección válida -> estado_calibracion --
    BLOQUEADO: `estado_calibracion` no existe en ninguna entidad.
(d) Diferenciación en RF-59 -- BLOQUEADO por la misma razón que (c).

Cómo se prueba: grep exhaustivo + inspección de `TipoDispositivoIoT`.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m03_g151_rfc011_camara_sin_requisito_redactado.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G151.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


def _grep(termino: str, carpetas: tuple[str, ...]) -> list[str]:
    archivos: list[str] = []
    for carpeta in carpetas:
        base = REPO_ROOT / carpeta
        if not base.exists():
            continue
        for p in base.rglob('*.py'):
            if termino in p.read_text(encoding='utf-8', errors='ignore'):
                archivos.append(str(p.relative_to(REPO_ROOT)))
        for p in base.rglob('*.sql'):
            if termino in p.read_text(encoding='utf-8', errors='ignore'):
                archivos.append(str(p.relative_to(REPO_ROOT)))
    return archivos


class TestConfirmaElBloqueoDeclaradoPorLaPropiaFicha:
    @pytest.mark.parametrize('termino', ['CAMARA', 'estado_calibracion'])
    def test_termino_del_rfc011_no_existe_en_codigo_ni_esquema(self, termino):
        archivos = _grep(termino, ('src', 'alembic'))
        pytest.fail(
            f"HALLAZGO (confirma el BLOQUEO declarado por la propia ficha): '{termino}' no "
            f"aparece en ningun archivo de src/ ni alembic/ (encontrados: {archivos or 'ninguno'})."
        ) if not archivos else None

    def test_tipo_dispositivo_iot_no_declara_categorias_con_tratamiento_especial(self):
        archivo = REPO_ROOT / 'src/configuration/domain/entities/tipo_dispositivo_iot.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'CAMARA' not in texto
        pytest.fail(
            "HALLAZGO (a): TipoDispositivoIoT no declara ningun enum cerrado de categorias de "
            "dispositivo con tratamiento especial -- la categoria es un dato configurable en BD."
        )

    def test_algoritmo_de_estado_no_distingue_categoria_de_dispositivo(self):
        archivo = REPO_ROOT / 'src/telemetry/domain/entities/estado_dispositivo_iot.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'CAMARA' not in texto
        assert 'categoria' not in texto.lower()
