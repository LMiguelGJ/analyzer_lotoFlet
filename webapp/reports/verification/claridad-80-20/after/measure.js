async page => {
 const base='http://127.0.0.1:8791';
 const routes={experiments:'/experimentos',wizard:'/experimentos/nuevo',detail:'/experimentos/96225a72d61e4b5da1288ecb1eeec451',comparison:'/experimentos/96225a72d61e4b5da1288ecb1eeec451/comparacion',library:'/configuraciones',settings:'/ajustes'};
 const out={};
 for(const width of [390,799,1100,1280]) {
  await page.setViewportSize({width,height:900}); out[width]={};
  for(const [name,path] of Object.entries(routes)) {
   await page.goto(base+path); await page.waitForLoadState('networkidle');
   out[width][name]=await page.evaluate(()=>({doc:document.documentElement.scrollWidth,view:document.documentElement.clientWidth,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+2,heading:document.querySelector('h1')?.textContent}));
  }
 }
 return out;
}
