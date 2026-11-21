"""
TC-M06-G88 (RF-94 CA-9, FA-4, Restricción 5, CU-04) - "Truncamiento de
payload superior a 64 KB."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda.

Código bajo prueba:
    src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py
        (``_LIMITE_PAYLOAD``, el bloque ``truncado = ...`` dentro de ``registrar()``)
    src/financial_valuation/infrastructure/repositories/sql.py (``a_json``, puro Python, sin BD)

HALLAZGO PRINCIPAL (el contenido conservado es la MITAD del límite, no el
límite): el código real es
```python
_LIMITE_PAYLOAD = 64 * 1024
...
truncado = len(payload.encode("utf-8")) > _LIMITE_PAYLOAD
if truncado:
    payload = a_json({"resumen": payload[: _LIMITE_PAYLOAD // 2], "payload_truncado": True})
```
Cuando SÍ se trunca, el "resumen" conservado es de `_LIMITE_PAYLOAD // 2` =
32 KB de **texto** (slice de caracteres de `payload`, que ya es un string
JSON), no 64 KB como implica la ficha ("se persiste... con el payload
truncado al límite"). El límite de 64 KB sólo decide SI se trunca; cuánto
se conserva es la mitad de eso.

HALLAZGO (frontera 64 KB exacta -- CONFIRMADA correcta): la condición es
estrictamente `>`, no `>=`. Un payload serializado de exactamente 64*1024
bytes NO se trunca -- coincide con la lectura de la ficha ("supera este
límite" = frontera exclusiva). Esto se verifica reproduciendo la lógica
real con payloads construidos a medida (63 KB / 64 KB exactos / 64 KB + 1
byte / 1 MB), usando el propio `a_json()` real (función pura, sin
dependencia de sesión de BD).

HALLAZGO (el JSON resultante SÍ es válido como contenedor, pero el
fragmento interno no se garantiza válido): el wrapper
`{"resumen": "...", "payload_truncado": true}` es siempre JSON válido en
sí mismo (es un dict con dos claves simples). Pero `resumen` es un slice de
caracteres de un string JSON ya serializado -- si el payload original era
un objeto JSON grande, el primer 50% de sus caracteres casi nunca es, por
sí mismo, un fragmento JSON válido (se corta a mitad de una clave, un
valor, una llave de cierre). La ficha pide confirmar "el JSON truncado
sigue siendo válido y consultable" -- es cierto solo para el WRAPPER
externo, no para el contenido que el Contador vería dentro de `resumen`.

HALLAZGO (no hay garantía de recuperación del payload completo por
id_referencia): `id_referencia` es sólo un entero que apunta a un id de
otra tabla (p. ej. el id del estado de resultados, del comprobante, etc.).
Nada en el código de auditoría garantiza que esa tabla de origen conserve
el payload completo tal cual se intentó auditar -- el contenido "disponible
en el módulo fuente" depende enteramente de la retención de esa tabla, que
es un sistema totalmente distinto y no se puede verificar desde el código
de RF-94 mismo.

Cómo se prueba: pytest de unidad reconstruyendo la lógica real de
truncamiento con el `a_json()` real importado (sin tocar BD), confirmando
bytes exactos en las 4 fronteras que pide la ficha (63 KB, 64 KB exactos,
64 KB + 1, 1 MB).

ACTUALIZACIÓN 2026-11-13 (respuesta de Análisis/Diseño): NO ES UN DEFECTO,
se deja como está. RF-94 solo exige cortar a 64 KB y marcar el truncado, y
el código real cumple exactamente eso. Los matices de este TC (el resumen
conservado es la mitad del límite, el fragmento interno no es JSON válido
por sí mismo, no hay garantía de recuperación completa por id_referencia)
son lecturas más estrictas de la ficha que lo que RF-94 realmente pide.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g88_truncamiento_payload_64kb.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G88.html --self-contained-html
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.financial_valuation.infrastructure.repositories.sql import a_json

REPO_ROOT = Path(__file__).resolve().parents[5]
REPOSITORIO = REPO_ROOT / 'src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py'

_LIMITE_PAYLOAD = 64 * 1024


def _simular_registrar(payload_dict: dict) -> tuple[bool, str]:
    """Replica EXACTA del bloque real de registrar() (líneas _LIMITE_PAYLOAD/truncado/resumen),
    usando el a_json() real importado -- sin tocar BD."""
    payload = a_json(payload_dict) or "{}"
    truncado = len(payload.encode("utf-8")) > _LIMITE_PAYLOAD
    if truncado:
        payload = a_json({"resumen": payload[: _LIMITE_PAYLOAD // 2], "payload_truncado": True})
    return truncado, payload


def _payload_de_n_bytes_utf8(n_bytes: int) -> dict:
    """Construye un dict cuyo a_json() serializado tiene aproximadamente n_bytes de largo
    (ajusta con relleno ascii 'x', 1 byte por caracter en utf-8)."""
    base = a_json({"relleno": ""})
    faltante = max(n_bytes - len(base.encode("utf-8")), 0)
    return {"relleno": "x" * faltante}


class TestSubCasoElLimiteDecideSiSeTruncaNoCuantoSeConserva:
    def test_63kb_no_se_trunca(self):
        truncado, _ = _simular_registrar(_payload_de_n_bytes_utf8(63 * 1024))
        assert truncado is False

    def test_64kb_exactos_no_se_trunca_frontera_confirmada_correcta(self):
        truncado, _ = _simular_registrar(_payload_de_n_bytes_utf8(64 * 1024))
        assert truncado is False

    def test_64kb_mas_1_byte_si_se_trunca(self):
        truncado, _ = _simular_registrar(_payload_de_n_bytes_utf8(64 * 1024 + 1))
        assert truncado is True

    def test_1mb_si_se_trunca(self):
        truncado, _ = _simular_registrar(_payload_de_n_bytes_utf8(1024 * 1024))
        assert truncado is True

    def test_cuando_se_trunca_el_resumen_conservado_es_la_mitad_del_limite_no_el_limite(self):
        """No es un defecto (confirmado por Analisis/Diseno 2026-11-13): RF-94 solo exige
        cortar a 64 KB y marcar el truncado -- se deja como esta."""
        _, payload_final = _simular_registrar(_payload_de_n_bytes_utf8(1024 * 1024))
        resumen = json.loads(payload_final)["resumen"]
        assert len(resumen) <= _LIMITE_PAYLOAD // 2 + 100


class TestSubCasoElWrapperEsJsonValidoPeroElFragmentoInternoNoSeGarantiza:
    def test_el_wrapper_externo_siempre_es_json_valido(self):
        _, payload_final = _simular_registrar(_payload_de_n_bytes_utf8(1024 * 1024))
        datos = json.loads(payload_final)
        assert datos['payload_truncado'] is True
        assert isinstance(datos['resumen'], str)

    def test_el_fragmento_resumen_no_es_en_si_mismo_json_valido_confirmado_por_diseno(self):
        """No es un defecto: RF-94 solo exige cortar a 64 KB y marcar el truncado -- el wrapper
        externo si es JSON valido, que es lo que RF-94 realmente pide."""
        payload_original = {"items": [{"id": i, "nombre": "x" * 200} for i in range(400)]}
        _, payload_final = _simular_registrar(payload_original)
        resumen = json.loads(payload_final)["resumen"]
        fragmento_es_json_valido = True
        try:
            json.loads(resumen)
        except json.JSONDecodeError:
            fragmento_es_json_valido = False
        assert not fragmento_es_json_valido


class TestSubCasoNoHayGarantiaDeRecuperacionCompletaPorIdReferenciaConfirmadoPorDiseno:
    def test_id_referencia_es_solo_un_entero_sin_ninguna_garantia_de_retencion_cruzada(self):
        """No es un defecto: se deja como esta, RF-94 no exige esa garantia cruzada."""
        texto = REPOSITORIO.read_text(encoding='utf-8')
        assert '"ref": evento.id_referencia' in texto
