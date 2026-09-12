FROM python:3.13-slim

WORKDIR /app

# NO se instala nada con apt-get, y es deliberado.
#
# Antes esta imagen instalaba `gcc` y `libpq-dev` para compilar ruedas de las
# dependencias. Ninguno de los dos hace falta:
#   - requirements.txt usa `psycopg2-binary`, no `psycopg2`. La rueda binaria
#     trae su propio libpq embebido (se comprueba con
#     `python -c "import psycopg2; print(psycopg2.__version__)"`, que reporta
#     "pq3"), asi que no necesita ni las cabeceras de desarrollo ni libpq5.
#   - Todas las demas dependencias publican ruedas manylinux para cp313
#     (cryptography, pillow, reportlab, bcrypt, pydantic_core, grpcio), asi que
#     pip nunca compila nada y `gcc` jamas se usa.
#
# Quitarlos resuelve dos cosas a la vez:
#   1. El compilador ya no viaja en la imagen de produccion. gcc solo servia
#      durante la construccion; en tiempo de ejecucion era superficie de
#      ataque sin ninguna funcion.
#   2. Desaparece el aviso DL3008 de Hadolint (versiones de apt sin fijar) sin
#      tener que fijar versiones de Debian. Eso importa porque Dokploy
#      construye la imagen en CADA despliegue: una version fijada que Debian
#      rote fuera del mirror convierte un despliegue rutinario en un fallo de
#      build. Al no instalar paquetes, el problema no existe.
#
# Si en el futuro alguna dependencia deja de publicar rueda y pip intenta
# compilar, el build fallara de forma ruidosa en `pip install` con un error de
# compilador ausente. Ese es el momento de reevaluar: primero buscar una
# alternativa con rueda, y solo si no hay, volver a instalar gcc en una etapa
# de construccion aparte (multi-stage) para que no llegue a la imagen final.

COPY requirements.txt .
COPY vendor ./vendor
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# --uid 1000 explicito (DL3066: un UID no numerico puede no ser resoluble por
# el host). 1000 NO es un valor nuevo: es exactamente el que `useradd` ya
# asignaba por defecto en python:3.13-slim, verificado con
# `docker run --rm python:3.13-slim sh -c 'useradd --create-home appuser && id -u appuser'`.
#
# Es importante que sea 1000 y no otro numero: los volumenes de dev, test y
# produccion (sgpmp_modelos_prod y equivalentes) ya tienen archivos con
# propietario 1000. Cambiar el UID a cualquier otro valor dejaria al proceso
# sin permiso de escritura sobre datos existentes -- RF-26 (logotipos) y el
# almacenamiento de modelos dejarian de funcionar despues del despliegue, sin
# ningun error en el build que lo anticipe. Hacer explicito lo que ya ocurria
# es todo el cambio; no hay migracion de permisos que ejecutar.
RUN useradd --create-home --uid 1000 appuser
# `USER 1000` y no `USER appuser`: DL3066 exige el UID numerico en la
# directiva, no solo en useradd. El usuario sigue existiendo en /etc/passwd,
# asi que `id` y las herramientas que resuelven el nombre siguen funcionando
# igual (verificado dentro del contenedor: uid=1000(appuser) gid=1000(appuser)).
USER 1000

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
