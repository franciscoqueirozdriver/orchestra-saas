// Local synthetic API only. Never connects to the backend, provider or production.
const { chromium } = require('playwright-core');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../frontend');
const server = http.createServer((req,res)=>{
  const file = {'/':'index.html','/app.js':'app.js','/styles.css':'styles.css','/llm-ui.js':'llm-ui.js'}[req.url];
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
  let revision=1,status='open',rejectSend=true;
  let profile={enabled:false,tone:'neutral',conciseness:'balanced',emojis:'none',context_minutes:60,max_wait_seconds:20,part_chars:1500,part_delay_seconds:1,presence:false,vocabulary:[],examples:[]};
  await page.route('**/*',async route=>{
    const request=route.request(),url=new URL(request.url());
    if(url.origin!==origin)return route.abort();
    if(!url.pathname.startsWith('/api/'))return route.continue();
    const endpoint=url.pathname.slice(4);let data;
    if(request.method()!=='GET')mutations.push({endpoint,body:request.postDataJSON()});
    if(endpoint==='/dashboard/summary')data={counts:{}};
    else if(endpoint==='/agents')data=[{id:'synthetic-agent',name:'Agente fictício',description:'',system_prompt:'',enabled:true,auto_reply_enabled:false}];
    else if(endpoint==='/agents/synthetic-agent/conversation-policy'){
      if(request.method()==='PUT')profile=request.postDataJSON();data=profile;
    }else if(endpoint==='/conversations')data=[{id:'synthetic-conversation',contact_name:'Contato fictício',last_message:'Pergunta fictícia'}];
    else if(endpoint==='/conversations/synthetic-conversation/state')data={id:'synthetic-conversation',revision,status,pause_reason:status==='human'?'takeover':null,outbox:[]};
    else if(endpoint==='/conversations/synthetic-conversation/messages'){
      if(request.method()==='POST'){
        if(rejectSend){rejectSend=false;return route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:'Conversa alterada: erro fictício visível'})});}
        status='human';revision++;data={id:'synthetic-outbox',status:'pending'};
      }else data=[{id:'message-1',direction:'incoming',author_kind:'user',text:'Pergunta fictícia',status:'received',created_at:'2026-01-01'}];
    }else if(endpoint.endsWith('/takeover')){status='human';revision++;data={revision,status};}
    else if(endpoint.endsWith('/resume')){status='open';revision++;data={revision,status};}
    else if(endpoint.endsWith('/cancel')){status='paused';revision++;data={revision,status};}
    else throw new Error('Unexpected synthetic endpoint: '+endpoint);
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.addInitScript(()=>{
    sessionStorage.setItem('zapia_token','synthetic-test-token');sessionStorage.setItem('zapia_role','tenant_admin');sessionStorage.setItem('zapia_tenant_id','synthetic-company');sessionStorage.setItem('zapia_tenant','Empresa fictícia');
  });
  await page.goto(origin);
  await page.locator('[data-route="agents"]').click();
  await page.getByRole('button',{name:'Tom e conversa'}).click();
  await page.locator('#conversation-profile-form [name="enabled"]').check();
  await page.locator('#conversation-profile-form [name="tone"]').selectOption('formal');
  await page.getByRole('button',{name:'Salvar perfil'}).click();
  await page.waitForFunction(()=>!document.querySelector('#modal').open);
  assert.equal(profile.enabled,true);assert.equal(profile.tone,'formal');
  await page.locator('[data-route="conversations"]').click();await page.locator('[data-conversation]').click();
  await page.getByRole('button',{name:'Assumir',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#message-title').textContent.includes('human'));
  await page.getByRole('button',{name:'Responder',exact:true}).click();
  await page.locator('#human-reply-form textarea').fill('Resposta fictícia para teste');
  await page.getByRole('button',{name:'Assumir e enfileirar'}).click();
  await page.locator('#human-reply-form [data-form-error]').waitFor();
  assert.match(await page.locator('#modal-body').innerText(),/erro fictício visível/);
  await page.getByRole('button',{name:'Assumir e enfileirar'}).click();
  await page.waitForFunction(()=>!document.querySelector('#modal').open);
  const sends=mutations.filter(r=>r.endpoint.endsWith('/messages'));
  assert.equal(sends.length,2);assert.equal(sends[0].body.idempotency_key,sends[1].body.idempotency_key);
  page.once('dialog',dialog=>dialog.accept());await page.getByRole('button',{name:'Retomar IA',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#message-title').textContent.includes('open'));
  assert.equal(errors.length,0,errors.join(';'));
  console.log('UI sintética aprovada: perfil, takeover, erro dentro do modal, retry idempotente e retomada.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>server.close());
