import re

PASSWORD = re.compile(
    r"^(?=.*[A-Z])(?=.*\d)(?=.*[@#$%^&+=!]).{8,}$"
)

NOMBRE = re.compile(
    r"^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$"
)

TELEFONO = re.compile(
    r"^\d{7,15}$"
)
