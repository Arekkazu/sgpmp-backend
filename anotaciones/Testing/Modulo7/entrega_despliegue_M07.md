# Documento de entrega — Módulo 7 (Integración contable con AgroFusión) al equipo de Despliegue — v1.0

| Campo | Valor |
|---|---|
| Módulo | M07 — Integración contable (`src/accounting_integration/`) |
| Alcance | RF-95, RF-96, RF-97, RF-98, RF-101, RF-102, RF-AE01 y RF-AE02 (8 requisitos activos; RF-99 diferido, fuera de alcance) |
| Fecha de corte | 2026-11-21 |
| Fuente | `informe_consolidado_pruebas_M07.md` (v1.0, 2026-11-21) |
| Ambiente de prueba | Backend TEST (`https://api.inmero.co/api-sgpmp-test`) |
| Emite | Equipo QA |
| Destino | Equipo de Despliegue |

---

## 1. Resumen

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 54 | 100 % |
| Aprobados | **53** | **98.1 %** |
| Rechazados | 1 | 1.9 % |
| Pendientes | 0 | 0.0 % |

## 2. Verificación de criterios de cierre de módulo

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **53/54 = 98.1 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **8/8** | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | `informe_consolidado_pruebas_M07.md` redactado (pendiente de firmas) | ✅ (firmas pendientes) |

**El módulo cumple los tres criterios de cierre evaluados.** Queda pendiente la firma de la entrega. El caso no aprobado se entrega a Desarrollo (sección 3); su detalle completo está en el informe consolidado.

## 3. Casos rechazados y pendientes

| TC | RF | Resultado | Estado | Motivo |
|---|---|---:|---|---|
| G035 | RF-97 | 4/5 | Rechazado | Con 15 o más solicitudes concurrentes a la vista previa AAEF casi todas expiran por timeout; el caso exige que 20 concurrentes respondan en tiempo. Defecto abierto INC-M07-376-G035 (severidad Alta, categoría PERFORMANCE); causa exacta sin identificar |

### Casos bloqueados y dependencias

- **RF-97 (G035):** el techo real de concurrencia está entre 13 y 15 solicitudes simultáneas (con 14 ya hay cola de ~4 s). Es compatible con un pool de conexiones o recursos de ~13-14 en el backend o en la infraestructura de TEST. Despliegue debe revisar el tamaño del pool, los workers y los timeouts del proxy o gateway de TEST antes de reejecutar. Con cualquier cambio, QA repite el barrido de 5 a 20 concurrentes con k6.
- **RF-97 (G035):** siguen sin verificar RNF-97.1 (2.000 facturas en ≤ 5 s), RNF-97.7 (escalado a 2 y 4 instancias sin estado compartido) y CA-14 (AgroFusión de pruebas sin error 502). Requieren un dataset de alto volumen, un entorno con varias instancias y un AgroFusión de pruebas.
- **RF-98:** el contrato 3.1 con el Mapper `06` solo se activa cuando SIGCON acepte el tipo 06; no se probó en TEST (el límite de 2 versiones vigentes lo impide).
- **RF-99:** diferido sin receptor; QA solo debe confirmar que no queda expuesto en TEST (pendiente de confirmar con los líderes).
- No hay casos pendientes.

### Casos aprobados con alcance delimitado

El manual de usuario y el despliegue deben reflejarlo:

| TC | RF | Alcance de la aprobación |
|---|---|---|
| G019 | RF-96 | Aprobado por prueba unitaria: el tipo de línea ya se valida contra la matriz contable. En TEST una fila comodín de la matriz hace inalcanzable el rechazo `LINETYPE_NO_CATALOGADO` (INC-M07-378-G019, de datos; responsable DBA) |
| G025 | RF-97 | Aprobado con dos observaciones: el `ExchangeId` real (`AF-SIGAB-AAAA-MM-nonce`) no coincide con la ficha, por exigencia de SIGCON; y `SourceSystem.Environment` dice `DEV` en TEST (INC-M07-377-G025, abierta, de configuración de despliegue) |
| G027 | RF-97 | Aprobados los tres negativos de rango. La periodicidad trimestral y el mes sin período abierto no se verificaron, por falta de un titular con esa configuración |
| G040 | RF-98 | Aprobado aceptando `VERSION_NO_REGISTRADA` y `VERSION_NO_ENCONTRADA` como código de versión inexistente, hasta que Análisis cambie el nombre del error en FA-7 |

## 4. Insumos para el despliegue a `main`

Lo que QA observó que debe viajar junto con el código. Todo se verificó en TEST; QA no revisó los scripts de migración ni la configuración de `main`.

| # | Elemento | Detalle | Origen |
|---|---|---|---|
| 1 | Configuración del ambiente | `SGPMP_ENTORNO` del contenedor de TEST está mal puesto: el envelope AAEF reporta `SourceSystem.Environment = "DEV"`. En `main` debe reflejar el entorno real que atiende la solicitud | INC-M07-377-G025 |
| 2 | Migraciones de base de datos | Índice único `uq_cliente_externo_nombre` (migración `b4d2f8e61c07`) para impedir clientes externos con nombre repetido; política de retención y archivado histórico de la auditoría de RF-102 (5 años general, 10 para `PAQUETE_AAEF_CONSULTADO`, `VISTA_AAEF_GENERADA` y `CONTRATO_ACTIVADO`) | INC-M07-373-G043, INC-M07-371-G58 |
| 3 | Datos de seed | Las credenciales de `modulo7.identificadores_apis` deben estar todas en bcrypt (20 de 20 en TEST tras la corrección del DBA). Confirmar lo mismo en `main` | INC-M07-374-G047 |
| 4 | Datos de la matriz contable | La matriz contable de TEST tiene una fila comodín (`CONSUMO_INSUMO` / `UNICO` sin subtipo de costo). Revisar que la de `main` tenga un par de cuentas activo por cada subtipo de costo | INC-M07-378-G019 |
| 5 | Contrato de la API | `POST /integracion/anexos/{id}/revision` ahora exige el cuerpo `{"justificacion": <20 a 1000 caracteres>}`. Los clientes que ya llamen al endpoint sin cuerpo recibirán 422 | Commit `20b5f701` |
| 6 | Contrato de la API | Todo error trae el campo `field`; `password` es una credencial prohibida en la URL (400 `CREDENCIALES_EN_URL`); la query de la consulta AAEF no se escribe en el log de acceso | #1169, #1187 |
| 7 | Límites de la consulta AAEF | El cliente `QA_M07_AAEF` tiene 5 consultas por minuto, y el token de canal dura 300 s con 30 s de tolerancia. Son valores de QA; en `main` deben fijarse los reales de cada cliente | Observación O-1 |
| 8 | Release probado | Retests de RF-95, RF-98 y RF-101 contra `1.4.0-rc.80`; los de G060 y G061 el 2026-11-21. El último release visible en `origin/test` es `1.4.0-rc.82`. QA no comprobó que TEST corra rc.82 | `git log` de `origin/test` |

## 5. Estado por requisito (insumo para el manual de usuario)

| RF | Función | Casos | Aprobados | Rechazados | Pendientes | Observación para el manual |
|---|---|---:|---:|---:|---:|---|
| RF-95 | Gateway de API REST del sistema | 6 | 6 | 0 | 0 | Documentar completo. Mencionar la tolerancia de 30 s del token de canal |
| RF-96 | Transformadores de datos (Mappers) | 12 | 12 | 0 | 0 | Documentar completo. Una compra con importe menor a 0,01 se rechaza y el usuario debe corregir el costo en Finanzas |
| RF-97 | Exportación de datos financieros | 12 | 11 | 1 | 0 | **Documentar con limitaciones**: con 15 o más consultas simultáneas el servicio puede expirar; no se verificaron volúmenes de 2.000 facturas, el escalado ni la interoperabilidad con AgroFusión real; el formato del `ExchangeId` es el que exige SIGCON |
| RF-98 | Gestión de versiones del contrato | 6 | 6 | 0 | 0 | Documentar completo. El contrato 3.1 y el Mapper `06` quedan por activar cuando SIGCON acepte el tipo 06 |
| RF-101 | Gestión de credenciales y clientes externos | 6 | 6 | 0 | 0 | Documentar completo. El nombre del cliente es único; `GET_ROLES` es público por contrato de AgroFusión |
| RF-102 | Auditoría y trazabilidad | 7 | 7 | 0 | 0 | Documentar completo, con la retención de 5 y 10 años y el archivado histórico |
| RF-AE01 y RF-AE02 | Consulta AAEF (validaciones) y Anexo de mapeo | 5 | 5 | 0 | 0 | Documentar completo. Pasar el Anexo a revisión exige una justificación de 20 caracteres o más y el Anexo aprobado no se modifica |

## 6. Decisión de liberación a `main`

Marque la opción que aplique y firme:

- [ ] **Liberación certificada por QA** — con los criterios evaluados cumplidos; requiere las firmas de esta entrega.
- [ ] **Liberación con condiciones definidas por Coordinación**: ________________________________________________

Si se autoriza, Despliegue puede programar el despliegue a `main` y el equipo de documentación puede iniciar el manual de usuario con las observaciones de la sección 5. Los RF marcados «con limitaciones» deben documentarse indicando la limitación conocida. Antes del despliegue deben atenderse los puntos 1 a 4 de la sección 4.

## 7. Firmas de entrega

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM (excepción) | | | |
| Equipo de Despliegue (recibido) | | | |
