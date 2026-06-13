"""Value object ``Contrasena`` del dominio de identidad.

Encapsula la política de contraseñas y el hashing. El dominio nunca maneja la
contraseña en texto plano más allá del instante de construirla o verificarla:
hacia afuera solo existe el ``hash``. Esto concentra en un único lugar la regla
"qué es una contraseña válida" y "cómo se cifra/verifica", que antes estaban
repartidas entre el repositorio (al crear) y el caso de uso de login (al
verificar).

Nota de diseño: se importa ``bcrypt`` (librería pura de hashing, sin I/O ni
framework) dentro del dominio porque el cifrado de credenciales es una *regla
de dominio*, no un detalle de infraestructura. Una variante más estricta
inyectaría un puerto ``Hasher``; aquí se prioriza la claridad del ejemplo.
"""
from __future__ import annotations

from dataclasses import dataclass

import bcrypt

from src.shared.errors import ValidationError
from src.shared.regex import PASSWORD


@dataclass(frozen=True)
class Contrasena:
    """Contraseña de usuario representada por su hash bcrypt.

    No se instancia directamente: usar :meth:`desde_texto_plano` para una
    contraseña nueva (valida la política y cifra) o :meth:`desde_hash` para
    reconstruirla desde un hash ya almacenado en base de datos.

    Attributes:
        hash: Hash bcrypt de la contraseña. Es el único dato que se persiste.
    """

    hash: str

    @classmethod
    def desde_texto_plano(cls, texto: str) -> "Contrasena":
        """Crea una contraseña validando la política de seguridad y cifrándola.

        Args:
            texto: Contraseña en texto plano tal como la escribió el usuario.

        Returns:
            Instancia con el hash bcrypt ya calculado.

        Raises:
            ValidationError: Si no cumple la política (mínimo 8 caracteres, una
                mayúscula, un número y un carácter especial). HTTP 400.
        """
        if not PASSWORD.match(texto):
            raise ValidationError(
                code="CONTRASENA_INSEGURA",
                message=(
                    "La contraseña debe tener mínimo 8 caracteres, "
                    "una mayúscula, un número y un carácter especial."
                ),
                field="contrasena",
            )
        hash_calculado = bcrypt.hashpw(texto.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        return cls(hash_calculado)

    @classmethod
    def cifrar(cls, texto: str) -> "Contrasena":
        """Cifra una contraseña ya validada, sin volver a aplicar la política.

        A diferencia de :meth:`desde_texto_plano`, no valida la política: se usa
        en los flujos de cambio y restablecimiento, donde el DTO de entrada
        (``CambiarContrasenaDTO`` / ``RestablecerContrasenaDTO``) ya verificó los
        requisitos antes de llegar al dominio. Evita rechazar contraseñas válidas
        por la divergencia entre la política del DTO y la de :data:`PASSWORD`.

        Args:
            texto: Contraseña en texto plano ya validada por la capa de entrada.

        Returns:
            Instancia con el hash bcrypt ya calculado.
        """
        hash_calculado = bcrypt.hashpw(texto.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        return cls(hash_calculado)

    @classmethod
    def desde_hash(cls, hash_almacenado: str) -> "Contrasena":
        """Reconstruye la contraseña desde un hash ya persistido.

        No vuelve a cifrar ni valida la política: el hash ya existe en la base
        de datos. Se usa al mapear una fila ORM a la entidad de dominio.

        Args:
            hash_almacenado: Hash bcrypt leído de la base de datos.

        Returns:
            Instancia que envuelve el hash dado.
        """
        return cls(hash_almacenado)

    def verificar(self, texto_plano: str) -> bool:
        """Indica si un texto plano coincide con esta contraseña.

        Args:
            texto_plano: Candidato a contraseña a comparar contra el hash.

        Returns:
            ``True`` si coincide, ``False`` en caso contrario.
        """
        return bcrypt.checkpw(texto_plano.encode("utf-8"), self.hash.encode("utf-8"))
