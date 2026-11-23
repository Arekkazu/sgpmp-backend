# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-22 | Arekkazu | SEG-M04-01 RF-69: la firma validada al registrar se guarda con la versión |
"""SEG-M04-01: la firma que se valida al registrar tiene que quedar guardada.

Sin ella, poner en sombra, activar y la copia por animal (que la exigen) fallan siempre con
FIRMA_ARTEFACTO_INVALIDA aunque el registro la haya aceptado.
"""
from unittest.mock import Mock

from src.prediction.infrastructure.models.version_modelo_model import VersionModeloModel
from src.prediction.infrastructure.repositories.version_modelo_repository import SqlAlchemyVersionModeloRepository
from tests.prediction.test_rfc010_version_por_animal_y_sombra import _version


def test_guardar_persiste_la_firma_del_artefacto():
    db = Mock()
    version = _version()
    version.firma_artefacto = "f" * 64

    SqlAlchemyVersionModeloRepository(db).guardar(version)

    orm = db.add.call_args.args[0]
    assert isinstance(orm, VersionModeloModel)
    assert orm.firma_artefacto == "f" * 64
