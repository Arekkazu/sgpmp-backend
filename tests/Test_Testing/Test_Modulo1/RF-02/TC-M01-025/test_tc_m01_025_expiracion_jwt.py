"""
TC-M01-025 - Expiracion del token JWT exactamente a las 8 horas de
haber sido generado.

RF relacionado: RF-02
Categoria: Valores limite

Estrategia: en vez de mockear datetime.now() dentro de create_token(),
se construye el JWT manualmente (mismo payload, misma clave secreta y
algoritmo que usa el modulo real) con un 'iat' fijado exactamente a
7h59min u 8h01min en el pasado, y un 'exp' calculado igual que lo hace
create_token() (iat + JWT_EXPIRE_HOURS). Esto permite probar el limite
con precision exacta al minuto, sin esperar tiempo real ni parchear
el reloj del sistema.

Requiere la variable de entorno SECRET_KEY seteada (cualquier valor,
solo debe ser consistente durante la corrida del test) ademas de
DATABASE_URL (por el import de src.shared.database que arrastra
create_engine al importar otros modulos de src.shared).

Como correrlo (desde la raiz del repo, con las env vars seteadas):

    $env:DATABASE_URL = "postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test"
    $env:SECRET_KEY = "clave-de-prueba-solo-para-este-test"
    python -m pytest <ruta>\\test_tc_m01_025_expiracion_jwt.py -v \
        --html=reporte-TC-M01-025.html --self-contained-html
"""
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt as jose_jwt

from src.shared import jwt as jwt_module
from src.shared.errors import AuthenticationError

SECRET_KEY = jwt_module._SECRET_KEY
ALGORITHM = jwt_module._ALGORITHM
HORAS_EXPIRACION = jwt_module._EXPIRE_HOURS  # 8 por defecto, segun RF-02


def _construir_token(minutos_desde_generado: int) -> str:
    """Construye un JWT valido en formato, con iat/exp fijados con precision
    exacta al minuto, simulando que fue generado hace X minutos."""
    ahora = datetime.now(timezone.utc)
    iat = ahora - timedelta(minutes=minutos_desde_generado)
    exp = iat + timedelta(hours=HORAS_EXPIRACION)
    payload = {
        "sub": "74",
        "jti": "999999",
        "rol": 2,
        "exp": exp,
        "iat": iat,
    }
    return jose_jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


class TestTCM01025ExpiracionJWT:
    """Suite de pruebas para el limite de expiracion del JWT (8 horas)."""

    def test_token_de_7h59min_sigue_siendo_valido(self):
        """
        Limite inferior: un token generado hace 7 horas y 59 minutos
        (479 min) todavia le queda 1 minuto de vigencia. verify_token()
        debe aceptarlo sin lanzar ninguna excepcion.
        """
        token = _construir_token(minutos_desde_generado=479)

        payload = jwt_module.verify_token(token)

        assert payload["sub"] == "74"
        assert payload["rol"] == 2

    def test_token_de_8h01min_esta_expirado(self):
        """
        Limite superior: un token generado hace 8 horas y 1 minuto
        (481 min) ya supero las 8 horas de vigencia por 1 minuto.
        verify_token() debe rechazarlo con TOKEN_EXPIRADO (401).
        """
        token = _construir_token(minutos_desde_generado=481)

        with pytest.raises(AuthenticationError) as exc_info:
            jwt_module.verify_token(token)

        assert exc_info.value.code == "TOKEN_EXPIRADO"

    def test_token_exactamente_a_las_8_horas_limite_exacto(self):
        """
        Control adicional en el limite exacto (480 min = 8h00min0s).
        Documenta el comportamiento en el instante exacto del corte
        (puede caer para cualquiera de los dos lados dependiendo de
        microsegundos de ejecucion; se deja como informativo, no
        se afirma un resultado esperado especifico).
        """
        token = _construir_token(minutos_desde_generado=480)
        try:
            payload = jwt_module.verify_token(token)
            print(f"En el limite exacto (480min): ACEPTADO. payload={payload}")
        except AuthenticationError as e:
            print(f"En el limite exacto (480min): RECHAZADO. code={e.code}")