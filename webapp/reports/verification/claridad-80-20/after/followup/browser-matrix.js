async page => {
 const base='http://127.0.0.1:8791', dir='webapp/reports/verification/claridad-80-20/after/followup/';
 const paths={experiments:'/experimentos',comparison:'/experimentos/96225a72d61e4b5da1288ecb1eeec451/comparacion',library:'/configuraciones'};
 const out={};
 for(const width of [390,799,1100,1280]){
  await page.setViewportSize({width,height:900});out[width]={};
  for(const [name,path] of Object.entries(paths)){
   await page.goto(base+path);await page.waitForLoadState('networkidle');
   out[width][name]=await page.evaluate(()=>{
    const r=document.querySelector('.data-table-region'); const t=r?.querySelector('table');
    const lines=el=>{if(!el)return null;const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let n=walker.nextNode();const rects=[];while(n){const range=document.createRange();range.selectNodeContents(n);rects.push(...Array.from(range.getClientRects()));n=walker.nextNode();}return [...new Set(rects.filter(x=>x.width>0).map(x=>Math.round(x.top)))].length};
    const heads=[...document.querySelectorAll('.data-table-region th')].map(x=>({text:x.textContent?.trim(),wrap:getComputedStyle(x).whiteSpace,lines:lines(x),width:Math.round(x.getBoundingClientRect().width)}));
    const dateCell=r?.querySelector('td.table-date');const nameCell=r?.querySelector('td.table-name');
    return {document:{client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth},region:r?{client:r.clientWidth,scroll:r.scrollWidth,scrollable:r.scrollWidth>r.clientWidth,tabIndex:r.tabIndex,ariaLabel:r.getAttribute('aria-label')}:null,table:t?{client:t.clientWidth,scroll:t.scrollWidth}:null,headers:heads,date:dateCell?{text:dateCell.textContent?.trim(),wrap:getComputedStyle(dateCell).whiteSpace,lines:lines(dateCell)}:null,longName:nameCell?{text:nameCell.textContent?.trim(),lines:lines(nameCell),width:Math.round(nameCell.getBoundingClientRect().width)}:null,libraryCount:document.querySelectorAll('.saved-strategy-row').length};
   });
   if(width===390||width===1280)await page.screenshot({path:`${dir}${name}-${width}.png`,fullPage:true});
  }
 }
 return out;
}
