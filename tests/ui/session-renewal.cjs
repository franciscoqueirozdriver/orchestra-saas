// Synthetic auth responses only; no real credentials or production API calls.
const {chromium}=require('playwright-core');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../frontend');
const files={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css','/llm-ui.js':'llm-ui.js','/business-ui.js':'business-ui.js'};
const server=http.createServer((req,res)=>{const f=files[req.url];if(!f){res.writeHead(404);return res.end();}res.setHeader('Content-Type',f.endsWith('.js')?'application/javascript':f.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(root,f)));});
function token(exp,marker){const enc=value=>Buffer.from(JSON.stringify(value)).toString('base64url');return `${enc({alg:'none',typ:'JWT'})}.${enc({sub:'synthetic-user',exp,marker})}.signature`;}
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}`;
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const start=Date.now(),oldToken=token(Math.floor(start/1000)+360,'old'),renewedToken=()=>token(Math.floor(Date.now()/1000)+1800,'renewed');let renewals=0,agent401=true,agentCalls=0;
  await page.clock.install({time:new Date(start)});
  await page.route('**/*',async route=>{const req=route.request(),u=new URL(req.url());if(u.origin!==origin)return route.abort();if(!u.pathname.startsWith('/api/'))return route.continue();const endpoint=u.pathname.slice(4);let status=200,data={};
   if(endpoint==='/dashboard/summary')data={counts:{agents:1,instances:0,open_conversations:0,active_agents:0}};
   else if(endpoint==='/auth/me'){renewals++;data={access_token:renewedToken(),role:'platform_admin',tenant_name:null,tenant_id:null};}
   else if(endpoint==='/agents'){agentCalls++;assert.equal(req.headers()['x-tenant-id'],'tenant-synthetic','renewal must preserve selected company for platform admin');if(agent401){agent401=false;status=401;data={detail:'Sessão inválida ou expirada'}}else data=[];}
   else throw new Error('Unexpected API call: '+endpoint);
   await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.addInitScript(({oldToken})=>{sessionStorage.setItem('zapia_token',oldToken);sessionStorage.setItem('zapia_role','platform_admin');sessionStorage.setItem('zapia_tenant','Empresa selecionada');sessionStorage.setItem('zapia_tenant_id','tenant-synthetic');},{oldToken});
  await page.goto(origin);await page.locator('#page-content .metric-card').first().waitFor();
  await page.clock.fastForward(60_000);await page.waitForFunction(()=>{try{const payload=sessionStorage.getItem('zapia_token').split('.')[1].replace(/-/g,'+').replace(/_/g,'/');return JSON.parse(atob(payload)).marker==='renewed'}catch{return false}});
  assert.equal(renewals,1,'active session should renew before expiration');
  await page.locator('[data-route="agents"]').click();await page.getByText('Crie seu primeiro agente para começar.').waitFor();
  assert.ok(agentCalls>=2,'a 401 should renew and retry the protected request');assert.ok(renewals>=2,'the retry should have obtained a fresh token');assert.ok((await page.locator('#page-content').innerText()).includes('Agentes'));assert.equal(await page.locator('#login-view').isVisible(),false);
  assert.deepEqual(errors,[],errors.join(';'));
  console.log('UI sessão aprovada: renovação silenciosa antes da expiração e retry único após 401 sem voltar ao login.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>server.close());
