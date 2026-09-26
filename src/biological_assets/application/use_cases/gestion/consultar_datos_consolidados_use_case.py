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
from src.shared.errors import BusinessRuleError, ConflictError, InfrastructureError, NotFoundError

# INC-M02-92-G93: RF-50 exige registrar el "módulo solicitante" en la
# auditoría. Las identidades técnicas de consumidores analíticos creadas para
# ese fin (INC-M02-90-G92) siguen el patrón de nombre 'Integración M0<n>' —
# cualquier otro rol (humano, viendo su propio módulo) conserva el valor
# histórico 'modulo2'.
_PATRON_ROL_MODULO = re.compile(r'^integraci[oó]n\s+m0*(\d+)$', re.IGNORECASE)
MODULO_PROPIO = 'modulo2'

# INC-M02-93-G93 (RF-50 FA-03): la validación de "métricas de peso
# insuficientes" solo aplica a M06 -- RF-50 mismo distingue "políticas de
# consistencia fuerte para consultas críticas (ej. M06 - valoración
# financiera)" de la "consistencia eventual" del resto de consumidores (ej.
# M08 dashboards). Aplicarla a todos habría sido una regresión: hoy Admin/
# Productor/Veterinario/Ingeniero reciben 200 con metricas_actuales en null
# cuando no hay peso, comportamiento que RF-50 no prohíbe para ellos.
_MODULO_CONSISTENCIA_FUERTE = 'modulo6'
_TIPOS_DATO_CON_METRICAS = {'metricas', 'todos'}

# RF-50 FA "Fallo de normalización de datos": magnitudes físicas que nunca pueden
# ser negativas. ponytail: solo el signo; rangos plausibles por especie requieren
# un catálogo en M09 que no existe (mismo límite que el umbral de RF-51).
_METRICAS_NO_NEGATIVAS = ('peso_actual', 'biomasa_total', 'cantidad_actual')


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

        modulo_consumidor = self._resolver_modulo_consumidor(usuario.id_rol)

        if modulo_consumidor == _MODULO_CONSISTENCIA_FUERTE and dto.tipo_dato in _TIPOS_DATO_CON_METRICAS:
            total_peso = self.indicadores_repo.contar_metricas_peso_en_rango(
                id_activo, dto.fecha_inicio, dto.fecha_fin,
            )
            if total_peso == 0:
                raise BusinessRuleError(
                    code='METRICAS_PESO_INSUFICIENTES',
                    message=(
                        f'Información incompleta: El activo {id_activo} no registra métricas de '
                        f'peso necesarias para el cálculo de transformación biológica en el rango '
                        f'de fechas solicitado.'
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

        # Antes de auditar el consumo: una exportación cancelada no se consumió.
        metricas = resultado.secciones.metricas_actuales
        if any((metricas.get(campo) or 0) < 0 for campo in _METRICAS_NO_NEGATIVAS):
            raise InfrastructureError(
                code='METRICAS_CORRUPTAS',
                message=(
                    f'Error de consistencia interna: Se detectaron métricas corruptas para el activo '
                    f'{id_activo}. La exportación de datos se ha cancelado para proteger la integridad '
                    'de los modelos analíticos.'
                ),
            )

        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen='RF50', tipo_evento='DATOS_ANALITICOS_CONSULTADOS',
            clasificacion_biologica='ACCESO_DATOS', resultado='EXITOSO',
            severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=id_activo,
            detalle_tecnico={'tipo_dato': dto.tipo_dato},
            id_usuario_responsable=usuario.id_usuario,
            modulo_consumidor=modulo_consumidor,
        ))

        return resultado

    def _resolver_modulo_consumidor(self, id_rol: int) -> str:
        return resolver_modulo_consumidor(self.rol_repo, id_rol)


def resolver_modulo_consumidor(rol_repo: RolRepository | None, id_rol: int) -> str:
    """Deriva qué módulo consumió el dato, para RF-50/RF-52 (INC-M02-92-G93).

    Antes de esto el campo quedaba siempre con el default `'modulo2'` de
    `EventoAuditoria` — inútil para identificar el módulo externo real que
    consultó (ver hallazgo de `estado_M02.md`, RF-50). Es función de módulo
    (no solo método) porque el limitador de tasa de RF-50 necesita la misma
    identidad para agrupar su contador por módulo consumidor.
    """
    if rol_repo is None:
        return MODULO_PROPIO
    rol = rol_repo.obtener_por_id(id_rol)
    if rol is None:
        return MODULO_PROPIO
    match = _PATRON_ROL_MODULO.match(rol.nombre_rol.strip())
    if not match:
        return MODULO_PROPIO
    return f'modulo{int(match.group(1))}'
