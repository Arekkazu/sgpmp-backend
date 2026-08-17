# TAIGA — Tareas [Frontend] · SGPMP DESARROLLO

> Datos extraídos de Taiga (volcado de la información tal cual está registrada en el proyecto).

## Metadatos del proyecto

| Campo | Valor |
|-------|-------|
| Nombre | SGPMP DESARROLLO |
| ID | 1802172 |
| Slug | arekkazu-sgpmp-desarrollo |
| Descripción | DESAROLLO DE BACKEND Y FRONT-END |
| Owner | Alexander Lozada Caviedes (arekkazu) |
| Fecha de extracción | 2026-08-15 |

## Referencias

### Estados (user story status)

| ID | Nombre | Cerrado |
|----|--------|---------|
| 10935173 | New | no |
| 10935174 | Ready | no |
| 10935175 | In progress | no |
| 10935176 | Ready for test | no |
| 10935177 | Done | sí |
| 10935178 | Archived | sí |

### Sprints (milestones)

| ID | Nombre | Inicio estimado | Fin estimado |
|----|--------|-----------------|--------------|
| 528107 | Sprint 1 — Crítico y fundacional | — | — |
| 528108 | Sprint 2 — Funcional | 2026-08-24 | 2026-09-04 |
| 528109 | Sprint 3 — Cierre | 2026-09-07 | 2026-09-08 |

### Módulos (épicas)

| ID | Ref | Nombre | Color |
|----|-----|--------|-------|
| 364460 | 1 | Módulo 1 — Identity & Access: cierre de gaps | #2E86AB |
| 364461 | 2 | Módulo 2 — Biological Assets: cierre de gaps | #A23B72 |
| 364462 | 3 | Módulo 9 — Configuration: cierre de gaps | #F18F01 |

### Usuarios asignados

| ID | Username | Nombre |
|----|----------|--------|
| 907781 | arekkazu | Alexander Lozada Caviedes |
| 907873 | SamuelPR21 | Samuel Alexander Perdomo Fajardo |
| 907888 | leandroEstiven | Leandro Estiven Ramírez Molina |
| 909001 | Danielsxanti | Daniel Santiago rivera |

---

## Sprint 1 — Crítico y fundacional

### #53 · [Frontend] JWT de localStorage a variable en memoria (RF-02)

| Campo | Valor |
|-------|-------|
| ID | 9464098 |
| Estado | Ready for test |
| Asignado a | leandroEstiven |
| Módulo | Módulo 1 — Identity & Access: cierre de gaps |
| Etiquetas | p0-critico, m1 |
| Puntos | — |
| Versión | 3 |
| Creada | 2026-08-07T20:47:56.977Z |
| Modificada | 2026-08-14T21:40:34.100Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

El JWT se guarda en localStorage en vez de memoria (tokenStore.ts usa localStorage.getItem/setItem/removeItem). Contradice CLAUDE.md: "JWT en variable de módulo, nunca en localStorage". Migrar a variable en memoria (singleton).

---

### #54 · [Frontend] Logout llama DELETE /sesiones/ (RF-02)

| Campo | Valor |
|-------|-------|
| ID | 9464099 |
| Estado | Ready for test |
| Asignado a | leandroEstiven |
| Módulo | Módulo 1 — Identity & Access: cierre de gaps |
| Etiquetas | p0-critico, m1 |
| Puntos | — |
| Versión | 3 |
| Creada | 2026-08-07T20:47:57.771Z |
| Modificada | 2026-08-14T22:50:22.187Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

authApi.logout() (DELETE /sesiones/) existe en código pero nunca se invoca. El logout real en App.tsx solo hace clearSession() + redirect sin invalidar sesión en backend.

---

### #55 · [Frontend] Timeout de inactividad 30 min (RF-02)

| Campo | Valor |
|-------|-------|
| ID | 9464100 |
| Estado | New |
| Asignado a | leandroEstiven |
| Módulo | Módulo 1 — Identity & Access: cierre de gaps |
| Etiquetas | p1-alto, m1 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:47:59.100Z |
| Modificada | 2026-08-07T23:41:19.780Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

Implementar temporizador de inactividad en cliente que cierre sesión tras 30 min sin actividad. También leer expira_en del LoginResponse para countdown/aviso.

---

### #56 · [Frontend] Mapeo errores 410/429 en errors.ts (RF-08/09)

| Campo | Valor |
|-------|-------|
| ID | 9464101 |
| Estado | New |
| Asignado a | leandroEstiven |
| Módulo | Módulo 1 — Identity & Access: cierre de gaps |
| Etiquetas | p1-alto, m1 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:00.519Z |
| Modificada | 2026-08-07T23:24:21.397Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

Agregar casos 410 (token expirado) y 429 (rate limiting) en shared/api/errors.ts. RF-08 muestra mensaje incorrecto porque backend devuelve 422 en vez de 429.

---

### #57 · [Frontend] Pasar tipo_activo a EventoReproductivoForm, restringir LOTE a nacimiento (RF-42)

| Campo | Valor |
|-------|-------|
| ID | 9464102 |
| Estado | New |
| Asignado a | Danielsxanti |
| Módulo | Módulo 2 — Biological Assets: cierre de gaps |
| Etiquetas | p0-critico, m2 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:02.082Z |
| Modificada | 2026-08-07T23:25:31.946Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

EventoReproductivoForm no recibe esPoblacional como prop. Mostrar solo 'nacimiento' como categoría para LOTE, ocultar resto. Es el gap frontend más grave del módulo 2.

---

### #58 · [Frontend] Propagación de error en useFichaIntegral → FichaIntegralView (RF-47)

| Campo | Valor |
|-------|-------|
| ID | 9464103 |
| Estado | New |
| Asignado a | Danielsxanti |
| Módulo | Módulo 2 — Biological Assets: cierre de gaps |
| Etiquetas | p1-alto, m2 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:03.527Z |
| Modificada | 2026-08-07T23:25:32.074Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

FichaIntegralView descarta silenciosamente el error de useFichaIntegral. Propagar error para mostrar alerta cuando falle carga parcial de secciones.

---

### #59 · [Frontend] Pasar estadoActual a FasesSection, ocultar "Cambiar fase" en CERRADO/BAJA (RF-37)

| Campo | Valor |
|-------|-------|
| ID | 9464104 |
| Estado | New |
| Asignado a | Danielsxanti |
| Módulo | Módulo 2 — Biological Assets: cierre de gaps |
| Etiquetas | p1-alto, m2 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:05.024Z |
| Modificada | 2026-08-07T23:25:38.132Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

ActivoDetallePage no pasa estadoActual a FasesSection. El botón "Cambiar fase" queda visible para activos CERRADO/BAJA. Agregar la prop y ocultar/mostrar mensaje en estados terminales.

---

### #60 · [Frontend] Fix usePermission(12,5)→(12,1) en CalibracionSection (RF-24)

| Campo | Valor |
|-------|-------|
| ID | 9464105 |
| Estado | New |
| Asignado a | arekkazu |
| Módulo | Módulo 9 — Configuration: cierre de gaps |
| Etiquetas | p0-critico, m9 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:06.755Z |
| Modificada | 2026-08-07T23:16:18.992Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

Una línea: CalibracionSection.tsx:342 usa usePermission(12,5) pero recurso 12 solo tiene C,R,U. Cambiar a usePermission(12,1) para desbloquear calibración.

---

### #61 · [Frontend] Corregir mapeo theme_mode 0/1/2→1/2/3 + conectar AppBar (RF-27)

| Campo | Valor |
|-------|-------|
| ID | 9464106 |
| Estado | New |
| Asignado a | arekkazu |
| Módulo | Módulo 9 — Configuration: cierre de gaps |
| Etiquetas | p0-critico, m9 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:08.197Z |
| Modificada | 2026-08-07T23:16:19.427Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

Frontend usa 0=Claro,1=Oscuro,2=Auto pero backend espera 1=Claro,2=Oscuro,3=Auto. Corregir mapeo. Conectar useTheme (toggle AppBar) al sistema de tema del backend para que no sean dos sistemas paralelos.

---

## Sprint 2 — Funcional

### #62 · [Frontend] CAPTCHA real reemplaza checkbox simulado (RF-01)

| Campo | Valor |
|-------|-------|
| ID | 9464107 |
| Estado | New |
| Asignado a | leandroEstiven |
| Módulo | Módulo 1 — Identity & Access: cierre de gaps |
| Etiquetas | p1-alto, m1 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:14.000Z |
| Modificada | 2026-08-07T23:24:26.791Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

El captcha actual es un checkbox con label "No soy un robot (simulación)". Reemplazar por reCAPTCHA real (v2 o v3). Requiere: instalar librería, nueva variable VITE_RECAPTCHA_SITE_KEY, campo captcha_token en UsuarioCreateDTO.

---

### #63 · [Frontend] Corrección verificación integridad + archivado en auditoría (RF-10)

| Campo | Valor |
|-------|-------|
| ID | 9464108 |
| Estado | New |
| Asignado a | SamuelPR21 |
| Módulo | Módulo 1 — Identity & Access: cierre de gaps |
| Etiquetas | p2-medio, m1 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:15.314Z |
| Modificada | 2026-08-07T23:25:57.183Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

Dos fixes: 1) Reemplazar hashSimulado() por verificación real contra SHA-256 del backend. 2) "Simular archivado" debe llamar endpoint real de archivado, no solo contar filas locales. Ambas funciones hoy son cosméticas.

---

### #64 · [Frontend] CSV exporta resultado completo, no solo página actual (RF-10)

| Campo | Valor |
|-------|-------|
| ID | 9464109 |
| Estado | New |
| Asignado a | leandroEstiven |
| Módulo | Módulo 1 — Identity & Access: cierre de gaps |
| Etiquetas | p2-medio, m1 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:16.753Z |
| Modificada | 2026-08-07T23:41:28.711Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

generarCsv() en AuditoriaPage solo exporta la página actual (max 50 filas). Debe exportar el resultado completo de los filtros aplicados, con advertencia si se trunca.

---

### #65 · [Frontend] Bandeja de notificaciones interna (RF-14)

| Campo | Valor |
|-------|-------|
| ID | 9464110 |
| Estado | New |
| Asignado a | leandroEstiven |
| Módulo | Módulo 1 — Identity & Access: cierre de gaps |
| Etiquetas | p2-medio, m1 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:18.555Z |
| Modificada | 2026-08-07T23:41:37.422Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

RF-14 es el único sin implementación real (~15%). Crear: notificacionesApi, tabla Dexie, bandeja de notificaciones (icono campana en AppBar con badge funcional), acción "marcar como leída", push notifications FCM conectadas.

---

### #66 · [Frontend] Captura de atributos_dinamicos en Registro de Activo (RF-33)

| Campo | Valor |
|-------|-------|
| ID | 9464111 |
| Estado | New |
| Asignado a | Danielsxanti |
| Módulo | Módulo 2 — Biological Assets: cierre de gaps |
| Etiquetas | p1-alto, m2 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:20.084Z |
| Modificada | 2026-08-07T23:25:38.350Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

RegistrarActivoForm no declara controles para atributos_dinamicos. El tipo ya modela el campo (types.ts) pero submit nunca lo incluye. Implementar campos dinámicos según especie, validación contra configuración.

---

### #67 · [Frontend] Validación uniforme de fecha max={HOY} en forms de eventos (RF-39/40/41/42)

| Campo | Valor |
|-------|-------|
| ID | 9464112 |
| Estado | New |
| Asignado a | SamuelPR21 |
| Módulo | Módulo 2 — Biological Assets: cierre de gaps |
| Etiquetas | p1-alto, m2 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:21.690Z |
| Modificada | 2026-08-07T23:25:57.572Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

Solo EventoProductivoForm valida max={HOY} en fecha. Agregar validación de fecha no futura a EventoCrecimientoForm, EventoSanitarioForm y EventoReproductivoForm. Inconsistencia entre formularios del mismo módulo.

---

### #68 · [Frontend] Mapeo ApiError.field → setError en todos los forms de escritura (transversal M2)

| Campo | Valor |
|-------|-------|
| ID | 9464113 |
| Estado | New |
| Asignado a | SamuelPR21 |
| Módulo | Módulo 2 — Biological Assets: cierre de gaps |
| Etiquetas | p1-alto, m2 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:23.408Z |
| Modificada | 2026-08-07T23:25:57.646Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

Ningún formulario del módulo 2 mapea ApiError.field al campo correspondiente vía setError. Todos muestran Alert genérico. Aplicar mapeo en RegistrarActivoForm, EditarActivoModal, todos los Evento*Form, RegistrarBajaModal, CambiarEstadoModal, etc.

---

### #69 · [Frontend] id_especie/id_infraestructura como selects de catálogo (RF-33)

| Campo | Valor |
|-------|-------|
| ID | 9464114 |
| Estado | New |
| Asignado a | Danielsxanti |
| Módulo | Módulo 2 — Biological Assets: cierre de gaps |
| Etiquetas | p2-medio, m2 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:24.934Z |
| Modificada | 2026-08-07T23:25:38.831Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

Reemplazar inputs numéricos libres por selects de catálogo en Registro de Activo. Validar en cliente que especie/infraestructura existe y está activa. Usar endpoints de configuration module.

---

### #70 · [Frontend] Validación cantidad_afectada ≤ cantidad_actual en baja parcial (RF-36/45)

| Campo | Valor |
|-------|-------|
| ID | 9464115 |
| Estado | Ready |
| Asignado a | SamuelPR21 |
| Módulo | Módulo 2 — Biological Assets: cierre de gaps |
| Etiquetas | p2-medio, m2 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:26.427Z |
| Modificada | 2026-08-07T23:26:02.556Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

RegistrarBajaModal no recibe cantidad_actual del lote. Agregar prop y validar que cantidad_afectada no exceda la existencia actual antes de enviar, con mensaje específico de error.

---

### #71 · [Frontend] Bloqueo de TRATAMIENTO/VACUNACION sin DIAGNÓSTICO previo (RF-41)

| Campo | Valor |
|-------|-------|
| ID | 9464116 |
| Estado | New |
| Asignado a | Danielsxanti |
| Módulo | Módulo 2 — Biological Assets: cierre de gaps |
| Etiquetas | p2-medio, m2 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:27.808Z |
| Modificada | 2026-08-07T23:25:44.674Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

Validar en cliente que no se pueda registrar TRATAMIENTO o VACUNACION sin al menos un DIAGNÓSTICO previo en el historial de eventos sanitarios del activo.

---

### #72 · [Frontend] Ocultar campos irrelevantes por categoría reproductiva (RF-42)

| Campo | Valor |
|-------|-------|
| ID | 9464117 |
| Estado | New |
| Asignado a | Danielsxanti |
| Módulo | Módulo 2 — Biological Assets: cierre de gaps |
| Etiquetas | p3-bajo, m2 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:29.328Z |
| Modificada | 2026-08-07T23:25:45.188Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

EventoReproductivoForm muestra campos igual para todas las categorías (ej. "Número de crías" aparece incluso para aborto/servicio). Condicionar campos como lo hace EventoSanitarioForm por tipo.

---

### #73 · [Frontend] Selector/catálogo de fases por especie en CambiarFase (RF-37)

| Campo | Valor |
|-------|-------|
| ID | 9464118 |
| Estado | New |
| Asignado a | Danielsxanti |
| Módulo | Módulo 2 — Biological Assets: cierre de gaps |
| Etiquetas | p2-medio, m2 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:30.847Z |
| Modificada | 2026-08-07T23:25:45.248Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

CambiarFaseModal usa input numérico para id_ciclo_productiva. Reemplazar por select cargado desde el catálogo de fases de la especie del activo. Validar que la fase destino es distinta a la actual.

---

### #74 · [Frontend] Conectar DashboardPage a useDashboardLayout (RF-28)

| Campo | Valor |
|-------|-------|
| ID | 9464119 |
| Estado | New |
| Asignado a | arekkazu |
| Módulo | Módulo 9 — Configuration: cierre de gaps |
| Etiquetas | p0-critico, m9 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:40.500Z |
| Modificada | 2026-08-07T23:16:23.003Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

DashboardPage.tsx es estática con 4 tarjetas KPI hardcodeadas. El layout de DashboardLayoutSection se guarda correctamente pero nunca se consume. Conectar DashboardPage a useDashboardLayout para que los cambios se apliquen en tiempo real.

---

### #75 · [Frontend] Reemplazar buildSnapshot() con captura real de configuración (RF-31)

| Campo | Valor |
|-------|-------|
| ID | 9464120 |
| Estado | New |
| Asignado a | arekkazu |
| Módulo | Módulo 9 — Configuration: cierre de gaps |
| Etiquetas | p1-alto, m9 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:41.651Z |
| Modificada | 2026-08-07T23:16:23.471Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

buildSnapshot() en PlantillaModal.tsx solo envía flags booleanos por categoría en vez de obtener ciclos/patologías/métricas/umbrales reales de la especie seleccionada. Reemplazar por captura real de configuración para que RF-32 pueda mostrar diff antes/después.

---

### #76 · [Frontend] Conectar ContextoInterfaz API al layout/sidebar (RF-25)

| Campo | Valor |
|-------|-------|
| ID | 9464121 |
| Estado | New |
| Asignado a | arekkazu |
| Módulo | Módulo 9 — Configuration: cierre de gaps |
| Etiquetas | p1-alto, m9 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:43.218Z |
| Modificada | 2026-08-07T23:16:19.901Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

ContextoInterfazResponse y contextoApi.obtener() existen pero ningún componente los consume. Conectar al layout: sidebar dinámico según finca/especies configuradas, refresh de permisos durante la sesión, "finca activa" determinada por contexto.

---

### #77 · [Frontend] Implementar i18n con i18next es/en (RF-29)

| Campo | Valor |
|-------|-------|
| ID | 9464122 |
| Estado | New |
| Asignado a | arekkazu |
| Módulo | Módulo 9 — Configuration: cierre de gaps |
| Etiquetas | p2-medio, m9 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:44.809Z |
| Modificada | 2026-08-07T23:16:20.321Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

No existe framework de i18n en el proyecto. Todo el texto está hardcodeado en español. Instalar i18next + react-i18next, crear archivos es.json/en.json, conectar useIdioma.ts para cambiar idioma en tiempo real sin recargar.

---

### #78 · [Frontend] Validar coherencia unidad↔tipo_medición en métricas (RF-16)

| Campo | Valor |
|-------|-------|
| ID | 9464123 |
| Estado | New |
| Asignado a | arekkazu |
| Módulo | Módulo 9 — Configuration: cierre de gaps |
| Etiquetas | p2-medio, m9 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:46.694Z |
| Modificada | 2026-08-07T23:16:21.371Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

RF-16 exige coherencia unidad↔tipo_medición (PESO→kg/g/lb, VOLUMEN→litros/ml, etc.). unidad_medida es texto libre. Agregar validate cruzado y select restrictivo como el de UNIDADES_POR_MEDICION en EventoCrecimientoForm.

---

### #79 · [Frontend] Validar no-solapamiento de niveles de alerta (RF-17)

| Campo | Valor |
|-------|-------|
| ID | 9464124 |
| Estado | New |
| Asignado a | arekkazu |
| Módulo | Módulo 9 — Configuration: cierre de gaps |
| Etiquetas | p2-medio, m9 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:48.290Z |
| Modificada | 2026-08-07T23:16:21.228Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

RF-17 exige que niveles de alerta sean contiguos (límite superior de Precaución = límite inferior de Crítico). Agregar validación cruzada entre niveles, prevención de configuración duplicada (misma especie + misma variable), y validación de rango físicamente válido por variable.

---

### #80 · [Frontend] Catálogo tipo_area extensible, no hardcodeado (RF-20)

| Campo | Valor |
|-------|-------|
| ID | 9464125 |
| Estado | New |
| Asignado a | arekkazu |
| Módulo | Módulo 9 — Configuration: cierre de gaps |
| Etiquetas | p2-medio, m9 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:49.697Z |
| Modificada | 2026-08-07T23:16:21.659Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

TIPOS_AREA está hardcodeado como ['Galpón','Corral','Potrero','Estanque','Invernadero']. RF-20 exige que sea extensible desde Configuración. Crear CRUD de tipos de área con endpoint dedicado.

---

### #81 · [Frontend] UI para registrar sensores bajo dispositivo (RF-21)

| Campo | Valor |
|-------|-------|
| ID | 9464126 |
| Estado | New |
| Asignado a | arekkazu |
| Módulo | Módulo 9 — Configuration: cierre de gaps |
| Etiquetas | p2-medio, m9 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:51.306Z |
| Modificada | 2026-08-07T23:16:22.714Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

sensoresDispositivoApi.registrar y RegistrarSensorDTO existen pero no hay UI. Agregar formulario/botón para registrar sensores bajo un dispositivo desde la sección de IoT, completando el flujo que RF-22 y RF-24 asumen que ya existe.

---

## Sprint 3 — Cierre

### #82 · [Frontend] CSV export en AuditoriaM02View (RF-52)

| Campo | Valor |
|-------|-------|
| ID | 9464127 |
| Estado | New |
| Asignado a | SamuelPR21 |
| Módulo | Módulo 2 — Biological Assets: cierre de gaps |
| Etiquetas | p2-medio, m2 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:57.463Z |
| Modificada | 2026-08-07T23:26:03.056Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

Agregar botón de exportación CSV a AuditoriaM02View.tsx, similar al patrón de AuditoriaPage (RF-10). Exportar resultado completo de filtros aplicados a trazabilidad de eventos de transformación biológica.

---

### #83 · [Frontend] Aviso de reasignación en wizard de sensores (RF-22)

| Campo | Valor |
|-------|-------|
| ID | 9464128 |
| Estado | New |
| Asignado a | arekkazu |
| Módulo | Módulo 9 — Configuration: cierre de gaps |
| Etiquetas | p3-bajo, m9 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:58.420Z |
| Modificada | 2026-08-07T23:16:23.905Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

El wizard de asociación de sensores no advierte que reasignar un sensor finaliza automáticamente su asociación anterior. Agregar verificación previa y mensaje de confirmación antes de completar el wizard.

---

### #84 · [Frontend] Validar tamaño/formatos de logo + botón descartar (RF-26)

| Campo | Valor |
|-------|-------|
| ID | 9464129 |
| Estado | New |
| Asignado a | arekkazu |
| Módulo | Módulo 9 — Configuration: cierre de gaps |
| Etiquetas | p3-bajo, m9 |
| Puntos | — |
| Versión | 2 |
| Creada | 2026-08-07T20:48:59.982Z |
| Modificada | 2026-08-07T23:16:22.572Z |
| Finalizada | — |
| Bloqueada | no |

**Descripción**

Identidad visual: validar tamaño máximo 2 MB (hoy solo informativo), restringir a PNG/JPEG/SVG (no cualquier image/*), y agregar botón "Descartar" para cancelar vista previa sin recargar la página.

---

## Sin sprint asignado

### #85 · [FRONT-END][BACKEND ] IMPLEMENTACION DE SSO

| Campo | Valor |
|-------|-------|
| ID | 9465135 |
| Estado | Done |
| Asignado a | arekkazu |
| Módulo | Módulo 1 — Identity & Access: cierre de gaps |
| Etiquetas | m1, back-end |
| Puntos | — |
| Versión | 7 |
| Creada | 2026-08-08T19:45:50.039Z |
| Modificada | 2026-08-10T01:40:21.409Z |
| Finalizada | 2026-08-15T05:44:47.303Z |
| Bloqueada | no |

**Descripción**

*(sin descripción en Taiga)*
