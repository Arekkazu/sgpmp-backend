"""Caso de uso: Aplicar una plantilla a una especie destino (RF-32).

Reemplaza las configuraciones activas (ciclos, métricas, umbrales, patologías)
de la especie destino con las del snapshot de la plantilla. Registra el evento
en `aplicaciones_plantillas` con before/after para trazabilidad.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.aplicacion_plantilla import AplicacionPlantilla
from src.configuration.domain.esquema_plantilla import es_compatible, versiones_compatibles
from src.configuration.domain.repositories.aplicacion_plantilla_repository import AplicacionPlantillaRepository
from src.configuration.domain.repositories.ciclo_biologico_repository import CicloBiologicoRepository
from src.configuration.domain.repositories.especie_patologia_repository import EspeciePatologiaRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.repositories.metrica_produccion_repository import MetricaProduccionRepository
from src.configuration.domain.repositories.plantilla_repository import PlantillaRepository
from src.configuration.domain.repositories.umbral_ambiental_repository import UmbralAmbientalRepository
from src.configuration.infrastructure.dto.aplicar_plantilla_dto import AplicarPlantillaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError, PreconditionFailedError


class AplicarPlantillaUseCase:
    """Aplica una plantilla de configuración sobre la especie destino."""

    def __init__(
        self,
        db: Session,
        plantilla_repo: PlantillaRepository,
        especie_repo: EspecieRepository,
        ciclo_repo: CicloBiologicoRepository,
        metrica_repo: MetricaProduccionRepository,
        umbral_repo: UmbralAmbientalRepository,
        patologia_repo: EspeciePatologiaRepository,
        aplicacion_repo: AplicacionPlantillaRepository,
    ) -> None:
        self.db = db
        self.plantilla_repo = plantilla_repo
        self.especie_repo = especie_repo
        self.ciclo_repo = ciclo_repo
        self.metrica_repo = metrica_repo
        self.umbral_repo = umbral_repo
        self.patologia_repo = patologia_repo
        self.aplicacion_repo = aplicacion_repo

    def execute(
        self, id_plantilla: int, dto: AplicarPlantillaDTO, usuario_actual: UsuarioActual
    ) -> AplicacionPlantilla:
        plantilla = self.plantilla_repo.obtener_por_id(id_plantilla)
        if plantilla is None:
            raise NotFoundError(
                code="PLANTILLA_NO_ENCONTRADA",
                message=f"No existe la plantilla con id {id_plantilla}.",
            )

        schema_version = plantilla.params_snapshot.get('schema_version', 0)
        if not es_compatible(schema_version):
            raise PreconditionFailedError(
                code="VERSION_SNAPSHOT_INCOMPATIBLE",
                message=(
                    f"Incompatibilidad estructural: la plantilla '{plantilla.template_name}' "
                    f"(versión {plantilla.version}) usa schema_version={schema_version} y el "
                    f"sistema solo puede aplicar {list(versiones_compatibles())}. "
                    "Es necesario recrear la plantilla con el formato actual."
                ),
            )

        especie_destino = self.especie_repo.obtener_por_id(dto.id_especie_destino)
        if especie_destino is None:
            raise NotFoundError(
                code="ESPECIE_DESTINO_NO_ENCONTRADA",
                message=f"No existe la especie destino con id {dto.id_especie_destino}.",
                field="id_especie_destino",
            )
        if not especie_destino.es_activo:
            raise BusinessRuleError(
                code="ESPECIE_DESTINO_INACTIVA",
                message="No se puede aplicar una plantilla a una especie inactiva.",
                field="id_especie_destino",
            )

        # Concurrencia optimista sobre la especie destino (fecha_actualizacion, no
        # fecha_creacion: esta última es inmutable y nunca detectaría una edición real).
        ts_db = especie_destino.fecha_actualizacion
        ts_dto = dto.fecha_actualizacion_especie_destino
        if ts_db is not None and ts_dto is not None:
            if ts_db.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
                raise PreconditionFailedError(
                    code="CONFLICTO_CONCURRENCIA",
                    message="La especie destino fue modificada. Recarga y reintenta.",
                )
        elif ts_db != ts_dto:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message="La especie destino fue modificada. Recarga y reintenta.",
            )

        id_dest = dto.id_especie_destino
        snapshot = plantilla.params_snapshot

        before_snapshot = self._capturar_estado(id_dest)

        try:
            self.ciclo_repo.desactivar_todos_por_especie(id_dest)
            self.metrica_repo.desactivar_todas_por_especie(id_dest)
            self.umbral_repo.desactivar_todos_por_especie(id_dest)
            self.patologia_repo.eliminar_todas_de_especie(id_dest)

            for datos in snapshot.get('ciclos_biologicos', []):
                self.ciclo_repo.guardar_desde_snapshot(datos, id_dest)

            for datos in snapshot.get('metricas_produccion', []):
                self.metrica_repo.guardar_desde_snapshot(datos, id_dest, usuario_actual.id_usuario)

            for datos in snapshot.get('umbrales_ambientales', []):
                self.umbral_repo.guardar_desde_snapshot(datos, id_dest, usuario_actual.id_usuario)

            for datos in snapshot.get('patologias', []):
                self.patologia_repo.vincular_desde_snapshot(id_dest, datos)

            after_snapshot = self._capturar_estado(id_dest)

            aplicacion = AplicacionPlantilla.crear(
                id_usuario=usuario_actual.id_usuario,
                id_plantilla=id_plantilla,
                target_config={"id_especie": id_dest},
                fecha_aplicacion=datetime.now(timezone.utc),
                before_snapshot=before_snapshot,
                after_snapshot=after_snapshot,
            )
            registro = self.aplicacion_repo.guardar(aplicacion)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return registro

    def _capturar_estado(self, id_especie: int) -> dict:
        ciclos = self.ciclo_repo.listar_por_especie(id_especie, solo_activas=True)
        metricas = self.metrica_repo.listar_por_especie(id_especie, solo_activas=True)
        umbrales = self.umbral_repo.listar_por_especie(id_especie, solo_activas=True)
        patologias = self.patologia_repo.listar_por_especie(id_especie)

        return {
            "ciclos_biologicos": [
                {"nombre": c.nombre.valor, "duracion_dias": c.duracion_dias.valor, "descripcion": c.descripcion}
                for c in ciclos
            ],
            "metricas_produccion": [
                {
                    "nombre": m.nombre.valor,
                    "unidad_medida": m.unidad_medida,
                    "tipo_medicion": m.tipo_medicion.value,
                    "aplica_a_tipo_activo": m.aplica_a_tipo_activo.value,
                }
                for m in metricas
            ],
            "umbrales_ambientales": [
                {
                    "id_variable_ambiental": u.id_variable_ambiental,
                    "unidad_medida": u.unidad_medida,
                    "valor_min": str(u.valor_min),
                    "valor_max": str(u.valor_max),
                    "niveles": [
                        {
                            "nivel": n.nivel.value,
                            "limite_inferior": str(n.limite_inferior),
                            "limite_superior": str(n.limite_superior),
                        }
                        for n in u.niveles
                    ],
                }
                for u in umbrales
            ],
            "patologias": [
                {"nombre": p.nombre.valor, "descripcion": p.descripcion, "es_activo": p.es_activo}
                for p in patologias
            ],
        }
