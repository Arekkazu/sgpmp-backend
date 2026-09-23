from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.domain.entities.activo_biologico import DatosConsolidados, EventoAuditoria
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.indicadores_repository import IndicadoresRepository
from src.biological_assets.infrastructure.dto.datos_consolidados_dto import DatosConsolidadosDTO
from src.identity_access.domain.repositories.rol_repository import RolRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, NotFoundError

# INC-M02-92-G93: RF-50 exige registrar el "módulo solicitante" en la
# auditoría. Las identidades técnicas de consumidores analíticos creadas para
# ese fin (INC-M02-90-G92) siguen el patrón de nombre 'Integración M0<n>' —
# cualquier otro rol (humano, viendo su propio módulo) conserva el valor
# histórico 'modulo2'.
_PATRON_ROL_MODULO = re.compile(r'^integraci[oó]n\s+m0*(\d+)$', re.IGNORECASE)


class ConsultarDatosConsolidadosUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        indicadores_repo: IndicadoresRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
        rol_repo: RolRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.indicadores_repo = indicadores_repo
        self.bitacora_repo = bitacora_repo
        self.rol_repo = rol_repo

    def execute(
        self,
        id_activo: int,
        dto: DatosConsolidadosDTO,
        usuario: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> DatosConsolidados:
        activo = self.activo_repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe en los registros del sistema.',
            )

        asociacion_activa = self.activo_repo.obtener_asociacion_activa(id_activo)
        if asociacion_activa is not None and not asociacion_activa.es_activo_infraestructura:
            raise ConflictError(
                code='INCONSISTENCIA_JERARQUICA',
                message=(
                    f'El activo mantiene una asociación vigente con la infraestructura '
                    f'"{asociacion_activa.nombre_infraestructura}", la cual está inactiva. '
                    f'Regulariza la jerarquía del activo antes de consultar datos consolidados.'
                ),
            )

        resultado = self.indicadores_repo.obtener_datos_consolidados(
            id_activo=id_activo,
            tipo_dato=dto.tipo_dato,
            fecha_inicio=dto.fecha_inicio,
            fecha_fin=dto.fecha_fin,
            pagina=dto.pagina,
            page_size=dto.page_size,
        )

        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen='RF50', tipo_evento='DATOS_ANALITICOS_CONSULTADOS',
            clasificacion_biologica='ACCESO_DATOS', resultado='EXITOSO',
            severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=id_activo,
            detalle_tecnico={'tipo_dato': dto.tipo_dato},
            id_usuario_responsable=usuario.id_usuario,
            modulo_consumidor=self._resolver_modulo_consumidor(usuario.id_rol),
        ))

        return resultado

    def _resolver_modulo_consumidor(self, id_rol: int) -> str:
        """Deriva qué módulo consumió el dato, para RF-50/RF-52 (INC-M02-92-G93).

        Antes de esto el campo quedaba siempre con el default `'modulo2'` de
        `EventoAuditoria` — inútil para identificar el módulo externo real que
        consultó (ver hallazgo de `estado_M02.md`, RF-50).
        """
        if self.rol_repo is None:
            return 'modulo2'
        rol = self.rol_repo.obtener_por_id(id_rol)
        if rol is None:
            return 'modulo2'
        match = _PATRON_ROL_MODULO.match(rol.nombre_rol.strip())
        if not match:
            return 'modulo2'
        return f'modulo{int(match.group(1))}'
