async page => {
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  const root = 'webapp/reports/verification/claridad-80-20/after/';
  const base = 'http://127.0.0.1:8791';
  const shortId = '96225a72d61e4b5da1288ecb1eeec451'; // GET /api/v1/experiments, observed at runtime
  const routes = {experiments:'/experimentos', detail:`/experimentos/${shortId}`, comparison:`/experimentos/${shortId}/comparacion`, library:'/configuraciones', settings:'/ajustes', notfound:'/ruta-que-no-existe'};
  const result = {origin:base, browser:await page.evaluate(() => navigator.userAgent), time:new Date().toISOString(), routes:{}, states:{}, keyboard:{}, contrast:{}, errors:[]};
  const visit = async path => { await page.goto(base+path); await page.waitForLoadState('networkidle'); };
  const bounds = async (target=page) => await target.evaluate(() => {
    const width = document.documentElement.clientWidth;
    const offending = [...document.querySelectorAll('body *')].filter(el => {const r=el.getBoundingClientRect(); const s=getComputedStyle(el); return r.width && r.right > width+2 && s.position !== 'fixed' && !el.closest('table, svg, canvas, [role="table"]'); }).slice(0,8).map(el => ({tag:el.tagName, cls:String(el.className).slice(0,80), right:Math.round(el.getBoundingClientRect().right)}));
    return {viewport:innerWidth, document:document.documentElement.scrollWidth, body:document.body.scrollWidth, contentOverflow:document.documentElement.scrollWidth > width+2, offending};
  });
  for (const width of [390,799,1100,1280]) {
    await page.setViewportSize({width,height:900});
    for (const [name,path] of Object.entries(routes)) {
      await visit(path);
      const metric = await bounds();
      const heading = await page.locator('h1').first().textContent().catch(()=>null);
      result.routes[name] ||= {};
      result.routes[name][width] = {...metric, heading};
      if (width===390 || width===1280) await page.screenshot({path:`${root}${name==='notfound'?'not-found':name}-${width}.png`, fullPage:true});
    }
  }
  await page.setViewportSize({width:1280,height:900}); await visit('/experimentos');
  // Actual API filtered state; no fixture mutation.
  await page.getByRole('searchbox',{name:'Buscar por nombre'}).fill('sin-coincidencia-ci04');
  await page.waitForTimeout(700); result.states.filtered = (await page.locator('main').innerText()).slice(0,500);
  await page.screenshot({path:`${root}experiments-filtered-1280.png`,fullPage:true});
  // Isolated GET injection, never presented as genuine empty or incident.
  for (const width of [390,1280]) {
    await page.setViewportSize({width,height:900});
    await page.route('**/api/v1/experiments?*', route => route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({total:0,offset:0,limit:20,items:[]})}));
    await visit('/experimentos'); result.states.emptyInjected = (await page.locator('main').innerText()).slice(0,500);
    await page.screenshot({path:`${root}experiments-empty-${width}.png`,fullPage:true}); await page.unroute('**/api/v1/experiments?*');
  }
  await page.route('**/api/v1/experiments?*', route => route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Fallo sintético de auditoría'})}));
  await visit('/experimentos'); result.states.errorInjected=(await page.locator('main').innerText()).slice(0,500); await page.screenshot({path:`${root}experiments-error-injected-1280.png`,fullPage:true}); await page.unroute('**/api/v1/experiments?*');
  // Delayed GET, screenshot while pending, then release response.
  let release; const pending = new Promise(resolve => release=resolve);
  await page.route('**/api/v1/experiments?*', async route => {await pending; await route.continue();});
  await page.goto(base+'/experimentos',{waitUntil:'domcontentloaded'});
  result.states.loadingInjected=(await page.locator('main').innerText()).slice(0,500);
  await page.screenshot({path:`${root}experiments-loading-injected-1280.png`,fullPage:true}); release(); await page.waitForLoadState('networkidle'); await page.unroute('**/api/v1/experiments?*');
  // Queue opened on actual data; close and check focus.
  const trigger=page.getByRole('button',{name:'Cola'}); await trigger.focus(); await trigger.click();
  result.keyboard.queueOpen = await page.evaluate(() => ({focus:document.activeElement?.outerHTML.slice(0,160),dialogs:[...document.querySelectorAll('[role="dialog"]')].map(x=>x.getAttribute('aria-label'))}));
  for (const width of [390,1280]) {await page.setViewportSize({width,height:900}); await page.screenshot({path:`${root}queue-drawer-${width}.png`,fullPage:true});}
  await page.keyboard.press('Escape'); result.keyboard.queueAfterEscape=await page.evaluate(()=>({focus:document.activeElement?.textContent?.trim(),dialogs:document.querySelectorAll('[role="dialog"]').length}));
  await visit('/experimentos'); await page.getByRole('button',{name:/Acciones de Prueba base/}).click();
  result.keyboard.actions = (await page.locator('main').innerText()).slice(-400);
  result.keyboard.tabSequence = [];
  await page.keyboard.press('Tab'); result.keyboard.tabSequence.push(await page.evaluate(()=>({tag:document.activeElement?.tagName,text:document.activeElement?.textContent?.trim().slice(0,70),outline:getComputedStyle(document.activeElement).outlineStyle})));
  await page.keyboard.press('Shift+Tab'); result.keyboard.tabSequence.push(await page.evaluate(()=>({tag:document.activeElement?.tagName,text:document.activeElement?.textContent?.trim().slice(0,70),outline:getComputedStyle(document.activeElement).outlineStyle})));
  await page.keyboard.press('Escape');
  result.keyboard.actionsAfterEscape=await page.evaluate(()=>({focus:document.activeElement?.textContent?.trim().slice(0,80),dialogCount:document.querySelectorAll('[role="dialog"]').length}));
  // Wizard state uses disposable pages; closing a dirty form bypasses beforeunload, never submits.
  for (const width of [390,799,1100,1280]) {
    const form=await page.context().newPage(); await form.setViewportSize({width,height:900});
    await form.goto(base+'/experimentos/nuevo'); await form.waitForLoadState('networkidle');
    result.routes.wizardConditions ||= {}; result.routes.wizardConditions[width]=await bounds(form);
    if ([390,1280].includes(width)) await form.screenshot({path:`${root}wizard-conditions-${width}.png`,fullPage:true});
    await form.getByRole('textbox',{name:'Nombre del experimento'}).fill('Auditoría sin enviar');
    await form.getByRole('combobox',{name:'Sorteo inicial'}).selectOption({label:'2025-09-02 05:10'});
    await form.getByRole('textbox',{name:'Capital inicial (RD$)'}).fill('1000');
    await form.getByRole('textbox',{name:'Meta de saldo final (RD$)'}).fill('2000');
    await form.getByRole('textbox',{name:'Código para repetir el azar (semilla)'}).fill('42');
    await form.getByRole('button',{name:'Continuar'}).click();
    result.routes.wizardStrategies ||= {}; result.routes.wizardStrategies[width]=await bounds(form);
    if ([390,1280].includes(width)) await form.screenshot({path:`${root}wizard-strategies-${width}.png`,fullPage:true});
    if (width===1280) {
      result.states.wizardAfterNext = (await form.locator('main').innerText()).slice(-500);
      const next=form.getByRole('button',{name:'Continuar'});
      if (await next.isEnabled()) {await next.click(); result.states.review = (await form.locator('main').innerText()).slice(0,1200); await form.screenshot({path:`${root}wizard-review-1280.png`,fullPage:true});}
    }
    await form.close({runBeforeUnload:false});
  }
  // Measure computed color against solid backgrounds; alpha compositing captured separately as a limitation.
  await visit('/experimentos/nuevo');
  result.contrast = await page.evaluate(() => {
    const samples=[['body','body'],['heading','h1'],['primary','.btn-primary'],['field-help','.field-help'],['field-label','.field-label'],['focus','input:focus-visible']];
    const input=document.querySelector('input'); input?.focus();
    const parse=s=>{const m=s.match(/[\d.]+/g); return m?m.slice(0,4).map(Number):[]};
    const luminance=c=>{const v=c.slice(0,3).map(x=>x/255).map(x=>x<=0.04045?x/12.92:Math.pow((x+0.055)/1.055,2.4));return 0.2126*v[0]+0.7152*v[1]+0.0722*v[2]};
    const ratio=(a,b)=>{let x=luminance(parse(a)),y=luminance(parse(b));return +((Math.max(x,y)+.05)/(Math.min(x,y)+.05)).toFixed(2)};
    return samples.map(([name,selector])=>{const el=document.querySelector(selector); if(!el)return {name,missing:true}; const s=getComputedStyle(el); let bg=el, background='rgba(0, 0, 0, 0)'; while(bg){const b=getComputedStyle(bg).backgroundColor;if(parse(b)[3]===undefined || parse(b)[3]>0){background=b;break}bg=bg.parentElement} return {name,tag:el.tagName,color:s.color,background,contrast:ratio(s.color,background),fontSize:s.fontSize,fontWeight:s.fontWeight,outlineColor:s.outlineColor,outlineStyle:s.outlineStyle,outlineWidth:s.outlineWidth,backgroundSource:bg?.tagName};});
  });
  result.states.help=await page.evaluate(()=>{const el=document.querySelector('input[aria-describedby]');return el?{input:el.getAttribute('aria-label')||el.id, describedBy:el.getAttribute('aria-describedby'), help:el.getAttribute('aria-describedby')?.split(' ').map(id=>({id,exists:!!document.getElementById(id),text:document.getElementById(id)?.textContent?.slice(0,180)}))}:null});
  return result;
}
