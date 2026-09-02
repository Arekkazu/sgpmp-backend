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
# pg_cron solo puede vivir en la base que declara cron.database_name, así que su
# extensión se excluye. No hay objeto de módulo que dependa de ella.
"${DUMP[@]}" -d "$ORIGEN" --schema-only \
  | grep -vE "(CREATE EXTENSION IF NOT EXISTS|COMMENT ON EXTENSION) pg_cron" > "$TMP/esquema.sql"
echo "    $(wc -l < "$TMP/esquema.sql") líneas"

echo "==> Volcando catálogos"
args=(); for t in "${CATALOGOS[@]}"; do args+=(--table="$t"); done
# session_replication_role=replica desactiva los triggers de auditoría durante la
# carga: varios exigen app.usuario_id, que en una restauración no existe.
{ echo "SET session_replication_role = replica;"
  "${DUMP[@]}" -d "$ORIGEN" --data-only "${args[@]}"; } > "$TMP/catalogos.sql"
echo "    $(wc -l < "$TMP/catalogos.sql") líneas"

echo "==> Recreando '$DESTINO'"
"${PSQL[@]}" -d postgres -c "DROP DATABASE IF EXISTS \"$DESTINO\" WITH (FORCE);" >/dev/null
"${PSQL[@]}" -d postgres -c "CREATE DATABASE \"$DESTINO\";" >/dev/null

echo "==> Cargando esquema y catálogos"
"${PSQL[@]}" -d "$DESTINO" -f "$TMP/esquema.sql" >/dev/null
"${PSQL[@]}" -d "$DESTINO" -f "$TMP/catalogos.sql" >/dev/null

echo "==> Sellando en head"
# El sello es veraz porque '$ORIGEN' está en head: su esquema ya refleja todas
# las migraciones. Si dejara de estarlo, este script mentiría — de ahí la
# comprobación de abajo.
CABEZA_ORIGEN="$(DATABASE_URL="${URL%/*}/$ORIGEN" .venv/bin/python -m alembic current 2>/dev/null | tail -1)"
case "$CABEZA_ORIGEN" in
  *"(head)"*) ;;
  *) echo "ABORTA: '$ORIGEN' no está en head ($CABEZA_ORIGEN). Aplica sus migraciones primero." >&2; exit 1 ;;
esac
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
