# Resultado de Prueba: TC-M05-G16

**Requerimiento:** RF-76 (CU03, `POST /suministros/medicamentos`)  
**Grupo:** TC-M05-G16 — Evento sanitario vinculado y registros duplicados  
**Subcasos cubiertos:** TC-M05-006 (A01–A04) y TC-M05-007 (B01–B02)  
**Veredicto:** Aprobado (9/9 pruebas conformes, 0 fallidas)  
**Ambiente:** Staging TEST (`https://www.api.inmero.co/api-sgpmp-test`)  
**Mecanismo:** Sandbox transaccional PostgreSQL (`X-Test-Run-Id: tc-m05-g16-316436c7-0abe-48e1-8b62-f1c585915288`)  

---

## 1. Resumen de Checkpoints

| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|:------:|
| 1 | T00 Línea base y setup de precondiciones | HTTP 200 en consultas base de activos 853 y 5; HTTP 201 en apertura de fase (853) y creación de eventos sanitarios EA (853) y EB (5) | Línea base capturada para activos 853 y 5 (HTTP 200). Fase abierta en 853 (HTTP 201) y eventos EA y EB creados (HTTP 201) | **OK** |
| 2 | A01 Vínculo válido con evento sanitario | HTTP 201, id_evento_sanitario == EA en respuesta, incremento de +1 en medicamentos del activo 853 | HTTP 201 Created, medicamento vinculado con id_evento_sanitario EA, conteo +1 en sandbox | **OK** |
| 3 | A02 Rechazo por evento sanitario inexistente | HTTP 422 (E12), mensaje contiene 'evento sanitario', sin persistencia | HTTP 422 Unprocessable Entity (EVENTO_SANITARIO_INVALIDO), mensaje menciona 'evento sanitario', sin persistencia | **OK** |
| 4 | A03 Rechazo por evento sanitario de otro activo | HTTP 422 (E12), mensaje contiene 'evento sanitario', sin persistencia | HTTP 422 Unprocessable Entity (EVENTO_SANITARIO_INVALIDO), mensaje menciona 'evento sanitario', sin persistencia | **OK** |
| 5 | A04 Registro preventivo sin evento sanitario | HTTP 201, id_evento_sanitario null, incremento de +1 en medicamentos del activo 853 | HTTP 201 Created, medicamento registrado con id_evento_sanitario=null, conteo +1 en sandbox | **OK** |
| 6 | B01 Rechazo de registro duplicado exacto | Primer registro HTTP 201; segundo registro idéntico rechazado con HTTP 409 (E13, CA-7), mensaje contiene 'duplicad', sin incremento adicional | Primer registro HTTP 201, duplicado idéntico rechazado con HTTP 409 Conflict (MEDICAMENTO_DUPLICADO), mensaje contiene 'duplicad' | **OK** |
| 7 | B02 Dosis subsecuente en hora posterior | HTTP 201, id de registro independiente y distinto al previo, incremento de +1 en medicamentos del activo 853 | HTTP 201 Created a las 14:00 (hora posterior), nuevo id_registro generado, conteo +1 en sandbox | **OK** |
| 8 | T98 Cierre ordenado de sandbox | DELETE /test-control/runs/<run_id> responde HTTP 200 con 'Rollback exitoso' | DELETE HTTP 200: {"status": "Rollback exitoso"} | **OK** |
| 9 | T99 Verificación de inocuidad final sin sandbox | Conteos de medicamentos, estados y fases en activos 853 y 5 coinciden 100% con la línea base capturada en T00 | Conteos, estados y fases en activos 853 y 5 verificados 100% idénticos fuera de sandbox | **OK** |

---

## 2. Observaciones de Diseño e Implementación

1. **Nombre del campo en contrato DTO vs Especificación (P1):**
   - La especificación funcional / CU03 menciona el atributo como `tipo_evento_sanitario` o referencia textual genérica.
   - La implementación real en backend (`RegistrarMedicamentoDTO` en `src/supplies/infrastructure/dto/registrar_medicamento_dto.py`) utiliza `id_evento_sanitario: Optional[int] = Field(default=None, gt=0)`.
   - Se validó exitosamente contra el contrato real de backend (`id_evento_sanitario`).

2. **Evaluación de duplicidad con dosis distinta (Diagnóstico exploratorio):**
   - **Especificación (Restricción 13):** Menciona que la duplicidad considera activo, medicamento, dosis, fecha y hora.
   - **Comportamiento observado en backend:** El caso de uso (`RegistrarMedicamentoUseCase:195`) y el repositorio invocan `existe_duplicado_validado` evaluando únicamente `(id_activo_biologico, nombre_medicamento, fecha_aplicacion, hora_aplicacion)` sin incluir `dosis_aplicada`.
   - **Resultado de la sonda diagnóstica:** Una petición con misma fecha, misma hora ("08:30:00") y dosis diferente (15.0 ml vs 5.0 ml) respondió `HTTP 409 Conflict` (`MEDICAMENTO_DUPLICADO`). Se deja documentado que en la implementación vigente la clave de unicidad temporal por activo es `(activo, medicamento, fecha, hora)`.

3. **Cobertura no ejecutada por riesgo de efecto colateral irreversible:**
   - La regla de negocio que calcula `fecha_fin_retiro` propia por medicamento y activa el estado `EN_TRATAMIENTO` mediante RF-44 exige `periodo_retiro_dias > 0`.
   - La invocación de RF-44 dispara el envío real de correo electrónico SMTP (`NotificacionMedicamentoEmailAdapter`), operación externa irreversible que el rollback del sandbox de base de datos no puede deshacer.
   - Por estricto cumplimiento del principio de inocuidad en el ambiente compartido de TEST, todas las pruebas se ejecutaron con `periodo_retiro_dias = 0`.

4. **Inocuidad y Reversión Transaccional:**
   - Cierre de corrida: `DELETE /test-control/runs/tc-m05-g16-316436c7-0abe-48e1-8b62-f1c585915288` respondió `HTTP 200` (`{"status": "Rollback exitoso"}`).
   - La verificación independiente (T99 fuera de sandbox) confirmó que los conteos de medicamentos, estados de activo y fases activas de los activos 853 y 5 quedaron exactamente idénticos a la línea base capturada en T00.

---

## 3. Estado de Defectos (INC)

- **INC:** ninguno (todas las precondiciones, rechazos y flujos de negocio respondieron conforme a los criterios de aceptación y códigos de respuesta vigentes).
