# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-22 | Arekkazu | USAB2 M01 RF-02: un refresh rotado cuya respuesta se perdió no cierra la sesión |
"""El token que presenta el navegador ya se rotó, pero el que emitió esa rotación nunca se usó: no es robo."""
from datetime import datetime, timedelta, timezone

from src.identity_access.application.use_cases.sesiones.refresh_token_use_case import _es_sucesor
from src.identity_access.domain.entities.token import Token

ROTACION = datetime(2026, 11, 22, 14, 0, tzinfo=timezone.utc)


def _token(**kw) -> Token:
    return Token(id_token=kw.pop("id_token", 1), **kw)


def test_sucesor_sin_usar_de_la_misma_rotacion_se_tolera():
    viejo = _token(fecha_uso=ROTACION)
    vigente = _token(id_token=2, fecha_creacion=ROTACION + timedelta(milliseconds=200))
    assert _es_sucesor(vigente, viejo)


def test_si_la_cadena_avanzo_o_el_sucesor_se_uso_es_reuso():
    viejo = _token(fecha_uso=ROTACION)
    assert not _es_sucesor(_token(id_token=2, fecha_creacion=ROTACION, fecha_uso=ROTACION + timedelta(minutes=1)), viejo)
    assert not _es_sucesor(_token(id_token=3, fecha_creacion=ROTACION + timedelta(minutes=10)), viejo)
    assert not _es_sucesor(None, viejo)
