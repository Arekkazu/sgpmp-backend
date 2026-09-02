"""Pruebas unitarias de la cola asíncrona de exportaciones de auditoría RF-10."""
from datetime import datetime, timezone

import pytest

from src.identity_access.application.use_cases.auditoria.exportacion_async_use_cases import (
    ConsultarExportacionAuditoriaUseCase,
    DescargarExportacionAuditoriaUseCase,
    ProcesarColaExportacionesUseCase,
    SolicitarExportacionAuditoriaUseCase,
    deserializar_filtros,
    serializar_filtros,
)
from src.identity_access.domain.entities.exportacion_auditoria import (
    ConfiguracionExportacion,
    EstadoExportacion,
    ResultadoExportacion,
    TrabajoExportacion,
)
from src.identity_access.domain.value_objects.evento_categoria import EventoCategoria
from src.shared.errors import BusinessRuleError, NotFoundError, TooManyRequestsError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class ColaRepoFake:
    def __init__(
        self,
        activos: int = 0,
        config: ConfiguracionExportacion | None = None,
        pendiente: TrabajoExportacion | None = None,
        trabajo: TrabajoExportacion | None = None,
        resultado: ResultadoExportacion | None = None,
    ) -> None:
        self.activos = activos
        self.config = config or ConfiguracionExportacion()
        self.pendiente = pendiente
        self.trabajo = trabajo
        self.resultado = resultado
        self.encolados: list[TrabajoExportacion] = []
        self.completados: list[tuple[int, ResultadoExportacion]] = []
        self.fallidos: list[tuple[int, str, bool]] = []

    def obtener_configuracion(self) -> ConfiguracionExportacion:
        return self.config

    def contar_activos(self) -> int:
        return self.activos

    def encolar(self, trabajo: TrabajoExportacion) -> TrabajoExportacion:
        trabajo.id_cola = 1
        self.encolados.append(trabajo)
        return trabajo

    def obtener(self, id_cola: int):
        return self.trabajo

    def tomar_pendiente(self):
        pendiente, self.pendiente = self.pendiente, None
        return pendiente

    def completar(self, id_cola: int, resultado: ResultadoExportacion) -> None:
        self.completados.append((id_cola, resultado))

    def fallar(self, id_cola: int, error: str, reintentable: bool) -> None:
        self.fallidos.append((id_cola, error, reintentable))

    def obtener_resultado(self, id_cola: int):
        return self.resultado


class ExportarUseCaseFake:
    def __init__(self, lineas=None, error: Exception | None = None) -> None:
        self.lineas = lineas or ["cabecera\r\n", "fila\r\n"]
        self.error = error
        self.filtros_recibidos: dict | None = None

    def execute(self, usuario_actual, **filtros):
        self.filtros_recibidos = filtros
        if self.error:
            raise self.error
        return iter(self.lineas), 12000, 10000


def _trabajo(**overrides) -> TrabajoExportacion:
    base = dict(
        id_cola=1,
        parametros={"archivados": False},
        id_usuario_solicitante=7,
        estado=EstadoExportacion.PENDIENTE.value,
        intentos=1,
    )
    base.update(overrides)
    return TrabajoExportacion(**base)


# ── Solicitar ────────────────────────────────────────────────────────────────

def test_encolar_deja_el_trabajo_pendiente_y_commitea() -> None:
    repo = ColaRepoFake()
    db = DbFake()

    trabajo = SolicitarExportacionAuditoriaUseCase(db=db, cola_repo=repo).execute(
        filtros={"id_usuario": 7, "categoria": EventoCategoria.CONSULTA},
        id_usuario=7,
    )

    assert trabajo.estado == EstadoExportacion.PENDIENTE.value
    assert db.commits == 1
    assert repo.encolados[0].parametros["categoria"] == "CONSULTA"


def test_demasiadas_exportaciones_simultaneas_se_rechazan() -> None:
    repo = ColaRepoFake(activos=3, config=ConfiguracionExportacion(limite_concurrencia=3))

    with pytest.raises(TooManyRequestsError) as excinfo:
        SolicitarExportacionAuditoriaUseCase(db=DbFake(), cola_repo=repo).execute(
            filtros={}, id_usuario=7
        )

    assert excinfo.value.code == "LIMITE_EXPORTACIONES_EXCEDIDO"


# ── Consultar y descargar ────────────────────────────────────────────────────

def test_consultar_un_trabajo_inexistente_es_404() -> None:
    with pytest.raises(NotFoundError) as excinfo:
        ConsultarExportacionAuditoriaUseCase(cola_repo=ColaRepoFake()).execute(99)

    assert excinfo.value.code == "EXPORTACION_NO_ENCONTRADA"


def test_no_se_puede_descargar_un_trabajo_que_sigue_en_proceso() -> None:
    repo = ColaRepoFake(trabajo=_trabajo(estado=EstadoExportacion.EN_PROCESO.value))

    with pytest.raises(BusinessRuleError) as excinfo:
        DescargarExportacionAuditoriaUseCase(cola_repo=repo).execute(1)

    assert excinfo.value.code == "EXPORTACION_NO_DISPONIBLE"


def test_descargar_un_trabajo_completado_entrega_el_csv() -> None:
    repo = ColaRepoFake(
        trabajo=_trabajo(estado=EstadoExportacion.COMPLETADO.value),
        resultado=ResultadoExportacion("﻿ID,Usuario\r\n", "auditoria.csv", 5, 5),
    )

    resultado = DescargarExportacionAuditoriaUseCase(cola_repo=repo).execute(1)

    assert resultado.contenido_csv.startswith("﻿")
    assert resultado.nombre_archivo == "auditoria.csv"


# ── Worker ───────────────────────────────────────────────────────────────────

def test_el_worker_genera_el_csv_y_marca_el_trabajo_completado() -> None:
    repo = ColaRepoFake(pendiente=_trabajo())
    db = DbFake()
    exportar = ExportarUseCaseFake()

    procesados = ProcesarColaExportacionesUseCase(
        db=db, cola_repo=repo, exportar_use_case=exportar
    ).ejecutar()

    assert procesados == 1
    id_cola, resultado = repo.completados[0]
    assert id_cola == 1
    assert resultado.contenido_csv == "cabecera\r\nfila\r\n"
    assert resultado.total_exportado == 10000


def test_el_worker_no_aplica_el_tope_sincrono() -> None:
    """Nadie está esperando del otro lado: el corte de 422 no tiene sentido aquí."""
    repo = ColaRepoFake(pendiente=_trabajo())
    exportar = ExportarUseCaseFake()

    ProcesarColaExportacionesUseCase(
        db=DbFake(), cola_repo=repo, exportar_use_case=exportar
    ).ejecutar()

    assert "umbral_async" not in exportar.filtros_recibidos


def test_un_fallo_con_reintentos_disponibles_devuelve_el_trabajo_a_la_cola() -> None:
    repo = ColaRepoFake(
        pendiente=_trabajo(intentos=1),
        config=ConfiguracionExportacion(max_reintentos=3),
    )
    exportar = ExportarUseCaseFake(error=RuntimeError("db caída"))

    procesados = ProcesarColaExportacionesUseCase(
        db=DbFake(), cola_repo=repo, exportar_use_case=exportar
    ).ejecutar()

    assert procesados == 0
    _, error, reintentable = repo.fallidos[0]
    assert "db caída" in error
    assert reintentable is True


def test_agotados_los_reintentos_el_trabajo_queda_fallido() -> None:
    repo = ColaRepoFake(
        pendiente=_trabajo(intentos=3),
        config=ConfiguracionExportacion(max_reintentos=3),
    )
    exportar = ExportarUseCaseFake(error=RuntimeError("db caída"))

    ProcesarColaExportacionesUseCase(
        db=DbFake(), cola_repo=repo, exportar_use_case=exportar
    ).ejecutar()

    assert repo.fallidos[0][2] is False


def test_la_configuracion_desactivada_detiene_el_worker() -> None:
    repo = ColaRepoFake(
        pendiente=_trabajo(), config=ConfiguracionExportacion(es_activo=False)
    )

    procesados = ProcesarColaExportacionesUseCase(
        db=DbFake(), cola_repo=repo, exportar_use_case=ExportarUseCaseFake()
    ).ejecutar()

    assert procesados == 0
    assert repo.completados == []


# ── Serialización de filtros ─────────────────────────────────────────────────

def test_los_filtros_sobreviven_el_viaje_por_la_cola() -> None:
    """Se guardan como JSON y vuelven tipados; si se pierde algo, el archivo sale mal."""
    originales = {
        "id_usuario": 7,
        "tipo_evento": 16,
        "categoria": EventoCategoria.CONSULTA,
        "fecha_desde": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "fecha_hasta": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "archivados": True,
    }

    recuperados = deserializar_filtros(serializar_filtros(originales))

    assert recuperados == originales
