// Local synthetic API only. Never connects to the backend, provider or production.
const { chromium } = require('playwright-core');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../frontend');
const server = http.createServer((req,res)=>{
  const file = {'/':'index.html','/app.js':'app.js','/styles.css':'styles.css','/llm-ui.js':'llm-ui.js','/business-ui.js':'business-ui.js'}[req.url];
  if(!file){res.writeHead(404);return res.end();}
  res.setHeader('Content-Type',file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html');
  res.end(fs.readFileSync(path.join(root,file)));
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin=`http://127.0.0.1:${server.address().port}`;
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage();const errors=[];const mutations=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
    const request=route.request(),url=new URL(request.url());
    if(url.origin!==origin)return route.abort();
    if(!url.pathname.startsWith('/api/'))return route.continue();
    const endpoint=url.pathname.slice(4);let data;
    if(request.method()!=='GET')mutations.push({endpoint,body:request.postDataJSON()});
    if(endpoint==='/dashboard/summary')data={counts:{}};
    else if(endpoint==='/business/profile')data={version:1,data:{name:'Empresa fictícia',description:'Descrição fictícia',hours:'9h às 18h'}};
    else if(endpoint==='/business/products')data=[{id:'product-1',name:'Produto fictício',price_text:'R$ 100',active:true}];
    else if(endpoint==='/business/processes')data=[{id:'process-1',name:'Processo fictício',steps:['a','b'],sla_text:'2 dias',active:true}];
    else if(endpoint==='/knowledge/documents')data=[{id:'doc-1',filename:'documento-ficticio.pdf',status:'pending_index'}];
    else throw new Error('Unexpected synthetic endpoint: '+endpoint);
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.addInitScript(()=>{
    sessionStorage.setItem('zapia_token','synthetic-test-token');sessionStorage.setItem('zapia_role','tenant_admin');sessionStorage.setItem('zapia_tenant_id','synthetic-company');sessionStorage.setItem('zapia_tenant','Empresa fictícia');
  });
  await page.goto(origin);
  await page.locator('[data-route="business"]').click();
  await page.locator('#edit-business-profile').waitFor();
  assert.match(await page.locator('body').innerText(),/Empresa fictícia/);
  assert.match(await page.locator('body').innerText(),/Produto fictício/);
  assert.match(await page.locator('body').innerText(),/Processo fictício/);
  assert.match(await page.locator('body').innerText(),/documento-ficticio\.pdf/);
  await page.getByRole('button',{name:'Novo produto'}).click();
  await page.locator('#product-form [name="name"]').fill('Produto novo');
  await page.getByRole('button',{name:'Salvar'}).click();
  await page.waitForFunction(()=>!document.querySelector('#modal').open);
  assert.equal(mutations.at(-1).endpoint,'/business/products');
  assert.equal(mutations.at(-1).body.name,'Produto novo');
  assert.equal(errors.length,0,errors.join(';'));
  console.log('UI sintética aprovada: painel de negócio, catálogo, processos e documentos.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>server.close());
