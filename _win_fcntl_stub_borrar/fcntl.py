"""Stub NO OFICIAL de `fcntl` solo para poder correr Pytest en Windows local.

`fcntl` es exclusivo de Unix; el buffer de auditoria RF-52 (E1/E3, ver
src/biological_assets/application/use_cases/_registrar_evento_bitacora.py)
lo importa sin guardia de plataforma, asi que en Windows ni siquiera se puede
COLECTAR pytest (falla en conftest.py antes de correr un solo test).

Esta carpeta NO se versiona ni se importa en produccion: solo sirve para que
esta sesion de QA pueda seguir corriendo Pytest localmente. Ver PYTHONPATH en
los comandos de newman/pytest de este repo. flock() aqui es un no-op -- NO
prueba el comportamiento real de locking entre workers, solo evita el
ImportError para poder ejecutar el resto del archivo.
"""
LOCK_EX = 2
LOCK_UN = 8
LOCK_SH = 1
LOCK_NB = 4


def flock(fd, operation):
    return None
