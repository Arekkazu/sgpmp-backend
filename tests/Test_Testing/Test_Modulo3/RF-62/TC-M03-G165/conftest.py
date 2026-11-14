# conftest.py para aislar Test_Testing de los conftest padres que importan main.py
pytest_plugins = []

def pytest_sessionstart(session):
    """Imprime el banner informativo de D7 Resuelto antes de iniciar las pruebas."""
    banner = (
        "\n"
        "=" * 78 + "\n"
        " [BANNER D7 RESUELTO] TC-M03-G165 -- ESTADO DE EVALUACION DE CALIDAD\n"
        "=" * 78 + "\n"
        " * D7 RESUELTO: literal 'VIGENTE'; catálogo {'VIGENTE', 'SUPERADA'}; RFC de aclaración en trámite.\n"
        " * Regla canónica: máximo UNA evaluación VIGENTE por lectura.\n"
        " * Defecto conocido: /evaluar duplica VIGENTES (invariante debe fallar hoy).\n"
        "=" * 78 + "\n"
    )
    print(banner)

