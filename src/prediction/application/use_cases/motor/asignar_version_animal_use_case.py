# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-69/RFC-010: copia automática en sombra para un animal nuevo   |
"""Un animal individual sin versión recibe una propia, en SOMBRA, para que el motor IA lo atienda.

RFC-010 exige que un modelo INDIVIDUAL sea de un animal y que no produzca resultados de otro.
Para no registrar a mano cada animal nuevo, el motor pide esta copia: misma ``.onnx`` y mismas
métricas que la versión vigente de su tipo de modelo, con ``id_activo_biologico`` del animal y
``version_referencia`` apuntando al original. ``detalle_validacion`` deja dicho que no se entrenó
con ese animal. Es idempotente: si el animal ya tiene versión ACTIVO o SOMBRA, la devuelve.
"""
from __future__ import annotations

from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.domain.repositories.catalogo_motor_port import CatalogoMotorPort
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository
from src.shared.errors import BusinessRuleError, NotFoundError

SISTEMA = "motor-ia"


class AsignarVersionAnimalUseCase:
    def __init__(
        self,
        db,
        catalogo: CatalogoMotorPort,
        repo: VersionModeloRepository,
        auditoria_repo: EventoAuditoriaM04Repository,
    ) -> None:
        self._db = db
        self._catalogo = catalogo
        self._repo = repo
        self._auditoria_repo = auditoria_repo

    def execute(self, id_activo: int) -> VersionModelo:
        animal = next(iter(self._catalogo.animales(id_activo)), None)
        if animal is None:
            raise NotFoundError(
                code="ANIMAL_FUERA_DEL_MOTOR",
                message=(
                    f"El activo {id_activo} no es un animal individual vivo, con sensor directo, "
                    "en un área de modelo individual."
                ),
                field="id_activo_biologico",
            )
        if animal.id_version_modelo is not None:
            return self._repo.obtener_por_id(animal.id_version_modelo)

        id_ref = self._catalogo.version_referencia(animal.tipo_modelo)
        ref = self._repo.obtener_por_id(id_ref) if id_ref is not None else None
        if ref is None:
            raise NotFoundError(
                code="SIN_MODELO_DE_REFERENCIA",
                message=f"No hay ninguna versión ACTIVO o SOMBRA de {animal.tipo_modelo} para copiar.",
                field="tipo_modelo",
            )

        copia = VersionModelo.crear(
            tipo_modelo=ref.tipo_modelo,
            formato_artefacto=ref.formato_artefacto,
            ruta_artefacto=ref.ruta_artefacto,
            tamanio_artefacto_bytes=ref.tamanio_artefacto_bytes,
            hash_artefacto_sha256=ref.hash_artefacto_sha256,
            dataset_entrenamiento_hash=ref.dataset_entrenamiento_hash,
            id_proceso_rf71=ref.id_proceso_rf71,
            f1_score=ref.f1_score,
            recall_clase_riesgo_alto=ref.recall_clase_riesgo_alto,
            precision_modelo=ref.precision_modelo,
            accuracy=ref.accuracy,
            roc_auc_score=ref.roc_auc_score,
            recall_por_clase=ref.recall_por_clase,
            matriz_confusion=ref.matriz_confusion,
            compatibilidad_variables=ref.compatibilidad_variables,
            fecha_entrenamiento=ref.fecha_entrenamiento,
            version_referencia=ref.id_version_modelo,
            id_activo_biologico=id_activo,
            fuente_datos=ref.fuente_datos,
        )
        copia.validar_y_asignar_estado()
        if copia.estado_version != "APROBADO":
            raise BusinessRuleError(
                code="COPIA_NO_APROBADA",
                message=f"La versión {ref.id_version_modelo} ya no pasa la validación: {copia.detalle_validacion}",
            )
        detalle_aprobacion = copia.detalle_validacion or "Evaluación automática de métricas"
        copia.poner_en_sombra()
        origen = (
            f"Copia automática de la versión {ref.id_version_modelo} para el activo {id_activo}: "
            "mismo artefacto, no se entrenó con este animal."
        )
        copia.detalle_validacion = f"{origen} {detalle_aprobacion}"

        try:
            copia = self._repo.guardar(copia)
            for anterior, nuevo, motivo in (
                (None, "EN_VALIDACION", origen),
                ("EN_VALIDACION", "APROBADO", detalle_aprobacion),
                ("APROBADO", "SOMBRA", "Puesta en sombra automática para el motor IA"),
            ):
                self._repo.registrar_historial(
                    id_version_modelo=copia.id_version_modelo,
                    estado_anterior=anterior,
                    estado_nuevo=nuevo,
                    tipo_actor="SISTEMA",
                    id_sistema=SISTEMA,
                    id_proceso_rf71=ref.id_proceso_rf71,
                    motivo=motivo,
                )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        self._auditoria_repo.registrar(
            tipo_evento="VERSION_REGISTRADA",
            tipo_actor="SISTEMA",
            id_sistema=SISTEMA,
            id_referencia=str(copia.id_version_modelo),
            entidad_referencia="version_modelo",
            resultado_operacion="EXITOSO",
            severidad_evento="INFO",
            payload_evento={"copia_de": ref.id_version_modelo, **copia._snapshot()},
        )
        try:
            self._db.commit()
        except Exception:  # la versión ya quedó registrada aunque la auditoría falle
            self._db.rollback()
        return copia
