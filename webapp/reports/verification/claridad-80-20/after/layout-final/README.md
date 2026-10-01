# CI04 — cierre de distribución (layout final)

## Causa y ajuste

La tabla compartida tenía `min-w-max`: sus mínimos de columna sumaban 1075 px en el recheck anterior, más que los 1012 px de la región a 1280 px. La última columna y «Acciones» quedaban fuera sin necesidad de scroll. Se retiró ese mínimo intrínseco y se conservó `w-full`: las columnas mantienen sus mínimos semánticos, pero sólo la región desplaza horizontalmente cuando no hay ancho suficiente. En biblioteca, la fila de estrategia guardada pasó de `minmax(0, 1fr) auto` a una única columna fluida; los controles quedan debajo de los datos y pueden ajustarse sin comprimir los valores. No se cambió contenido, orden DOM, funcionalidad, formatos ni etiquetas.

## Navegador real

Chromium headless, servidor propio `127.0.0.1:8791`, fixture sintético copiado `OS_TEMP/ci-80-20-harness/followup-data` (dos experimentos y una plantilla). Navegación GET; no se ejecutó POST, DELETE ni acción mutadora. Capturas `experiments-*.png`, `comparison-*.png` y `library-*.png` a 390, 799, 1100 y 1280 px. Medidas completas: `matrix-run.txt`; resumen: `matrix.json`; receta: `browser-matrix.js`. Una sola iteración layout → navegador.

- **1280 px, experimentos:** región/tabla 1012/1012 px, scroll 0, cinco encabezados en una línea y «Acciones» visible sin desplazar. Fecha completa en una línea; nombre largo completo en dos líneas. Documento 1280/1280 px.
- **390 px, experimentos:** región 332 px, tabla 921 px, documento 390/390 px. Nombre largo en tres líneas naturales; encabezados y fecha en una línea. La región recibe foco, `ArrowRight` mueve 40 px; siete Tab alcanzan «Acciones», que desplaza localmente a 589 px, abre menú con Enter y restaura foco con Escape.
- **799 y 1100 px:** el scroll local restante es necesario (741/921 y 832/921 px), sin overflow del documento.
- **Comparación compartida:** encabezados completos en una línea; región/tabla 1012/1012 px a 1280 px, 332/881 px a 390 px; sin overflow del documento en los cuatro anchos.
- **Biblioteca poblada:** valores de 814 px a 1280 px (frente a la estrechez anterior); 134 px a 390 px y acciones visibles debajo, sin overflow del documento. Capturas revisadas visualmente.

## Validación

- `cd webapp/frontend && npm run test -- --run`: 25 archivos, **282/282** tests OK. Aparece en stderr el error esperado de jsdom para el status ficticio `bogus`; la suite termina con código 0.
- `cd webapp/frontend && npm run typecheck`: OK.
- `cd webapp/frontend && npm run build`: OK.
- `node "<impeccable-skill>/scripts/detect.mjs" --json webapp/frontend/src`: `[]`, una vez tras la última edición fuente.
- `git diff --check`: OK, sólo advertencias de conversión LF→CRLF. Diff stat de rutas prohibidas: vacío.
- El único error de consola observado fue un 404 de `/favicon.ico`, ajeno al layout. El proceso propio Python PID 4528 se verificó por puerto, ejecutable y línea de comandos; se apagó, sin listener en 8791. Sesión de navegador cerrada.

## Hashes finales SHA-256 de fuente intervenida

| Archivo bajo `webapp/frontend/src/` | SHA-256 |
| --- | --- |
| `components/DataTable.tsx` | `5d0423fee8ffad98fffbe69bb34aebff69d43b5f607103294478af280068cc0c` |
| `components/DataTable.test.tsx` | `6d93ad02041ae62dafd43e0b542b593e9a8477e008a276aa58388be75892953d` |
| `pages/configurations/ConfigurationsPage.test.tsx` | `345eecd3f71623b8da448da7b2169278f4d646df0f9deeb3d48079cdc25f9d89` |
| `styles/index.css` | `6624e5cd95b5ceb8dc5d040f3b85e7b24ed0e7fbc6fd77d001da82986b0fbb85` |

## Cinco aprendizajes

1. `min-w-max` protege contenidos, pero también puede imponer scroll innecesario en escritorio.
2. El mínimo de cada columna es más preciso que un mínimo rígido para toda la tabla.
3. La biblioteca necesita prioridad de ancho para sus valores; las acciones toleran bajar de línea.
4. jsdom protege estructura y clases; sólo el navegador demuestra anchuras, recorte y foco visible.
5. Un mismo componente compartido debe medirse en todas sus rutas, no sólo donde apareció el defecto.
