async page => {
 const base='http://127.0.0.1:8791/experimentos', dir='webapp/reports/verification/claridad-80-20/after/followup/';const out={};
 for(const width of [390,1280]){
  await page.setViewportSize({width,height:900});await page.goto(base);await page.waitForLoadState('networkidle');
  const region=page.getByRole('region',{name:'Experimentos'}); await region.focus();
  const initial=await page.evaluate(()=>({focus:document.activeElement?.getAttribute('aria-label'),scroll:document.querySelector('.data-table-region')?.scrollLeft}));
  await page.keyboard.press('ArrowRight');await page.waitForTimeout(200);
  const arrow=await page.evaluate(()=>({scroll:document.querySelector('.data-table-region')?.scrollLeft,focus:document.activeElement?.getAttribute('aria-label')}));
  await page.keyboard.press('Tab');const tab=await page.evaluate(()=>({tag:document.activeElement?.tagName,name:document.activeElement?.textContent?.trim(),outline:getComputedStyle(document.activeElement).outlineStyle}));
  const action=page.getByRole('button',{name:'Acciones de Prueba base 80-20'});await action.focus();await page.waitForTimeout(200);
  const focusAction=await page.evaluate(()=>{const r=document.querySelector('.data-table-region'),b=document.activeElement?.getBoundingClientRect(),rr=r.getBoundingClientRect();return {scroll:r.scrollLeft,buttonVisible:b?.left>=rr.left&&b?.right<=rr.right,buttonText:document.activeElement?.textContent?.trim(),outline:getComputedStyle(document.activeElement).outlineStyle}});
  await page.screenshot({path:`${dir}experiments-${width}-action-focused.png`,fullPage:true});
  await page.keyboard.press('Enter');const opened=await page.evaluate(()=>({menu:document.querySelector('[role=menu]')?.getAttribute('aria-label'),focus:document.activeElement?.textContent?.trim()}));
  await page.keyboard.press('Escape');const closed=await page.evaluate(()=>({menu:!!document.querySelector('[role=menu]'),focus:document.activeElement?.getAttribute('aria-label')}));
  out[width]={initial,arrow,tab,focusAction,opened,closed};
 }
 return out;
}
