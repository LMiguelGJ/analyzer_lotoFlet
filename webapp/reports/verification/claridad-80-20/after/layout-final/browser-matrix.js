async page => {
  const base = 'http://127.0.0.1:8791';
  const dir = 'webapp/reports/verification/claridad-80-20/after/layout-final/';
  const paths = {
    experiments: '/experimentos',
    comparison: '/experimentos/96225a72d61e4b5da1288ecb1eeec451/comparacion',
    library: '/configuraciones'
  };
  const result = {};
  for (const width of [390, 799, 1100, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    result[width] = {};
    for (const [surface, path] of Object.entries(paths)) {
      await page.goto(base + path);
      await page.waitForLoadState('networkidle');
      result[width][surface] = await page.evaluate(() => {
        const rect = element => { const r = element.getBoundingClientRect(); return { left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width) }; };
        const lines = element => {
          if (!element) return null;
          const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
          const tops = [];
          let node;
          while ((node = walker.nextNode())) {
            const range = document.createRange(); range.selectNodeContents(node);
            tops.push(...Array.from(range.getClientRects()).filter(r => r.width > 0).map(r => Math.round(r.top)));
          }
          return new Set(tops).size;
        };
        const region = document.querySelector('.data-table-region');
        const table = region?.querySelector('table');
        const action = region?.querySelector('td.table-actions button');
        const date = region?.querySelector('td.table-date');
        const name = region?.querySelector('td.table-name');
        const saved = document.querySelector('.saved-strategy-row');
        const list = saved?.querySelector('.data-list');
        const values = saved ? Array.from(saved.querySelectorAll('dd')) : [];
        const buttons = saved ? Array.from(saved.querySelectorAll('a.btn, button.btn')) : [];
        return {
          document: { client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth },
          region: region ? { client: region.clientWidth, scroll: region.scrollWidth, scrollLeft: region.scrollLeft, ariaLabel: region.getAttribute('aria-label'), tabIndex: region.tabIndex, rect: rect(region) } : null,
          table: table ? { width: Math.round(table.getBoundingClientRect().width) } : null,
          headers: region ? Array.from(region.querySelectorAll('th')).map(h => ({ text: h.textContent.trim(), lines: lines(h), width: rect(h).width, whiteSpace: getComputedStyle(h).whiteSpace })) : [],
          date: date ? { text: date.textContent.trim(), lines: lines(date), width: rect(date).width, whiteSpace: getComputedStyle(date).whiteSpace } : null,
          longName: name ? { text: name.textContent.trim(), lines: lines(name), width: rect(name).width, overflowWrap: getComputedStyle(name).overflowWrap } : null,
          action: action ? { rect: rect(action), visibleAtZero: rect(action).left >= rect(region).left && rect(action).right <= rect(region).right } : null,
          library: saved ? {
            count: document.querySelectorAll('.saved-strategy-row').length,
            row: rect(saved), list: rect(list),
            values: values.map(v => ({ text: v.textContent.trim(), width: rect(v).width, lines: lines(v) })),
            actions: buttons.map(b => ({ text: b.textContent.trim(), rect: rect(b), visible: rect(b).left >= 0 && rect(b).right <= document.documentElement.clientWidth }))
          } : null
        };
      });
      await page.screenshot({ path: `${dir}${surface}-${width}.png`, fullPage: true });
      if (surface === 'experiments' && (width === 390 || width === 1280)) {
        const region = page.locator('.data-table-region');
        await region.focus();
        await page.keyboard.press('ArrowRight');
        const arrow = await region.evaluate(el => el.scrollLeft);
        let tabs = 0;
        while (tabs < 12) {
          await page.keyboard.press('Tab'); tabs++;
          if (await page.getByRole('button', { name: 'Acciones de Prueba base 80-20' }).evaluate(el => el === document.activeElement)) break;
        }
        const focused = await page.evaluate(() => {
          const region = document.querySelector('.data-table-region');
          const button = document.activeElement;
          const br = button.getBoundingClientRect(), rr = region.getBoundingClientRect();
          return { scrollLeft: region.scrollLeft, name: button.getAttribute('aria-label'), visible: br.left >= rr.left && br.right <= rr.right };
        });
        await page.keyboard.press('Enter');
        const menuOpen = await page.getByRole('menu', { name: 'Acciones de Prueba base 80-20' }).count();
        await page.keyboard.press('Escape');
        const restored = await page.getByRole('button', { name: 'Acciones de Prueba base 80-20' }).evaluate(el => el === document.activeElement);
        result[width].experiments.keyboard = { arrowScrollLeft: arrow, tabsToAction: tabs, focused, menuOpen, restored };
      }
    }
  }
  return result;
}
