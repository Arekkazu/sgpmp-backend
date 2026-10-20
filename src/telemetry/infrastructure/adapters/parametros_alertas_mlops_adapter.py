from src.configuration.domain.entities.parametro_mlops import RF57_CONFIANZA, numero_configurado
from src.telemetry.domain.repositories.parametros_alertas_port import ParametrosAlertasPort


class ParametrosAlertasMLOpsAdapter(ParametrosAlertasPort):
    def __init__(self, parametros_repo):
        self.parametros_repo = parametros_repo

    def obtener_confianza_edge_ia(self):
        return numero_configurado(self.parametros_repo.obtener([RF57_CONFIANZA]), RF57_CONFIANZA,
                                 minimo='0.70', maximo='0.95')
