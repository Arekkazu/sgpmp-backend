# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77: alcance, 429 compartido, bajas     |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Caso de uso: generar el reporte de gastos acumulados (RF-77).

Decide síncrono vs. asíncrono según el rango solicitado (R8/R13: > 12 meses
individual, > 6 meses agregado → 202) y orquesta la recolección de líneas de
gasto (período actual + período anterior equivalente para la tendencia)
delegando el cálculo puro en :class:`CalculadoraReporteGasto`.

- Validaciones (paso 2): E2 rango invertido 400, fecha futura 400, E3 inicio
  anterior al ciclo 400, E7 activo sin ciclo 422, infraestructura/especie
  inexistente 404.
- Seguridad (R9): solo datos de activos de las fincas del usuario; un activo
  ajeno responde 403 y los agregados se limitan a sus activos.
- E10 / R15-R16: el límite de generaciones simultáneas lo comparten las
  solicitudes síncronas y las asíncronas (429 con tiempo estimado).
- R6: para un lote con bajas en el período, nota informativa del promedio.

``construir`` arma el reporte sin persistirlo (exportación y regeneración desde
el historial). ``commit()``/``rollback()`` viven aquí.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Union

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import (
    AuthorizationError,
    BusinessRuleError,
    NotFoundError,
    TooManyRequestsError,
    ValidationError,
)
from src.shared.fechas import hoy_usuario
from src.supplies.domain.entities.reporte_gasto import FiltrosReporteGasto, ReporteGasto
from src.supplies.domain.entities.trabajo_reporte_gasto import TrabajoReporteGasto
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.alcance_activo_port import AlcanceActivoPort
from src.supplies.domain.repositories.configuracion_batch_reporte_gasto_repository import (
    ConfiguracionBatchReporteGastoRepository,
)
from src.supplies.domain.repositories.detalle_gasto_read_port import DetalleGastoReadPort
from src.supplies.domain.repositories.reporte_gasto_repository import ReporteGastoRepository
from src.supplies.domain.repositories.trabajo_reporte_gasto_repository import TrabajoReporteGastoRepository
from src.supplies.domain.services.calculadora_reporte_gasto import CalculadoraReporteGasto

_DIAS_UMBRAL_ASYNC_INDIVIDUAL = 366  # > 12 meses (Restricción 8/13 RF-77)
_DIAS_UMBRAL_ASYNC_AGREGADO = 183  # > 6 meses para consultas agregadas (Restricción 13)
_CERO = Decimal("0")
_MINUTOS_POR_TRABAJO = 1

# ponytail: contador por proceso de las generaciones síncronas en curso; con varios
# workers de uvicorn cada uno cuenta las suyas. Si se escala, llevarlo a la BD.
_lock_sincronos = threading.Lock()
_sincronos_en_curso = 0


class GenerarReporteGastosUseCase:
    def __init__(
        self,
        db: Session,
        detalle_port: DetalleGastoReadPort,
        activo_port: ActivoConsultaPort,
        reporte_repo: ReporteGastoRepository,
        trabajo_repo: TrabajoReporteGastoRepository,
        config_repo: ConfiguracionBatchReporteGastoRepository,
        alcance_port: AlcanceActivoPort,
        calculadora: Optional[CalculadoraReporteGasto] = None,
    ) -> None:
        self.db = db
        self.detalle_port = detalle_port
        self.activo_port = activo_port
        self.reporte_repo = reporte_repo
        self.trabajo_repo = trabajo_repo
        self.config_repo = config_repo
        self.alcance_port = alcance_port
        self.calculadora = calculadora or CalculadoraReporteGasto()

    def execute(
        self, filtros: FiltrosReporteGasto, usuario_actual: UsuarioActual,
        formato_exportacion: Optional[str] = None,
    ) -> Union[ReporteGasto, TrabajoReporteGasto]:
        ids_permitidos = self.alcance_port.listar_ids_activos_permitidos(
            usuario_actual.id_usuario, usuario_actual.id_rol
        )
        activo = self._validar(filtros, ids_permitidos)

        if self._requiere_async(filtros):
            self._verificar_cupo()
            return self._encolar(filtros, usuario_actual.id_usuario, ids_permitidos, formato_exportacion)

        with self._cupo_sincrono():
            reporte = self.construir(filtros, usuario_actual.id_usuario, activo, ids_permitidos)
            return self._persistir(reporte)

    def generar_forzado(self, filtros: FiltrosReporteGasto, id_usuario: int,
                        ids_permitidos: Optional[list[int]] = None) -> ReporteGasto:
        """Genera y persiste sin evaluar el umbral ni el cupo (worker del motor async)."""
        activo = self._validar(filtros, ids_permitidos)
        return self._persistir(self.construir(filtros, id_usuario, activo, ids_permitidos))

    def construir_desde_parametros(self, parametros: dict, usuario_actual: UsuarioActual) -> ReporteGasto:
        """Reporte con el estado actual de los datos a partir de parámetros guardados (no persiste)."""
        filtros = FiltrosReporteGasto.desde_dict(parametros)
        ids_permitidos = self.alcance_port.listar_ids_activos_permitidos(
            usuario_actual.id_usuario, usuario_actual.id_rol
        )
        activo = self._validar(filtros, ids_permitidos)
        return self.construir(filtros, usuario_actual.id_usuario, activo, ids_permitidos)

    # ── Validaciones (paso 2, E2, E3, E7, R9) ────────────────────────────────
    def _validar(self, filtros: FiltrosReporteGasto, ids_permitidos: Optional[list[int]]):
        if filtros.fecha_inicio > filtros.fecha_fin:
            raise ValidationError(
                code="RANGO_FECHAS_INVALIDO",
                message=(
                    f"El rango de fechas es inválido. La fecha de inicio ({filtros.fecha_inicio}) "
                    f"no puede ser posterior a la fecha de fin ({filtros.fecha_fin})."
                ),
                field="fecha_inicio_reporte",
            )
        if filtros.fecha_fin > hoy_usuario():
            raise ValidationError(
                code="FECHA_FIN_FUTURA",
                message=(
                    f"El rango de fechas del reporte no puede ser futuro. La fecha de fin ({filtros.fecha_fin}) "
                    "es posterior a la fecha actual del sistema."
                ),
                field="fecha_fin_reporte",
            )

        if filtros.id_activo_biologico is None:
            if filtros.id_infraestructura is None and filtros.id_especie is None:
                raise ValidationError(
                    code="REPORTE_SIN_ALCANCE",
                    message=(
                        "Las consultas agregadas requieren id_infraestructura o id_especie, "
                        "o especificar activo_biologico_id para un reporte individual."
                    ),
                    field="activo_biologico_id",
                )
            if filtros.id_infraestructura is not None and not self.detalle_port.existe_infraestructura(
                filtros.id_infraestructura
            ):
                raise NotFoundError(
                    code="INFRAESTRUCTURA_NO_ENCONTRADA",
                    message=f"La infraestructura {filtros.id_infraestructura} no existe.",
                    field="id_infraestructura",
                )
            if filtros.id_especie is not None and not self.detalle_port.existe_especie(filtros.id_especie):
                raise NotFoundError(
                    code="ESPECIE_NO_ENCONTRADA",
                    message=f"La especie {filtros.id_especie} no existe en el catálogo.",
                    field="id_especie",
                )
            return None

        activo = self.activo_port.obtener(filtros.id_activo_biologico)
        if activo is None:
            raise NotFoundError(
                code="ACTIVO_NO_ENCONTRADO",
                message=f"El activo biológico {filtros.id_activo_biologico} no existe.",
                field="activo_biologico_id",
            )
        if ids_permitidos is not None and filtros.id_activo_biologico not in ids_permitidos:
            raise AuthorizationError(
                code="ACCESO_DENEGADO",
                message=(
                    f"No tiene permisos para consultar los gastos del activo {filtros.id_activo_biologico}. "
                    "Verifique su rol y las fincas asignadas."
                ),
            )
        if activo.fecha_inicio_ciclo is None:
            raise BusinessRuleError(
                code="ACTIVO_SIN_CICLO",
                message=(
                    f"El activo {filtros.id_activo_biologico} no tiene un ciclo productivo registrado. "
                    "No es posible generar el reporte de gastos sin una referencia temporal del ciclo. "
                    "Registre el inicio del ciclo (RF-37) antes de continuar."
                ),
                field="activo_biologico_id",
            )
        if filtros.fecha_inicio < activo.fecha_inicio_ciclo:
            raise ValidationError(
                code="FECHA_INICIO_ANTERIOR_CICLO",
                message=(
                    f"La fecha de inicio del reporte ({filtros.fecha_inicio}) es anterior a la fecha de inicio "
                    f"del ciclo productivo del activo ({activo.fecha_inicio_ciclo}). Ajuste el rango de consulta."
                ),
                field="fecha_inicio_reporte",
            )
        return activo

    def _requiere_async(self, filtros: FiltrosReporteGasto) -> bool:
        umbral = _DIAS_UMBRAL_ASYNC_AGREGADO if filtros.es_agregado else _DIAS_UMBRAL_ASYNC_INDIVIDUAL
        return filtros.dias > umbral

    def tiempo_estimado_minutos(self) -> int:
        return (self.trabajo_repo.contar_activos() + 1) * _MINUTOS_POR_TRABAJO

    # ── Cupo de generaciones simultáneas (E10, R15-R17) ──────────────────────
    def _verificar_cupo(self) -> None:
        limite = self.config_repo.obtener().limite_concurrencia
        if self.trabajo_repo.contar_activos() + _sincronos_en_curso >= limite:
            minutos = self.tiempo_estimado_minutos()
            raise TooManyRequestsError(
                code="LIMITE_CONCURRENCIA_EXCEDIDO",
                message=(
                    "El sistema ha alcanzado el límite de reportes en generación simultánea. Por favor, "
                    f"intente nuevamente en unos minutos. Tiempo estimado de disponibilidad: {minutos} minutos."
                ),
                headers={"Retry-After": str(minutos * 60)},
            )

    @contextmanager
    def _cupo_sincrono(self):
        global _sincronos_en_curso
        with _lock_sincronos:
            self._verificar_cupo()
            _sincronos_en_curso += 1
        try:
            yield
        finally:
            with _lock_sincronos:
                _sincronos_en_curso -= 1

    # ── Camino asíncrono ──────────────────────────────────────────────────────
    def _encolar(self, filtros: FiltrosReporteGasto, id_usuario: int,
                 ids_permitidos: Optional[list[int]], formato_exportacion: Optional[str]) -> TrabajoReporteGasto:
        parametros = {
            **filtros.a_dict(), "ids_permitidos": ids_permitidos, "formato_exportacion": formato_exportacion,
        }
        trabajo = TrabajoReporteGasto(parametros=parametros, id_usuario_solicitante=id_usuario)
        try:
            trabajo = self.trabajo_repo.encolar(trabajo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return trabajo

    # ── Camino síncrono ───────────────────────────────────────────────────────
    def construir(self, filtros: FiltrosReporteGasto, id_usuario: int, activo,
                  ids_permitidos: Optional[list[int]] = None) -> ReporteGasto:
        lineas = self.detalle_port.consultar(
            fecha_inicio=filtros.fecha_inicio,
            fecha_fin=filtros.fecha_fin,
            id_activo_biologico=filtros.id_activo_biologico,
            id_infraestructura=filtros.id_infraestructura,
            id_especie=filtros.id_especie,
            categorias=filtros.categorias_incluidas,
            ids_permitidos=ids_permitidos,
        )

        gasto_anterior, recortado, fecha_recorte = self._periodo_anterior(filtros, activo, ids_permitidos)

        resultado_calc = self.calculadora.calcular(
            lineas=lineas,
            tipo_periodo=filtros.tipo_periodo,
            gasto_periodo_anterior=gasto_anterior,
            periodo_anterior_recortado=recortado,
            fecha_inicio_ciclo_recorte=fecha_recorte,
        )

        gasto_promedio_individuo = None
        causa_no_calculable_promedio = None
        nota_bajas = None
        if activo is not None and activo.es_poblacional:
            if not activo.cantidad_actual:
                causa_no_calculable_promedio = (
                    "La cantidad actual del lote es cero. No es posible calcular el promedio por individuo."
                )
            else:
                gasto_promedio_individuo = resultado_calc.gasto_total_acumulado / activo.cantidad_actual
            bajas = self.detalle_port.contar_bajas(activo.id_activo_biologico, filtros.fecha_inicio, filtros.fecha_fin)
            if bajas:
                nota_bajas = (
                    f"El lote registró {bajas} bajas durante el período consultado. El gasto promedio por "
                    "individuo usa la cantidad actual del lote y no la cantidad promedio del período."
                )

        return ReporteGasto(
            fecha_inicio=filtros.fecha_inicio,
            fecha_fin=filtros.fecha_fin,
            tipo_periodo=filtros.tipo_periodo,
            gasto_total_acumulado=resultado_calc.gasto_total_acumulado,
            desglose_categorias=resultado_calc.desglose_categorias,
            desglose_temporal=resultado_calc.desglose_temporal,
            registros_sin_costo=resultado_calc.registros_sin_costo,
            tendencia=resultado_calc.tendencia,
            id_activo_biologico=filtros.id_activo_biologico,
            id_infraestructura=filtros.id_infraestructura,
            id_especie=filtros.id_especie,
            gasto_promedio_individuo=gasto_promedio_individuo,
            causa_no_calculable_promedio=causa_no_calculable_promedio,
            nota_bajas=nota_bajas,
            sin_datos=resultado_calc.sin_datos,
            id_usuario=id_usuario,
            parametros=filtros.a_dict(),
            lineas=lineas,
        )

    def _persistir(self, reporte: ReporteGasto) -> ReporteGasto:
        try:
            reporte = self.reporte_repo.guardar(reporte)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return reporte

    def _periodo_anterior(self, filtros: FiltrosReporteGasto, activo,
                          ids_permitidos: Optional[list[int]]) -> tuple[Decimal, bool, Optional[date]]:
        """Calcula el gasto del período anterior equivalente (Proceso paso 6 de RF-77)."""
        dias = filtros.dias
        fecha_fin_anterior = filtros.fecha_inicio - timedelta(days=1)
        fecha_inicio_anterior = fecha_fin_anterior - timedelta(days=dias - 1)

        recortado = False
        fecha_recorte: Optional[date] = None
        if (
            activo is not None
            and activo.fecha_inicio_ciclo is not None
            and fecha_inicio_anterior < activo.fecha_inicio_ciclo
        ):
            fecha_inicio_anterior = activo.fecha_inicio_ciclo
            fecha_recorte = activo.fecha_inicio_ciclo
            recortado = fecha_inicio_anterior <= fecha_fin_anterior

        if fecha_inicio_anterior > fecha_fin_anterior:
            return _CERO, False, None

        lineas_anteriores = self.detalle_port.consultar(
            fecha_inicio=fecha_inicio_anterior,
            fecha_fin=fecha_fin_anterior,
            id_activo_biologico=filtros.id_activo_biologico,
            id_infraestructura=filtros.id_infraestructura,
            id_especie=filtros.id_especie,
            categorias=filtros.categorias_incluidas,
            ids_permitidos=ids_permitidos,
        )
        gasto_anterior = sum((l.monto for l in lineas_anteriores if l.monto is not None), _CERO)
        return gasto_anterior, recortado, fecha_recorte
