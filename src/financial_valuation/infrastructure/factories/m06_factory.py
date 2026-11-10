# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: ensamblado de repositorios, servicios y casos de uso |
# | 2026-11-09 | destroyerban | INC-M06-323-G27 RF-85 FA-1/FA-2: la cosecha pendiente continúa con precio o costos manuales |
"""Fábrica de M06: arma los casos de uso con sus repositorios SQL para una sesión."""
from __future__ import annotations

from functools import cached_property

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.application.services.medidor import Medidor
from src.financial_valuation.application.services.propuesta_reconocimiento import ProponedorReconocimiento
from src.financial_valuation.application.services.reportes import ConstructorEstadoResultados, ConstructorInformeRevelaciones
from src.financial_valuation.application.services.valorador import Valorador
from src.financial_valuation.application.use_cases.auditoria.consultar_auditoria_financiera_use_case import (
    ConsultarAuditoriaFinancieraUseCase,
)
from src.financial_valuation.application.use_cases.cierre.ejecutar_cierre_periodo_use_case import EjecutarCierrePeriodoUseCase
from src.financial_valuation.application.use_cases.configuracion.actualizar_configuracion_contable_use_case import (
    ActualizarConfiguracionContableUseCase,
)
from src.financial_valuation.application.use_cases.configuracion.guardar_asignacion_cuenta_use_case import (
    GuardarAsignacionCuentaUseCase,
)
from src.financial_valuation.application.use_cases.configuracion.guardar_costos_venta_use_case import GuardarCostosVentaUseCase
from src.financial_valuation.application.use_cases.configuracion.guardar_parametro_especie_use_case import (
    GuardarParametroEspecieUseCase,
)
from src.financial_valuation.application.use_cases.costos.clasificar_costo_use_case import ClasificarCostoUseCase
from src.financial_valuation.application.use_cases.costos.procesar_provisiones_m05_use_case import ProcesarProvisionesM05UseCase
from src.financial_valuation.application.use_cases.costos.registrar_costo_use_case import RegistrarCostoUseCase
from src.financial_valuation.application.use_cases.cotizaciones.modificar_cotizacion_use_case import ModificarCotizacionUseCase
from src.financial_valuation.application.use_cases.cotizaciones.registrar_cotizacion_use_case import RegistrarCotizacionUseCase
from src.financial_valuation.application.use_cases.precios.listar_precios_use_case import ListarPreciosUseCase
from src.financial_valuation.application.use_cases.precios.registrar_precio_use_case import RegistrarPrecioUseCase
from src.financial_valuation.application.use_cases.reconocimiento.confirmar_reconocimiento_use_case import (
    ConfirmarReconocimientoUseCase,
)
from src.financial_valuation.application.use_cases.reconocimiento.listar_propuestas_reconocimiento_use_case import (
    ListarPropuestasReconocimientoUseCase,
)
from src.financial_valuation.application.use_cases.reconocimiento.revertir_reconocimiento_use_case import (
    RevertirReconocimientoUseCase,
)
from src.financial_valuation.application.use_cases.reportes.exportar_reporte_use_case import ExportarReporteUseCase
from src.financial_valuation.application.use_cases.reportes.generar_estado_resultados_use_case import (
    GenerarEstadoResultadosUseCase,
)
from src.financial_valuation.application.use_cases.reportes.generar_informe_revelaciones_use_case import (
    GenerarInformeRevelacionesUseCase,
)
from src.financial_valuation.application.use_cases.trazabilidad.verificar_trazabilidad_use_case import (
    VerificadorTrazabilidad,
    VerificarTrazabilidadUseCase,
)
from src.financial_valuation.application.use_cases.valoracion.procesar_eventos_m02_use_case import ProcesarEventosM02UseCase
from src.financial_valuation.application.use_cases.valoracion.reconocer_cosecha_pendiente_use_case import (
    ReconocerCosechaPendienteUseCase,
)
from src.financial_valuation.application.use_cases.valoracion_costo.cambiar_a_valor_razonable_use_case import (
    CambiarAValorRazonableUseCase,
)
from src.financial_valuation.application.use_cases.valoracion_costo.registrar_deterioro_use_case import RegistrarDeterioroUseCase
from src.financial_valuation.infrastructure.adapters.activo_financiero_m02_adapter import ActivoFinancieroM02Adapter
from src.financial_valuation.infrastructure.adapters.evento_m02_adapter import EventoM02Adapter
from src.financial_valuation.infrastructure.adapters.notificacion_financiera_m01_adapter import NotificacionFinancieraM01Adapter
from src.financial_valuation.infrastructure.repositories.asiento_repository import SqlAlchemyAsientoRepository
from src.financial_valuation.infrastructure.repositories.auditoria_financiera_repository import (
    SqlAlchemyAuditoriaFinancieraRepository,
)
from src.financial_valuation.infrastructure.repositories.configuracion_contable_repository import (
    SqlAlchemyConfiguracionContableRepository,
)
from src.financial_valuation.infrastructure.repositories.costo_repository import SqlAlchemyCostoRepository
from src.financial_valuation.infrastructure.repositories.cotizacion_repository import SqlAlchemyCotizacionRepository
from src.financial_valuation.infrastructure.repositories.periodo_repository import SqlAlchemyPeriodoRepository
from src.financial_valuation.infrastructure.repositories.precio_repository import SqlAlchemyPrecioRepository
from src.financial_valuation.infrastructure.repositories.reporte_repository import SqlAlchemyReporteRepository
from src.financial_valuation.infrastructure.repositories.trazabilidad_repository import SqlAlchemyTrazabilidadRepository
from src.financial_valuation.infrastructure.repositories.valoracion_repository import SqlAlchemyValoracionRepository
from src.shared.database import id_usuario_servicio, sesion_sistema


class M06:
    """Contenedor perezoso por sesión: cada propiedad se construye una vez."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Repositorios ---
    @cached_property
    def activos(self): return ActivoFinancieroM02Adapter(self.db)
    @cached_property
    def eventos(self): return EventoM02Adapter(self.db)
    @cached_property
    def config(self): return SqlAlchemyConfiguracionContableRepository(self.db)
    @cached_property
    def asientos(self): return SqlAlchemyAsientoRepository(self.db)
    @cached_property
    def auditoria(self): return SqlAlchemyAuditoriaFinancieraRepository(self.db)
    @cached_property
    def periodos(self): return SqlAlchemyPeriodoRepository(self.db)
    @cached_property
    def precios(self): return SqlAlchemyPrecioRepository(self.db)
    @cached_property
    def valoraciones(self): return SqlAlchemyValoracionRepository(self.db)
    @cached_property
    def costos(self): return SqlAlchemyCostoRepository(self.db)
    @cached_property
    def cotizaciones(self): return SqlAlchemyCotizacionRepository(self.db)
    @cached_property
    def reportes(self): return SqlAlchemyReporteRepository(self.db)
    @cached_property
    def trazabilidad(self): return SqlAlchemyTrazabilidadRepository(self.db)
    @cached_property
    def notificador(self): return NotificacionFinancieraM01Adapter(sesion_sistema)

    # --- Servicios ---
    @cached_property
    def contabilizador(self): return Contabilizador(self.config, self.periodos, self.asientos, self.auditoria)
    @cached_property
    def valorador(self): return Valorador(self.precios, self.config)
    @cached_property
    def medidor(self): return Medidor(self.valorador, self.valoraciones, self.contabilizador)
    @cached_property
    def proponedor(self): return ProponedorReconocimiento(self.valorador, self.config)
    @cached_property
    def verificador(self): return VerificadorTrazabilidad(self.asientos, self.trazabilidad, self.auditoria)
    @cached_property
    def constructor_estado(self): return ConstructorEstadoResultados(self.reportes, self.costos)
    @cached_property
    def constructor_informe(self): return ConstructorInformeRevelaciones(self.reportes)

    # --- Casos de uso ---
    def actualizar_configuracion(self): return ActualizarConfiguracionContableUseCase(self.db, self.config, self.auditoria)
    def guardar_parametro_especie(self): return GuardarParametroEspecieUseCase(self.db, self.config, self.auditoria)
    def guardar_costos_venta(self): return GuardarCostosVentaUseCase(self.db, self.config, self.auditoria)
    def guardar_asignacion(self): return GuardarAsignacionCuentaUseCase(self.db, self.config, self.asientos, self.auditoria)
    def registrar_precio(self):
        return RegistrarPrecioUseCase(self.db, self.precios, self.config, self.auditoria, self.activos, self.notificador)
    def listar_precios(self): return ListarPreciosUseCase(self.precios)
    def propuestas(self): return ListarPropuestasReconocimientoUseCase(self.activos, self.proponedor)
    def confirmar_reconocimiento(self):
        return ConfirmarReconocimientoUseCase(self.db, self.activos, self.valoraciones, self.proponedor, self.contabilizador)
    def revertir_reconocimiento(self):
        return RevertirReconocimientoUseCase(self.db, self.activos, self.valoraciones, self.contabilizador)
    def procesar_eventos(self):
        return ProcesarEventosM02UseCase(self.db, self.eventos, self.activos, self.valoraciones, self.precios,
                                         self.medidor, self.contabilizador, id_usuario_servicio(self.db))
    def reconocer_cosecha_pendiente(self):
        return ReconocerCosechaPendienteUseCase(self.db, self.eventos, self.procesar_eventos())
    def procesar_provisiones(self):
        return ProcesarProvisionesM05UseCase(self.db, self.costos, self.activos, self.contabilizador, id_usuario_servicio(self.db))
    def registrar_costo(self):
        return RegistrarCostoUseCase(self.db, self.costos, self.activos, self.valoraciones, self.contabilizador)
    def clasificar_costo(self): return ClasificarCostoUseCase(self.db, self.costos, self.activos, self.contabilizador)
    def cierre(self):
        return EjecutarCierrePeriodoUseCase(
            self.db, self.periodos, self.activos, self.valoraciones, self.costos, self.cotizaciones, self.eventos,
            self.medidor, self.contabilizador, self.verificador, self.constructor_estado, self.constructor_informe,
            self.notificador, self.procesar_eventos())
    def verificar_trazabilidad(self): return VerificarTrazabilidadUseCase(self.db, self.asientos, self.verificador, self.periodos)
    def registrar_deterioro(self): return RegistrarDeterioroUseCase(self.db, self.activos, self.valoraciones, self.contabilizador)
    def cambiar_a_valor_razonable(self):
        return CambiarAValorRazonableUseCase(self.db, self.activos, self.valoraciones, self.valorador, self.contabilizador)
    def registrar_cotizacion(self):
        return RegistrarCotizacionUseCase(self.db, self.cotizaciones, self.activos, self.valoraciones, self.contabilizador)
    def modificar_cotizacion(self): return ModificarCotizacionUseCase(self.db, self.cotizaciones, self.auditoria)
    def estado_resultados(self):
        return GenerarEstadoResultadosUseCase(self.db, self.periodos, self.reportes, self.constructor_estado, self.auditoria)
    def informe_revelaciones(self):
        return GenerarInformeRevelacionesUseCase(self.db, self.periodos, self.reportes, self.constructor_informe, self.auditoria)
    def exportar(self): return ExportarReporteUseCase(self.periodos, self.reportes)
    def consultar_auditoria(self): return ConsultarAuditoriaFinancieraUseCase(self.auditoria)
