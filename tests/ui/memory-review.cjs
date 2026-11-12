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
    else if(endpoint==='/conversations')data=[{id:'synthetic-conversation',contact_name:'Contato fictício',last_message:'Pergunta fictícia'}];
    else if(endpoint==='/conversations/synthetic-conversation/state')data={id:'synthetic-conversation',revision:1,status:'open',pause_reason:null,consent_status:'granted',opted_out:false,controls:{global:{enabled:true,source:'painel'},connection:{id:'synthetic-connection',label:'Conexão sintética',active:true,status:'connected',sending_enabled:true,webhook_configured:true},agent:{id:'synthetic-agent',name:'Agente fictício',enabled:true,auto_reply_enabled:true},policy_denial:null,blockers:[],processing:{}},outbox:[]};
    else if(endpoint==='/conversations/synthetic-conversation/messages')data=[{id:'message-1',direction:'incoming',author_kind:'user',text:'Pergunta fictícia',status:'received',created_at:'2026-01-01'}];
    else if(endpoint==='/conversations/synthetic-conversation/memory')data={summary:'Resumo fictício',pending:['bairro'],items:[{id:'memory-1',kind:'preference',content:'prefere manhã',source_message_id:'msg-1',approved:false}]};
    else if(endpoint==='/conversations/synthetic-conversation/decision')data={intent:'pedido',decision_action:'respond'};
    else if(endpoint==='/memory/memory-1'){mutations.push({endpoint,body:request.postDataJSON()});data={id:'memory-1',approved:true};}
    else throw new Error('Unexpected synthetic endpoint: '+endpoint);
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.addInitScript(()=>{
    sessionStorage.setItem('zapia_token','synthetic-test-token');sessionStorage.setItem('zapia_role','tenant_admin');sessionStorage.setItem('zapia_tenant_id','synthetic-company');sessionStorage.setItem('zapia_tenant','Empresa fictícia');
  });
  await page.goto(origin);
  await page.locator('[data-route="conversations"]').click();
  await page.locator('[data-conversation]').click();
  await page.waitForFunction(()=>document.querySelector('#messages-content').textContent.includes('Memória da conversa'));
  assert.match(await page.locator('body').innerText(),/Memória da conversa/);
  assert.match(await page.locator('body').innerText(),/prefere manhã/);
  assert.match(await page.locator('body').innerText(),/Resumo fictício/);
  assert.match(await page.locator('body').innerText(),/Última decisão: pedido \/ respond/);
  const patched=page.waitForResponse(r=>r.url().endsWith('/api/memory/memory-1')&&r.request().method()==='PATCH');
  await page.getByRole('button',{name:'Aprovar'}).click();
  await patched;
  assert.equal(mutations.at(-1).endpoint,'/memory/memory-1');
  assert.equal(mutations.at(-1).body.approved,true);
  assert.equal(errors.length,0,errors.join(';'));
  console.log('UI sintética aprovada: memória da conversa exibida e fato aprovado.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>server.close());
