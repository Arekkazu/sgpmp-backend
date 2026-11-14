# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77/79/81: outbox y archivos exportados |
"""Registro de los modelos ORM de ``modulo5`` para la resolución de mappers.

Importar este paquete garantiza que todas las clases estén registradas en la
``Base`` compartida antes de que SQLAlchemy resuelva relaciones y FK cruzadas.
"""
from .tipo_alimento_model import TipoAlimentoModel
from .registro_consumo_alimento_model import RegistroConsumoAlimentoModel
from .registro_medicamento_model import RegistroMedicamentoModel
from .ciclo_productivo_model import CicloProductivoModel
from .registro_suministro_model import RegistroSuministroModel
from .acumulado_ciclo_model import AcumuladoCicloModel
from .provision_nic41_model import ProvisionNic41Model
from .auditoria_suministro_model import AuditoriaSuministroModel
from .outbox_provision_m06_model import OutboxProvisionM06Model
from .archivo_exportacion_suministro_model import ArchivoExportacionSuministroModel

__all__ = [
    "TipoAlimentoModel",
    "RegistroConsumoAlimentoModel",
    "RegistroMedicamentoModel",
    "CicloProductivoModel",
    "RegistroSuministroModel",
    "AcumuladoCicloModel",
    "ProvisionNic41Model",
    "AuditoriaSuministroModel",
    "OutboxProvisionM06Model",
    "ArchivoExportacionSuministroModel",
]
