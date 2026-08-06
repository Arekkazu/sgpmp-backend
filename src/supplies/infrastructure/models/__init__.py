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

__all__ = [
    "TipoAlimentoModel",
    "RegistroConsumoAlimentoModel",
    "RegistroMedicamentoModel",
    "CicloProductivoModel",
    "RegistroSuministroModel",
    "AcumuladoCicloModel",
    "ProvisionNic41Model",
    "AuditoriaSuministroModel",
]
