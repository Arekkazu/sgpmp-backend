"""Caso de uso: Aplicar una plantilla a una especie destino (RF-32).

Reemplaza las configuraciones activas (ciclos, métricas, umbrales, patologías)
de la especie destino con las del snapshot de la plantilla. Registra el evento
en `aplicaciones_plantillas` con before/after para trazabilidad.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.application.use_cases.plantillas._auditoria_comun import registrar_intento_fallido
from src.configuration.domain.entities.aplicacion_plantilla import AplicacionPlantilla
from src.configuration.domain.esquema_plantilla import es_compatible, versiones_compatibles
from src.configuration.domain.repositories.aplicacion_plantilla_repository import AplicacionPlantillaRepository
from src.configuration.domain.repositories.auditoria_plantilla_repository import AuditoriaPlantillaRepository
from src.configuration.domain.repositories.ciclo_biologico_repository import CicloBiologicoRepository
from src.configuration.domain.repositories.especie_patologia_repository import EspeciePatologiaRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.repositories.metrica_produccion_repository import MetricaProduccionRepository
from src.configuration.domain.repositories.plantilla_repository import PlantillaRepository
from src.configuration.domain.repositories.umbral_ambiental_repository import UmbralAmbientalRepository
from src.configuration.domain.repositories.variable_ambiental_repository import VariableAmbientalRepository
from src.configuration.infrastructure.dto.aplicar_plantilla_dto import AplicarPlantillaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError


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
        auditoria_repo: AuditoriaPlantillaRepository,
        variable_repo: VariableAmbientalRepository,
    ) -> None:
        self.db = db
        self.plantilla_repo = plantilla_repo
        self.especie_repo = especie_repo
        self.ciclo_repo = ciclo_repo
        self.metrica_repo = metrica_repo
        self.umbral_repo = umbral_repo
        self.patologia_repo = patologia_repo
        self.aplicacion_repo = aplicacion_repo
        self.auditoria_repo = auditoria_repo
        self.variable_repo = variable_repo

    def execute(
        self, id_plantilla: int, dto: AplicarPlantillaDTO, usuario_actual: UsuarioActual
    ) -> AplicacionPlantilla:
        # INC-M09-04-124 (#316): auditar también los intentos fallidos de
        # aplicación (con o sin rollback de datos ya hecho más abajo).
        try:
            return self._ejecutar(id_plantilla, dto, usuario_actual)
        except Exception as exc:
            registrar_intento_fallido(
                self.db,
                self.auditoria_repo,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="APPLY",
                id_plantilla=id_plantilla,
                detalle={
                    "id_especie_destino": dto.id_especie_destino,
                    "error": str(exc),
                },
            )
            raise

    def _ejecutar(
        self, id_plantilla: int, dto: AplicarPlantillaDTO, usuario_actual: UsuarioActual
    ) -> AplicacionPlantilla:
        plantilla = self.plantilla_repo.obtener_por_id(id_plantilla)
        if plantilla is None:
            raise NotFoundError(
                code="PLANTILLA_NO_ENCONTRADA",
                message=f"No existe la plantilla con id {id_plantilla}.",
            )

        # INC-M09-03-122 (#317): el versionado solo cumple su propósito de
        # control de cambios si una versión superada deja de poder aplicarse.
        # RF-31 exige que "una actualización genere una nueva versión, no
        # sobreescriba la original" -- eso implica que la anterior queda
        # superada, no que las dos siguen siendo intercambiables al aplicar.
        vigente = self.plantilla_repo.obtener_ultima_version(plantilla.template_name)
        if vigente is not None and vigente.version != plantilla.version:
            raise BusinessRuleError(
                code="PLANTILLA_VERSION_NO_VIGENTE",
                message=(
                    f"Versión superada: la plantilla '{plantilla.template_name}' "
                    f"(versión {plantilla.version}) ya no es la vigente. La versión "
                    f"actual es la {vigente.version} (id {vigente.id_plantilla}); "
                    "aplique esa o genere una nueva versión de la plantilla que "
                    "quiere usar."
                ),
                field="id_plantilla",
            )

        schema_version = plantilla.params_snapshot.get('schema_version', 0)
        if not es_compatible(schema_version):
            # RF-32 pide 422 para "Incompatibilidad de esquema (Versión Legacy)".
            # El 412 que había aquí venía del flujo homólogo de RF-30, que sin
            # embargo describe la *creación* de plantillas; aplicar una plantilla
            # legacy solo ocurre por esta ruta, así que manda RF-32.
            raise BusinessRuleError(
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
        # El resto del módulo usa 412 para este patrón, pero RF-32 pide
        # explícitamente 409 para su "Conflicto de modificación concurrente" —y es
        # el único RF que gobierna este endpoint, así que aquí manda su letra.
        ts_db = especie_destino.fecha_actualizacion
        ts_dto = dto.fecha_actualizacion_especie_destino
        if ts_db is not None and ts_dto is not None:
            desincronizado = ts_db.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc)
        else:
            desincronizado = ts_db != ts_dto
        if desincronizado:
            raise ConflictError(
                code="CONFLICTO_CONCURRENCIA",
                message=(
                    "Conflicto de concurrencia: Los parámetros de la especie destino han "
                    "cambiado recientemente. Por favor, recargue el resumen para "
                    "visualizar los valores actuales antes de confirmar."
                ),
            )

        id_dest = dto.id_especie_destino
        snapshot = plantilla.params_snapshot

        self._verificar_referencias(snapshot)

        before_snapshot = self._capturar_estado(id_dest)

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

        return registro

    def _verificar_referencias(self, snapshot: dict) -> None:
        """RF-32, flujo alterno "Fallo de consistencia (Referencias huérfanas)".

        Una plantilla guarda un snapshot congelado: nada impide que el catálogo
        maestro cambie después. La única referencia del snapshot a un catálogo
        externo es ``id_variable_ambiental`` de cada umbral —ciclos, métricas y
        patologías viajan por valor y se recrean bajo la especie destino—, así
        que es la que hay que revalidar antes de desactivar nada. Si se aplicara
        sin esta comprobación, el fallo saldría abajo como violación de FK
        (409/500) en vez del 400 con el detalle que pide el RF.
        """
        huerfanas = [
            int(datos['id_variable_ambiental'])
            for datos in snapshot.get('umbrales_ambientales', [])
            if not self._variable_vigente(int(datos['id_variable_ambiental']))
        ]
        if huerfanas:
            raise ValidationError(
                code="REFERENCIAS_HUERFANAS",
                message=(
                    "Inconsistencia detectada: La plantilla contiene parámetros que ya "
                    "no son válidos en el sistema (Detalle: variables ambientales "
                    f"{sorted(set(huerfanas))} inexistentes o inactivas). La operación "
                    "ha sido cancelada."
                ),
            )

    def _variable_vigente(self, id_variable_ambiental: int) -> bool:
        variable = self.variable_repo.obtener_por_id(id_variable_ambiental)
        return variable is not None and variable.es_activo

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
                    "tipo_dato": m.tipo_dato.value,
                    "es_obligatorio": m.es_obligatorio,
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
