"""
Retest TC-M01-112 (2026-09-12)
Validar que el mensaje mostrado en las 3 solicitudes de recuperacion
permitidas y en la 4ta (bloqueada) sea consistente y no filtre informacion
adicional

Defectos originales:
  1. La 4ta solicitud (bloqueada) respondia `422` en vez de `429 Too Many
     Requests` -- mismo defecto documentado en TC-M01-043 / INC-M01-07-43.
  2. La hora de "reintento permitido" en el mensaje de bloqueo era incorrecta:
     siempre mostraba la hora ACTUAL de la respuesta (calculada como
     `hace_una_hora + 1 hora`, que matematicamente siempre da "ahora"), en vez
     de la hora real de desbloqueo -- INC-M01-20-112.

Causa raiz corregida (confirmada en codigo, sincronizado desde origin/test):
  - `solicitar_recuperacion_use_case.py` ahora lanza `TooManyRequestsError`
    (HTTP 429) en vez de `BusinessRuleError` (422).
  - La hora de reintento ahora se calcula como
    `(mas_antigua_intento_en_ventana or ahora) + 1 hora`, usando la fecha del
    intento MAS ANTIGUO dentro de la ventana vigente -- un calculo que si
    corresponde a cuando se libera cupo realmente, y que por lo tanto es
    ESTABLE entre llamadas sucesivas (no cambia con cada consulta).

Esta prueba unitaria verifica, contra el use case real (con mocks de
infraestructura), que:
  1. Las 3 solicitudes dentro del limite responden con el mismo mensaje
     generico (ya cubierto tambien por TC-M01-041, se reconfirma aqui en el
     contexto especifico de esta ficha).
  2. La 4ta solicitud (fuera del limite) responde `429` (no `422`) -- defecto 1.
  3. El mensaje de bloqueo NO incluye el correo electronico solicitado (no
     filtra informacion adicional sobre la cuenta).
  4. La hora de reintento mostrada es IDENTICA entre dos llamadas bloqueadas
     sucesivas, cuando el intento mas antiguo de la ventana es el mismo --
     defecto 2.

Ejecutar desde la raiz del repositorio:
    python -m pytest tests/Test_Testing/Test_Modulo1/RF-08/TC-M01-112/tc_m01_112_retest.py -v --html=reporte-TC-M01-112-v2.0.html --self-contained-html
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case import (
    SolicitarRecuperacionUseCase,
    _MENSAJE_GENERICO,
)
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dto.contrasena_dto import SolicitarRecuperacionDTO
from src.shared.errors import TooManyRequestsError


def _build_use_case(solicitudes_en_ventana: int, mas_antigua: datetime = None):
    """Arma el use case con una cuenta activa valida y un contador de
    intentos por IP controlado (simula cuantas solicitudes ya hay en la
    ventana de la ultima hora)."""
    usuario = MagicMock()
    usuario.id_usuario = 68
    usuario.nombre = "Cuenta de prueba 68"

    cuenta = MagicMock()
    cuenta.id_estado_cuenta = Cuenta.ESTADO_ACTIVO
    cuenta.esta_pendiente.return_value = False

    usuarios_repo = MagicMock()
    usuarios_repo.obtener_por_correo.return_value = usuario

    cuentas_repo = MagicMock()
    cuentas_repo.obtener_por_usuario.return_value = cuenta

    eventos_repo = MagicMock()
    intentos_anonimos_repo = MagicMock()
    intentos_anonimos_repo.contar_por_ip.return_value = solicitudes_en_ventana
    intentos_anonimos_repo.obtener_fecha_mas_antigua_por_ip.return_value = mas_antigua
    db = MagicMock()
    correo_recuperacion_port = MagicMock()

    use_case = SolicitarRecuperacionUseCase(
        usuarios_repo=usuarios_repo,
        cuentas_repo=cuentas_repo,
        eventos_repo=eventos_repo,
        intentos_anonimos_repo=intentos_anonimos_repo,
        db=db,
        correo_recuperacion_port=correo_recuperacion_port,
    )
    return use_case


class TestTCM01112ConsistenciaDeMensajes:
    """TC-M01-112: 3 solicitudes permitidas + 4ta bloqueada, mismo mensaje
    generico en las permitidas y 409/429 consistente y sin fugas en el bloqueo."""

    @pytest.mark.parametrize("numero_solicitud", [1, 2, 3])
    def test_las_3_solicitudes_permitidas_responden_mensaje_generico(self, numero_solicitud):
        """Dentro del limite (contador <= 3), cada solicitud debe completarse
        con el mismo mensaje generico, sin importar cual de las 3 sea."""
        use_case = _build_use_case(solicitudes_en_ventana=numero_solicitud)
        dto = SolicitarRecuperacionDTO(correo_electronico="existente@sgpmp-test.com")

        mensaje = use_case.execute(dto, ip="127.0.0.1")

        assert mensaje == _MENSAJE_GENERICO

    def test_4ta_solicitud_responde_429_no_422(self):
        """Defecto 1: al superar el limite, el codigo debe ser 429, no 422."""
        mas_antigua = datetime.now(timezone.utc) - timedelta(minutes=45)
        use_case = _build_use_case(solicitudes_en_ventana=4, mas_antigua=mas_antigua)
        dto = SolicitarRecuperacionDTO(correo_electronico="existente@sgpmp-test.com")

        with pytest.raises(TooManyRequestsError) as exc_info:
            use_case.execute(dto, ip="127.0.0.1")

        exc = exc_info.value
        assert exc.status_code == 429, f"Se esperaba HTTP 429, se obtuvo {exc.status_code}"
        assert exc.code == "LIMITE_SOLICITUDES_EXCEDIDO"

    def test_mensaje_de_bloqueo_no_filtra_el_correo_solicitado(self):
        """El mensaje de bloqueo no debe mencionar el correo electronico
        especifico que se intento usar -- no debe dar pistas adicionales."""
        mas_antigua = datetime.now(timezone.utc) - timedelta(minutes=45)
        use_case = _build_use_case(solicitudes_en_ventana=4, mas_antigua=mas_antigua)
        correo_solicitado = "correo-especifico-tc112@sgpmp-test.com"
        dto = SolicitarRecuperacionDTO(correo_electronico=correo_solicitado)

        with pytest.raises(TooManyRequestsError) as exc_info:
            use_case.execute(dto, ip="127.0.0.1")

        assert correo_solicitado not in exc_info.value.message

    def test_hora_de_reintento_es_estable_entre_dos_llamadas_sucesivas(self):
        """Defecto 2: si el intento mas antiguo de la ventana no cambia entre
        dos consultas, la hora de reintento mostrada debe ser exactamente la
        misma -- no la hora actual de cada consulta."""
        mas_antigua_fija = datetime.now(timezone.utc) - timedelta(minutes=50)

        use_case_1 = _build_use_case(solicitudes_en_ventana=4, mas_antigua=mas_antigua_fija)
        dto = SolicitarRecuperacionDTO(correo_electronico="existente@sgpmp-test.com")
        with pytest.raises(TooManyRequestsError) as exc_1:
            use_case_1.execute(dto, ip="127.0.0.1")

        # Segunda consulta "mas tarde" (misma ventana, mismo intento mas antiguo)
        use_case_2 = _build_use_case(solicitudes_en_ventana=5, mas_antigua=mas_antigua_fija)
        with pytest.raises(TooManyRequestsError) as exc_2:
            use_case_2.execute(dto, ip="127.0.0.1")

        mensaje_1 = exc_1.value.message
        mensaje_2 = exc_2.value.message
        print(f"\nTC-M01-112: mensaje intento bloqueado 1 -> \"{mensaje_1}\"")
        print(f"TC-M01-112: mensaje intento bloqueado 2 -> \"{mensaje_2}\"")

        assert mensaje_1 == mensaje_2, (
            "La hora de reintento cambio entre dos llamadas con el mismo intento "
            "mas antiguo -- indicarial que todavia se calcula con la hora actual."
        )

        # Y el calculo debe corresponder exactamente a mas_antigua + 1 hora
        hora_esperada = (mas_antigua_fija + timedelta(hours=1)).strftime("%H:%M:%S")
        assert hora_esperada in mensaje_1