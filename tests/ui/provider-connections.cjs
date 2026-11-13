// Synthetic fixtures only; no credentials, provider discovery or production access.
const {chromium}=require('playwright-core');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'../../frontend');
const files={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css','/llm-ui.js':'llm-ui.js','/business-ui.js':'business-ui.js'};
const server=http.createServer((req,res)=>{const f=files[req.url];if(!f){res.writeHead(404);return res.end();}res.setHeader('Content-Type',f.endsWith('.js')?'application/javascript':f.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(root,f)));});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}`;
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage();const errors=[],external=[],mutations=[],probes=[];page.on('pageerror',e=>errors.push(e.message));
  const presets=[
   {id:'gemini',label:'Google Gemini',protocol:'gemini',base_url:'https://generativelanguage.googleapis.com/v1beta'},
   {id:'groq',label:'Groq',protocol:'chat-completions',base_url:'https://api.groq.com/openai/v1'},
   {id:'mistral',label:'Mistral AI',protocol:'chat-completions',base_url:'https://api.mistral.ai/v1'},
   {id:'openrouter',label:'OpenRouter',protocol:'chat-completions',base_url:'https://openrouter.ai/api/v1'},
   {id:'openai',label:'OpenAI',protocol:'responses',base_url:'https://api.openai.com/v1'},
   {id:'xai',label:'xAI',protocol:'responses',base_url:'https://api.x.ai/v1'},
   {id:'anthropic',label:'Anthropic / Claude',protocol:'anthropic',base_url:'https://api.anthropic.com/v1'},
   {id:'openai-compatible',label:'OpenAI compatível',protocol:'chat-completions',base_url:''}];
  const rows=[{id:'old-default',name:'Original fictícia',provider:'openai-compatible',protocol:'chat-completions',resolved_protocol:'chat-completions',base_url:'https://old.invalid/v1',model:'original-model',enabled:true,is_default:true,max_output_tokens:512,has_api_key:true,embedding_configured:true,embedding_model:'synthetic-embedding',embedding_base_url:'https://embedding.invalid/v1'}];
  let agent={id:'agent-a',name:'Enrico fictício',description:'',system_prompt:'Instrução fictícia',enabled:true,auto_reply_enabled:false,llm_config_id:null,fallback_config_ids:[]};
  await page.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());if(u.origin!==origin){external.push(u.hostname);return route.abort();}if(!u.pathname.startsWith('/api/'))return route.continue();
   const endpoint=u.pathname.slice(4),method=req.method();let data,status=200;
   if(method!=='GET')mutations.push({endpoint,method,body:req.postData()?req.postDataJSON():null});
   if(endpoint==='/dashboard/summary')data={counts:{}};
   else if(endpoint==='/llm/provider-presets')data={presets,protocols:['chat-completions','responses','gemini','anthropic','auto'].map(id=>({id,label:id}))};
   else if(endpoint==='/llm/connections'&&method==='GET')data=rows;
   else if(/^\/llm\/connections\/[^/]+\/test$/.test(endpoint)&&method==='POST'){
    const id=endpoint.split('/')[3];probes.push(id);
    const count=probes.filter(x=>x===id).length;
    data=(id==='connection-3'&&count===1)||(id==='connection-2'&&count===2)?{ok:false,model:rows.find(x=>x.id===id)?.model||'synthetic',category:'authentication',status_code:401,message:'Chave ou acesso ao modelo inválido.'}:{ok:true,model:rows.find(x=>x.id===id)?.model||'synthetic',elapsed_ms:15,message:'O modelo respondeu ao teste.'};
   }
   else if(endpoint==='/llm/connections'&&method==='POST'){
    const body=req.postDataJSON();data={...body,id:'connection-'+(rows.length+1),is_default:false,has_api_key:true,embedding_configured:false};delete data.api_key;delete data.embedding_api_key;rows.push(data);
   }else if(endpoint.startsWith('/llm/connections/')){
    const [id,action]=endpoint.slice('/llm/connections/'.length).split('/');const row=rows.find(r=>r.id===id);assert.ok(row);
    if(method==='PUT'){const body=req.postDataJSON();delete body.api_key;delete body.embedding_api_key;Object.assign(row,body);data=row;}
    else if(action==='default'){rows.forEach(r=>r.is_default=r.id===id);data=row;}
    else if(action==='resume')data=row;
    else if(method==='DELETE'){status=409;data={detail:'Conexão em uso por agente'};}
    else throw new Error('Unexpected connection operation');
   }else if(endpoint==='/agents')data=[agent];
   else if(endpoint==='/agents/agent-a'&&method==='PUT'){Object.assign(agent,req.postDataJSON());data=agent;}
   else throw new Error('Unexpected API: '+endpoint);
   await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.addInitScript(()=>{sessionStorage.setItem('zapia_token','synthetic-only-token');sessionStorage.setItem('zapia_role','tenant_admin');sessionStorage.setItem('zapia_tenant_id','synthetic-a');});
  await page.goto(origin);await page.locator('[data-route="model"]').click();
  async function add(preset,name,model,key){
   await page.getByRole('button',{name:'Nova conexão'}).click();
   await page.locator('[name="preset"]').selectOption(preset);
   await page.locator('#connection-name').fill(name);await page.locator('#connection-model').fill(model);await page.locator('#connection-key').fill(key);
  }
  await add('gemini','Gemini fictício','models/synthetic-google','synthetic-google-key');
  assert.equal(await page.locator('#connection-protocol').inputValue(),'gemini');assert.equal(await page.locator('#connection-url').inputValue(),presets[0].base_url);
  const labels=await page.locator('#connection-provider option').allTextContents();for(const label of ['Google Gemini','Mistral AI','OpenRouter','Anthropic / Claude','Outro provedor / personalizado'])assert.ok(labels.includes(label));
  await page.getByRole('button',{name:'Salvar e testar modelo',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#modal').open);
  await add('mistral','Mistral fictício','synthetic-mistral','synthetic-mistral-key');assert.equal(await page.locator('#connection-protocol').inputValue(),'chat-completions');await page.getByRole('button',{name:'Salvar e testar modelo',exact:true}).click();await page.getByRole('alert').filter({hasText:'HTTP 401'}).waitFor();assert.equal(rows.length,3);await page.locator('#llm-connection-form [data-close-modal]').click();
  await add('openrouter','Router fictício','vendor/synthetic','synthetic-router-key');await page.getByRole('button',{name:'Salvar e testar modelo',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#modal').open);
  await add('__custom__','Acme fictício','new-model','synthetic-acme-key');await page.locator('#connection-provider-id').fill('acme-new');await page.locator('#connection-url').fill('https://acme.invalid/api/v1');await page.locator('#connection-protocol').selectOption('responses');await page.locator('#connection-limit').fill('1024');await page.getByRole('button',{name:'Salvar e testar modelo',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#modal').open);
  assert.equal(rows.length,5);assert.equal(rows[0].model,'original-model');assert.equal(rows[0].is_default,true);
  await page.locator('tr').filter({hasText:'Acme fictício'}).getByRole('button',{name:'Editar',exact:true}).click();
  assert.equal(await page.locator('#connection-provider').inputValue(),'__custom__');assert.equal(await page.locator('#connection-provider-id').inputValue(),'acme-new');assert.equal(await page.locator('#connection-protocol').inputValue(),'responses');assert.equal(await page.locator('#connection-key').inputValue(),'');
  await page.locator('#connection-model').fill('newer-model');await page.getByRole('button',{name:'Salvar e testar modelo',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#modal').open);
  const edit=mutations.find(m=>m.method==='PUT'&&m.endpoint.endsWith('/connection-5'));assert.ok(edit);assert.ok(!Object.hasOwn(edit.body,'api_key'));assert.ok(!Object.hasOwn(edit.body,'embedding_base_url'));assert.equal(edit.body.max_output_tokens,1024);
  await page.locator('[data-route="agents"]').click();await page.getByRole('button',{name:'Editar',exact:true}).click();
  await page.locator('#agent-model-primary').selectOption('connection-2');
  for(const id of ['connection-3','connection-4']){await page.locator('#agent-model-alternative').selectOption(id);await page.getByRole('button',{name:'Adicionar alternativa',exact:true}).click();}
  await page.getByRole('button',{name:'Subir alternativa 2',exact:true}).click();await page.getByRole('button',{name:'Salvar agente',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#modal').open);
  assert.equal(agent.llm_config_id,'connection-2');assert.deepEqual(agent.fallback_config_ids,['connection-4','connection-3']);assert.equal(agent.auto_reply_enabled,false);
  await page.locator('[data-route="model"]').click();assert.equal(probes.length,5);assert.deepEqual(probes,['connection-2','connection-3','connection-4','connection-5','connection-5']);
  const geminiRow=page.locator('tr').filter({hasText:'Gemini fictício'});await geminiRow.getByRole('button',{name:'Testar modelo'}).click();await geminiRow.locator('[data-llm-test-result]').filter({hasText:/Falha ao testar models\/synthetic-google.*HTTP 401/}).waitFor();assert.equal(probes.at(-1),'connection-2');
  await page.locator('tr').filter({hasText:'Router fictício'}).getByRole('button',{name:'Excluir',exact:true}).click();await page.locator('#confirm-dialog').waitFor({state:'visible'});await page.locator('#confirm-ok').click();await page.getByText('Conexão em uso por agente',{exact:true}).waitFor();assert.equal(rows.length,5);
  assert.equal(mutations.some(m=>m.endpoint==='/llm/config'),false);assert.ok(probes.every(id=>id.startsWith('connection-')));assert.equal(external.length,0);assert.equal(errors.length,0,errors.join(';'));
  assert.ok(!(await page.locator('body').innerText()).includes('synthetic-google-key'));
  console.log('UI provedores aprovada: teste automático no salvamento, erro de modelo visível, botão de teste para conexões existentes, edição sem chave, vínculos ordenados e exclusão protegida.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{server.close();const result=spawnSync(process.execPath,[path.join(__dirname,'session-renewal.cjs')],{stdio:'inherit',env:process.env});if(result.status!==0)process.exitCode=result.status||1;});
