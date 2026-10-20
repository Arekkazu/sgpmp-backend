"""DEV-15 (RF-70/RF-73, D6 de AIOT-DEV-03): orquestador OTA de modelos por componente.

Fakes en memoria que respetan la regla de DB-04 (un despliegue vigente por
nodo y componente). El endpoint de descarga se prueba de punta a punta con
TestClient para comprobar la URL firmada y el soporte de Range.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.prediction.application.use_cases.ota._aviso_fase import COMPONENTE_MODELO_COMPLETO
from src.prediction.application.use_cases.ota.crear_distribucion_ota_use_case import CrearDistribucionOtaUseCase
from src.prediction.application.use_cases.ota.obtener_artefacto_ota_use_case import ObtenerArtefactoOtaUseCase
from src.prediction.application.use_cases.ota.registrar_reporte_ota_use_case import RegistrarReporteOtaUseCase
from src.prediction.domain.entities.despliegue_ota import DespliegueOta
from src.prediction.domain.entities.distribucion_ota import planificar_fases
from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.domain.repositories.ota_edge_port import ResultadoAvisoOta
from src.prediction.infrastructure.adapters.ota_edge_adapters import UrlDescargaHmacAdapter
from src.prediction.infrastructure.dto.ota_dto import CrearDistribucionOtaDTO, ReporteOtaDTO
from src.shared.errors import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)

SERIALES = {38: "EDGE-38", 39: "EDGE-39", 40: "EDGE-40", 41: "EDGE-41"}
SHA = "a" * 64


def _version(id_version=3, componente="DETECTOR", estado="ACTIVO", tipo="MODELO_AVES", **kw) -> VersionModelo:
    return VersionModelo(
        id_version_modelo=id_version, nombre_version=f"{componente or 'modelo'}-v{id_version}", tipo_modelo=tipo,
        estado_version=estado, formato_artefacto="TFLITE", ruta_artefacto=kw.get("ruta", "aves/detector_v3.tflite"),
        tamanio_artefacto_bytes=2048, hash_artefacto_sha256=kw.get("sha", SHA), dataset_entrenamiento_hash=None,
        id_proceso_rf71=None, version_referencia=None, f1_score=None, recall_clase_riesgo_alto=None,
        precision_modelo=None, accuracy=None, roc_auc_score=None, recall_por_clase=None, matriz_confusion=None,
        compatibilidad_variables=None, notas_validacion=None, detalle_validacion=None, id_usuario=1,
        esta_produccion=estado == "ACTIVO", fecha_entrenamiento=None, fecha_registro=None, fecha_despliegue=None,
        componente=componente, firma_artefacto="firma-ed25519-base64",
    )


class _Versiones:
    def __init__(self, *versiones): self.versiones = {v.id_version_modelo: v for v in versiones}
    def obtener_por_id(self, id_version): return self.versiones.get(id_version)


class _Despliegues:
    """Despliegues en memoria con la unicidad de DB-04."""

    def __init__(self, existentes=()):
        self.filas: dict[int, DespliegueOta] = {}
        self.siguiente = 100
        for d in existentes:
            self.filas[d.id_despliegue_ota] = d

    def _vigente(self, d):
        return d.estado_despliegue in ("PENDIENTE", "EN_PROCESO")

    def crear(self, e):
        for d in self.filas.values():
            if (self._vigente(d) and d.id_dispositivo_iot == e.id_dispositivo_iot
                    and d.tipo_modelo == e.tipo_modelo and d.componente == e.componente):
                raise ConflictError(code="DUPLICADO", message="uq_despliegue_ota_vigente")
        self.siguiente += 1
        nuevo = dataclasses.replace(e, id_despliegue_ota=self.siguiente)
        self.filas[nuevo.id_despliegue_ota] = nuevo
        return dataclasses.replace(nuevo)

    def actualizar(self, e):
        self.filas[e.id_despliegue_ota] = dataclasses.replace(e)
        return dataclasses.replace(e)

    def obtener_por_id(self, id_despliegue, *, bloquear=False):
        d = self.filas.get(id_despliegue)
        return dataclasses.replace(d) if d else None

    def listar_por_distribucion(self, id_distribucion, fase=None):
        return [dataclasses.replace(d) for d in sorted(self.filas.values(), key=lambda x: x.id_despliegue_ota)
                if d.id_distribucion_ota == id_distribucion and (fase is None or d.fase_rollout == fase)]

    def nodos_con_despliegue_vigente(self, ids, tipo_modelo, componente):
        return sorted({d.id_dispositivo_iot for d in self.filas.values() if self._vigente(d)
                       and d.id_dispositivo_iot in ids and d.tipo_modelo == tipo_modelo and d.componente == componente})

    def version_instalada(self, id_dispositivo, tipo_modelo, componente):
        exitosos = [d for d in self.filas.values() if d.estado_despliegue == "EXITOSO"
                    and d.id_dispositivo_iot == id_dispositivo and d.tipo_modelo == tipo_modelo and d.componente == componente]
        return exitosos[-1].id_version_modelo if exitosos else None


class _Distribuciones:
    def __init__(self): self.filas = {}

    def guardar(self, e):
        e = dataclasses.replace(e, id_distribucion_ota=len(self.filas) + 1)
        self.filas[e.id_distribucion_ota] = e
        return dataclasses.replace(e)

    def obtener_por_id(self, i, *, bloquear=False):
        return dataclasses.replace(self.filas[i]) if i in self.filas else None

    def actualizar(self, e):
        self.filas[e.id_distribucion_ota] = dataclasses.replace(e)
        return dataclasses.replace(e)


class _Nodos:
    def __init__(self, seriales=None): self.seriales = SERIALES if seriales is None else seriales
    def obtener_seriales(self, ids): return {i: self.seriales[i] for i in ids if i in self.seriales}


class _Broker:
    def __init__(self, publica=True):
        self.publica = publica
        self.avisos = []

    def notificar(self, aviso):
        self.avisos.append(aviso)
        if not self.publica:
            return ResultadoAvisoOta(publicado=False, mensaje="El broker no publicó ota/notify. Causa: HTTP 503.")
        return ResultadoAvisoOta(publicado=True, mensaje="ok", id_mensaje=f"msg-{len(self.avisos)}")


class _Url:
    def __init__(self, configurada=True): self._configurada = configurada
    def configurada(self): return self._configurada
    def generar(self, id_despliegue, expira): return f"https://api/prediccion/ota/artefactos/{id_despliegue}?firma=x"
    def es_valida(self, *a): return True


class _Auditoria:
    def __init__(self): self.eventos = []
    def registrar(self, **kw): self.eventos.append(kw)


class _Db:
    def __init__(self): self.commits = 0
    def commit(self): self.commits += 1
    def rollback(self): pass


class _Ctx:
    """Un escenario completo compartido por crear y reportar."""

    def __init__(self, *, versiones=None, existentes=(), broker=None, url=None, nodos=None):
        self.versiones = _Versiones(*(versiones or [_version()]))
        self.despliegues = _Despliegues(existentes)
        self.distribuciones = _Distribuciones()
        self.broker = broker or _Broker()
        self.url = url or _Url()
        self.nodos = nodos or _Nodos()
        self.auditoria = _Auditoria()

    def crear(self, **campos):
        datos = dict(id_version_modelo=3, lista_dispositivos_objetivo=[38], modo_distribucion="INMEDIATO",
                     tamano_fragmento_bytes=65536, max_reintentos_descarga=3, nivel_bateria_minimo=Decimal("30"))
        datos.update(campos)
        return CrearDistribucionOtaUseCase(
            db=_Db(), version_repo=self.versiones, distribucion_repo=self.distribuciones,
            despliegue_repo=self.despliegues, nodo_port=self.nodos, aviso_port=self.broker, url_port=self.url,
        ).execute(CrearDistribucionOtaDTO(**datos), id_usuario=1)

    def reportar(self, id_despliegue, evento, serial=None, **detalle):
        d = self.despliegues.filas[id_despliegue]
        return RegistrarReporteOtaUseCase(
            db=_Db(), despliegue_repo=self.despliegues, distribucion_repo=self.distribuciones,
            version_repo=self.versiones, auditoria_repo=self.auditoria, nodo_port=self.nodos,
            aviso_port=self.broker, url_port=self.url,
        ).execute(ReporteOtaDTO(serial=serial or SERIALES[d.id_dispositivo_iot], id_despliegue_ota=id_despliegue,
                                componente=d.componente, evento=evento, detalle=detalle))


def _exitoso(id_despliegue, id_dispositivo, id_version, componente):
    ahora = datetime.now(timezone.utc)
    return DespliegueOta(
        id_despliegue_ota=id_despliegue, id_version_modelo=id_version, id_dispositivo_iot=id_dispositivo,
        tipo_modelo="MODELO_AVES", modo_distribucion="INMEDIATO", estado_despliegue="EXITOSO", hash_modelo_sha256=SHA,
        resultado_validacion_hash=True, id_version_modelo_anterior=None, rollback_ejecutado=False, intentos_descarga=1,
        max_reintentos=3, tamano_modelo_bytes=10, tamano_descargado_bytes=10, duracion_proceso_ms=5, ventana_inicio=None,
        ventana_fin=None, nivel_bateria_al_inicio=None, fecha_inicio=ahora, fecha_fin=ahora, motivo_fallo=None,
        componente=componente,
    )


# ── Rollout por fases ──────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "nodos, porcentaje, esperado",
    [
        (1, 25, ["CANARY"]),
        (2, 25, ["CANARY", "PARCIAL"]),
        (4, 25, ["CANARY", "PARCIAL", "TOTAL", "TOTAL"]),
        (10, 25, ["CANARY"] + ["PARCIAL"] * 3 + ["TOTAL"] * 6),
        (10, 20, ["CANARY"] + ["PARCIAL"] * 2 + ["TOTAL"] * 7),
    ],
)
def test_planifica_canary_de_un_nodo_luego_parcial_y_luego_total(nodos, porcentaje, esperado):
    assert planificar_fases(nodos, porcentaje) == esperado


# ── Crear distribución ─────────────────────────────────────────────────────

def test_crea_una_fila_pendiente_por_nodo_y_solo_avisa_al_canary():
    ctx = _Ctx()
    resultado = ctx.crear(lista_dispositivos_objetivo=[38, 39, 40, 41])
    assert [d.fase_rollout for d in resultado.despliegues] == ["CANARY", "PARCIAL", "TOTAL", "TOTAL"]
    assert all(d.estado_despliegue == "PENDIENTE" for d in resultado.despliegues)
    assert resultado.distribucion.fase_rollout == "CANARY" and resultado.distribucion.estado_distribucion == "EN_CURSO"
    assert [a["serial"] for a in ctx.broker.avisos] == ["EDGE-38"]
    aviso = ctx.broker.avisos[0]
    assert aviso["sha256"] == SHA and aviso["firma"] == "firma-ed25519-base64"
    assert aviso["componente"] == "DETECTOR" and aviso["version"] == "DETECTOR-v3" and aviso["tamano_bytes"] == 2048
    assert aviso["url_descarga"].startswith("https://api/prediccion/ota/artefactos/")
    assert aviso["parametros"]["tamano_fragmento_bytes"] == 65536
    assert aviso["parametros"]["nivel_bateria_minimo"] == 30.0 and aviso["parametros"]["fase_rollout"] == "CANARY"
    canary = resultado.despliegues[0]
    assert canary.id_mensaje_notify == "msg-1" and canary.fecha_expiracion_url is not None


def test_criterio_d05_detector_v3_en_un_nodo_que_tiene_anomalias_v1():
    """El nodo 38 tiene ANOMALIAS v1 instalado: distribuir DETECTOR v3 no lo toca."""
    ctx = _Ctx(existentes=[_exitoso(10, 38, 1, "ANOMALIAS")])
    canary = ctx.crear().despliegues[0]
    assert (canary.componente, canary.id_version_modelo, canary.id_version_modelo_anterior) == ("DETECTOR", 3, None)
    ctx.reportar(canary.id_despliegue_ota, "activated")
    por_componente = {d.componente: (d.id_version_modelo, d.estado_despliegue) for d in ctx.despliegues.filas.values()}
    assert por_componente == {"ANOMALIAS": (1, "EXITOSO"), "DETECTOR": (3, "EXITOSO")}


def test_registra_la_version_que_el_nodo_tenia_del_mismo_componente():
    ctx = _Ctx(existentes=[_exitoso(10, 38, 2, "DETECTOR")])
    assert ctx.crear().despliegues[0].id_version_modelo_anterior == 2


def test_un_despliegue_vigente_del_mismo_componente_es_409():
    ctx = _Ctx()
    ctx.crear()
    with pytest.raises(ConflictError) as exc:
        ctx.crear()
    assert exc.value.code == "DESPLIEGUE_OTA_VIGENTE"


def test_otro_componente_en_el_mismo_nodo_si_se_puede_distribuir():
    ctx = _Ctx(versiones=[_version(3, "DETECTOR"), _version(4, "ANOMALIAS")])
    ctx.crear(id_version_modelo=3)
    assert ctx.crear(id_version_modelo=4).despliegues[0].componente == "ANOMALIAS"


@pytest.mark.parametrize(
    "version, codigo",
    [(_version(estado="APROBADO"), "VERSION_NO_DISTRIBUIBLE"), (_version(ruta=None), "ARTEFACTO_NO_DISPONIBLE"),
     (_version(sha=None), "ARTEFACTO_NO_DISPONIBLE")],
)
def test_solo_se_distribuye_una_version_activa_con_artefacto(version, codigo):
    with pytest.raises(BusinessRuleError) as exc:
        _Ctx(versiones=[version]).crear()
    assert exc.value.code == codigo


def test_version_inexistente_es_404():
    with pytest.raises(NotFoundError):
        _Ctx().crear(id_version_modelo=999)


def test_dispositivo_inexistente_o_inactivo_es_422():
    with pytest.raises(BusinessRuleError) as exc:
        _Ctx(nodos=_Nodos({38: "EDGE-38"})).crear(lista_dispositivos_objetivo=[38, 77])
    assert exc.value.code == "DISPOSITIVO_OTA_INVALIDO" and "77" in exc.value.message


def test_sin_clave_de_firma_responde_503_sin_crear_nada():
    ctx = _Ctx(url=_Url(configurada=False))
    with pytest.raises(ServiceUnavailableError):
        ctx.crear()
    assert ctx.despliegues.filas == {}


def test_si_el_broker_no_publica_queda_pendiente_con_el_motivo():
    ctx = _Ctx(broker=_Broker(publica=False))
    canary = ctx.crear().despliegues[0]
    assert canary.estado_despliegue == "PENDIENTE" and "ota/notify" in canary.motivo_fallo
    assert canary.id_mensaje_notify is None


def test_modelo_sin_componente_viaja_como_modelo_completo():
    ctx = _Ctx(versiones=[_version(5, None, tipo="MODELO_ESPECIES_GRANDES")])
    ctx.crear(id_version_modelo=5)
    assert ctx.broker.avisos[0]["componente"] == COMPONENTE_MODELO_COMPLETO


def test_programado_exige_ventana():
    with pytest.raises(ValueError):
        CrearDistribucionOtaDTO(id_version_modelo=3, lista_dispositivos_objetivo=[38], modo_distribucion="PROGRAMADO",
                                tamano_fragmento_bytes=1, max_reintentos_descarga=0)


# ── Reportes del nodo y eventos RF-73 ──────────────────────────────────────

def _distribuida(n=4):
    ctx = _Ctx()
    ids = [d.id_despliegue_ota for d in ctx.crear(lista_dispositivos_objetivo=list(SERIALES)[:n]).despliegues]
    return ctx, ids


def test_integrity_ok_emite_modelo_distribuido_edge():
    ctx, (canary, *_) = _distribuida()
    resultado = ctx.reportar(canary, "integrity_ok")
    assert resultado.evento_rf73 == "MODELO_DISTRIBUIDO_EDGE"
    evento = ctx.auditoria.eventos[0]
    assert (evento["tipo_actor"], evento["id_sistema"], evento["entidad_referencia"]) == ("DISPOSITIVO_EDGE", "EDGE-38", "despliegue_ota")
    assert evento["payload_evento"]["componente"] == "DETECTOR"
    assert ctx.despliegues.filas[canary].resultado_validacion_hash is True


def test_canary_activado_emite_el_evento_y_pasa_a_la_fase_parcial():
    ctx, (canary, parcial, total_1, total_2) = _distribuida()
    resultado = ctx.reportar(canary, "activated", duracion_proceso_ms=1200)
    assert resultado.evento_rf73 == "MODELO_ACTIVADO_EDGE" and resultado.fase_avanzada_a == "PARCIAL"
    assert ctx.despliegues.filas[canary].estado_despliegue == "EXITOSO"
    assert [a["serial"] for a in ctx.broker.avisos] == ["EDGE-38", "EDGE-39"]
    resultado = ctx.reportar(parcial, "activated")
    assert resultado.fase_avanzada_a == "TOTAL"
    assert [a["serial"] for a in ctx.broker.avisos][2:] == ["EDGE-40", "EDGE-41"]
    ctx.reportar(total_1, "activated")
    ctx.reportar(total_2, "activated")
    assert ctx.distribuciones.filas[1].estado_distribucion == "COMPLETADA"


def test_rollback_detiene_la_distribucion_y_no_avisa_a_las_fases_siguientes():
    ctx, (canary, *_) = _distribuida()
    resultado = ctx.reportar(canary, "rollback", motivo="modelo no carga")
    assert resultado.evento_rf73 == "DISTRIBUCION_FALLIDA"
    fila = ctx.despliegues.filas[canary]
    assert (fila.estado_despliegue, fila.rollback_ejecutado, fila.motivo_fallo) == ("FALLIDO", True, "modelo no carga")
    assert ctx.distribuciones.filas[1].estado_distribucion == "DETENIDA"
    assert len(ctx.broker.avisos) == 1


def test_critical_failure_por_hash_marca_el_hash_invalido():
    ctx, (canary, *_) = _distribuida()
    resultado = ctx.reportar(canary, "critical_failure", causa="HASH_INVALIDO")
    assert resultado.evento_rf73 == "DISTRIBUCION_FALLIDA"
    assert ctx.auditoria.eventos[0]["severidad_evento"] == "CRITICAL"
    assert ctx.despliegues.filas[canary].resultado_validacion_hash is False


def test_status_pospuesto_emite_distribucion_pospuesta_y_vuelve_a_pendiente():
    ctx, (canary, *_) = _distribuida()
    ctx.reportar(canary, "download_progress", bytes_descargados=1024, intento=1)
    resultado = ctx.reportar(canary, "status", pospuesto=True, motivo="batería 12 % < 30 %")
    assert resultado.evento_rf73 == "DISTRIBUCION_POSPUESTA"
    fila = ctx.despliegues.filas[canary]
    assert (fila.estado_despliegue, fila.tamano_descargado_bytes, fila.motivo_fallo) == ("PENDIENTE", 1024, "batería 12 % < 30 %")


def test_download_progress_pasa_a_en_proceso_sin_evento():
    ctx, (canary, *_) = _distribuida()
    resultado = ctx.reportar(canary, "download_progress", bytes_descargados=4096, intento=2, nivel_bateria=81.5)
    fila = ctx.despliegues.filas[canary]
    assert resultado.evento_rf73 is None and fila.estado_despliegue == "EN_PROCESO"
    assert (fila.tamano_descargado_bytes, fila.intentos_descarga, fila.nivel_bateria_al_inicio) == (4096, 2, Decimal("81.5"))


def test_un_nodo_no_puede_reportar_por_el_despliegue_de_otro():
    ctx, (canary, *_) = _distribuida()
    with pytest.raises(AuthorizationError):
        ctx.reportar(canary, "activated", serial="EDGE-99")


def test_reporte_repetido_sobre_un_despliegue_terminado_no_cambia_nada():
    ctx, (canary, *_) = _distribuida()
    ctx.reportar(canary, "activated")
    eventos = len(ctx.auditoria.eventos)
    resultado = ctx.reportar(canary, "rollback")
    assert resultado.sin_cambios and ctx.despliegues.filas[canary].estado_despliegue == "EXITOSO"
    assert len(ctx.auditoria.eventos) == eventos


# ── URL firmada y descarga con Range ───────────────────────────────────────

@pytest.fixture
def url_hmac(monkeypatch):
    monkeypatch.setenv("OTA_URL_SECRET", "clave-de-prueba")
    monkeypatch.setenv("OTA_URL_BASE", "https://api.sgpmp/api/")
    return UrlDescargaHmacAdapter()


def test_url_firmada_vence_y_no_admite_otra_firma_ni_otro_despliegue(url_hmac):
    ahora = datetime.now(timezone.utc)
    url = url_hmac.generar(101, ahora + timedelta(hours=1))
    assert url.startswith("https://api.sgpmp/api/prediccion/ota/artefactos/101?expira=")
    expira = int((ahora + timedelta(hours=1)).timestamp())
    firma = url.rsplit("firma=", 1)[1]
    assert url_hmac.es_valida(101, expira, firma, ahora)
    assert not url_hmac.es_valida(102, expira, firma, ahora)
    assert not url_hmac.es_valida(101, expira + 1, firma, ahora)
    assert not url_hmac.es_valida(101, expira, firma, ahora + timedelta(hours=2))


def test_descarga_por_url_firmada_admite_range(tmp_path, monkeypatch, url_hmac):
    from src.prediction.infrastructure.routers import ota_router as router_mod
    from src.shared.database import get_db_sistema
    from src.shared.error_handlers import register_error_handlers

    (tmp_path / "aves").mkdir()
    (tmp_path / "aves" / "detector_v3.tflite").write_bytes(bytes(range(256)) * 8)
    monkeypatch.setenv("OTA_ARTEFACTOS_DIR", str(tmp_path))
    ctx, (canary, *_) = _distribuida(1)
    monkeypatch.setattr(router_mod, "SqlAlchemyDespliegueOtaRepository", lambda db: ctx.despliegues)
    monkeypatch.setattr(router_mod, "SqlAlchemyVersionModeloRepository", lambda db: ctx.versiones)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_mod.router)
    app.dependency_overrides[get_db_sistema] = lambda: _Db()
    client = TestClient(app)

    url = url_hmac.generar(canary, datetime.now(timezone.utc) + timedelta(hours=1)).replace("https://api.sgpmp/api", "")
    completo = client.get(url)
    assert completo.status_code == 200 and len(completo.content) == 2048
    parcial = client.get(url, headers={"Range": "bytes=1024-1535"})
    assert parcial.status_code == 206 and parcial.content == (bytes(range(256)) * 8)[1024:1536]
    assert client.get(url.replace("firma=", "firma=0")[:-1]).status_code == 401


def test_el_artefacto_no_puede_salir_del_directorio(tmp_path):
    ctx = _Ctx(versiones=[_version(ruta="../../etc/passwd")])
    canary = ctx.crear().despliegues[0]
    with pytest.raises(NotFoundError):
        ObtenerArtefactoOtaUseCase(
            despliegue_repo=ctx.despliegues, version_repo=ctx.versiones, url_port=_Url(), directorio_artefactos=str(tmp_path),
        ).execute(canary.id_despliegue_ota, 0, "x")


def test_sirve_el_artefacto_que_rf69_guardo_con_ruta_absoluta_en_el_almacen(tmp_path, monkeypatch):
    monkeypatch.delenv("OTA_ARTEFACTOS_DIR", raising=False)
    monkeypatch.setenv("MODELOS_STORAGE_PATH", str(tmp_path))
    artefacto = tmp_path / "proceso_MODELO_AVES.tflite"
    artefacto.write_bytes(b"modelo")
    ctx = _Ctx(versiones=[_version(ruta=str(artefacto))])
    canary = ctx.crear().despliegues[0]
    servido = ObtenerArtefactoOtaUseCase(
        despliegue_repo=ctx.despliegues, version_repo=ctx.versiones, url_port=_Url(),
    ).execute(canary.id_despliegue_ota, 0, "x")
    assert servido == artefacto.resolve()


def test_url_invalida_es_401():
    class _Rechaza(_Url):
        def es_valida(self, *a): return False
    with pytest.raises(AuthenticationError):
        ObtenerArtefactoOtaUseCase(despliegue_repo=_Despliegues(), version_repo=_Versiones(), url_port=_Rechaza()).execute(1, 0, "x")
