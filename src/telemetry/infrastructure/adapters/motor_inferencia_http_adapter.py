# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-120-G63 RF-56: cliente HTTPS hacia M04 con TLS mínimo 1.3, desactivado sin URL |
# | 2026-10-30 | Arekkazu     | RF-66: URL base del motor en cualquier dominio y ventana del activo en cada paquete |
"""Cliente de transporte M03 → M04 para paquetes de inferencia (RF-56 Fase 6, INC-M03-120-G63).

RF-56 exige "canales cifrados (TLS/SSL)"; los RNF de M03 fijan TLS 1.3. Este cliente:

- Solo acepta URLs ``https://``: una URL ``http://`` se rechaza al construirlo, sin tráfico.
- Exige ``IOT_INFERENCIA_TLS_MIN`` (por defecto ``1.3``): un servidor que solo ofrece una
  versión anterior no completa el handshake.
- Verifica certificado y nombre del servidor contra las CA del sistema o contra
  ``IOT_INFERENCIA_CA_FILE``. No sigue redirecciones (evita que un 3xx lleve a ``http://``).

``IOT_INFERENCIA_M04_URL`` es la URL base del motor IA en cualquier dominio, con o sin prefijo
(``https://api.inmero.co/model-ia-test``, ``https://motor.arekkazu.top``, ``https://1-2-3-4.sslip.io``):
se le agrega ``/v1/paquetes``. Una URL que ya termina en ``/v1/paquetes`` se usa tal cual. Sin ella
se sigue con ``MotorInferenciaStubAdapter``.

Contrato IA-1 v1 (decisión D-B; INC-M03-115-G58): ``{"paquetes": [...]}`` con ``Bearer``; cada
paquete lleva además ``id_activo_biologico`` y ``lecturas`` (ventana del activo, ver
``VentanaInferenciaPort``) cuando el adaptador tiene de dónde sacarlas.
"""
from __future__ import annotations

import dataclasses
import functools
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
from src.telemetry.domain.repositories.ventana_inferencia_port import VentanaInferenciaPort

logger = logging.getLogger(__name__)

VERSIONES_TLS = {"1.2": ssl.TLSVersion.TLSv1_2, "1.3": ssl.TLSVersion.TLSv1_3}
TLS_MINIMO_POR_DEFECTO = "1.3"
_TIMEOUT_SEGUNDOS = 10.0
RUTA_PAQUETES = "/v1/paquetes"


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


def url_paquetes(url: str) -> str:
    """URL base del motor (cualquier dominio, con o sin prefijo) → URL de ``/v1/paquetes``."""
    url = url.strip().rstrip("/")
    return url if url.endswith(RUTA_PAQUETES) else url + RUTA_PAQUETES


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
                 timeout: float = _TIMEOUT_SEGUNDOS, ventanas: Optional[VentanaInferenciaPort] = None) -> None:
        if urlsplit(url).scheme.lower() != "https" or not urlsplit(url).hostname:
            raise CanalInferenciaInseguroError("la URL de M04 debe usar https://")
        if contexto.verify_mode != ssl.CERT_REQUIRED or not contexto.check_hostname:
            raise CanalInferenciaInseguroError("el certificado del servidor debe verificarse")
        if contexto.minimum_version < ssl.TLSVersion.TLSv1_2:
            raise CanalInferenciaInseguroError("la versión mínima de TLS no puede ser anterior a 1.2")
        self._url = url
        self._contexto = contexto
        self._token = token
        self._timeout = timeout
        self._ventanas = ventanas

    @property
    def url(self) -> str:
        return self._url

    @classmethod
    def desde_entorno(cls, ventanas: Optional[VentanaInferenciaPort] = None) -> Optional["MotorInferenciaHttpAdapter"]:
        url = os.environ.get("IOT_INFERENCIA_M04_URL", "").strip()
        if not url:
            return None
        contexto = contexto_tls(
            os.environ.get("IOT_INFERENCIA_TLS_MIN", TLS_MINIMO_POR_DEFECTO).strip(),
            os.environ.get("IOT_INFERENCIA_CA_FILE", "").strip() or None,
        )
        return cls(url_paquetes(url), contexto, token=os.environ.get("IOT_INFERENCIA_M04_TOKEN", ""),
                   ventanas=ventanas)

    def enviar_paquete(self, paquete: PaqueteInferencia) -> bool:
        return self._enviar([paquete])

    def enviar_lote(self, paquetes: list[PaqueteInferencia]) -> bool:
        return self._enviar(paquetes)

    def _enviar(self, paquetes: list[PaqueteInferencia]) -> bool:
        cuerpo = json.dumps({"paquetes": self._cuerpos(paquetes)}, default=str)
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


    def _cuerpos(self, paquetes: list[PaqueteInferencia]) -> list[dict]:
        cuerpos = [dataclasses.asdict(p) for p in paquetes]
        if self._ventanas is None:
            return cuerpos
        ventanas = self._ventanas.ventanas(paquetes)
        for cuerpo in cuerpos:
            ventana = ventanas.get(cuerpo["id_paquetes_inferencia"])
            if ventana is not None:
                cuerpo["id_activo_biologico"] = ventana.id_activo_biologico
                cuerpo["lecturas"] = ventana.lecturas
        return cuerpos


def motor_inferencia_http_desde_entorno(
    ventanas: Optional[VentanaInferenciaPort] = None,
) -> Optional[MotorInferenciaHttpAdapter]:
    """Cliente HTTPS si ``IOT_INFERENCIA_M04_URL`` está configurada; ``None`` para usar el stub.

    Una configuración insegura (``http://``, TLS < 1.2, versión desconocida) no se usa: se registra
    y se devuelve ``None``, así los paquetes quedan pendientes en vez de salir por un canal sin cifrar.
    """
    try:
        cliente = MotorInferenciaHttpAdapter.desde_entorno(ventanas)
    except CanalInferenciaInseguroError as exc:
        logger.critical("RF-56: configuración de M04 rechazada, se usa el stub: %s", exc.message)
        return None
    if cliente is not None:
        _avisar_habilitado(cliente.url)
    return cliente


@functools.lru_cache(maxsize=8)
def _avisar_habilitado(url: str) -> None:
    """Una vez por URL (el cliente se arma por request): deja en el log a qué motor se envía."""
    logger.info("RF-56: motor de inferencia habilitado en %s", url)
