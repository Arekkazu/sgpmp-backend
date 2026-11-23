# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: ensamblado de repositorios, servicios y casos de uso |
# | 2026-11-08 | destroyerban | INC-M06-308-G12 RF-83: el procesador de eventos M02 recibe el notificador |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-296-G34-01 RF-86: notificador en el procesamiento de eventos |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-281-G68-07 RF-88: notificador en el registro de deterioro |
# | 2026-11-09 | destroyerban | INC-M06-317-G17 RF-84: cálculo en revisión y validación del valor neto ≤ 0 |
# | 2026-11-09 | destroyerban | INC-M06-320-G24 RF-85 FA-4: la cosecha del 100 % deja el activo en cero e inicia su baja |
# | 2026-11-09 | destroyerban | INC-M06-323-G27 RF-85 FA-1/FA-2: la cosecha pendiente continúa con precio o costos manuales |
# | 2026-11-09 | destroyerban | INC-M06-325-G30 RF-85 RNF-85-05: historial de productos con filtros, evento y usuario |
# | 2026-11-10 | Arekkazu | INC-M06-342/351 RF-86/87: avisos de cuenta faltante y ajuste de período anterior |
# | 2026-11-10 | destroyerban | INC-M06-336-G36 RF-86: correctivo de variaciones con aprobación del Contador |
# | 2026-11-13 | Arekkazu | INC-M06-90-G97 RF-88: consulta de la depreciación de un activo al costo |
# | 2026-11-13 | Leandro | TC-M06-G61 RF-92: conectar la notificación financiera de supuestos faltantes. |
# | 2026-11-13 | Arekkazu | TC-M06-G74 RF-93 FA-2: conciliación del estado de resultados con sus fuentes (hechos sin asiento) |
# | 2026-11-14 | destroyerban | INC-M06-361-G24 RF-85 FA-4: la baja del activo cosechado usa la sesión de M06 |
# | 2026-11-15 | Arekkazu | INC-M06-366-G31 RF-82/84/85: avisos de M06 en la bandeja del Contador |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
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
from src.financial_valuation.application.use_cases.cierre.registrar_ajuste_periodo_anterior_use_case import (
    RegistrarAjustePeriodoAnteriorUseCase,
)
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
from src.financial_valuation.application.use_cases.valoracion.consultar_productos_agricolas_use_case import (
    ConsultarProductosAgricolasUseCase,
)
from src.financial_valuation.application.use_cases.valoracion.correctivo_variacion_use_case import (
    ResolverCorrectivoVariacionUseCase,
    SolicitarCorrectivoVariacionUseCase,
)
from src.financial_valuation.application.use_cases.valoracion.procesar_eventos_m02_use_case import ProcesarEventosM02UseCase
from src.financial_valuation.application.use_cases.valoracion.validar_calculo_no_positivo_use_case import (
    ValidarCalculoNoPositivoUseCase,
)
from src.financial_valuation.application.use_cases.valoracion.reconocer_cosecha_pendiente_use_case import (
    ReconocerCosechaPendienteUseCase,
)
from src.financial_valuation.application.use_cases.valoracion_costo.cambiar_a_valor_razonable_use_case import (
    CambiarAValorRazonableUseCase,
)
from src.financial_valuation.application.use_cases.valoracion_costo.consultar_depreciacion_use_case import (
    ConsultarDepreciacionUseCase,
)
from src.financial_valuation.application.use_cases.valoracion_costo.registrar_deterioro_use_case import RegistrarDeterioroUseCase
from src.financial_valuation.infrastructure.adapters.activo_financiero_m02_adapter import ActivoFinancieroM02Adapter
from src.financial_valuation.infrastructure.adapters.baja_activo_m02_adapter import BajaActivoM02Adapter
from src.financial_valuation.infrastructure.adapters.evento_m02_adapter import EventoM02Adapter
from src.financial_valuation.infrastructure.adapters.notificacion_financiera_m01_adapter import NotificacionFinancieraM01Adapter
from src.financial_valuation.infrastructure.repositories.asiento_repository import SqlAlchemyAsientoRepository
from src.financial_valuation.infrastructure.repositories.auditoria_financiera_repository import (
    SqlAlchemyAuditoriaFinancieraRepository,
)
from src.financial_valuation.infrastructure.repositories.configuracion_contable_repository import (
    SqlAlchemyConfiguracionContableRepository,
)
from src.financial_valuation.infrastructure.repositories.correctivo_variacion_repository import (
    SqlAlchemyCorrectivoVariacionRepository,
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
    def activos(self):
        """``ActivoFinancieroM02Adapter`` con las dependencias del módulo."""
        return ActivoFinancieroM02Adapter(self.db)
    @cached_property
    def eventos(self):
        """``EventoM02Adapter`` con las dependencias del módulo."""
        return EventoM02Adapter(self.db)
    @cached_property
    def config(self):
        """``SqlAlchemyConfiguracionContableRepository`` con las dependencias del módulo."""
        return SqlAlchemyConfiguracionContableRepository(self.db)
    @cached_property
    def asientos(self):
        """``SqlAlchemyAsientoRepository`` con las dependencias del módulo."""
        return SqlAlchemyAsientoRepository(self.db)
    @cached_property
    def auditoria(self):
        """``SqlAlchemyAuditoriaFinancieraRepository`` con las dependencias del módulo."""
        return SqlAlchemyAuditoriaFinancieraRepository(self.db)
    @cached_property
    def periodos(self):
        """``SqlAlchemyPeriodoRepository`` con las dependencias del módulo."""
        return SqlAlchemyPeriodoRepository(self.db)
    @cached_property
    def precios(self):
        """``SqlAlchemyPrecioRepository`` con las dependencias del módulo."""
        return SqlAlchemyPrecioRepository(self.db)
    @cached_property
    def valoraciones(self):
        """``SqlAlchemyValoracionRepository`` con las dependencias del módulo."""
        return SqlAlchemyValoracionRepository(self.db)
    @cached_property
    def correctivos(self):
        """``SqlAlchemyCorrectivoVariacionRepository`` con las dependencias del módulo."""
        return SqlAlchemyCorrectivoVariacionRepository(self.db)
    @cached_property
    def costos(self):
        """``SqlAlchemyCostoRepository`` con las dependencias del módulo."""
        return SqlAlchemyCostoRepository(self.db)
    @cached_property
    def cotizaciones(self):
        """``SqlAlchemyCotizacionRepository`` con las dependencias del módulo."""
        return SqlAlchemyCotizacionRepository(self.db)
    @cached_property
    def reportes(self):
        """``SqlAlchemyReporteRepository`` con las dependencias del módulo."""
        return SqlAlchemyReporteRepository(self.db)
    @cached_property
    def trazabilidad(self):
        """``SqlAlchemyTrazabilidadRepository`` con las dependencias del módulo."""
        return SqlAlchemyTrazabilidadRepository(self.db)
    @cached_property
    def notificador(self):
        """``NotificacionFinancieraM01Adapter`` con las dependencias del módulo."""
        return NotificacionFinancieraM01Adapter(sesion_sistema, self.db)

    # --- Servicios ---
    @cached_property
    def contabilizador(self):
        """``Contabilizador`` con las dependencias del módulo."""
        return Contabilizador(self.config, self.periodos, self.asientos, self.auditoria, self.notificador, self.activos)
    @cached_property
    def valorador(self):
        """``Valorador`` con las dependencias del módulo."""
        return Valorador(self.precios, self.config)
    @cached_property
    def medidor(self):
        """``Medidor`` con las dependencias del módulo."""
        return Medidor(self.valorador, self.valoraciones, self.contabilizador)
    @cached_property
    def proponedor(self):
        """``ProponedorReconocimiento`` con las dependencias del módulo."""
        return ProponedorReconocimiento(self.valorador, self.config)
    @cached_property
    def verificador(self):
        """``VerificadorTrazabilidad`` con las dependencias del módulo."""
        return VerificadorTrazabilidad(self.asientos, self.trazabilidad, self.auditoria)
    @cached_property
    def constructor_estado(self):
        """``ConstructorEstadoResultados`` con las dependencias del módulo."""
        return ConstructorEstadoResultados(self.reportes, self.costos)
    @cached_property
    def constructor_informe(self):
        """``ConstructorInformeRevelaciones`` con las dependencias del módulo."""
        return ConstructorInformeRevelaciones(self.reportes)

    # --- Casos de uso ---
    def actualizar_configuracion(self):
        """``ActualizarConfiguracionContableUseCase`` con las dependencias del módulo."""
        return ActualizarConfiguracionContableUseCase(self.db, self.config, self.auditoria)
    def guardar_parametro_especie(self):
        """``GuardarParametroEspecieUseCase`` con las dependencias del módulo."""
        return GuardarParametroEspecieUseCase(self.db, self.config, self.auditoria)
    def guardar_costos_venta(self):
        """``GuardarCostosVentaUseCase`` con las dependencias del módulo."""
        return GuardarCostosVentaUseCase(self.db, self.config, self.auditoria)
    def guardar_asignacion(self):
        """``GuardarAsignacionCuentaUseCase`` con las dependencias del módulo."""
        return GuardarAsignacionCuentaUseCase(self.db, self.config, self.asientos, self.auditoria)
    def registrar_precio(self):
        """``RegistrarPrecioUseCase`` con las dependencias del módulo."""
        return RegistrarPrecioUseCase(self.db, self.precios, self.config, self.auditoria, self.activos, self.notificador)
    def listar_precios(self):
        """``ListarPreciosUseCase`` con las dependencias del módulo."""
        return ListarPreciosUseCase(self.precios)
    def propuestas(self):
        """``ListarPropuestasReconocimientoUseCase`` con las dependencias del módulo."""
        return ListarPropuestasReconocimientoUseCase(self.activos, self.proponedor)
    def confirmar_reconocimiento(self):
        """``ConfirmarReconocimientoUseCase`` con las dependencias del módulo."""
        return ConfirmarReconocimientoUseCase(self.db, self.activos, self.valoraciones, self.proponedor, self.contabilizador,
                                              self.notificador)
    def validar_calculo(self):
        """``ValidarCalculoNoPositivoUseCase`` con las dependencias del módulo."""
        return ValidarCalculoNoPositivoUseCase(self.db, self.valoraciones, self.contabilizador)
    def revertir_reconocimiento(self):
        """``RevertirReconocimientoUseCase`` con las dependencias del módulo."""
        return RevertirReconocimientoUseCase(self.db, self.activos, self.valoraciones, self.contabilizador)
    def procesar_eventos(self):
        """``ProcesarEventosM02UseCase`` con las dependencias del módulo."""
        return ProcesarEventosM02UseCase(self.db, self.eventos, self.activos, self.valoraciones, self.precios,
                                         self.medidor, self.contabilizador, id_usuario_servicio(self.db),
                                         notificador=self.notificador, bajas=BajaActivoM02Adapter(self.db))
    def reconocer_cosecha_pendiente(self):
        """``ReconocerCosechaPendienteUseCase`` con las dependencias del módulo."""
        return ReconocerCosechaPendienteUseCase(self.db, self.eventos, self.procesar_eventos())
    def solicitar_correctivo(self):
        """``SolicitarCorrectivoVariacionUseCase`` con las dependencias del módulo."""
        return SolicitarCorrectivoVariacionUseCase(self.db, self.correctivos, self.valoraciones, self.contabilizador)
    def resolver_correctivo(self):
        """``ResolverCorrectivoVariacionUseCase`` con las dependencias del módulo."""
        return ResolverCorrectivoVariacionUseCase(self.db, self.correctivos, self.valoraciones, self.contabilizador)
    def procesar_provisiones(self):
        """``ProcesarProvisionesM05UseCase`` con las dependencias del módulo."""
        return ProcesarProvisionesM05UseCase(self.db, self.costos, self.activos, self.contabilizador, id_usuario_servicio(self.db))
    def registrar_costo(self):
        """``RegistrarCostoUseCase`` con las dependencias del módulo."""
        return RegistrarCostoUseCase(self.db, self.costos, self.activos, self.valoraciones, self.contabilizador,
                                     notificador=self.notificador)
    def clasificar_costo(self):
        """``ClasificarCostoUseCase`` con las dependencias del módulo."""
        return ClasificarCostoUseCase(self.db, self.costos, self.activos, self.contabilizador)
    def cierre(self):
        """``EjecutarCierrePeriodoUseCase`` con las dependencias del módulo."""
        return EjecutarCierrePeriodoUseCase(
            self.db, self.periodos, self.activos, self.valoraciones, self.costos, self.cotizaciones, self.eventos,
            self.medidor, self.contabilizador, self.verificador, self.constructor_estado, self.constructor_informe,
            self.notificador, self.procesar_eventos())
    def ajuste_periodo_anterior(self):
        """``RegistrarAjustePeriodoAnteriorUseCase`` con las dependencias del módulo."""
        return RegistrarAjustePeriodoAnteriorUseCase(self.db, self.contabilizador)
    def verificar_trazabilidad(self):
        """``VerificarTrazabilidadUseCase`` con las dependencias del módulo."""
        return VerificarTrazabilidadUseCase(self.db, self.asientos, self.verificador, self.periodos)
    def registrar_deterioro(self):
        """``RegistrarDeterioroUseCase`` con las dependencias del módulo."""
        return RegistrarDeterioroUseCase(self.db, self.activos, self.valoraciones, self.contabilizador,
                                         notificador=self.notificador)
    def cambiar_a_valor_razonable(self):
        """``CambiarAValorRazonableUseCase`` con las dependencias del módulo."""
        return CambiarAValorRazonableUseCase(self.db, self.activos, self.valoraciones, self.valorador, self.contabilizador)
    def consultar_depreciacion(self):
        """``ConsultarDepreciacionUseCase`` con las dependencias del módulo."""
        return ConsultarDepreciacionUseCase(self.activos, self.valoraciones, self.config)
    def registrar_cotizacion(self):
        """``RegistrarCotizacionUseCase`` con las dependencias del módulo."""
        return RegistrarCotizacionUseCase(self.db, self.cotizaciones, self.activos, self.valoraciones, self.contabilizador)
    def modificar_cotizacion(self):
        """``ModificarCotizacionUseCase`` con las dependencias del módulo."""
        return ModificarCotizacionUseCase(self.db, self.cotizaciones, self.auditoria)
    def estado_resultados(self):
        """``GenerarEstadoResultadosUseCase`` con las dependencias del módulo."""
        return GenerarEstadoResultadosUseCase(self.db, self.periodos, self.reportes, self.constructor_estado, self.auditoria,
                                              self.notificador)
    def informe_revelaciones(self):
        """``GenerarInformeRevelacionesUseCase`` con las dependencias del módulo."""
        return GenerarInformeRevelacionesUseCase(
            self.db, self.periodos, self.reportes, self.constructor_informe, self.auditoria, self.notificador,
        )
    def exportar(self):
        """``ExportarReporteUseCase`` con las dependencias del módulo."""
        return ExportarReporteUseCase(self.periodos, self.reportes)
    def consultar_auditoria(self):
        """``ConsultarAuditoriaFinancieraUseCase`` con las dependencias del módulo."""
        return ConsultarAuditoriaFinancieraUseCase(self.auditoria)
    def consultar_productos(self):
        """``ConsultarProductosAgricolasUseCase`` con las dependencias del módulo."""
        return ConsultarProductosAgricolasUseCase(self.valoraciones)
