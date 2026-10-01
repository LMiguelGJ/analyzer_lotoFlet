async page => {
 await page.goto('http://127.0.0.1:8791/experimentos/nuevo'); await page.waitForLoadState('networkidle');
 return await page.evaluate(()=>{
  const input=document.querySelector('input'); input?.focus();
  const rgb=s=>(s.match(/[\d.]+/g)||[]).slice(0,4).map(Number);
  const lum=s=>{const c=rgb(s).slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4));return .2126*c[0]+.7152*c[1]+.0722*c[2]};
  const ratio=(a,b)=>{const x=lum(a),y=lum(b);return +((Math.max(x,y)+.05)/(Math.min(x,y)+.05)).toFixed(2)};
  return [['body','body'],['heading','h1'],['primary','.btn-primary'],['help','.field-help'],['label','.field-label'],['focus','input:focus-visible']].map(([name,q])=>{
   const el=document.querySelector(q);if(!el)return {name,missing:true};
   const s=getComputedStyle(el);let n=el,bg='rgb(255, 255, 255)';
   while(n){let b=getComputedStyle(n).backgroundColor;if(rgb(b)[3]===undefined||rgb(b)[3]>0){bg=b;break}n=n.parentElement}
   return {name,color:s.color,bg,ratio:ratio(s.color,bg),size:s.fontSize,weight:s.fontWeight,outline:s.outlineColor,outlineStyle:s.outlineStyle,outlineRatio:s.outlineStyle==='none'?null:ratio(s.outlineColor,bg),backgroundSource:n?.tagName};
  });
 });
}
