#!/usr/bin/env bash
#
# Provisiona la base de pruebas a partir del esquema de la base de desarrollo.
#
# Por qué existe: el baseline de Alembic (f7fe43537842) es un no-op deliberado —
# el esquema hasta ese punto se construyó a mano, módulo por módulo, vía SQL
# suelto. Eso significa que `alembic upgrade head` NO puede levantar una base
# desde cero: solo aplica los deltas posteriores, y falla en cuanto intenta
# ALTERar una tabla que no existe. Por eso la base de pruebas quedó con solo
# `modulo1` y sellada en el baseline, y la integración de módulo 9 nunca corrió.
#
# Mientras el baseline siga siendo un no-op, la única fuente fiel del esquema
# completo es la base de desarrollo, que sí está en head. Este script la copia
# (esquema + catálogos, sin datos transaccionales) y sella el destino en head,
# de modo que ambas bases quedan alineadas y de ahí en adelante avanzan juntas
# con `alembic upgrade head`.
#
# Solo reemplaza los schemas del proyecto (auditoria + modulo1..9). No toca la
# base de destino ni el schema public: `public` de la base de desarrollo tiene
# tablas de otra aplicación que no pintan nada acá.
#
# Uso:
#   ./scripts/provisionar_pruebas.sh
#   ORIGEN=sgpmp DESTINO=pruebas ./scripts/provisionar_pruebas.sh
#
# Lee la conexión de DATABASE_URL (.env). Requiere pg_dump, psql y el venv.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

ORIGEN="${ORIGEN:-sgpmp}"
DESTINO="${DESTINO:-pruebas}"

# Salvaguarda: este script BORRA la base de destino. Solo se permiten nombres de
# base de pruebas — la misma lista que valida tests/integration/conftest.py.
case "$DESTINO" in
  pruebas|pruebas-integrador|*test*) ;;
  *) echo "ABORTA: '$DESTINO' no parece una base de pruebas." >&2; exit 1 ;;
esac
[ "$ORIGEN" != "$DESTINO" ] || { echo "ABORTA: origen y destino son la misma base." >&2; exit 1; }

URL="$(grep -m1 '^DATABASE_URL=' .env | cut -d= -f2-)"
[ -n "$URL" ] || { echo "ABORTA: no encontré DATABASE_URL en .env" >&2; exit 1; }
USUARIO="$(sed -E 's|.*://([^:]+):.*|\1|' <<<"$URL")"
export PGPASSWORD="$(sed -E 's|.*://[^:]+:([^@]+)@.*|\1|' <<<"$URL")"
HOST="$(sed -E 's|.*@([^:/]+).*|\1|' <<<"$URL")"
PUERTO="$(sed -E 's|.*@[^:]+:([0-9]+)/.*|\1|' <<<"$URL")"
PSQL=(psql -h "$HOST" -p "$PUERTO" -U "$USUARIO" -v ON_ERROR_STOP=1 -q)
DUMP=(pg_dump -h "$HOST" -p "$PUERTO" -U "$USUARIO")

# Catálogos que sí llevan datos: son de referencia y varias migraciones los
# siembran, así que una base sellada en head tiene que tenerlos. Todo lo demás
# (usuarios, eventos, sesiones, registros de negocio) se queda fuera: los tests
# crean lo que necesitan y conftest revierte cada uno en su transacción.
CATALOGOS=(
  modulo1.acciones modulo1.estados_cuentas modulo1.roles modulo1.recursos
  modulo1.permisos modulo1.tipos_eventos modulo1.notificaciones_canal
  modulo1.configuracion_batch_exportacion_auditoria
  modulo9.especies modulo9.variables_ambientales modulo9.ciclos_productivos
  modulo9.tipos_dispositivo_iot modulo9.rangos_calibracion
  modulo9.widgets modulo9.dashboard_layouts_default
)

# El sello solo es veraz si el origen está en head: su esquema refleja entonces
# todas las migraciones. Se comprueba ANTES de tocar nada — si falla a mitad de
# camino, el destino queda con el esquema cargado y sin sellar.
#
# También falla cuando el checkout no conoce la revisión en la que está el
# origen; es el caso típico de correr esto con una migración sin mergear. Mejor
# abortar que dejar la base sellada en una revisión que la rama base desconoce.
echo "==> Comprobando que '$ORIGEN' esté en head"
if ! SALIDA_ALEMBIC="$(DATABASE_URL="${URL%/*}/$ORIGEN" .venv/bin/python -m alembic current 2>&1)"; then
  echo "ABORTA: no pude leer la revisión de '$ORIGEN'." >&2
  echo "$SALIDA_ALEMBIC" | grep -E "ERROR|FAILED" >&2 || true
  echo "Si dice \"Can't locate revision\", el checkout no tiene esa migración: cambia de rama o mergéala." >&2
  exit 1
fi
CABEZA_ORIGEN="$(tail -1 <<<"$SALIDA_ALEMBIC")"
case "$CABEZA_ORIGEN" in
  *"(head)"*) echo "    $CABEZA_ORIGEN" ;;
  *) echo "ABORTA: '$ORIGEN' no está en head ($CABEZA_ORIGEN). Corre 'alembic upgrade head' contra él primero." >&2; exit 1 ;;
esac

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> Respaldando '$DESTINO'"
mkdir -p backups
RESPALDO="backups/${DESTINO}_$(date +%Y%m%d_%H%M%S).dump"
if "${DUMP[@]}" -d "$DESTINO" -Fc -f "$RESPALDO" 2>/dev/null; then
  echo "    $RESPALDO ($(du -h "$RESPALDO" | cut -f1))"
else
  echo "    '$DESTINO' no existe todavía; no hay nada que respaldar."
  rm -f "$RESPALDO"
fi

echo "==> Volcando el esquema de '$ORIGEN'"
# Solo los schemas del proyecto. `public` queda fuera a propósito: en la base de
# desarrollo tiene las tablas de otra aplicación, que no deben acabar acá.
# pg_cron se excluye porque solo puede vivir en la base que declara
# cron.database_name; ningún objeto de módulo depende de él.
"${DUMP[@]}" -d "$ORIGEN" --schema-only --schema=auditoria --schema='modulo*' \
  | grep -vE "(CREATE EXTENSION IF NOT EXISTS|COMMENT ON EXTENSION) pg_cron" > "$TMP/esquema.sql"
echo "    $(wc -l < "$TMP/esquema.sql") líneas"

echo "==> Volcando catálogos"
args=(); for t in "${CATALOGOS[@]}"; do args+=(--table="$t"); done
# session_replication_role=replica desactiva los triggers de auditoría durante la
# carga: varios exigen app.usuario_id, que en una restauración no existe.
{ echo "SET session_replication_role = replica;"
  "${DUMP[@]}" -d "$ORIGEN" --data-only "${args[@]}"; } > "$TMP/catalogos.sql"
echo "    $(wc -l < "$TMP/catalogos.sql") líneas"

echo "==> Reemplazando los schemas del proyecto en '$DESTINO'"
EXISTE="$("${PSQL[@]}" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DESTINO';")"
if [ -z "$EXISTE" ]; then
  "${PSQL[@]}" -d postgres -c "CREATE DATABASE \"$DESTINO\";" >/dev/null
  echo "    base creada"
fi
# pgcrypto vive en public y el volcado no la trae (public queda fuera); alguna
# función de módulo la usa vía public.digest.
"${PSQL[@]}" -d "$DESTINO" -c "SET client_min_messages = warning; CREATE EXTENSION IF NOT EXISTS pgcrypto;" >/dev/null
"${PSQL[@]}" -d "$DESTINO" -c "SET client_min_messages = warning;
DO \$\$ DECLARE s text; BEGIN
  FOR s IN SELECT nspname FROM pg_namespace WHERE nspname LIKE 'modulo%' OR nspname = 'auditoria'
  LOOP EXECUTE format('DROP SCHEMA %I CASCADE', s); END LOOP;
END \$\$;" >/dev/null
"${PSQL[@]}" -d "$DESTINO" -c "SET client_min_messages = warning; DROP TABLE IF EXISTS public.alembic_version;" >/dev/null

echo "==> Cargando esquema y catálogos"
"${PSQL[@]}" -d "$DESTINO" -f "$TMP/esquema.sql" >/dev/null
"${PSQL[@]}" -d "$DESTINO" -f "$TMP/catalogos.sql" >/dev/null

echo "==> Sellando en head"
DATABASE_URL="${URL%/*}/$DESTINO" .venv/bin/python -m alembic stamp head >/dev/null

echo "==> Verificando"
"${PSQL[@]}" -d "$DESTINO" -tAc "
SELECT '    schemas: '||string_agg(nspname, ' ' ORDER BY nspname)
FROM pg_namespace WHERE nspname LIKE 'modulo%';"
"${PSQL[@]}" -d "$DESTINO" -tAc "
SELECT '    modulo9: '||count(*) FILTER (WHERE table_type='BASE TABLE')||' tablas, '
       ||count(*) FILTER (WHERE table_type='VIEW')||' vistas'
FROM information_schema.tables WHERE table_schema='modulo9';"
echo "    alembic: $(DATABASE_URL="${URL%/*}/$DESTINO" .venv/bin/python -m alembic current 2>/dev/null | tail -1)"
echo
echo "Listo. Ahora: TEST_DATABASE_URL=\"${URL%/*}/$DESTINO\" python -m pytest tests -m integration -q"
