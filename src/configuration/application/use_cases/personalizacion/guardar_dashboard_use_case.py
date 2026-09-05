"""Caso de uso: Guardar configuración del dashboard del usuario (PATCH RF-28).

Rechaza, en el orden en que el RF enumera sus flujos alternos: perfil modificado
durante la edición (409), widget inexistente (400), widget fuera del alcance del
rol (403), indicador activo inexistente (400) y, ya en el dominio, límite de 12
widgets (400), coordenadas o span inválidos (400) y solapamiento de celdas (409).

Todo se valida antes de tocar la base: una configuración inválida no puede dejar
un cambio parcial persistido.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.dashboard_layout import DashboardLayout, WidgetConfig
from src.configuration.domain.repositories.dashboard_layout_repository import DashboardLayoutRepository
from src.configuration.domain.repositories.widget_repository import WidgetRepository
from src.configuration.infrastructure.dto.guardar_dashboard_dto import GuardarDashboardDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AuthorizationError, ConflictError, ValidationError


class GuardarDashboardUseCase:

    def __init__(
        self,
        db: Session,
        dashboard_repo: DashboardLayoutRepository,
        widget_repo: WidgetRepository,
    ) -> None:
        self.db = db
        self.dashboard_repo = dashboard_repo
        self.widget_repo = widget_repo

    def execute(self, dto: GuardarDashboardDTO, usuario_actual: UsuarioActual) -> DashboardLayout:
        self._verificar_perfil_vigente(dto, usuario_actual)
        self._verificar_catalogo(dto, usuario_actual)

        grid = [
            WidgetConfig(
                id_widget=w.id_widget,
                posicion_fila=w.posicion_fila,
                posicion_columna=w.posicion_columna,
                span_columnas=w.span_columnas,
                visible=w.visible,
                orden=w.orden,
            )
            for w in dto.layout_config
        ]

        existente = self.dashboard_repo.obtener_por_usuario(usuario_actual.id_usuario)

        try:
            if existente is not None:
                existente.actualizar(grid=grid, active_widget=dto.active_widget)
                resultado = self.dashboard_repo.actualizar(existente)
            else:
                nuevo = DashboardLayout.crear(
                    id_usuario=usuario_actual.id_usuario,
                    grid=grid,
                    active_widget=dto.active_widget,
                )
                resultado = self.dashboard_repo.guardar(nuevo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return resultado

    def _verificar_perfil_vigente(
        self,
        dto: GuardarDashboardDTO,
        usuario_actual: UsuarioActual,
    ) -> None:
        if dto.version_perfil is None:
            return
        version_actual = self.dashboard_repo.version_perfil(usuario_actual.id_usuario)
        if version_actual is not None and version_actual != dto.version_perfil:
            raise ConflictError(
                code="CONFLICTO_PERFIL_MODIFICADO",
                message=(
                    "Conflicto de datos: No se pudo actualizar la personalización del "
                    "dashboard porque su configuración de perfil ha sido modificada "
                    "recientemente. Por favor, refresque la interfaz."
                ),
                field="version_perfil",
            )

    def _verificar_catalogo(
        self,
        dto: GuardarDashboardDTO,
        usuario_actual: UsuarioActual,
    ) -> None:
        catalogo = self.widget_repo.obtener_activos()
        ids_catalogo = {w.id_widget for w in catalogo}
        claves_catalogo = {w.clave for w in catalogo}

        pedidos = [w.id_widget for w in dto.layout_config]
        desconocidos = sorted(set(pedidos) - ids_catalogo)
        if desconocidos:
            raise ValidationError(
                code="WIDGET_INEXISTENTE",
                message=(
                    "Tipo de widget inexistente: no existe un widget con identificador "
                    f"{desconocidos[0]} en el catálogo del dashboard."
                ),
                field="id_widget",
            )

        legibles = self.widget_repo.ids_legibles_por_rol(usuario_actual.id_rol)
        if set(pedidos) - legibles:
            raise AuthorizationError(
                code="WIDGET_NO_AUTORIZADO",
                message=(
                    "Acceso denegado: El indicador o panel solicitado no está disponible "
                    "para su nivel de permisos o rol asignado."
                ),
                field="id_widget",
            )

        claves_desconocidas = sorted(set(dto.active_widget) - claves_catalogo)
        if claves_desconocidas:
            raise ValidationError(
                code="ACTIVE_WIDGET_INEXISTENTE",
                message=(
                    "Indicador inexistente: "
                    f"'{claves_desconocidas[0]}' no corresponde a ningún widget del catálogo."
                ),
                field="active_widget",
            )
