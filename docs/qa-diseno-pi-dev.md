# QA de diseño frente a pi.dev

Auditoría estática inicial basada en el frontend de `c3cfe5f` y CSS/HTML previamente descargados a `%TEMP%/pidev-audit/`. No hubo screenshots ni navegador/live acceptance. CVPI-08 aplica únicamente los arreglos visuales seguros aprobados, preservando la identidad vigente; las opciones de identidad que figuran en la auditoría original no se adoptaron.

## Identidad confirmada

- Tema oscuro únicamente; se conserva la paleta existente: fondo `#171e26`, superficie `#222830`, campo `#242f3b`, texto `#d0d4d8`, secundario `#adb5bf`, acento `#7eb3da`, separadores `#3b4652` y borde funcional `#6c7f92`.
- Se conservan las fuentes existentes: cuerpo sans y títulos Georgia/serif. Los encabezados mantienen la cursiva serif incumbente, ahora coherente en las superficies que usan `font-heading`; el cuerpo no pasa a cursiva.
- Radio de control `0`: controles y paneles afectados son cuadrados. No se cambió la paleta ni se añadieron fuentes, modo claro, mayúsculas mono ni anchos opcionales de rediseño.

## Correcciones aplicadas

| Hallazgo | Resolución |
| --- | --- |
| Breakpoint `sm` ausente | `tailwind.config.ts` declara `sm: 640px` y conserva `nav: 800px` y `wide: 1100px`; se corrigió el comentario que decía que los defaults estaban sin uso. El CSS compilado incluye las reglas `sm:grid`/`sm:grid-cols-*` a partir de 640px. |
| Ocho utilidades `disabled:opacity-50` | Retiradas de QueueDrawer, configuraciones, experimentos y ajustes. Se mantiene el estado tokenizado `opacity: 1` y cursores disabled existentes; no se usó `!important` para reemplazarlas. |
| Estilos de enlace inconsistentes | Estilo reutilizable `.link` en la capa components: acento, subrayado 1.5px y offset `0.14em`; el hover cambia sólo el color del texto en dispositivos que admiten hover. Foco global conservado. Aplicado a los enlaces y controles-sort actuales de DataTable, RunTrajectory, QueueDrawer, asistente y experimentos; sort conserva botón, tamaño, semántica y teclado. |
| Reduced motion | Animaciones desactivadas, transiciones limitadas a 1ms y scroll automático. Se conservan cambios inmediatos de estado y estilos de foco/hover; no se afirma que el valor anterior por sí mismo suprimiera esos cambios. |
| Cursiva de encabezados desigual | `font-heading` aplica la cursiva serif existente de forma coherente; no se hizo cursiva global al cuerpo. |
| Colores raw del gráfico | Cuatro colores de serie existentes centralizados en `--chart-1..4`, con valores exactos `#876c42`, `#6a7e9c`, `#925e6d`, `#60877a`. La primera serie continúa usando `var(--color-accent, currentColor)`. |
| Radios | `--radius-control: 0`; radios explícitos en los controles/paneles incluidos se retiraron. |

No se aplicaron las propuestas opcionales de cambiar anchos máximos o rediseñar. Ninguna ruta, handler, etiqueta accesible, copy funcional, API o comportamiento financiero se cambió intencionalmente.

## Verificación CVPI-08

- `cd webapp/frontend && npm run test -- --run --maxWorkers=1`: **exit 0**, 35/35 archivos y 485/485 tests pasan. El único fallo de la primera corrida (expectativa antigua de `screens` que excluía `sm`) se resolvió en la actualización autorizada del test; se mantuvieron los casos de layout/nav/foco y no se borraron ni omitieron tests.
- `cd webapp/frontend && npm run typecheck`: **exit 0** (`tsc --noEmit`).
- `cd webapp/frontend && npm run build`: **exit 0**, Vite transformó 70 módulos. Artefactos: `dist/index.html`, `dist/assets/index-Boygnquc.css` (22.64 kB) y `dist/assets/index-BOtJ_3gN.js` (480.45 kB).
- `git diff --check -- webapp/frontend docs/qa-diseno-pi-dev.md`: **exit 0**, sólo advertencias de conversión LF→CRLF del checkout.
- Inspección estructural del CSS compilado: media queries 640/800/1100px; `sm:grid`, `sm:grid-cols-*`, `.link:hover`, `--radius-control: 0`, tokens `--chart-1..4` y `font-heading` presentes. Inspección de las fuentes acotadas: ningún `disabled:opacity-50` ni enlace subrayado ad hoc en las superficies revisadas. Los colores de base existentes permanecen intactos.

## Limitaciones y pendientes

- No se inició navegador/servidor ni se inspeccionó una vista renderizada: screenshots, hover/foco visual, zoom, tablet/coarse-pointer, reduced-motion real, overflow y aceptación manual siguen pendientes para el usuario.
- El script de contexto de Impeccable falló por una aserción ambiental; el detector no se ejecutó. No se reintentó ni se instalaron herramientas.
- Sin aprobación nativa ni revisión visual independiente en este trabajo. Los resultados de test, typecheck, build e inspección CSS no equivalen a aceptación visual en dispositivo.
