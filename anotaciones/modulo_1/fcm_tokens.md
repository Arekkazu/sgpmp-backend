# FCM Tokens — Composición y decisiones de diseño

## Qué es un FCM token

Firebase Cloud Messaging (FCM) asigna un token único a cada combinación de **aplicación + dispositivo + browser**. Es generado por el SDK de Firebase en el cliente cuando el usuario acepta las notificaciones push. No lo produce el backend.

Formato real:
```
evOontfYTYQEYr1rCizrOl:APA91bEp6NPYyMCeZu7rruWSUjDnKpS1eoWxp1P4vPgqaFiHbkad4y9Y-7SPDz0_LuDpiEeve2OTg4mM4odca1iy2vOEKj0P_fip4I4aOXy3Aj6RAZfO898
```

Estructura interna (opaca, no parseable por el backend):
- Prefijo corto antes de `:` — identifica la instancia de la app
- Sufijo largo después de `:` — token de registro del dispositivo en FCM

El backend trata el token como una cadena opaca. No lo interpreta.

---

## Por qué se usa una tabla separada (`dispositivos_fcm`)

La primera versión guardaba `fcm_token TEXT` directo en `cuentas_usuarios` (un token por usuario). Se migró a tabla propia por:

| Razón | Detalle |
|---|---|
| Multi-dispositivo | Un usuario puede tener el PWA abierto en celular y en PC simultáneamente. Cada uno tiene su propio token. |
| Notificaciones de seguridad | Eventos como cambio de contraseña o bloqueo de cuenta deben llegar a **todos** los dispositivos del usuario, no solo al que tiene la sesión activa. |
| Ciclo de vida propio | Los tokens caducan, se renuevan y se revocan independientemente de la sesión. Merecen tabla propia. |

---

## Estructura de la tabla

```sql
modulo1.dispositivos_fcm
├── id_dispositivo   SERIAL PK
├── id_usuario       INT FK → modulo1.usuarios(id_usuario) ON DELETE CASCADE
├── fcm_token        TEXT NOT NULL UNIQUE  -- globalmente único por naturaleza de FCM
├── user_agent       TEXT                  -- raw del header HTTP, identifica el dispositivo
├── fecha_registro   TIMESTAMPTZ NOT NULL DEFAULT NOW()
└── ultimo_uso       TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

`fcm_token` tiene `UNIQUE` global (no por usuario) porque FCM garantiza que el mismo token nunca puede pertenecer a dos usuarios distintos.

---

## Flujo de registro del token

1. Usuario inicia sesión → recibe JWT
2. Browser solicita permiso de notificaciones al usuario
3. Si acepta, Firebase devuelve el FCM token al frontend
4. Frontend llama `POST /me/fcm-token` con el token en el body
5. El backend extrae el `User-Agent` del header HTTP y guarda ambos en `dispositivos_fcm`

El token **no se registra en el login**. El login solo autentica; el token se registra por separado porque el permiso de notificaciones es una acción distinta del usuario.

---

## Triggers automáticos en la tabla

> **Aplicado en la DB el 2026-06-08** (esquema `modulo1`). La tabla y sus triggers
> no existían; se crearon manualmente vía el MCP de postgres. **No hay sistema de
> migraciones**, así que un restore desde un dump anterior los revertiría. El DDL
> exacto está al final de este documento.

**Trigger B — Limpieza de tokens caducados** (`trg_fcm_1_limpiar_caducados`, `BEFORE INSERT`, corre primero)
Elimina todos los tokens del mismo usuario con `ultimo_uso` anterior a 30 días. Mantiene la tabla limpia sin necesidad de un job externo.

**Trigger A — Revocar token previo y registrar el nuevo** (`trg_fcm_2_revocar_token_previo`, `BEFORE INSERT`, corre después)
Si el mismo `fcm_token` ya existe (mismo dispositivo/navegador, posiblemente bajo otra cuenta), **borra (revoca) el registro previo** y deja pasar el INSERT, que crea la fila nueva para el usuario actual. Así cada `fcm_token` representa siempre el registro más reciente y el token "sigue" al dispositivo: las notificaciones (incluidas las de seguridad) llegan a quien usa ese dispositivo ahora.

> Decisión: se eligió **revocar + registrar** en lugar del *upsert en sitio* original
> (que solo actualizaba `ultimo_uso` y `user_agent`). El revoke no deja rastro del
> registro anterior y reinicia `id_dispositivo`/`fecha_registro` para el nuevo dueño.

---

## Envío de notificaciones push

Cuando `NotificacionService` procesa un evento de tipo INTERNO:
1. Llama `buscar_fcm_tokens(id_usuario)` — devuelve todos los tokens del usuario
2. Itera la lista y llama `send_push(token, titulo, cuerpo)` por cada uno
3. Si **al menos uno** entrega con éxito → estado de la notificación = `ENVIADO`
4. Si todos fallan → `FALLIDO`

`send_push` nunca lanza excepción. Si Firebase falla, registra en log y retorna `False`.

---

## DDL aplicado (2026-06-08)

Tabla + triggers creados a mano en la DB (no hay migraciones). Si se restaura un
dump anterior, re-aplicar esto:

```sql
CREATE TABLE modulo1.dispositivos_fcm (
    id_dispositivo  SERIAL,
    id_usuario      INTEGER     NOT NULL,
    fcm_token       TEXT        NOT NULL,
    fecha_registro  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_uso      TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_agent      TEXT,
    CONSTRAINT dispositivos_fcm_pkey PRIMARY KEY (id_dispositivo),
    CONSTRAINT uq_dispositivos_fcm_token UNIQUE (fcm_token),
    CONSTRAINT dispositivos_fcm_id_usuario_fkey
        FOREIGN KEY (id_usuario) REFERENCES modulo1.usuarios(id_usuario) ON DELETE CASCADE
);

-- B: limpieza >30 días (corre primero)
CREATE FUNCTION modulo1.trg_fn_fcm_limpiar_caducados() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM modulo1.dispositivos_fcm
    WHERE id_usuario = NEW.id_usuario AND ultimo_uso < now() - INTERVAL '30 days';
    RETURN NEW;
END; $$;
CREATE TRIGGER trg_fcm_1_limpiar_caducados BEFORE INSERT ON modulo1.dispositivos_fcm
    FOR EACH ROW EXECUTE FUNCTION modulo1.trg_fn_fcm_limpiar_caducados();

-- A: revocar token previo + registrar nuevo (corre después)
CREATE FUNCTION modulo1.trg_fn_fcm_revocar_token_previo() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM modulo1.dispositivos_fcm WHERE fcm_token = NEW.fcm_token;
    RETURN NEW;
END; $$;
CREATE TRIGGER trg_fcm_2_revocar_token_previo BEFORE INSERT ON modulo1.dispositivos_fcm
    FOR EACH ROW EXECUTE FUNCTION modulo1.trg_fn_fcm_revocar_token_previo();
```
