# Documento de entrega — Módulo 1 (Identidad y Acceso) al equipo de Despliegue

| Campo | Valor |
|---|---|
| Módulo | M01 — Identidad y Acceso (`src/identity_access/`) |
| Fecha de corte | 2026-09-13 |
| Fuente | `informe_consolidado_pruebas_M01.md` v2.1 (2026-09-13), `qa-dashboard/` (scanner corregido — ver nota), `qa-dashboard/incidencias.csv` |
| Emite | Equipo QA |
| Destino | Equipo de Despliegue |

> **Nota de verificación:** antes de emitir esta entrega se detectó y corrigió
> un defecto en el escáner del panel QA (`qa-dashboard/scanner.py`) que, para
> casos con varios reportes de reintento, podía elegir el intento equivocado
> por tener mtimes casi idénticos (herencia de un `git checkout` en bloque).
> El % de aprobación real del módulo es **91.5 %**, no el 82.3 % que mostraba
> el informe del 08-09 (v2.0 lo había corregido a 90.8 %; v2.1 lo sube a
> 91.5 % tras reverificar en vivo INC-M01-03-119 el 13-09). Esa misma
> reverificación destapó un defecto Crítico nuevo — ver el criterio 3 abajo.

---

## Verificación de criterios de cierre de módulo

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | % de casos con veredicto Aprobado sobre el total planeado | ≥ 85 % | **129/141 = 91.5 %** | ✅ |
| 2 | RF del módulo con al menos un caso ejecutado | 100 % (ningún RF en 0 %) | **14/14 RF (RF-01 a RF-14) con casos ejecutados** — 100 % | ✅ |
| 3 | Defectos Crítico/Severo abiertos sin plan de mitigación aceptado por Desarrollo | 0 | **1** — INC-M01-24-500-nombre-rol (Crítico, descubierto el 13-09 al reverificar INC-M01-03-119) aún no tiene plan de Desarrollo. INC-M01-03-119 ya se cerró con retest exitoso (ver nota abajo) | ❌ **No cumple** |
| 4 | Casos Rechazados/Bloqueados sin incidencia formal o justificación documentada | 0 | **0** — los 12 casos Rechazados están cubiertos por una incidencia formal (`incidencias.csv`), un hallazgo documentado (sección 4.B del informe) o una causa de ambiente documentada (sección 4.C) | ✅ |
| 5 | Casos con veredicto fijado a mano (`declarados_sin_evidencia.csv`) | ≤ 5 % del módulo | **1/141 = 0.7 %** (TC-M01-052, extensión confirmada de TC-M01-053) | ✅ |
| 6 | Informe consolidado del módulo redactado con la plantilla completa | Completo | **Completo** — `informe_consolidado_pruebas_M01.md` v2.1, todas las secciones de la plantilla (resumen, por RF, cobertura, registro de defectos, condiciones de entrega, control de versiones) | ✅ (firmas pendientes — ver abajo) |

**El módulo NO certifica el cierre completo al 2026-09-13 — falla el criterio 3.**
Se descubrió un defecto Crítico nuevo (INC-M01-24-500-nombre-rol) durante la
reverificación de INC-M01-03-119, sin plan de mitigación de Desarrollo
todavía. Esto es un hallazgo genuino de esta misma sesión de QA, no una
condición preexistente que se venía arrastrando — se reporta de inmediato
en vez de esperar al siguiente corte. Una excepción a este criterio solo la
autoriza Coordinación, y debe quedar registrada en el control de versiones
del informe (no la está QA decidiendo por su cuenta).

---

## Notas que Despliegue debe conocer

1. **RF-13 (Visualización de perfil propio) sigue en 40 % de aprobación** (2/5
   casos). El defecto es de frontend: la tabla de usuarios no propaga
   `id_usuario`, por lo que el detalle de perfil no abre
   (`/usuarios/undefined/detalle` → HTTP 400). Está documentado como
   INC-M01-11-87/89, sin cambios desde el corte del 08-09. No bloquea ninguno
   de los 6 criterios de cierre (RF-13 sí tiene casos ejecutados y el defecto
   está formalizado), pero **la función "ver mi perfil" no funciona en
   producción tal como está el código actual de la tabla de usuarios** si se
   despliega sin la corrección de frontend.
2. **INC-M01-03-119 (Crítico, RF-03 — eliminar rol) ya se cerró.** Se
   reverificó en vivo contra TEST el 2026-09-13 con `admin.dev@gmail.com`:
   `DELETE /roles/{id}` responde 200 y elimina de verdad un rol sin usuarios
   asociados (evidencia: `TC-M01-119/test_tc_m01_119_v2.py`).
3. **INC-M01-24-500-nombre-rol (Crítico, nuevo, RF-03 — crear rol) — bloquea
   el criterio 3.** Durante la reverificación anterior se descubrió que
   `POST /roles/` responde HTTP 500 cuando `nombre_rol` empieza exactamente
   con `"Auxiliar de Campo"` (el nombre del rol semilla original, ya
   eliminado). Reproducido 10/10 veces fuera de pytest (curl + Python
   `requests`, 3 logins distintos, con control intercalado que descarta
   temporización). **No bloquea ningún caso de prueba planeado** (nadie más
   necesita crear un rol con ese nombre exacto), pero es un defecto Crítico
   real sin plan de Desarrollo — Despliegue no debería tratar el módulo como
   cerrado hasta que Coordinación decida si esto amerita una excepción
   registrada o si se espera el plan de Desarrollo. Evidencia completa en
   `INC-M01-24-500-nombre-rol/Resultados/INC-M01-24_evidencia-v2.0.md`
   (incluye una anomalía sin explicar: la reproducción vía pytest no dispara
   el 500 que sí dispara el mismo código fuera de pytest — señalado para que
   Desarrollo lo investigue, no se ocultó).
4. **`qa-dashboard/incidencias.csv` está desactualizado**: 10 filas siguen
   marcadas "Abierto" pese a tener evidencia de retest exitoso, y todavía no
   incluye INC-M01-24-500-nombre-rol (detalle en la sección 4.A del informe
   consolidado). No afecta los resultados de este documento (que se basan en
   el estado real de las pruebas, no en el campo "Estado" del CSV), pero QA
   debe sincronizarlo antes de usarlo como fuente para otro módulo.
5. **Firmas pendientes**: el informe consolidado (sección 6) aún no tiene las
   firmas de Responsable QA, Líder de Desarrollo y Coordinación/PM. Se
   recomienda obtenerlas antes de que Despliegue programe la ventana de
   despliegue, para que la entrega quede formalmente aceptada por las tres
   partes.

---

## Firmas de entrega

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM | | | |
| Equipo de Despliegue (recibido) | | | |
