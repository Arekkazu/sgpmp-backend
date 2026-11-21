"""Suite automatizada TC-M05-G18 (RF-76): Integracion con RF-44 y fallas de persistencia.

Cubre:
- S1 (plano 043 / orig 011): job diario `_revertir_retiros_vencidos_diariamente`
  (dos tratamientos vencido + vigente manana, vencimiento limite hoy, y
  notificacion de fin de retiro a Productor + Veterinario).
- S2 (plano 044 / orig 012): falla de RF-44 al transicionar a EN_TRATAMIENTO
  (RF-76 E10: HTTP 500, error_code no vacio, mensaje de reversion, rollback
  completo, sin registro, activo sin cambio y sin notificacion).
- S3 (plano 047 / orig 042): falla en calculo de `fecha_fin_retiro`, falla real
  de BD pasando por `db_error_translator.raise_from_db_error`, y verificacion
  estricta de incidente en auditoria sobreviviente al rollback (CU03 FA-13).
- R  (control real en TEST): camino feliz en sandbox con `periodo_retiro_dias=0`
  (fecha hoy y D-6) e inocuidad total tras rollback.

Nota de alcance RBAC: los tests en proceso (S2 y S3) inyectan un `UsuarioActual`
Veterinario activo (`id_rol=3`, `id_estado_cuenta=1`) con permiso `(48, 1)` sobre
`medicamentos`, porque la autorizacion por roles esta fuera del alcance de G18 y
ya fue verificada en TEST durante la Fase 1 (hallazgo B1).
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
import json
import os
from pathlib import Path
import smtplib
from types import SimpleNamespace
from typing import Any, Callable, Iterator, Optional
import uuid

from dotenv import dotenv_values
from fastapi.testclient import TestClient
import psycopg2
import pytest
import requests
import sqlalchemy
from sqlalchemy.exc import OperationalError

# Asignacion explicita antes de importar `main` / `database.py` (C2).
os.environ["SECRET_KEY"] = "test-secret-key-1234567890123456"
os.environ["DATABASE_URL"] = "postgresql://stub:stub@localhost:5432/stub_g18"
os.environ["ENV"] = "test"

import main
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
import src.shared.database as shared_database
import src.shared.fechas as shared_fechas
import src.shared.rbac as shared_rbac
import src.supplies.application.use_cases.suministros.registrar_medicamento_use_case as reg_med_uc_mod
import src.supplies.application.use_cases.suministros.revertir_retiros_vencidos_use_case as rev_uc_mod
from src.supplies.domain.entities.medicamento import Medicamento
from src.supplies.domain.repositories.activo_consulta_port import (
    ESTADO_ACTIVO,
    ESTADO_EN_TRATAMIENTO,
    ActivoConsulta,
)
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbierto
from src.supplies.domain.value_objects.estado_registro import EstadoRegistro
import src.supplies.infrastructure.adapters.activo_m02_adapter as activo_m02_mod
import src.supplies.infrastructure.adapters.estado_activo_m02_adapter as estado_activo_m02_mod
import src.supplies.infrastructure.adapters.notificacion_medicamento_email_adapter as notif_email_mod
import src.supplies.infrastructure.factories.suministros_factory as suministros_factory
import src.supplies.infrastructure.repositories.medicamento_repository as med_repo_mod
from src.supplies.infrastructure.repositories.medicamento_repository import (
    SqlAlchemyMedicamentoRepository,
)

# Referencias originales capturadas en el import para `dependency_overrides` y guards (C1).
_GET_DB_ORIGINAL = shared_database.get_db
_GET_CURRENT_USER_ORIGINAL = get_current_user
_SESION_SISTEMA_ORIGINAL = shared_database.sesion_sistema
_SESSION_LOCAL_ORIGINAL = shared_database.SessionLocal
_CREATE_ENGINE_ORIGINAL = sqlalchemy.create_engine

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        _ZONA_BOGOTA = ZoneInfo("America/Bogota")
    except ZoneInfoNotFoundError:
        from datetime import timezone
        _ZONA_BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")
except ImportError:
    from datetime import timezone
    _ZONA_BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")


ACTIVO_ID_PRUEBA = 853
CICLO_ID_PRUEBA = 5
FECHA_INICIO_CICLO = date(2026, 10, 22)
FECHA_SIMULADA_S1 = date(2026, 11, 10)
VET_USER_ID = 301
PRODUCTOR_CORREO = "productor.g18@finca.example"
VET_CORREO = "veterinario.g18@finca.example"

_TEXTOS_PROHIBIDOS_RESPUESTA = (
    "Traceback",
    "OverflowError",
    "RuntimeError",
    "psycopg2",
    "OperationalError",
    "INSERT INTO",
)

# Registro de guards disparados por prueba (C3). Se limpia al entrar y salir del fixture autouse.
_VIOLACIONES: list[str] = []


# ---------------------------------------------------------------------------
# Trazas estructuradas en $G18_RUN_DIR (C7: estados "OK" / "FALLA")
# ---------------------------------------------------------------------------

def _sanitizar_texto(texto: str) -> str:
    s = texto
    for k in ("TEST_ADMIN_PASSWORD", "TEST_SANDBOX_SECRET", "TEST_ADMIN_EMAIL"):
        v = (os.environ.get(k) or "").strip()
        if v:
            s = s.replace(v, "***")
    jwt_pref = "ey" + "J"
    if jwt_pref in s:
        s = s.replace(jwt_pref, "[JWT_OMITIDO]")
    return s


def _registrar_traza(
    *,
    test_id: str,
    caso_plano: str,
    caso_original: str,
    esperado: str,
    obtenido: str,
    estado: str,
) -> None:
    """Agrega una traza estructurada al archivo JSON de la corrida si G18_RUN_DIR esta definido."""
    assert estado in ("OK", "FALLA"), f"Estado de traza invalido: {estado}"
    run_dir = (os.getenv("G18_RUN_DIR") or "").strip()
    if not run_dir:
        return
    ruta = Path(run_dir) / "trazas_tc_m05_g18.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    registros: list[dict[str, Any]] = []
    if ruta.exists():
        try:
            data = json.loads(ruta.read_text(encoding="utf-8"))
            if isinstance(data, list):
                registros = data
        except (ValueError, OSError):
            registros = []
    registros = [r for r in registros if r.get("test") != test_id]
    registros.append(
        {
            "test": test_id,
            "caso_plano": caso_plano,
            "caso_original": caso_original,
            "esperado": esperado,
            "obtenido": _sanitizar_texto(obtenido),
            "estado": estado,
            "timestamp": datetime.now(_ZONA_BOGOTA).isoformat(),
        }
    )
    ruta.write_text(json.dumps(registros, indent=2, ensure_ascii=False), encoding="utf-8")


def _ejecutar_con_traza(
    *,
    test_id: str,
    caso_plano: str,
    caso_original: str,
    esperado: str,
    fn: Callable[[], str],
) -> None:
    """Ejecuta un checkpoint completo y registra OK o FALLA ante cualquier Exception."""
    try:
        obtenido = fn()
    except Exception as exc:
        _registrar_traza(
            test_id=test_id,
            caso_plano=caso_plano,
            caso_original=caso_original,
            esperado=esperado,
            obtenido=f"{type(exc).__name__}: {exc}",
            estado="FALLA",
        )
        raise
    _registrar_traza(
        test_id=test_id,
        caso_plano=caso_plano,
        caso_original=caso_original,
        esperado=esperado,
        obtenido=str(obtenido),
        estado="OK",
    )


def _assert_sin_violaciones_guard() -> None:
    assert _VIOLACIONES == [], f"INFRA: guard activado: {_VIOLACIONES}"


def _assert_sin_fugas_en_respuesta(resp: Any) -> None:
    texto = resp.text or ""
    presentes = [p for p in _TEXTOS_PROHIBIDOS_RESPUESTA if p in texto]
    assert not presentes, f"La respuesta expuso detalles internos prohibidos {presentes}: {texto[:300]}"


# ---------------------------------------------------------------------------
# Guards globales para pruebas en proceso (SMTP, BD real y scheduler lifespan)
# ---------------------------------------------------------------------------

def _prohibido_smtp(*_args: Any, **_kwargs: Any) -> None:
    _VIOLACIONES.append("smtplib.SMTP")
    raise AssertionError("smtplib.SMTP/SMTP_SSL esta prohibido en pruebas en proceso de TC-M05-G18.")


def _prohibido_smtp_ssl(*_args: Any, **_kwargs: Any) -> None:
    _VIOLACIONES.append("smtplib.SMTP_SSL")
    raise AssertionError("smtplib.SMTP/SMTP_SSL esta prohibido en pruebas en proceso de TC-M05-G18.")


def _fabricar_prohibicion_bd(nombre: str) -> Callable[..., Any]:
    def _prohibido(*_args: Any, **_kwargs: Any) -> None:
        _VIOLACIONES.append(nombre)
        raise AssertionError(f"Fabrica/funcion prohibida en pruebas en proceso: {nombre}")
    return _prohibido


@asynccontextmanager
async def _lifespan_neutralizado(_app: Any):
    """Lifespan vacio para evitar migraciones y tareas programadas en TestClient."""
    yield


@pytest.fixture(autouse=True)
def _proteger_entorno_en_proceso(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Aisla todas las pruebas en proceso de SMTP real, BD real y scheduler de FastAPI."""
    _VIOLACIONES.clear()
    main.app.dependency_overrides.clear()
    if "sandbox_real" in request.keywords:
        yield
        main.app.dependency_overrides.clear()
        _VIOLACIONES.clear()
        return

    monkeypatch.setattr(smtplib, "SMTP", _prohibido_smtp)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _prohibido_smtp_ssl)
    monkeypatch.setattr(sqlalchemy, "create_engine", _fabricar_prohibicion_bd("sqlalchemy.create_engine"))
    monkeypatch.setattr(shared_database, "SessionLocal", _fabricar_prohibicion_bd("SessionLocal"))
    monkeypatch.setattr(shared_database, "sesion_sistema", _fabricar_prohibicion_bd("sesion_sistema"))
    monkeypatch.setattr(shared_database, "get_db", _fabricar_prohibicion_bd("get_db"))

    monkeypatch.setattr(main, "lifespan", _lifespan_neutralizado)
    monkeypatch.setattr(main.app.router, "lifespan_context", _lifespan_neutralizado)
    monkeypatch.setattr(main, "verificar_migraciones_aplicadas", _fabricar_prohibicion_bd("verificar_migraciones"))
    monkeypatch.setattr(main, "verificar_token_configurado", _fabricar_prohibicion_bd("verificar_token"))

    yield
    main.app.dependency_overrides.clear()
    _VIOLACIONES.clear()


# ---------------------------------------------------------------------------
# Dobles en memoria para S1, S2 y S3
# ---------------------------------------------------------------------------

@dataclass
class _FakeStore:
    activo_id: int = ACTIVO_ID_PRUEBA
    activo_estado: int = ESTADO_ACTIVO
    medicamentos_persistidos: list[Medicamento] = field(default_factory=list)
    auditorias_persistidas: list[dict[str, Any]] = field(default_factory=list)
    revert_calls: list[dict[str, Any]] = field(default_factory=list)
    marcar_calls: list[dict[str, Any]] = field(default_factory=list)
    notificaciones_inicio: list[dict[str, Any]] = field(default_factory=list)
    correos_enviados: list[dict[str, Any]] = field(default_factory=list)
    listar_en_tratamiento_calls: int = 0
    obtener_tratamiento_vigente_calls: int = 0
    activo_obtener_calls: int = 0
    ciclo_obtener_abierto_calls: int = 0
    timedelta_calls: int = 0
    commit_calls: int = 0
    rollback_calls: int = 0
    sessions_opened: list["_FakeSession"] = field(default_factory=list)
    next_med_id: int = 9001


class _FakeExecuteResult:
    def __init__(self, row: Any) -> None:
        self._row = row

    def fetchone(self) -> Any:
        return self._row


def _es_objeto_auditoria(obj: Any) -> bool:
    nombre_cls = type(obj).__name__.lower()
    tabla = str(getattr(obj, "__tablename__", "") or "").lower()
    return ("auditoria" in nombre_cls or "incidente" in nombre_cls
            or "auditoria" in tabla or "incidente" in tabla)


def _es_insert_auditoria_sql(sql: str) -> bool:
    sql_norm = " ".join(sql.upper().split())
    return "INSERT INTO" in sql_norm and ("AUDITORIA" in sql_norm or "INCIDENTE" in sql_norm)


class _FakeSession:
    """Sesion de BD doble en memoria con staging transaccional atomico y rollback real."""

    def __init__(
        self,
        store: _FakeStore,
        *,
        flush_error: Optional[Exception] = None,
        es_sesion_peticion: bool = True,
    ) -> None:
        self.store = store
        self.flush_error = flush_error
        self.es_sesion_peticion = es_sesion_peticion
        self.info: dict[str, Any] = {}
        self.staged_meds: list[Medicamento] = []
        self.staged_estado: Optional[int] = None
        self.staged_audits: list[dict[str, Any]] = []
        self.staged_orm: list[Any] = []
        self.flush_calls: int = 0
        self.commits: int = 0
        self.rollbacks: int = 0
        self.closed: bool = False
        store.sessions_opened.append(self)

    def add(self, obj: Any) -> None:
        self.staged_orm.append(obj)
        if _es_objeto_auditoria(obj):
            self.staged_audits.append({"origen": "add", "model": type(obj).__name__, "obj": obj})

    def flush(self) -> None:
        self.flush_calls += 1
        if self.flush_error is not None:
            raise self.flush_error

    def refresh(self, _obj: Any) -> None:
        return None

    def in_transaction(self) -> bool:
        return bool(self.staged_meds or self.staged_estado is not None or self.staged_audits or self.staged_orm)

    def commit(self) -> None:
        self.commits += 1
        self.store.commit_calls += 1
        if self.staged_meds:
            self.store.medicamentos_persistidos.extend(self.staged_meds)
            self.staged_meds.clear()
        if self.staged_estado is not None:
            self.store.activo_estado = self.staged_estado
            self.staged_estado = None
        if self.staged_audits:
            # Solo cuentan incidentes confirmados en una sesion distinta a la de la peticion (C9).
            if not self.es_sesion_peticion:
                self.store.auditorias_persistidas.extend(self.staged_audits)
            self.staged_audits.clear()
        self.staged_orm.clear()

    def rollback(self) -> None:
        self.rollbacks += 1
        self.store.rollback_calls += 1
        self.staged_meds.clear()
        self.staged_estado = None
        self.staged_audits.clear()
        self.staged_orm.clear()

    def close(self) -> None:
        self.closed = True

    def execute(self, stmt: Any, _params: Optional[dict[str, Any]] = None) -> _FakeExecuteResult:
        sql = str(stmt)
        if _es_insert_auditoria_sql(sql):
            self.staged_audits.append({"origen": "execute_insert", "sql": sql[:200]})
            return _FakeExecuteResult(None)
        if "modulo2.activos_biologicos" in sql:
            return _FakeExecuteResult(
                SimpleNamespace(nombre="Carlos", apellidos="Productor", correo_electronico=PRODUCTOR_CORREO)
            )
        if "modulo1.usuarios" in sql:
            return _FakeExecuteResult(
                SimpleNamespace(nombre="Dra. Ana", apellidos="Veterinaria", correo_electronico=VET_CORREO)
            )
        return _FakeExecuteResult(None)


def _crear_medicamento_valido(
    *,
    id_reg: int,
    fecha_aplicacion: date,
    periodo_retiro_dias: int,
    fecha_fin_retiro: Optional[date],
    id_usuario: int = VET_USER_ID,
    id_usuario_veterinario: Optional[int] = VET_USER_ID,
) -> Medicamento:
    return Medicamento(
        id_registro_medicamento=id_reg,
        id_activo_biologico=ACTIVO_ID_PRUEBA,
        nombre_medicamento=f"Oxitetraciclina-{id_reg}",
        descripcion_clinica="Tratamiento de control RF-76 G18",
        unidad_dosis="ml",
        cantidad=5,
        fecha_aplicacion=fecha_aplicacion,
        costo_unitario_medicamento=2500,
        motivo_aplicacion="Tratamiento de control RF-76 G18",
        nombre_veterinario="Dra. Ana Veterinaria",
        id_usuario=id_usuario,
        via_aplicacion="IM",
        estado_registro=EstadoRegistro.VALIDADO.value,
        hora_aplicacion=time(9, 0),
        periodo_retiro_dias=periodo_retiro_dias,
        fecha_fin_retiro=fecha_fin_retiro,
        id_usuario_veterinario=id_usuario_veterinario,
    )


class _FakeAsyncioEnMain:
    """Proxy asyncio para ejecutar exactamente una iteracion del while True de S1."""

    def __init__(self) -> None:
        self.sleeps: list[float] = []
        self._real = asyncio

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        if len(self.sleeps) == 1:
            return None
        raise asyncio.CancelledError("fin_ciclo_unico_s1")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class _FakeDateTimeMain(datetime):
    """Hereda de `datetime` y fija `now(tz)` a las 02:59 del dia simulado para S1 (C6)."""

    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        base = datetime(FECHA_SIMULADA_S1.year, FECHA_SIMULADA_S1.month, FECHA_SIMULADA_S1.day, 2, 59, 0)
        return base.replace(tzinfo=tz) if tz is not None else base


def _ejecutar_scheduler_s1_con_dobles(store: _FakeStore, monkeypatch: pytest.MonkeyPatch) -> _FakeAsyncioEnMain:
    """Invoca directamente `main._revertir_retiros_vencidos_diariamente` una sola iteracion."""
    fake_asyncio = _FakeAsyncioEnMain()
    orig_rev_cls = rev_uc_mod.RevertirRetirosVencidosUseCase

    class _ActivoAdapterS1:
        def __init__(self, _db: Any) -> None:
            pass

        def listar_en_tratamiento(self) -> list[int]:
            store.listar_en_tratamiento_calls += 1
            return [store.activo_id] if store.activo_estado == ESTADO_EN_TRATAMIENTO else []

    class _MedicamentoRepoS1:
        def __init__(self, _db: Any) -> None:
            pass

        def obtener_tratamiento_vigente(self, id_activo: int) -> Optional[Medicamento]:
            store.obtener_tratamiento_vigente_calls += 1
            candidatos = [
                m for m in store.medicamentos_persistidos
                if m.id_activo_biologico == id_activo
                and m.estado_registro == EstadoRegistro.VALIDADO.value
                and m.fecha_fin_retiro is not None
            ]
            if not candidatos:
                return None
            candidatos.sort(key=lambda m: m.fecha_fin_retiro, reverse=True)
            return candidatos[0]

    class _EstadoAdapterS1:
        def __init__(self, db: _FakeSession) -> None:
            self.db = db

        def revertir_a_activo(self, *, id_activo: int, id_usuario: int, motivo: str) -> None:
            store.revert_calls.append({"id_activo": id_activo, "id_usuario": id_usuario, "motivo": motivo})
            self.db.staged_estado = ESTADO_ACTIVO

    class _UseCaseS1ConSesionFalsa(orig_rev_cls):
        def __init__(self, _session_factory: Any) -> None:
            # C5: acepta la factory sin compararla ni invocarla.
            super().__init__(session_factory=lambda: _FakeSession(store, es_sesion_peticion=False))

    def _spy_send_email(*, to: str, subject: str, html_body: str) -> None:
        store.correos_enviados.append({"to": to, "subject": subject, "html_body": html_body})

    # Parcheo exactamente en los modulos donde se buscan los simbolos (C4):
    # - `main` busca asyncio, datetime e importa RevertirRetirosVencidosUseCase desde `rev_uc_mod`.
    monkeypatch.setattr(main, "asyncio", fake_asyncio)
    monkeypatch.setattr(main, "datetime", _FakeDateTimeMain)
    monkeypatch.setattr(shared_fechas, "hoy_usuario", lambda: FECHA_SIMULADA_S1)
    monkeypatch.setattr(rev_uc_mod, "hoy_usuario", lambda: FECHA_SIMULADA_S1)
    monkeypatch.setattr(rev_uc_mod, "RevertirRetirosVencidosUseCase", _UseCaseS1ConSesionFalsa)
    # - `rev_uc_mod` importa ActivoM02Adapter, SqlAlchemyMedicamentoRepository, EstadoActivoM02Adapter
    #   localmente desde sus modulos definidores (`revertir_retiros_vencidos_use_case.py:38,54-57`).
    monkeypatch.setattr(activo_m02_mod, "ActivoM02Adapter", _ActivoAdapterS1)
    monkeypatch.setattr(med_repo_mod, "SqlAlchemyMedicamentoRepository", _MedicamentoRepoS1)
    monkeypatch.setattr(estado_activo_m02_mod, "EstadoActivoM02Adapter", _EstadoAdapterS1)
    # - `notificacion_medicamento_email_adapter.py:24,100` busca `send_email` en `notif_email_mod`.
    monkeypatch.setattr(notif_email_mod, "send_email", _spy_send_email)

    async def _correr() -> None:
        try:
            await main._revertir_retiros_vencidos_diariamente()
        except asyncio.CancelledError:
            pass

    asyncio.run(_correr())
    return fake_asyncio


def _configurar_cliente_api_en_proceso(
    store: _FakeStore,
    monkeypatch: pytest.MonkeyPatch,
    *,
    fallar_rf44: bool = False,
    usar_repo_real_con_flush_error: Optional[Exception] = None,
) -> tuple[TestClient, _FakeSession]:
    """Configura `TestClient(main.app)` usando llaves originales `Depends(...)` para S2 y S3 (C1)."""
    fake_db = _FakeSession(store, flush_error=usar_repo_real_con_flush_error, es_sesion_peticion=True)
    vet = UsuarioActual(
        id_usuario=VET_USER_ID,
        id_token=99,
        id_rol=3,
        id_estado_cuenta=1,
    )

    def _fake_get_db() -> Iterator[_FakeSession]:
        try:
            yield fake_db
        except Exception:
            fake_db.rollback()
            raise
        finally:
            fake_db.close()

    # C1: `medicamento_router.py:65-66` y `rbac.py:105-106` guardaron las referencias originales en `Depends(...)`.
    main.app.dependency_overrides[_GET_DB_ORIGINAL] = _fake_get_db
    main.app.dependency_overrides[_GET_CURRENT_USER_ORIGINAL] = lambda: vet
    # `rbac.py:110` busca `tiene_permiso` en el namespace de `src.shared.rbac`.
    monkeypatch.setattr(
        shared_rbac,
        "tiene_permiso",
        lambda _db, id_rol, id_recurso, id_accion: (id_rol == 3 and id_recurso == 48 and id_accion == 1),
    )

    class _ActivoAdapterStub:
        def __init__(self, _db: Any) -> None:
            pass

        def obtener(self, id_activo: int) -> Optional[ActivoConsulta]:
            store.activo_obtener_calls += 1
            if id_activo != store.activo_id:
                return None
            nombre_estado = "ACTIVO" if store.activo_estado == ESTADO_ACTIVO else "EN_TRATAMIENTO"
            return ActivoConsulta(
                id_activo_biologico=id_activo,
                tipo="INDIVIDUAL",
                id_estado=store.activo_estado,
                nombre_estado=nombre_estado,
                cantidad_actual=1,
                fecha_inicio_ciclo=FECHA_INICIO_CICLO,
            )

    class _CicloAdapterStub:
        def __init__(self, _db: Any) -> None:
            pass

        def obtener_abierto(self, id_activo: int) -> Optional[CicloAbierto]:
            store.ciclo_obtener_abierto_calls += 1
            return CicloAbierto(
                id_ciclo_productivo=CICLO_ID_PRUEBA,
                fecha_inicio=datetime(2026, 10, 22, 0, 0),
                id_gestion_fases=722,
            ) if id_activo == store.activo_id else None

    class _EventoAdapterStub:
        def __init__(self, _db: Any) -> None:
            pass

        def obtener_activo_de_evento(self, _id_evento: int) -> Optional[int]:
            return None

    class _EstadoAdapterStub:
        def __init__(self, db: _FakeSession) -> None:
            self.db = db

        def marcar_en_tratamiento(self, *, id_activo: int, id_usuario: int, motivo: str) -> None:
            store.marcar_calls.append({"id_activo": id_activo, "id_usuario": id_usuario, "motivo": motivo})
            if fallar_rf44:
                raise RuntimeError("Falla simulada de RF-44 al transicionar activo a EN_TRATAMIENTO")
            self.db.staged_estado = ESTADO_EN_TRATAMIENTO

    class _NotificacionAdapterStub:
        def __init__(self, _db: Any) -> None:
            pass

        def notificar_inicio_retiro(
            self,
            *,
            id_activo: int,
            id_usuario_veterinario: Optional[int],
            nombre_medicamento: str,
            fecha_fin_retiro: date,
        ) -> None:
            store.notificaciones_inicio.append(
                {
                    "id_activo": id_activo,
                    "id_usuario_veterinario": id_usuario_veterinario,
                    "nombre_medicamento": nombre_medicamento,
                    "fecha_fin_retiro": fecha_fin_retiro.isoformat(),
                }
            )

    class _RolAdapterStub:
        def __init__(self, _db: Any) -> None:
            pass

        def es_veterinario(self, id_usuario: int) -> bool:
            return id_usuario == VET_USER_ID

    class _RegistroRepoStub:
        def __init__(self, _db: Any) -> None:
            pass

        def obtener_por_origen(self, _tipo: str, _id_origen: int) -> None:
            return None

    class _MovimientoStub:
        def registrar(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    if usar_repo_real_con_flush_error is not None:
        class _RepoRealConDedupeBypass(SqlAlchemyMedicamentoRepository):
            def existe_duplicado_validado(self, **_kwargs: Any) -> bool:
                return False

        monkeypatch.setattr(suministros_factory, "SqlAlchemyMedicamentoRepository", _RepoRealConDedupeBypass)
    else:
        class _MedicamentoRepoStub:
            def __init__(self, db: _FakeSession) -> None:
                self.db = db

            def existe_duplicado_validado(self, **_kwargs: Any) -> bool:
                return False

            def guardar(self, medicamento: Medicamento) -> Medicamento:
                med_id = store.next_med_id
                store.next_med_id += 1
                guardado = Medicamento(
                    id_registro_medicamento=med_id,
                    id_activo_biologico=medicamento.id_activo_biologico,
                    nombre_medicamento=medicamento.nombre_medicamento,
                    descripcion_clinica=medicamento.descripcion_clinica,
                    unidad_dosis=medicamento.unidad_dosis,
                    cantidad=medicamento.cantidad,
                    fecha_aplicacion=medicamento.fecha_aplicacion,
                    costo_unitario_medicamento=medicamento.costo_unitario_medicamento,
                    motivo_aplicacion=medicamento.motivo_aplicacion,
                    nombre_veterinario=medicamento.nombre_veterinario,
                    id_usuario=medicamento.id_usuario,
                    via_aplicacion=medicamento.via_aplicacion,
                    estado_registro=medicamento.estado_registro,
                    hora_aplicacion=medicamento.hora_aplicacion,
                    periodo_retiro_dias=medicamento.periodo_retiro_dias,
                    fecha_fin_retiro=medicamento.fecha_fin_retiro,
                    dosis_por_individuo=medicamento.dosis_por_individuo,
                    id_evento_sanitario=medicamento.id_evento_sanitario,
                    id_usuario_veterinario=medicamento.id_usuario_veterinario,
                )
                self.db.staged_meds.append(guardado)
                return guardado

            def max_fecha_fin_retiro_vigente(self, id_activo: int) -> Optional[date]:
                fechas = [
                    m.fecha_fin_retiro for m in store.medicamentos_persistidos
                    if m.id_activo_biologico == id_activo and m.fecha_fin_retiro is not None
                ]
                return max(fechas) if fechas else None

            def contar_tratamientos_activos(self, id_activo: int, hoy: date) -> int:
                return sum(
                    1 for m in store.medicamentos_persistidos
                    if m.id_activo_biologico == id_activo
                    and m.estado_registro == EstadoRegistro.VALIDADO.value
                    and m.fecha_fin_retiro is not None
                    and m.fecha_fin_retiro >= hoy
                )

        monkeypatch.setattr(suministros_factory, "SqlAlchemyMedicamentoRepository", _MedicamentoRepoStub)

    # `suministros_factory.py:84-96` construye dependencias desde sus propios globals de modulo.
    monkeypatch.setattr(suministros_factory, "ActivoM02Adapter", _ActivoAdapterStub)
    monkeypatch.setattr(suministros_factory, "CicloM02Adapter", _CicloAdapterStub)
    monkeypatch.setattr(suministros_factory, "EventoSanitarioM02Adapter", _EventoAdapterStub)
    monkeypatch.setattr(suministros_factory, "EstadoActivoM02Adapter", _EstadoAdapterStub)
    monkeypatch.setattr(suministros_factory, "NotificacionMedicamentoEmailAdapter", _NotificacionAdapterStub)
    monkeypatch.setattr(suministros_factory, "RolUsuarioM01Adapter", _RolAdapterStub)
    monkeypatch.setattr(suministros_factory, "SqlAlchemyRegistroSuministroRepository", _RegistroRepoStub)
    monkeypatch.setattr(suministros_factory, "build_registrador_movimiento", lambda _db: _MovimientoStub())

    client = TestClient(main.app, raise_server_exceptions=False)
    return client, fake_db


def _payload_valido(*, periodo_retiro_dias: int = 5, fecha_aplicacion: Optional[date] = None) -> dict[str, Any]:
    hoy_bogota = datetime.now(_ZONA_BOGOTA).date()
    fecha = fecha_aplicacion or hoy_bogota
    return {
        "id_activo_biologico": ACTIVO_ID_PRUEBA,
        "nombre_medicamento": "Oxitetraciclina 20%",
        "fecha_aplicacion": fecha.isoformat(),
        "hora_aplicacion": "09:15",
        "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": 5,
        "unidad_dosis": "ml",
        "periodo_retiro_dias": periodo_retiro_dias,
        "motivo_aplicacion": "Control sanitario programado para activo en tratamiento",
        "costo_unitario": 25000,
        "nombre_veterinario": "Dra. Ana Veterinaria",
        "id_evento_sanitario": None,
    }


def _verificar_uso_stubs_api(resp: Any, store: _FakeStore, *, min_calls: int = 1) -> None:
    """C3 + C4: primero valida ausencia de guards, luego descarta 401/403 y exige invocacion de stubs."""
    _assert_sin_violaciones_guard()
    assert resp.status_code not in (401, 403), (
        f"Respuesta inesperada de autenticacion/RBAC HTTP {resp.status_code}: {resp.text[:250]}"
    )
    assert store.activo_obtener_calls >= min_calls, (
        f"El stub de activo.obtener no fue invocado >= {min_calls} veces ({store.activo_obtener_calls})."
    )
    assert store.ciclo_obtener_abierto_calls >= min_calls, (
        f"El stub de ciclo.obtener_abierto no fue invocado >= {min_calls} veces ({store.ciclo_obtener_abierto_calls})."
    )


# ---------------------------------------------------------------------------
# S1 (043 / orig 011): Scheduler diario de reversion de retiros vencidos
# ---------------------------------------------------------------------------

def test_g18_s1_01_dos_tratamientos_vencido_y_vigente_manana_no_revierte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S1.1: con un tratamiento vencido y otro en manana (> hoy), evalua el mayor y no revierte."""
    store = _FakeStore(
        activo_estado=ESTADO_EN_TRATAMIENTO,
        medicamentos_persistidos=[
            _crear_medicamento_valido(
                id_reg=1,
                fecha_aplicacion=FECHA_SIMULADA_S1 - timedelta(days=5),
                periodo_retiro_dias=3,
                fecha_fin_retiro=FECHA_SIMULADA_S1 - timedelta(days=2),
            ),
            _crear_medicamento_valido(
                id_reg=2,
                fecha_aplicacion=FECHA_SIMULADA_S1 - timedelta(days=2),
                periodo_retiro_dias=3,
                fecha_fin_retiro=FECHA_SIMULADA_S1 + timedelta(days=1),
            ),
        ],
    )

    def _verificar() -> str:
        _assert_sin_violaciones_guard()
        fake_asyncio = _ejecutar_scheduler_s1_con_dobles(store, monkeypatch)
        _assert_sin_violaciones_guard()
        assert store.listar_en_tratamiento_calls >= 1, "No se invoco listar_en_tratamiento del doble S1."
        assert store.obtener_tratamiento_vigente_calls >= 1, "No se invoco obtener_tratamiento_vigente del doble S1."
        assert len(fake_asyncio.sleeps) == 2, f"Se esperaba exactamente 1 ejecucion del loop; sleeps={fake_asyncio.sleeps}"
        assert store.revert_calls == [], f"No debio invocar RF-44 cuando hay retiro vigente manana: {store.revert_calls}"
        assert store.activo_estado == ESTADO_EN_TRATAMIENTO, (
            f"El activo debio seguir EN_TRATAMIENTO ({ESTADO_EN_TRATAMIENTO}), obtuvo {store.activo_estado}"
        )
        assert store.correos_enviados == [], f"No debio enviar correos de fin de retiro: {store.correos_enviados}"
        return (
            f"activo_estado={store.activo_estado}, revert_calls=0, "
            f"listar_calls={store.listar_en_tratamiento_calls}, "
            f"vigente_calls={store.obtener_tratamiento_vigente_calls}"
        )

    _ejecutar_con_traza(
        test_id="G18_S1_01",
        caso_plano="043",
        caso_original="011",
        esperado="Con un retiro vencido y max(fecha_fin_retiro)=manana, sigue EN_TRATAMIENTO y RF-44 no se invoca.",
        fn=_verificar,
    )


def test_g18_s1_02_retiro_vence_hoy_invoca_rf44_una_vez_y_revierte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S1.2: cuando el mayor retiro vence hoy (fecha_fin_retiro <= hoy), revierte a ACTIVO via RF-44."""
    store = _FakeStore(
        activo_estado=ESTADO_EN_TRATAMIENTO,
        medicamentos_persistidos=[
            _crear_medicamento_valido(
                id_reg=10,
                fecha_aplicacion=FECHA_SIMULADA_S1 - timedelta(days=7),
                periodo_retiro_dias=4,
                fecha_fin_retiro=FECHA_SIMULADA_S1 - timedelta(days=3),
            ),
            _crear_medicamento_valido(
                id_reg=11,
                fecha_aplicacion=FECHA_SIMULADA_S1 - timedelta(days=3),
                periodo_retiro_dias=3,
                fecha_fin_retiro=FECHA_SIMULADA_S1,
            ),
        ],
    )

    def _verificar() -> str:
        _assert_sin_violaciones_guard()
        fake_asyncio = _ejecutar_scheduler_s1_con_dobles(store, monkeypatch)
        _assert_sin_violaciones_guard()
        assert store.listar_en_tratamiento_calls >= 1, "No se invoco listar_en_tratamiento del doble S1."
        assert store.obtener_tratamiento_vigente_calls >= 1, "No se invoco obtener_tratamiento_vigente del doble S1."
        assert len(fake_asyncio.sleeps) == 2, f"Se esperaba 1 ciclo del scheduler; sleeps={fake_asyncio.sleeps}"
        assert len(store.revert_calls) == 1, f"Se esperaba 1 invocacion a RF-44, obtuvo {store.revert_calls}"
        assert store.revert_calls[0]["id_activo"] == ACTIVO_ID_PRUEBA
        assert store.activo_estado == ESTADO_ACTIVO, (
            f"El activo debio revertir a ACTIVO ({ESTADO_ACTIVO}), obtuvo {store.activo_estado}"
        )
        assert store.commit_calls >= 1 and store.rollback_calls == 0
        return (
            f"activo_estado={store.activo_estado}, revert_calls={len(store.revert_calls)}, "
            f"commits={store.commit_calls}, listar_calls={store.listar_en_tratamiento_calls}"
        )

    _ejecutar_con_traza(
        test_id="G18_S1_02",
        caso_plano="043",
        caso_original="011",
        esperado="Con max(fecha_fin_retiro)=hoy (<= hoy), RF-44 se invoca 1 vez y el activo pasa a ACTIVO.",
        fn=_verificar,
    )


def test_g18_s1_03_fin_retiro_notifica_veterinario_y_productor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S1.3 (RF-76 flujo paso 13): al finalizar retiro debe notificar a Veterinario y Productor."""
    store = _FakeStore(
        activo_estado=ESTADO_EN_TRATAMIENTO,
        medicamentos_persistidos=[
            _crear_medicamento_valido(
                id_reg=20,
                fecha_aplicacion=FECHA_SIMULADA_S1 - timedelta(days=4),
                periodo_retiro_dias=4,
                fecha_fin_retiro=FECHA_SIMULADA_S1,
                id_usuario=VET_USER_ID,
                id_usuario_veterinario=VET_USER_ID,
            ),
        ],
    )

    def _verificar() -> str:
        _assert_sin_violaciones_guard()
        _ejecutar_scheduler_s1_con_dobles(store, monkeypatch)
        _assert_sin_violaciones_guard()
        assert store.listar_en_tratamiento_calls >= 1, "No se invoco listar_en_tratamiento del doble S1."
        assert store.obtener_tratamiento_vigente_calls >= 1, "No se invoco obtener_tratamiento_vigente del doble S1."
        destinatarios = [c["to"] for c in store.correos_enviados]
        assert PRODUCTOR_CORREO in destinatarios, (
            f"Falto notificar al Productor ({PRODUCTOR_CORREO}); destinatarios={destinatarios}"
        )
        assert VET_CORREO in destinatarios, (
            f"Defecto RF-76 paso 13: no se notifico al Veterinario ({VET_CORREO}) al finalizar el retiro; "
            f"solo se envio a destinatarios={destinatarios}"
        )
        return f"destinatarios={destinatarios}"

    _ejecutar_con_traza(
        test_id="G18_S1_03",
        caso_plano="043",
        caso_original="011",
        esperado="Al revertir retiro vencido, NotificacionMedicamentoEmailAdapter envia correo a Productor Y Veterinario.",
        fn=_verificar,
    )


# ---------------------------------------------------------------------------
# S2 (044 / orig 012): Falla de RF-44 al cambiar estado a EN_TRATAMIENTO
# ---------------------------------------------------------------------------

def test_g18_s2_01_falla_rf44_retorna_500_y_mensaje_reversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S2.1 (RF-76 E10): fallo de RF-44 devuelve HTTP 500, error_code no vacio e informa reversion."""
    store = _FakeStore(activo_estado=ESTADO_ACTIVO)
    client, _ = _configurar_cliente_api_en_proceso(store, monkeypatch, fallar_rf44=True)

    def _verificar() -> str:
        _assert_sin_violaciones_guard()
        resp = client.post(
            "/suministros/medicamentos",
            json=_payload_valido(periodo_retiro_dias=5),
            headers={"X-Zona-Horaria": "America/Bogota"},
        )
        _verificar_uso_stubs_api(resp, store)
        _assert_sin_fugas_en_respuesta(resp)
        body = resp.json()
        assert resp.status_code == 500, f"Se esperaba HTTP 500 (E10), obtuvo {resp.status_code}: {body}"
        error_code = (body.get("error_code") or "").strip()
        assert error_code, f"La respuesta 500 debe incluir error_code no vacio: {body}"
        assert "revert" in (body.get("message") or "").lower(), (
            f"El mensaje debe informar reversion de la operacion: {body}"
        )
        return f"http={resp.status_code}, error_code={error_code}"

    _ejecutar_con_traza(
        test_id="G18_S2_01",
        caso_plano="044",
        caso_original="012",
        esperado="HTTP 500 con error_code no vacio y mensaje que informa reversion, sin fugas internas.",
        fn=_verificar,
    )


def test_g18_s2_02_falla_rf44_rollback_sin_registro_persistido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S2.2: fallo de RF-44 ejecuta rollback atomico y no deja ningun registro de medicamento."""
    store = _FakeStore(activo_estado=ESTADO_ACTIVO)
    client, fake_db = _configurar_cliente_api_en_proceso(store, monkeypatch, fallar_rf44=True)

    def _verificar() -> str:
        _assert_sin_violaciones_guard()
        resp = client.post(
            "/suministros/medicamentos",
            json=_payload_valido(periodo_retiro_dias=5),
            headers={"X-Zona-Horaria": "America/Bogota"},
        )
        _verificar_uso_stubs_api(resp, store)
        assert resp.status_code == 500
        assert fake_db.commits == 0 and store.commit_calls == 0, "No debe ocurrir commit cuando falla RF-44"
        assert fake_db.rollbacks >= 1 and store.rollback_calls >= 1, "Debe ejecutarse rollback en BD"
        assert store.medicamentos_persistidos == [] and fake_db.staged_meds == [], (
            f"No debe quedar medicamento persistido ni pendiente: {store.medicamentos_persistidos}"
        )
        return f"rollbacks={fake_db.rollbacks}, commits={fake_db.commits}, persistidos=0"

    _ejecutar_con_traza(
        test_id="G18_S2_02",
        caso_plano="044",
        caso_original="012",
        esperado="Rollback ejecutado (>=1), 0 commits y 0 registros de medicamento persistidos.",
        fn=_verificar,
    )


def test_g18_s2_03_falla_rf44_mantiene_estado_activo_y_sin_notificacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S2.3: fallo de RF-44 deja el activo en ACTIVO y no dispara notificacion de inicio."""
    store = _FakeStore(activo_estado=ESTADO_ACTIVO)
    client, _ = _configurar_cliente_api_en_proceso(store, monkeypatch, fallar_rf44=True)

    def _verificar() -> str:
        _assert_sin_violaciones_guard()
        resp = client.post(
            "/suministros/medicamentos",
            json=_payload_valido(periodo_retiro_dias=5),
            headers={"X-Zona-Horaria": "America/Bogota"},
        )
        _verificar_uso_stubs_api(resp, store)
        assert resp.status_code == 500
        assert len(store.marcar_calls) == 1
        assert store.activo_estado == ESTADO_ACTIVO, (
            f"El activo debio permanecer ACTIVO ({ESTADO_ACTIVO}), obtuvo {store.activo_estado}"
        )
        assert store.notificaciones_inicio == [], (
            f"No debio enviarse notificacion de inicio de retiro tras rollback: {store.notificaciones_inicio}"
        )
        return f"activo_estado={store.activo_estado}, notificaciones_inicio=0"

    _ejecutar_con_traza(
        test_id="G18_S2_03",
        caso_plano="044",
        caso_original="012",
        esperado="Activo permanece ACTIVO (id_estado=1) y 0 notificaciones de inicio enviadas.",
        fn=_verificar,
    )


# ---------------------------------------------------------------------------
# S3 (047 / orig 042): Falla calculo fecha_fin_retiro, BD y auditoria incidente
# ---------------------------------------------------------------------------

def test_g18_s3_01_falla_calculo_fecha_fin_retiro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S3.1: error calculando `fecha_fin_retiro` cancela operacion completa con HTTP 5xx y sin cambios."""
    store = _FakeStore(activo_estado=ESTADO_ACTIVO)
    client, fake_db = _configurar_cliente_api_en_proceso(store, monkeypatch, fallar_rf44=False)

    def _fallar_timedelta(*_args: Any, **_kwargs: Any) -> Any:
        store.timedelta_calls += 1
        raise OverflowError("Falla simulada calculando fecha_fin_retiro (CU03 FA-09)")

    monkeypatch.setattr(reg_med_uc_mod, "timedelta", _fallar_timedelta)

    def _verificar() -> str:
        _assert_sin_violaciones_guard()
        resp = client.post(
            "/suministros/medicamentos",
            json=_payload_valido(periodo_retiro_dias=5),
            headers={"X-Zona-Horaria": "America/Bogota"},
        )
        _verificar_uso_stubs_api(resp, store)
        assert store.timedelta_calls >= 1, "No se invoco el doble de timedelta en registrar_medicamento_use_case."
        _assert_sin_fugas_en_respuesta(resp)
        body = resp.json()
        assert 500 <= resp.status_code < 600, (
            f"Se esperaba HTTP 5xx ante falla en fecha_fin_retiro, obtuvo {resp.status_code}: {body}"
        )
        error_code = (body.get("error_code") or "").strip()
        assert error_code, f"La respuesta debe incluir error_code no vacio: {body}"
        assert fake_db.commits == 0 and fake_db.rollbacks >= 1
        assert store.medicamentos_persistidos == [] and store.marcar_calls == []
        assert store.activo_estado == ESTADO_ACTIVO
        return (
            f"http={resp.status_code}, error_code={error_code}, "
            f"rollbacks={fake_db.rollbacks}, timedelta_calls={store.timedelta_calls}"
        )

    _ejecutar_con_traza(
        test_id="G18_S3_01",
        caso_plano="047",
        caso_original="042",
        esperado="HTTP 5xx con error_code no vacio, sin fugas internas, rollback completo, sin registro y activo sin cambio.",
        fn=_verificar,
    )


def test_g18_s3_02_falla_bd_guardar_por_db_error_translator_y_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S3.2: excepcion real SQLAlchemy/psycopg2 en `guardar()` pasa por `raise_from_db_error` -> HTTP 5xx."""
    pg_err = psycopg2.OperationalError("connection to PostgreSQL server lost during flush")
    sa_err = OperationalError("INSERT INTO modulo5.registros_medicamentos ...", {}, pg_err)
    store = _FakeStore(activo_estado=ESTADO_ACTIVO)
    client, fake_db = _configurar_cliente_api_en_proceso(
        store,
        monkeypatch,
        fallar_rf44=False,
        usar_repo_real_con_flush_error=sa_err,
    )

    def _verificar() -> str:
        _assert_sin_violaciones_guard()
        resp = client.post(
            "/suministros/medicamentos",
            json=_payload_valido(periodo_retiro_dias=5),
            headers={"X-Zona-Horaria": "America/Bogota"},
        )
        _verificar_uso_stubs_api(resp, store)
        assert fake_db.flush_calls >= 1, (
            "flush() de _FakeSession no fue invocado; el repositorio real no ejecuto guardar()."
        )
        _assert_sin_fugas_en_respuesta(resp)
        body = resp.json()
        assert 500 <= resp.status_code < 600, f"Se esperaba HTTP 5xx por fallo de BD, obtuvo {resp.status_code}: {body}"
        error_code = (body.get("error_code") or "").strip()
        assert error_code, f"La respuesta debe incluir error_code no vacio: {body}"
        assert fake_db.commits == 0 and fake_db.rollbacks >= 1
        assert store.medicamentos_persistidos == [] and store.marcar_calls == []
        assert store.activo_estado == ESTADO_ACTIVO
        return (
            f"http={resp.status_code}, error_code={error_code}, "
            f"flush_calls={fake_db.flush_calls}, rollbacks={fake_db.rollbacks}"
        )

    _ejecutar_con_traza(
        test_id="G18_S3_02",
        caso_plano="047",
        caso_original="042",
        esperado="Falla de BD en guardar() responde HTTP 5xx con error_code no vacio, sin fugas internas y rollback.",
        fn=_verificar,
    )


def test_g18_s3_03_incidente_auditoria_sobrevive_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S3.3 (CU03 FA-13): tras S3_01 y S3_02 debe sobrevivir un incidente en auditoria fuera del rollback."""
    store = _FakeStore(activo_estado=ESTADO_ACTIVO)

    def _verificar() -> str:
        _assert_sin_violaciones_guard()

        # Escenario A: falla calculando fecha_fin_retiro (sesion_sistema liberada para registro independiente C9)
        with monkeypatch.context() as mp_a:
            mp_a.setattr(
                shared_database,
                "sesion_sistema",
                lambda: _FakeSession(store, es_sesion_peticion=False),
            )
            client_a, _ = _configurar_cliente_api_en_proceso(store, mp_a, fallar_rf44=False)

            def _fallar_td(*_a: Any, **_kw: Any) -> Any:
                store.timedelta_calls += 1
                raise OverflowError("Falla simulada fecha_fin_retiro")

            mp_a.setattr(reg_med_uc_mod, "timedelta", _fallar_td)
            resp_a = client_a.post(
                "/suministros/medicamentos",
                json=_payload_valido(periodo_retiro_dias=5),
                headers={"X-Zona-Horaria": "America/Bogota"},
            )
        _verificar_uso_stubs_api(resp_a, store, min_calls=1)
        assert store.timedelta_calls >= 1
        audit_post_a = list(store.auditorias_persistidas)

        # Escenario B: falla real de BD en guardar() (sesion_sistema liberada para registro independiente C9)
        pg_err = psycopg2.OperationalError("connection to PostgreSQL server lost during flush")
        sa_err = OperationalError("INSERT INTO modulo5.registros_medicamentos ...", {}, pg_err)
        with monkeypatch.context() as mp_b:
            mp_b.setattr(
                shared_database,
                "sesion_sistema",
                lambda: _FakeSession(store, es_sesion_peticion=False),
            )
            client_b, fake_db_b = _configurar_cliente_api_en_proceso(
                store,
                mp_b,
                fallar_rf44=False,
                usar_repo_real_con_flush_error=sa_err,
            )
            resp_b = client_b.post(
                "/suministros/medicamentos",
                json=_payload_valido(periodo_retiro_dias=5),
                headers={"X-Zona-Horaria": "America/Bogota"},
            )
        _verificar_uso_stubs_api(resp_b, store, min_calls=2)
        assert fake_db_b.flush_calls >= 1
        audit_post_b = list(store.auditorias_persistidas)

        assert 500 <= resp_a.status_code < 600
        assert 500 <= resp_b.status_code < 600
        sesiones_indep_commit = [
            s for s in store.sessions_opened if (not s.es_sesion_peticion) and s.commits > 0
        ]
        assert len(audit_post_a) >= 1 and len(sesiones_indep_commit) >= 1, (
            "Defecto CU03 FA-13: la falla al calcular fecha_fin_retiro no confirmo incidente de auditoria "
            f"en sesion independiente sobreviviente al rollback (incidentes_confirmados={len(audit_post_a)}, "
            f"sesiones_indep_commiteadas={len(sesiones_indep_commit)})."
        )
        assert len(audit_post_b) > len(audit_post_a) and len(sesiones_indep_commit) >= 2, (
            "Defecto CU03 FA-13: la falla de persistencia BD no confirmo incidente de auditoria "
            f"en sesion independiente sobreviviente al rollback (incidentes_confirmados={len(audit_post_b)}, "
            f"sesiones_indep_commiteadas={len(sesiones_indep_commit)})."
        )
        return f"incidentes_a={len(audit_post_a)}, incidentes_b={len(audit_post_b)}"

    _ejecutar_con_traza(
        test_id="G18_S3_03",
        caso_plano="047",
        caso_original="042",
        esperado="Un incidente de auditoria sobrevive al rollback en sesion independiente para S3_01 y S3_02.",
        fn=_verificar,
    )


# ---------------------------------------------------------------------------
# Control Real en TEST (sandbox transaccional con periodo_retiro_dias = 0)
# ---------------------------------------------------------------------------

def _cargar_env_test() -> dict[str, str]:
    repo = Path(__file__).resolve().parents[5]
    env_path = repo / ".env.test"
    assert env_path.exists(), f"Falta .env.test en la raiz del repo ({repo})"
    valores = dotenv_values(env_path)
    resultado: dict[str, str] = {}
    for k in ("TEST_BASE_URL", "TEST_SANDBOX_SECRET", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD", "TEST_M05_ACTIVO_ID"):
        val = (os.environ.get(k) or valores.get(k) or "").strip()
        if val:
            resultado[k] = val
    return resultado


def _login_sandbox_con_reintento(session: requests.Session, base_url: str, email: str, pwd: str) -> None:
    """Inicia sesion en TEST con backoff ante bloqueo temporal 423/429 (max 200 s)."""
    import time as time_mod
    for intento in range(7):
        resp = session.post(
            f"{base_url}/sesiones/",
            json={"correo_electronico": email, "contrasena": pwd},
            timeout=45,
        )
        if resp.status_code in (423, 429) and intento < 6:
            time_mod.sleep(30)
            continue
        assert resp.status_code == 200, f"Login Admin fallo en TEST con HTTP {resp.status_code}"
        token = (resp.json() or {}).get("token")
        assert token, "Login Admin no devolvio token en la respuesta"
        session.headers["Authorization"] = f"Bearer {token}"
        return


def _query_sandbox(session: requests.Session, base_url: str, sql: str) -> list[dict[str, Any]]:
    resp = session.post(f"{base_url}/test-control/query", json={"query": sql}, timeout=45)
    assert resp.status_code == 200, f"Consulta /test-control/query fallo HTTP {resp.status_code}"
    body = resp.json()
    return body["data"]


def _relanzar_con_rollback(cuerpo_exc: BaseException, del_resumen: str) -> None:
    """Preserva la excepcion original del cuerpo adjuntando el resultado del DELETE (C10)."""
    if hasattr(cuerpo_exc, "add_note"):
        cuerpo_exc.add_note(f"Rollback sandbox: {del_resumen}")
    if isinstance(cuerpo_exc, AssertionError):
        raise AssertionError(f"{cuerpo_exc} [rollback: {del_resumen}]") from cuerpo_exc
    if getattr(cuerpo_exc, "args", None) and isinstance(cuerpo_exc.args[0], str):
        cuerpo_exc.args = (f"{cuerpo_exc.args[0]} [rollback: {del_resumen}]", *cuerpo_exc.args[1:])
    raise cuerpo_exc


def _ejecutar_corrida_sandbox(
    *,
    base_url: str,
    secret: str,
    run_id: str,
    cuerpo_fn: Callable[[requests.Session], Any],
) -> Any:
    """Ejecuta una corrida sandbox garantizando DELETE /test-control/runs/{run_id} seguro en finally (C10)."""
    session = requests.Session()
    session.headers.update(
        {
            "X-Test-Run-Id": run_id,
            "X-Sandbox-Secret": secret,
            "X-Zona-Horaria": "America/Bogota",
        }
    )
    cuerpo_exc: Optional[BaseException] = None
    resultado: Any = None
    try:
        resultado = cuerpo_fn(session)
    except BaseException as exc:
        cuerpo_exc = exc
    finally:
        del_status: Optional[int] = None
        del_err: Optional[str] = None
        try:
            r_del = session.delete(f"{base_url}/test-control/runs/{run_id}", timeout=45)
            del_status = r_del.status_code
        except Exception as exc_del:
            del_err = f"{type(exc_del).__name__}: {exc_del}"
        finally:
            session.close()

        del_resumen = f"DELETE={del_status}" if del_err is None else f"DELETE_ERR={del_err}"
        if cuerpo_exc is not None:
            _relanzar_con_rollback(cuerpo_exc, del_resumen)
        assert del_status == 200, f"Rollback corrida {run_id} fallo: {del_resumen}"
    return resultado


@pytest.mark.sandbox_real
def test_g18_r_01_control_real_sandbox_sin_retiro_e_inocuidad() -> None:
    """Control real HTTP en TEST: registro hoy y D-6 con periodo_retiro_dias=0 y rollback inocuo."""
    cfg = _cargar_env_test()
    for obligatoria in ("TEST_BASE_URL", "TEST_SANDBOX_SECRET", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD"):
        assert obligatoria in cfg and cfg[obligatoria], f"Falta variable obligatoria en .env.test: {obligatoria}"

    base_url = cfg["TEST_BASE_URL"].rstrip("/")
    secret = cfg["TEST_SANDBOX_SECRET"]
    email = cfg["TEST_ADMIN_EMAIL"]
    pwd = cfg["TEST_ADMIN_PASSWORD"]
    activo_id = int(cfg.get("TEST_M05_ACTIVO_ID") or ACTIVO_ID_PRUEBA)

    hoy_bogota = datetime.now(_ZONA_BOGOTA).date()
    retro_d6 = hoy_bogota - timedelta(days=6)

    def _verificar() -> str:
        # Corrida 1: registro real con periodo_retiro_dias = 0
        run1 = f"tc-m05-g18-r01-{uuid.uuid4().hex[:8]}"

        def _cuerpo_run1(s1: requests.Session) -> int:
            _login_sandbox_con_reintento(s1, base_url, email, pwd)
            rows_base = _query_sandbox(
                s1,
                base_url,
                f"SELECT count(*) AS total FROM modulo5.registros_medicamentos WHERE id_activo_biologico = {activo_id}",
            )
            conteo_base_r1 = int(rows_base[0]["total"])

            r_fases = s1.get(f"{base_url}/activos-biologicos/{activo_id}/fases", timeout=45)
            assert r_fases.status_code == 200
            activas = [f for f in (r_fases.json().get("fases") or []) if f.get("es_activa") is True]
            if not activas:
                r_abrir = s1.post(
                    f"{base_url}/activos-biologicos/{activo_id}/fases",
                    json={
                        "id_ciclo_productiva": CICLO_ID_PRUEBA,
                        "motivo_cambio": "TC-M05-G18 control real sandbox",
                    },
                    timeout=45,
                )
                assert r_abrir.status_code == 201, f"Abrir fase en sandbox fallo HTTP {r_abrir.status_code}"

            p_hoy = _payload_valido(periodo_retiro_dias=0, fecha_aplicacion=hoy_bogota)
            p_hoy["id_activo_biologico"] = activo_id
            p_hoy["nombre_medicamento"] = f"ControlG18Hoy-{uuid.uuid4().hex[:6]}"
            p_hoy["hora_aplicacion"] = "10:15"
            r1 = s1.post(f"{base_url}/suministros/medicamentos", json=p_hoy, timeout=45)
            assert r1.status_code == 201, f"POST hoy fallo HTTP {r1.status_code}: {r1.text[:250]}"
            med1 = r1.json()["medicamento"]
            assert med1["estado_registro"] == "VALIDADO"
            assert med1["periodo_retiro_dias"] == 0
            assert med1["fecha_fin_retiro"] is None

            p_d6 = _payload_valido(periodo_retiro_dias=0, fecha_aplicacion=retro_d6)
            p_d6["id_activo_biologico"] = activo_id
            p_d6["nombre_medicamento"] = f"ControlG18D6-{uuid.uuid4().hex[:6]}"
            p_d6["hora_aplicacion"] = "10:16"
            r2 = s1.post(f"{base_url}/suministros/medicamentos", json=p_d6, timeout=45)
            assert r2.status_code == 201, f"POST D-6 fallo HTTP {r2.status_code}: {r2.text[:250]}"
            med2 = r2.json()["medicamento"]
            assert med2["estado_registro"] == "VALIDADO"
            assert med2["periodo_retiro_dias"] == 0
            assert med2["fecha_fin_retiro"] is None

            r_list = s1.get(
                f"{base_url}/suministros/medicamentos",
                params={"id_activo_biologico": activo_id},
                timeout=45,
            )
            assert r_list.status_code == 200
            assert r_list.json().get("total") == conteo_base_r1 + 2

            r_act = s1.get(f"{base_url}/activos-biologicos/{activo_id}", timeout=45)
            assert r_act.status_code == 200
            assert r_act.json().get("id_estado") == ESTADO_ACTIVO
            return conteo_base_r1

        conteo_base = _ejecutar_corrida_sandbox(
            base_url=base_url,
            secret=secret,
            run_id=run1,
            cuerpo_fn=_cuerpo_run1,
        )

        # Corrida 2 (estrictamente secuencial): verificar inocuidad post-rollback
        run2 = f"tc-m05-g18-inoc-{uuid.uuid4().hex[:8]}"

        def _cuerpo_run2(s2: requests.Session) -> int:
            _login_sandbox_con_reintento(s2, base_url, email, pwd)
            rows_fin = _query_sandbox(
                s2,
                base_url,
                f"SELECT count(*) AS total FROM modulo5.registros_medicamentos WHERE id_activo_biologico = {activo_id}",
            )
            conteo_fin_r2 = int(rows_fin[0]["total"])
            assert conteo_fin_r2 == conteo_base, (
                f"Inocuidad rota: base={conteo_base}, post_rollback={conteo_fin_r2}"
            )
            return conteo_fin_r2

        conteo_fin = _ejecutar_corrida_sandbox(
            base_url=base_url,
            secret=secret,
            run_id=run2,
            cuerpo_fn=_cuerpo_run2,
        )

        return f"activo={activo_id}, base={conteo_base}, en_sandbox={conteo_base + 2}, post_rollback={conteo_fin}"

    _ejecutar_con_traza(
        test_id="G18_R_01",
        caso_plano="043/044/047",
        caso_original="011/012/042",
        esperado="POST real en TEST con periodo_retiro_dias=0 (hoy y D-6) retorna 201 y el rollback deja conteo intacto.",
        fn=_verificar,
    )
