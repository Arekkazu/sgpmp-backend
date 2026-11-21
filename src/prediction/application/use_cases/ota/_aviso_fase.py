# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-204-G43/207-G46 RF-70: modo PROGRAMADO espera su ventana (E1) |
"""Avisar ``ota/notify`` a los nodos de una fase del rollout (DEV-15, D6 paso 3).

Lo usan crear la distribución (fase CANARY) y el avance de fase al llegar el
último ``activated`` de la fase anterior. Va siempre después de un commit: si el
broker no publica, el despliegue queda PENDIENTE con el motivo y se puede volver
a avisar sin perder la distribución.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from src.prediction.domain.entities.despliegue_ota import DespliegueOta
from src.prediction.domain.entities.distribucion_ota import DistribucionOta
from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.domain.repositories.despliegue_ota_repository import DespliegueOtaRepository
from src.prediction.domain.repositories.ota_edge_port import AvisoOtaPort, NodoOtaPort, UrlDescargaPort

#: El broker exige un componente; los modelos INDIVIDUAL y META no tienen (RFC-009).
COMPONENTE_MODELO_COMPLETO = "COMPLETO"

_TTL_URL_DEFAULT_SEGUNDOS = 24 * 3600

#: RF-70 E1: la distribución PROGRAMADO no se avisa fuera de su ventana.
MOTIVO_FUERA_VENTANA = "FUERA_VENTANA_ACTUALIZACION"


def ttl_url() -> timedelta:
    return timedelta(seconds=int(os.environ.get("OTA_URL_TTL_SEGUNDOS", _TTL_URL_DEFAULT_SEGUNDOS)))


def vencimiento_url(distribucion: DistribucionOta, ahora: datetime) -> datetime:
    """La URL dura ``OTA_URL_TTL_SEGUNDOS``, y al menos hasta el fin de la ventana."""
    expira = ahora + ttl_url()
    if distribucion.ventana_fin is not None and distribucion.ventana_fin > expira:
        expira = distribucion.ventana_fin
    return expira


def fuera_de_ventana(distribucion: DistribucionOta, ahora: datetime) -> bool:
    """PROGRAMADO solo se avisa entre ``ventana_inicio`` y ``ventana_fin`` (RF-70 Fase 1)."""
    if distribucion.modo_distribucion != "PROGRAMADO" or distribucion.ventana_inicio is None:
        return False
    return not (distribucion.ventana_inicio <= ahora <= (distribucion.ventana_fin or ahora))


def avisar_despliegues(
    *,
    despliegues: list[DespliegueOta],
    distribucion: DistribucionOta,
    version: VersionModelo,
    despliegue_repo: DespliegueOtaRepository,
    nodo_port: NodoOtaPort,
    aviso_port: AvisoOtaPort,
    url_port: UrlDescargaPort,
    ahora: datetime,
) -> list[DespliegueOta]:
    """Pide al broker el aviso de cada despliegue PENDIENTE y guarda el resultado (sin commit).

    Fuera de la ventana de una distribución PROGRAMADO no se avisa: el despliegue queda
    PENDIENTE con motivo FUERA_VENTANA_ACTUALIZACION y lo libera la tarea periódica al
    abrir la ventana (RF-70 E1).
    """
    pendientes = [d for d in despliegues if d.estado_despliegue == "PENDIENTE"]
    if fuera_de_ventana(distribucion, ahora):
        for despliegue in pendientes:
            despliegue.posponer(MOTIVO_FUERA_VENTANA)
        return [despliegue_repo.actualizar(d) for d in pendientes]
    seriales = nodo_port.obtener_seriales([d.id_dispositivo_iot for d in pendientes]) if pendientes else {}
    avisados = []
    for despliegue in pendientes:
        serial = seriales.get(despliegue.id_dispositivo_iot)
        if serial is None:
            despliegue.marcar_aviso_fallido("El nodo ya no está activo: no se le avisó la OTA.")
            avisados.append(despliegue_repo.actualizar(despliegue))
            continue
        expira = vencimiento_url(distribucion, ahora)
        resultado = aviso_port.notificar({
            "serial": serial,
            "id_despliegue_ota": despliegue.id_despliegue_ota,
            "tipo_modelo": despliegue.tipo_modelo,
            "componente": despliegue.componente or COMPONENTE_MODELO_COMPLETO,
            "version": version.nombre_version,
            "url_descarga": url_port.generar(despliegue.id_despliegue_ota, expira),
            "sha256": despliegue.hash_modelo_sha256,
            "firma": version.firma_artefacto,
            "tamano_bytes": version.tamanio_artefacto_bytes,
            "parametros": {"fase_rollout": despliegue.fase_rollout, **distribucion.parametros_nodo()},
        })
        if resultado.publicado:
            despliegue.marcar_notificado(resultado.id_mensaje, expira)
        else:
            despliegue.marcar_aviso_fallido(resultado.mensaje)
        avisados.append(despliegue_repo.actualizar(despliegue))
    return avisados
