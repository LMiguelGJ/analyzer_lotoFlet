# Revisá la interfaz de Quiniela

U2, U4 y U5 están implementados; tu revisión manual todavía está pendiente. Esta guía comprueba lo que ves y cómo interactuás, no sustituye las pruebas de integridad ni la revisión independiente.

## Antes de empezar

1. Usá el entorno QA preparado en `http://127.0.0.1:5173/laboratorios`.
2. Ese entorno se inició con datos separados bajo `.tmp/mejoras-quiniela/manual-qa-*/data/`. No esperes ver tus corridas habituales ni copies ahí tu base normal.
3. Si la URL no responde, avisá: no uses el launcher habitual como sustituto para estas pruebas, porque puede abrir tu base normal. No hace falta reinstalar ni cambiar la cuota.
4. Recargá antes de escribir un borrador para cargar la interfaz actual. Usá nombres de laboratorio con prefijo `QA`; no borres datos reales.

## Casos manuales

| ID | Qué hacés | Qué debería pasar |
| --- | --- | --- |
| M1 | Entrá en Nuevo laboratorio y enviá con nombre vacío y cobertura 0. | No se crea nada; aparece un resumen de errores, el foco queda en Nombre y sus enlaces te llevan a cada campo inválido. Los valores escritos permanecen. |
| M2 | Corregí los campos, creá `QA interfaz` con reglas válidas y ejecutá una vez. Podés empezar con una ventana corta que tenga datos. | Crear solo guarda reglas. Ejecutar queda bloqueado mientras trabaja; después aparece una corrida guardada. |
| M3 | Abrí el resultado y revisá Neto total y Retorno sobre apostado. | Neto = pagado − apostado. ROI = `100 × neto / apostado`, con signo y dos decimales. Sin apuestas: No disponible. Apostado, pagado, media de cerradas y contadores siguen presentes. |
| M4 | Abrí Datos de la reproducción y revisá cobertura, sorteos evaluados y huecos. | Cobertura dice números seleccionados, no «de 50» ni probabilidad. El desplegable muestra ventana y tres SHA-256 completos: historial, rankings y sesiones. Los huecos son solo entre extremos elegibles. |
| M5 | Si hay más de 50 sesiones, avanzá una página y volvé. Recargá y abrí otra vez la corrida. | Resumen y métricas permanecen al paginar; carga/error se limita a sesiones. No hay saltos o duplicados visibles en los ordinales. La corrida guardada sobrevive a la recarga. |
| M6 | Escribí un borrador en Nuevo laboratorio y reducí/ampliá el viewport cruzando 860/861 px. Repetí con una corrida y página seleccionadas. | En móvil, panel primero; en escritorio, lista primero. Sin selección, lista primero también en móvil. No se pierde texto, selección, página ni foco; no se crea otra corrida. |
| M7 | Navegá con Tab y abrí un laboratorio desde la lista. Probá pantalla estrecha y zoom 200 %. | Foco visible y orden coherente; el enlace lleva el foco al panel. No salta al panel por una carga de datos. El dinero no se corta; la tabla puede desplazarse sin ensanchar toda la página. |

Para M3, un ejemplo de referencia: neto `−1.482.496` y apostado `30.303.350` deben dar `−4,89 %`. No esperes esos importes en una configuración diferente. Un conteo de sesiones sin datos debe mostrar `Sesiones 0 de 0`, nunca `1–0`.

### Opcional: incertidumbre con el navegador sin conexión

Solo en QA y si sabés usar la pestaña Network del navegador:

1. Cargá un laboratorio, activá Offline y pulsá Ejecutar una vez.
2. Debe aparecer el aviso de falta de confirmación y bloquear otro envío.
3. Pulsá Actualizar corridas guardadas todavía Offline: debe seguir bloqueado y permitir volver a consultar.
4. Volvé a Online y consultá de nuevo. Solo la respuesta exitosa libera el bloqueo; no debe ejecutarse nada por sí solo.

Esto prueba la interacción ante un fallo de red. **No demuestra** el caso distinto en que el servidor guardó y devolvió una respuesta exitosa ilegible; ese caso necesita una prueba controlada.

## Cómo devolverme el resultado

No hace falta completar todo antes de avisar. Mandá el primer fallo con este formato:

```text
Caso: M6
Estado: OK / falló / no probado
Pasos:
Esperaba:
Ocurrió:
Navegador y ancho o zoom:
Error exacto o captura:
```

No compartas bases SQLite, credenciales ni archivos `.env`. Un caso no ejecutado queda como no probado, no como aprobado.

## Lo que no te corresponde comprobar a mano

- Atomicidad ante cuota/bytes: que no queden filas parciales ni cambie el uso al rechazar una escritura.
- Corrupción, huellas y equivalencia de todas las sesiones; revisar dos páginas no acredita la totalidad.
- Respuesta HTTP exitosa ilegible después de guardar y preservación de contratos históricos compartidos.
- U3: la migración 20 de época está implementada y probada en bases temporales; caché y lecturas SQL paginadas siguen pendientes de integración y aceptación. No apliques la migración a tu base habitual.

U1 sigue sin aceptación completa. Tampoco se ejecutó una regresión amplia ni se obtuvo la aceptación independiente de U2/U4/U5. Tus resultados manuales se agregan como evidencia concreta sin borrar esos pendientes.
