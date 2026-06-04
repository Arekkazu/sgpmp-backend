from src.identity_access.application.ports.cuentas_ports import CuentasPort


class ActivarCuentaUseCase:

    def __init__(self, cuentas_port: CuentasPort):
        self.cuentas_port = cuentas_port

    def execute(self, token: str) -> None:
        self.cuentas_port.activar_cuenta(token)
