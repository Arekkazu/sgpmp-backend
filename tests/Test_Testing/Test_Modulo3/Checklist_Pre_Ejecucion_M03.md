# Checklist previo a la ejecución funcional V1 — Módulo 03 (Juan Esteban)

**Ambiente decisorio:** TEST. **DEV:** solo como contraste, con autorización expresa. Los ejecutores **rechazan DEV por diseño**, así que un contraste en DEV necesitaría una variante controlada que hoy no existe.

**Alcance:** 31 grupos y 65 casos (ver `Inventario_Construccion_Juan_Esteban.md` y `Dependencias_Decisiones_QA_Juan_Esteban.md`).

Marque cada punto solo cuando esté verificado. Un punto incumplido no autoriza ejecutar el grupo afectado.

## 1. Autorización formal

- [ ] Referencia escrita de Desarrollo que autoriza ejecutar en TEST (se pasa con `--autorizacion "<referencia>"`, de 8 caracteres o más).
- [ ] Lista de grupos autorizados para esta ventana.
- [ ] `QA_AUTORIZADO=SI` en `.env.qa`, cambiado **solo** por el responsable QA en el momento de ejecutar. Se devuelve a `NO` al terminar.
- [ ] Efectos secundarios aceptados por escrito, grupo por grupo:
  - `notificacion-login`, para todos;
  - `sesion-persistente`, para G106;
  - `volumen-exportacion` y `fallo-exportador`, para G124 y G125;
  - los efectos persistentes declarados en los planes de G87–G92.

## 2. Disponibilidad de TEST

- [ ] API y frontend de TEST accesibles por HTTPS. `SIGAB_API_TEST_BASE` y `SIGAB_FRONT_TEST_URL` apuntan a TEST y son **distintos entre sí**.
- [ ] Alias `SIGAB_API_BASE` y `SIGAB_FRONT_URL` vacíos o iguales a los de TEST, nunca a DEV.
- [ ] Ventana de ejecución sin despliegues en curso.

## 3. Contratos y funcionalidades desplegados

Para cada grupo, compruebe su dependencia (sección 1 del documento de dependencias):

- [ ] **DEV-06:** si ya está desplegado, el punto único de credencial de cada grupo debe adaptarse **antes** de ejecutar; si no, la preparación falla y el resultado es BLOQUEADO.
- [ ] **DEV-05:** determinar si el estado actual, el semáforo y la vinculación son visibles dentro del sandbox.
- [ ] **DB-02:** revisar que los valores de preparación (por ejemplo, 25 °C) sigan siendo lecturas válidas.
- [ ] **M08:** disponible o no. G124 y G125 dependen de él; G127 lo usa solo si aplica.
- [ ] **RF-60:** disparador aislado (G90, G93, G96, G104, G105).
- [ ] **RF-54:** contrato del buffer local (G120).
- [ ] Auditoría del historial, auditoría de denegaciones, bitácoras de degradación y consistencia, filtro `id_activo_biologico`.
- [ ] Grupo **G98 congelado** hasta decidir las severidades.

## 4. Contraste con DEV

- [ ] Solo si una funcionalidad exigida no existe o no es verificable en TEST y hay autorización expresa.
- [ ] El resultado de DEV **no** sustituye al de TEST; se registra como información de contraste.

## 5. Cuentas QA y permisos

- [ ] Cuentas configuradas: Administrador de preparación (`QA_SETUP_*`), Productor, Ingeniero de Campo y Veterinario.
- [ ] Cuentas para los roles de las pruebas negativas:
  - sin lectura del monitoreo (G107-208);
  - lectura del historial sin exportación (G129-260);
  - sin lectura del historial (G129-261).

  Los ejecutores comprueban los permisos con `/roles/{id}/permisos`; deben existir candidatas con esos perfiles.
- [ ] **Sesión única por usuario:** no ejecutar en paralelo grupos que compartan cuenta. Ejecutar los grupos de uno en uno.
- [ ] G94: confirmar si se acepta la retirada temporal, con rollback, de las granjas del Productor, o disponer de una cuenta QA sin granjas.

## 6. Sandbox, aislamiento y rollback

- [ ] `/test-control/runs/{id}` y `/test-control/query` operativos y `QA_SANDBOX_SECRET` configurado.
- [ ] El DBA confirma `SELECT` sobre `auditoria.logs_dml` para el rol de la aplicación. Sin él, el aislamiento es «no verificable» y el RUN se detiene.
- [ ] Menos de 5 RUN concurrentes en el sandbox. Sin pausas de más de 180 s, salvo en los grupos diseñados para ello (G101, G106).
- [ ] Revisar en la evidencia de cada RUN: aislamiento (1 dentro, 0 fuera) y rollback confirmado (0 tras el cierre).

## 7. Barreras de seguridad de Node, Newman y Cypress

- [ ] Por cada grupo, `--validar-local` y sus pruebas unitarias en verde **antes** de activar la autorización. Varios grupos no tienen resultados documentados: ver el inventario, sección 4.
- [ ] Grupos con Cypress: verificar el descubrimiento del spec sin red antes de V1 (`--verificar-spec` en G87, G88, G97, G102 y G104; equivalente en los demás).
- [ ] **No** lanzar Cypress desde la configuración raíz `cypress.config.cjs`, cuyo `baseUrl` es remoto. Los ejecutores usan configuración propia o anulaciones dentro de `e2e`.
- [ ] En la terminal de VS Code, `ELECTRON_RUN_AS_NODE=1` impide arrancar Cypress. Los ejecutores corregidos la retiran; en otros, verificarlo.
- [ ] Las colecciones deben tener barrera propia. **G94 no la tiene**: ejecutarla solo a través de su ejecutor.
- [ ] Ninguna verificación local debe contactar TEST. Use destinos loopback y, para procesos externos, un proxy de loopback inexistente.

## 8. Datos de preparación y efectos

- [ ] Los escenarios se construyen en el sandbox con APIs oficiales y se revierten. Los que dependen de datos reales (G96 y G104 en solo lectura) pueden quedar BLOQUEADOS si no hay datos aptos.
- [ ] G128: ejecutar `--preparar-token-expirable` al menos 8 h antes (o lo que fije `JWT_EXPIRE_HOURS`).
- [ ] G105: panel persistente con los 4 estados y una alerta, y protocolo aprobado.
- [ ] G106: duración del periodo decidida (`--duracion`).
- [ ] G124 y G125: autorizaciones de volumen y de fallo del exportador.

## 9. Evidencia funcional

- [ ] V1 se guarda en `RESULTADOS/<RUN_ID>/` y V2 y siguientes en `EvaluacionVN/RESULTADOS/<RUN_ID>/`. Las evaluaciones anteriores no se sobrescriben.
- [ ] Cada RUN produce un informe Markdown y `evidencia.json`, y capturas o HTML de Newman solo si hace falta.
- [ ] Revisar que la evidencia no contenga contraseñas, JWT ni el secreto del sandbox (los ejecutores los redactan).
- [ ] Resultados propuestos:
  - APROBADO: solo con todas las aserciones requeridas;
  - RECHAZADO: solo con una aserción incumplida y el escenario válido;
  - BLOQUEADO: preparación, permisos o infraestructura.

  El responsable QA emite el dictamen.

## 10. Dependencias que pueden bloquear grupos completos

| Si falta… | Grupos que quedan BLOQUEADOS por completo |
| --- | --- |
| Autorización o `QA_AUTORIZADO=SI` | Todos |
| Sandbox o `SELECT` sobre `logs_dml` | Todos los grupos con escrituras preparatorias |
| DEV-06 desplegado sin adaptar | G87–G92, G96, G97, G99, G100, G102–G104, G107, G110, G120 y G126–G129 |
| M08 | G124 y G125 (salvo G125-252) |
| RF-60 aislado | G90; variantes de G93, G96 y G104; preparación de G105 |
| Expiración de sesión observable | G95 |
| Decisión sobre las severidades | G98 |
| Cuentas con perfiles negativos | G107-208, G129-260 y G129-261 |
| Duración / protocolo aprobados | G106 / G105 |

## Lección aplicada

Durante la construcción, una verificación local de Cypress cargó la configuración raíz y realizó entre 2 y 3 comprobaciones de disponibilidad, sin credenciales, contra el `baseUrl` remoto. La causa se corrigió y quedó documentada.

**Regla:** ninguna comprobación local se da por aislada solo porque `QA_AUTORIZADO=NO`. Hay que comprobar los destinos efectivos y bloquear la salida antes de arrancar cualquier herramienta externa.
