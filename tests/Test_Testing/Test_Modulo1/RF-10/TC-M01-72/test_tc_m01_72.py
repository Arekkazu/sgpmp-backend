from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.identity_access.application.use_cases.auditoria.archivar_auditoria_use_case import (
    ArchivarAuditoriaUseCase,
)


def test_tc_m01_72_archivar_registros_mayores_a_12_meses():
    """
    TC-M01-072
    Verificar archivado de registros con antigüedad superior a 12 meses.

    RF relacionado: RF-10
    Resultado esperado:
    - Registros con antigüedad <= 12 meses permanecen recientes.
    - Registros con antigüedad > 12 meses son archivados.
    - El archivado no elimina los registros.
    """

    # Arrange
    eventos_repo = MagicMock()
    db = MagicMock()

    eventos_repo.adquirir_bloqueo_archivado.return_value = True

    # Simulamos que se archivó un registro antiguo
    eventos_repo.archivar_eventos_anteriores.side_effect = [
        1,  # Primer lote: se archivó 1 evento
        0,  # Segundo intento: no hay más eventos por archivar
    ]

    use_case = ArchivarAuditoriaUseCase(
        eventos_repo=eventos_repo,
        db=db,
    )

    fecha_referencia = datetime(
        2026,
        6,
        15,
        tzinfo=timezone.utc,
    )

    # Act
    resultado = use_case.execute(
        fecha_referencia=fecha_referencia
    )

    # Assert

    # Se debe adquirir el bloqueo para ejecutar el archivado
    assert resultado.bloqueo_adquirido is True

    # Debe haberse archivado un evento antiguo
    assert resultado.eventos_archivados == 1

    # Debe procesarse un lote
    assert resultado.lotes_procesados == 1

    # El proceso no debe alcanzar el límite máximo
    assert resultado.limite_alcanzado is False

    # Verificamos que el repositorio recibió la fecha de corte correcta.
    # 15/06/2026 - 12 meses = 15/06/2025
    eventos_repo.archivar_eventos_anteriores.assert_called_with(
        fecha_corte=datetime(
            2025,
            6,
            15,
            tzinfo=timezone.utc,
        ),
        limite=5000,
    )

    # El proceso debe confirmar los cambios
    db.commit.assert_called_once()