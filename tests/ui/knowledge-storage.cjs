// Synthetic fixtures only; no credentials, provider discovery or production access.
const {chromium}=require('playwright-core');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../frontend');
const files={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css','/llm-ui.js':'llm-ui.js'};
const server=http.createServer((req,res)=>{const f=files[req.url];if(!f){res.writeHead(404);return res.end();}res.setHeader('Content-Type',f.endsWith('.js')?'application/javascript':f.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(root,f)));});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}`;
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage();const errors=[],external=[],mutations=[];page.on('pageerror',e=>errors.push(e.message));
  let saved=false,indexed=false,configured=false;const calls=[],payloads=[];
  await page.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());if(u.origin!==origin){external.push(u.hostname);return route.abort();}if(!u.pathname.startsWith('/api/'))return route.continue();
   calls.push([req.method(),u.pathname]);let data,status=200;
   if(u.pathname==='/api/dashboard/summary')data={counts:{}};
   else if(u.pathname==='/api/llm/connections')data=[{id:'google-a',name:'Gemini sintético',provider:'gemini',resolved_protocol:'gemini',enabled:true}];
   else if(u.pathname==='/api/knowledge/documents/search-settings'){
    if(req.method()==='PUT'){configured=true;payloads.push(req.postDataJSON());}
    data={configured,source:configured?'dedicated':'none',base_url:configured?'https://embedding.invalid/v1':'',model:configured?'synthetic-model':''};
   }else if(u.pathname==='/api/knowledge/documents/doc-a/index'){
    if(!configured){status=409;data={detail:'Configure a busca na base de conhecimento antes de indexar'};}
    else{indexed=true;data={status:'indexed'};}
   }else if(u.pathname==='/api/knowledge/documents'){
    if(req.method()==='POST'){saved=true;data={id:'doc-a',status:'pending_index'};status=201;}
    else data=saved?[{id:'doc-a',filename:'synthetic.txt',mime_type:'text/plain',status:indexed?'indexed':'pending_index'}]:[];
   }else throw new Error('Unexpected API '+u.pathname);
   await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.addInitScript(()=>{sessionStorage.setItem('zapia_token','synthetic');sessionStorage.setItem('zapia_role','tenant_admin');sessionStorage.setItem('zapia_tenant_id','tenant-a');});
  await page.goto(origin);await page.locator('[data-route="knowledge"]').click();
  await page.getByRole('button',{name:'Enviar documento'}).click();
  await page.locator('#doc-file').setInputFiles({name:'synthetic.txt',mimeType:'text/plain',buffer:Buffer.from('Synthetic knowledge')});
  await page.getByRole('button',{name:'Salvar documento',exact:true}).click();
  await page.getByText('Aguardando indexação',{exact:true}).waitFor();
  assert.equal(calls.filter(c=>c[1].endsWith('/index')).length,0);
  await page.getByRole('button',{name:'Indexar para busca'}).click();await page.locator('#confirm-dialog').waitFor({state:'visible'});await page.locator('#confirm-ok').click();await page.getByText('Configure a busca na base de conhecimento antes de indexar',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Configurar busca',exact:true}).click();
  await page.locator('#search-connection').selectOption('google-a');
  assert.equal(await page.locator('#search-model').inputValue(),'gemini-embedding-001');
  assert.equal(await page.locator('#search-key').isVisible(),false);
  await page.getByRole('button',{name:'Salvar configuração',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#modal').open);
  await page.getByRole('button',{name:'Indexar para busca'}).click();await page.locator('#confirm-dialog').waitFor({state:'visible'});await page.locator('#confirm-ok').click();await page.getByText('Disponível para busca',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Indexar para busca'}).count(),0);
  assert.deepEqual(payloads,[{model:'gemini-embedding-001',connection_id:'google-a'}]);assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  console.log('UI conhecimento aprovada: salvar sem IA, pendência, configuração própria e indexação explícita.');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
