import re

PASSWORD = re.compile(
    r"^(?=.*[A-Z])(?=.*\d)(?=.*[@#$%^&+=!]).{8,}$"
)
