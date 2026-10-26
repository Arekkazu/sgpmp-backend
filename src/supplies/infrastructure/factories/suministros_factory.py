# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-75/76: wiring de consumo y medicamento |
# | 2026-10-23 | Arekkazu         | M05 RF-75: catálogo de tipos de alimento      |
"""Fábricas de wiring de RF-75/RF-76 (consumo de alimento y medicamentos).

Cablean puertos → repositorios/adapters concretos y devuelven use cases listos.
Se usan desde ``consumo_alimento_router.py`` y ``medicamento_router.py``.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.supplies.application.use_cases.suministros.anular_consumo_alimento_use_case import (
    AnularConsumoAlimentoUseCase,
)
from src.supplies.application.use_cases.suministros.anular_medicamento_use_case import AnularMedicamentoUseCase
from src.supplies.application.use_cases.suministros.listar_tipos_alimento_use_case import ListarTiposAlimentoUseCase
from src.supplies.application.use_cases.suministros.consultar_consumos_use_case import ConsultarConsumosUseCase
from src.supplies.application.use_cases.suministros.consultar_medicamentos_use_case import (
    ConsultarMedicamentosUseCase,
)
from src.supplies.application.use_cases.suministros.rechazar_modificacion_use_case import (
    RechazarModificacionUseCase,
)
from src.supplies.application.use_cases.suministros.registrar_consumo_alimento_use_case import (
    RegistrarConsumoAlimentoUseCase,
)
from src.supplies.application.use_cases.suministros.registrar_medicamento_use_case import (
    RegistrarMedicamentoUseCase,
)
from src.supplies.infrastructure.adapters.activo_m02_adapter import ActivoM02Adapter
from src.supplies.infrastructure.adapters.alcance_activo_m02_adapter import AlcanceActivoM02Adapter
from src.supplies.infrastructure.adapters.ciclo_m02_adapter import CicloM02Adapter
from src.supplies.infrastructure.adapters.estado_activo_m02_adapter import EstadoActivoM02Adapter
from src.supplies.infrastructure.adapters.evento_sanitario_m02_adapter import EventoSanitarioM02Adapter
from src.supplies.infrastructure.adapters.notificacion_medicamento_email_adapter import (
    NotificacionMedicamentoEmailAdapter,
)
from src.supplies.infrastructure.adapters.rol_usuario_m01_adapter import RolUsuarioM01Adapter
from src.supplies.infrastructure.factories.costeo_suministros_factory import (
    build_compensador_anulacion,
    build_registrador_movimiento,
)
from src.supplies.infrastructure.repositories.consumo_alimento_repository import (
    SqlAlchemyConsumoAlimentoRepository,
)
from src.supplies.infrastructure.repositories.medicamento_repository import SqlAlchemyMedicamentoRepository
from src.supplies.infrastructure.repositories.registro_suministro_repository import (
    SqlAlchemyRegistroSuministroRepository,
)


def build_registrar_consumo_use_case(db: Session) -> RegistrarConsumoAlimentoUseCase:
    return RegistrarConsumoAlimentoUseCase(
        db=db,
        consumo_repo=SqlAlchemyConsumoAlimentoRepository(db),
        activo_port=ActivoM02Adapter(db),
        ciclo_port=CicloM02Adapter(db),
        registro_repo=SqlAlchemyRegistroSuministroRepository(db),
        movimiento=build_registrador_movimiento(db),
    )


def build_anular_consumo_use_case(db: Session) -> AnularConsumoAlimentoUseCase:
    return AnularConsumoAlimentoUseCase(
        db=db,
        consumo_repo=SqlAlchemyConsumoAlimentoRepository(db),
        compensador=build_compensador_anulacion(db),
    )


def build_consultar_consumos_use_case(db: Session) -> ConsultarConsumosUseCase:
    return ConsultarConsumosUseCase(
        consumo_repo=SqlAlchemyConsumoAlimentoRepository(db),
        alcance_port=AlcanceActivoM02Adapter(db),
    )


def build_listar_tipos_alimento_use_case(db: Session) -> ListarTiposAlimentoUseCase:
    return ListarTiposAlimentoUseCase(consumo_repo=SqlAlchemyConsumoAlimentoRepository(db))


def build_registrar_medicamento_use_case(db: Session) -> RegistrarMedicamentoUseCase:
    return RegistrarMedicamentoUseCase(
        db=db,
        medicamento_repo=SqlAlchemyMedicamentoRepository(db),
        activo_port=ActivoM02Adapter(db),
        ciclo_port=CicloM02Adapter(db),
        evento_port=EventoSanitarioM02Adapter(db),
        estado_port=EstadoActivoM02Adapter(db),
        notificacion_port=NotificacionMedicamentoEmailAdapter(db),
        rol_port=RolUsuarioM01Adapter(db),
        registro_repo=SqlAlchemyRegistroSuministroRepository(db),
        movimiento=build_registrador_movimiento(db),
    )


def build_anular_medicamento_use_case(db: Session) -> AnularMedicamentoUseCase:
    return AnularMedicamentoUseCase(
        db=db,
        medicamento_repo=SqlAlchemyMedicamentoRepository(db),
        compensador=build_compensador_anulacion(db),
        activo_port=ActivoM02Adapter(db),
        estado_port=EstadoActivoM02Adapter(db),
        notificacion_port=NotificacionMedicamentoEmailAdapter(db),
    )


def build_consultar_medicamentos_use_case(db: Session) -> ConsultarMedicamentosUseCase:
    return ConsultarMedicamentosUseCase(
        medicamento_repo=SqlAlchemyMedicamentoRepository(db),
        alcance_port=AlcanceActivoM02Adapter(db),
    )


def build_rechazar_modificacion_use_case(db: Session) -> RechazarModificacionUseCase:
    return RechazarModificacionUseCase(
        consumo_repo=SqlAlchemyConsumoAlimentoRepository(db),
        medicamento_repo=SqlAlchemyMedicamentoRepository(db),
    )
