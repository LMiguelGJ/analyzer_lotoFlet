async page => {
 const dir='webapp/reports/verification/claridad-80-20/after/followup/',base='http://127.0.0.1:8791/configuraciones',out={};
 for(const width of [390,1280]){
  const view=await page.context().newPage();await view.setViewportSize({width,height:900});await view.goto(base);await view.waitForLoadState('networkidle');
  await view.getByRole('button',{name:'Nueva estrategia guardada'}).click();
  out[width]={draft:{heading:await view.locator('main h2').allTextContents(),saveDisabled:await view.getByRole('button',{name:'Guardar estrategia',exact:true}).isDisabled(),itemCount:await view.locator('.saved-strategy-row').count()}};
  await view.screenshot({path:`${dir}library-draft-${width}.png`,fullPage:true});
  await view.getByRole('button',{name:'Cancelar edición'}).click();
  out[width].afterCancel={itemCount:await view.locator('.saved-strategy-row').count(),editorCount:await view.getByRole('button',{name:'Guardar estrategia',exact:true}).count()};
  if(width===390){
   const trigger=view.getByRole('button',{name:'Eliminar Plantilla frío conservadora'});await trigger.focus();await trigger.click();
   out[width].confirm=await view.evaluate(()=>({dialog:document.querySelector('[role=alertdialog]')?.innerText,focus:document.activeElement?.textContent?.trim()}));
   await view.keyboard.press('Escape');out[width].escape=await view.evaluate(()=>({dialog:!!document.querySelector('[role=alertdialog]'),focus:document.activeElement?.textContent?.trim()}));
   await trigger.click();await view.getByRole('button',{name:'Cancelar',exact:true}).click();out[width].cancel=await view.evaluate(()=>({dialog:!!document.querySelector('[role=alertdialog]'),focus:document.activeElement?.textContent?.trim()}));
   out[width].itemCountFinal=await view.locator('.saved-strategy-row').count();
  }
  await view.close({runBeforeUnload:false});
 }
 return out;
}
