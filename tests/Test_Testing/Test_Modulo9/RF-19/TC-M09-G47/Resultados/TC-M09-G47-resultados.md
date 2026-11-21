# TC-M09-G47 (agrupa TC-M09-95) — Auditoría de operaciones sobre fincas

**RF-19 / CU-04 — Gestionar Infraestructura Productiva**

Mismo patrón que TC-M09-G37 (RF-18): `modulo9.auditorias_fincas` sí se escribe correctamente
en cada `CREATE`/`UPDATE`/`DEACTIVATE` (confirmado leyendo `registrar_finca_use_case.py`,
`editar_finca_use_case.py`, `desactivar_finca_use_case.py` y `SqlAlchemyAuditoriaFincaRepository`),
pero no existe endpoint REST que exponga esa tabla — el único router de auditoría (`/auditoria/`)
lee `modulo1.eventos`, tabla distinta que este flujo no usa.

La colección Postman (`TC-M09-G47.postman_collection.json`) automatiza las tres operaciones
por API (registrar, editar, desactivar la misma finca) y confirma todo lo observable por HTTP.
La verificación puntual de las filas de auditoría se hizo con un `SELECT` directo contra la
BD de test tras la corrida:

```sql
SELECT tipo_operacion, id_usuario, fecha_gestion
FROM modulo9.auditorias_fincas
WHERE id_finca = 23
ORDER BY fecha_gestion;
```

**Resultado confirmado:** 3 filas — `CREATE`, `UPDATE`, `DEACTIVATE` — todas con `id_usuario=1`
(el administrador autenticado) y `valores_anteriores`/`valores_nuevos` coincidiendo exactamente
con cada operación (nombre y `tamano_h` cambiando en el `UPDATE`; `es_activo: true → false` en
el `DEACTIVATE`).

**Estado: PASA.** Las operaciones sobre fincas quedan registradas en auditoría con snapshot
antes/después e imputación correcta al usuario, para las tres acciones definidas por el RF.
