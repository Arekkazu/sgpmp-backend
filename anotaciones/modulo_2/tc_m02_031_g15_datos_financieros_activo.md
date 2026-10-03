# TC-M02-031-G15 — Protección de información financiera del activo

## Hallazgo

`GET /activos-biologicos/{id_activo}` aplicaba correctamente autenticación,
RBAC general y alcance por finca, pero el serializador devolvía siempre:

- `costo_adquisicion`;
- `soporte_documental`.

Por ello, un Ingeniero de Campo autorizado a consultar los datos operativos de
un activo recibía también información financiera sin una autorización
específica. El mismo serializador se utilizaba en el listado y en las respuestas
de alta y actualización, por lo que el riesgo no estaba limitado al endpoint
señalado por QA.

## Correspondencia con los RF

RF-34 establece visibilidad limitada por finca y rol. Los campos financieros
nacen en RF-33, donde Productor y Administrador registran el activo, y el costo
es insumo posterior de valoración para M06. Aunque RF-34 no enumera literalmente
los dos campos a ocultar, el hallazgo es válido por la separación de permisos y
el principio de mínimo privilegio: leer el activo no debe equivaler a leer sus
datos financieros.

## Corrección

Se agregó el recurso RBAC por nombre:

```text
datos_financieros_activo
```

La presentación de `ActivoBiologicoResponse` consulta su permiso READ. Si el
rol no lo tiene, responde `null` en ambos campos sin impedir la consulta de los
datos operativos. El valor seguro del serializador es ocultarlos por defecto,
de modo que un futuro endpoint no pueda exponerlos por omitir la evaluación.

La misma regla se aplica a:

- `POST /activos-biologicos`;
- `GET /activos-biologicos`;
- `GET /activos-biologicos/{id_activo}`;
- `PATCH /activos-biologicos/{id_activo}`.

No se codifica ningún rol en el router. La asignación queda administrada por
`modulo1.permisos` y puede cambiarse sin desplegar código.

## Migración

La revisión `96621b225009`, con mensaje
`v5.5.0_rf34_permiso_datos_financieros_activo`, crea el recurso de forma
idempotente y asigna lectura a:

- Administrador;
- Productor;
- Integración M06.

Ingeniero de Campo y Veterinario conservan la lectura operativa sobre
`activos_biologicos`, pero no reciben el permiso financiero.

La revisión usa el `DEFAULT` de `recursos_id_recurso_seq`. La sincronización de
esa secuencia ya forma parte de la revisión ancestral `d944f4d8c215`, por lo que
no repite `setval` ni exige a `member_dev` el privilegio `UPDATE` que la base
oficial no le concede.

El `downgrade()` retira los permisos reversibles de Productor y M06. Conserva
el permiso de Administrador y el recurso porque los triggers de seguridad de
M01 prohíben eliminar o desactivar permisos `admin_*`.

## Contrato resultante

| Escenario | HTTP | costo/adquisición y soporte | Datos operativos |
| --- | --- | --- | --- |
| Rol con READ financiero y activo dentro del alcance | 200 | Valores completos | Visibles |
| Rol sin READ financiero y activo dentro del alcance | 200 | `null` | Visibles |
| Activo fuera del alcance por finca | 404 | No se expone respuesta | No se exponen |
| Rol sin READ general sobre activos | 403 | No se expone respuesta | No se exponen |

## Pruebas

La cobertura automatizada verifica:

- enmascaramiento seguro por defecto;
- exposición únicamente con permiso explícito;
- evaluación dinámica del recurso por nombre;
- caso exacto del detalle consultado por Ingeniero;
- aplicación consistente en el listado;
- endpoint real con PostgreSQL para Ingeniero y Productor, bajo rollback.

La validación contra `sgpmp_dev` se ejecuta dentro de una transacción exterior:
la migración y las auditorías generadas por la consulta se revierten al final,
sin persistir DDL ni DML de prueba.

Resultado sobre el activo real 51:

| Usuario simulado | HTTP | `costo_adquisicion` | `soporte_documental` |
| --- | --- | --- | --- |
| Ingeniero de Campo | 200 | `null` | `null` |
| Administrador | 200 | `1500.0000` | `factura-trucha-001.pdf` |

La consulta generó dos auditorías dentro de la transacción. Después del
rollback, el recurso volvió de 1 a 0 filas y la bitácora permaneció en 134
filas, igual que antes de la prueba.
