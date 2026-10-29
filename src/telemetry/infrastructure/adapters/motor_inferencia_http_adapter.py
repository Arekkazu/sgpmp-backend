# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-120-G63 RF-56: cliente HTTPS hacia M04 con TLS mínimo 1.3, desactivado sin URL |
"""Cliente de transporte M03 → M04 para paquetes de inferencia (RF-56 Fase 6, INC-M03-120-G63).

RF-56 exige "canales cifrados (TLS/SSL)"; los RNF de M03 fijan TLS 1.3. Este cliente:

- Solo acepta URLs ``https://``: una URL ``http://`` se rechaza al construirlo, sin tráfico.
- Exige ``IOT_INFERENCIA_TLS_MIN`` (por defecto ``1.3``): un servidor que solo ofrece una
  versión anterior no completa el handshake.
- Verifica certificado y nombre del servidor contra las CA del sistema o contra
  ``IOT_INFERENCIA_CA_FILE``. No sigue redirecciones (evita que un 3xx lleve a ``http://``).

El contrato IA-1 (endpoint, cuerpo, ACK y autenticación de M04) no está definido (INC-M03-115-G58):
el cuerpo ``{"paquetes": [...]}`` y el ``Bearer`` son provisionales. Sin ``IOT_INFERENCIA_M04_URL``
el router sigue con ``MotorInferenciaStubAdapter``.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import ssl
from typing import Optional
from urllib.parse import urlsplit

import httpx

from src.shared.errors import InfrastructureError, ServiceUnavailableError
from src.telemetry.domain.entities.telemetria import PaqueteInferencia
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaPort

logger = logging.getLogger(__name__)

VERSIONES_TLS = {"1.2": ssl.TLSVersion.TLSv1_2, "1.3": ssl.TLSVersion.TLSv1_3}
TLS_MINIMO_POR_DEFECTO = "1.3"
_TIMEOUT_SEGUNDOS = 10.0


class CanalInferenciaInseguroError(InfrastructureError):
    """Configuración que no garantiza un canal cifrado: no se envía nada."""

    def __init__(self, detalle: str) -> None:
        super().__init__(
            code="CANAL_INFERENCIA_INSEGURO",
            message=f"El canal hacia el motor de inferencia no es seguro: {detalle}",
        )


class CanalInferenciaNoDisponibleError(ServiceUnavailableError):
    """El canal TLS no se estableció (versión, certificado o conexión): el paquete no salió."""

    def __init__(self, causa: str) -> None:
        super().__init__(
            code="CANAL_INFERENCIA_NO_DISPONIBLE",
            message=f"No se pudo establecer el canal seguro con el motor de inferencia: {causa}",
        )


def contexto_tls(version_minima: str = TLS_MINIMO_POR_DEFECTO, ca_file: Optional[str] = None) -> ssl.SSLContext:
    if version_minima not in VERSIONES_TLS:
        raise CanalInferenciaInseguroError(
            f"versión mínima de TLS '{version_minima}' no admitida (usar {', '.join(VERSIONES_TLS)})"
        )
    contexto = ssl.create_default_context(cafile=ca_file or None)
    contexto.minimum_version = VERSIONES_TLS[version_minima]
    return contexto


class MotorInferenciaHttpAdapter(MotorInferenciaPort):

    def __init__(self, url: str, contexto: ssl.SSLContext, token: str = "",
                 timeout: float = _TIMEOUT_SEGUNDOS) -> None:
        if urlsplit(url).scheme.lower() != "https":
            raise CanalInferenciaInseguroError("la URL de M04 debe usar https://")
        if contexto.verify_mode != ssl.CERT_REQUIRED or not contexto.check_hostname:
            raise CanalInferenciaInseguroError("el certificado del servidor debe verificarse")
        if contexto.minimum_version < ssl.TLSVersion.TLSv1_2:
            raise CanalInferenciaInseguroError("la versión mínima de TLS no puede ser anterior a 1.2")
        self._url = url
        self._contexto = contexto
        self._token = token
        self._timeout = timeout

    @classmethod
    def desde_entorno(cls) -> Optional["MotorInferenciaHttpAdapter"]:
        url = os.environ.get("IOT_INFERENCIA_M04_URL", "").strip()
        if not url:
            return None
        contexto = contexto_tls(
            os.environ.get("IOT_INFERENCIA_TLS_MIN", TLS_MINIMO_POR_DEFECTO).strip(),
            os.environ.get("IOT_INFERENCIA_CA_FILE", "").strip() or None,
        )
        return cls(url, contexto, token=os.environ.get("IOT_INFERENCIA_M04_TOKEN", ""))

    def enviar_paquete(self, paquete: PaqueteInferencia) -> bool:
        return self._enviar([paquete])

    def enviar_lote(self, paquetes: list[PaqueteInferencia]) -> bool:
        return self._enviar(paquetes)

    def _enviar(self, paquetes: list[PaqueteInferencia]) -> bool:
        cuerpo = json.dumps({"paquetes": [dataclasses.asdict(p) for p in paquetes]}, default=str)
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            # trust_env=False: ni proxies ni SSL_CERT_FILE del entorno cambian el canal configurado.
            with httpx.Client(verify=self._contexto, timeout=self._timeout,
                              follow_redirects=False, trust_env=False) as cliente:
                respuesta = cliente.post(self._url, content=cuerpo, headers=headers)
        except httpx.ConnectError as exc:
            # El motivo SSL (versión de protocolo, certificado, nombre) queda en el log y en el error.
            causa = f"handshake o conexión rechazados: {exc}"[:300]
            logger.error("RF-56: canal hacia M04 no establecido: %s", causa)
            raise CanalInferenciaNoDisponibleError(causa) from exc
        except httpx.HTTPError as exc:
            causa = f"sin respuesta de M04 ({type(exc).__name__})"
            logger.error("RF-56: %s", causa)
            raise CanalInferenciaNoDisponibleError(causa) from exc
        if not respuesta.is_success:
            logger.error("RF-56: M04 no confirmó %d paquete(s): HTTP %s", len(paquetes), respuesta.status_code)
            return False
        return True


def motor_inferencia_http_desde_entorno() -> Optional[MotorInferenciaHttpAdapter]:
    """Cliente HTTPS si ``IOT_INFERENCIA_M04_URL`` está configurada; ``None`` para usar el stub.

    Una configuración insegura (``http://``, TLS < 1.2, versión desconocida) no se usa: se registra
    y se devuelve ``None``, así los paquetes quedan pendientes en vez de salir por un canal sin cifrar.
    """
    try:
        return MotorInferenciaHttpAdapter.desde_entorno()
    except CanalInferenciaInseguroError as exc:
        logger.critical("RF-56: configuración de M04 rechazada, se usa el stub: %s", exc.message)
        return None
