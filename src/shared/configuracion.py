"""Validación de variables de entorno al arranque.

Sigue el patrón de ``src/shared/database.py`` (que falla con ``RuntimeError``
si falta ``DATABASE_URL``): levantar el proceso con configuración rota es
peor que no levantarlo — el fallo llega tarde, en runtime, y se confunde con
un bug de negocio.

Reglas (QA V2 M01, TC-DIS-22/24/27):

- ``SECRET_KEY`` siempre obligatoria: sin ella el primer JWT revienta en el
  login.
- ``COOKIE_SAMESITE`` / ``COOKIE_SECURE`` / ``JWT_LEEWAY_SECONDS``: si están
  seteadas, su valor debe ser válido — un typo (``COOKIE_SAMESITE=non``)
  equivale en la práctica a no emitir la cookie de refresco y matar la sesión
  al navegar.
- **En producción** (``ENV=production``) las dos variables de cookie son
  obligatorias: sin ellas la política queda al azar del fallback y el
  despliegue puede arrancar con una cookie que el navegador nunca enviará.
- Fuera de producción son opcionales (fallback al comportamiento previo) para
  no romper el desarrollo local.
"""
import logging
import os

logger = logging.getLogger(__name__)

VALORES_SAMESITE = {"none", "lax", "strict"}
VALORES_SECURE_VERDADEROS = {"1", "true", "yes", "si", "sí"}
VALORES_SECURE_FALSOS = {"0", "false", "no"}


def _leer_variable(nombre: str) -> str | None:
    valor = os.getenv(nombre)
    if valor is None:
        return None
    return valor.strip()


def validar_configuracion() -> None:
    """Lanza ``RuntimeError`` con todos los problemas de configuración.

    Acumula todos los incumplimientos en una sola lista para que el operador
    corrija todo de una vez, en vez de iterar arranque a arranque.
    """
    problemas: list[str] = []

    secret_key = _leer_variable("SECRET_KEY")
    if not secret_key:
        problemas.append(
            "Falta la variable de entorno SECRET_KEY (obligatoria para firmar los JWT)."
        )

    samesite = _leer_variable("COOKIE_SAMESITE")
    if samesite is not None and samesite.lower() not in VALORES_SAMESITE:
        problemas.append(
            f"COOKIE_SAMESITE='{samesite}' no es válida. Usa una de: "
            f"{', '.join(sorted(VALORES_SAMESITE))}."
        )

    secure = _leer_variable("COOKIE_SECURE")
    if secure is not None and secure.lower() not in (
        VALORES_SECURE_VERDADEROS | VALORES_SECURE_FALSOS
    ):
        problemas.append(
            f"COOKIE_SECURE='{secure}' no es válida. Usa true o false."
        )

    leeway = _leer_variable("JWT_LEEWAY_SECONDS")
    if leeway is not None:
        try:
            leeway_valor = int(leeway)
            if leeway_valor < 0:
                raise ValueError
        except ValueError:
            problemas.append(
                f"JWT_LEEWAY_SECONDS='{leeway}' no es válida. Usa un entero >= 0."
            )

    es_produccion = _leer_variable("ENV") == "production"
    if es_produccion and (not samesite or not secure):
        problemas.append(
            "ENV=production exige COOKIE_SECURE y COOKIE_SAMESITE explícitas: "
            "sin ellas la cookie de refresco queda al fallback y la sesión "
            "puede morir al navegar. Revisa el .env.example y confirma que "
            "docker-compose.yml las reenvía al contenedor."
        )

    if problemas:
        detalle = "\n  - ".join(problemas)
        raise RuntimeError(
            "Configuración de entorno inválida, la API no puede arrancar:\n  - "
            + detalle
        )

    _advertir_riesgo_cross_site(es_produccion, samesite, secure)


def _advertir_riesgo_cross_site(
    es_produccion: bool, samesite: str | None, secure: str | None
) -> None:
    """Avisa (sin bloquear) de una combinación sospechosa en no-producción.

    Cookie sin flags + origins CORS que no son localhost: si el front vive en
    otro sitio (dominio registrable distinto), la cookie Strict sin Secure no
    viajará y el refresh fallará de forma intermitente.
    """
    if es_produccion or samesite is not None or secure is not None:
        return
    origins = [
        o.strip().rstrip("/")
        for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
        if o.strip()
    ]
    if any(not o.startswith(("http://localhost", "http://127.0.0.1")) for o in origins):
        logger.warning(
            "COOKIE_SECURE/COOKIE_SAMESITE sin definir con ALLOWED_ORIGINS "
            "no-localhost: si el front está en otro dominio registrable, la "
            "cookie de refresco no viajará (QA TC-DIS-22/24/27)."
        )
