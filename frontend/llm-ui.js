/* Configurable connections. Provider tests run only through the authenticated backend. */
(() => {
  'use strict';
  window.OrchestraLlmUI = {create};
  function create({request,esc,pageHead,loading,errorBox,table,openModal,closeModal,formSubmit,toast,askConfirm,getRoute}) {
    const $=(selector,root=document)=>root.querySelector(selector);
    const $$=(selector,root=document)=>[...root.querySelectorAll(selector)];
    let cache=null;
    async function catalog(){if(!cache)cache=await request('/llm/provider-presets');return cache;}
    async function connections(){return request('/llm/connections');}
    function label(row){return `${row.name} — ${row.model}${row.enabled?'':' (desativada)'}`;}
    async function render(root){
      const action='<button class="button button-primary" id="new-llm-connection">＋ Nova conexão</button>';
      root.innerHTML=pageHead('Modelos IA','Cadastre provedores e escolha modelos por agente.',action)+loading();
      try {
        const [data,providers]=await Promise.all([connections(),catalog()]);
        if(getRoute()!=='model')return;
        const rows=data.map(c=>`<tr><td><strong>${esc(c.name)}</strong><small class="muted-text"> ${esc(c.provider)}</small></td><td>${esc(c.model)}<small class="muted-text"> ${esc(c.resolved_protocol||c.protocol)}</small><small class="muted-text" data-llm-test-result role="status" aria-live="polite" hidden></small></td><td>${c.is_default?'<span class="badge badge-good">Padrão da empresa</span>':''}<span class="badge">${c.enabled?'Habilitada':'Desativada'}</span></td><td>${c.has_api_key?'Chave cadastrada':'Sem chave'}<small class="muted-text"> ${c.embedding_configured?'Busca configurada':'Busca precisa de configuração'}</small></td><td><div class="actions"><button class="small-button" data-llm-test="${esc(c.id)}">Testar modelo</button><button class="small-button" data-llm-edit="${esc(c.id)}">Editar</button>${!c.is_default?`<button class="small-button" data-llm-default="${esc(c.id)}">Definir padrão</button>`:''}<button class="small-button" data-llm-resume="${esc(c.id)}">Limpar pausa de erro</button><button class="small-button" data-llm-delete="${esc(c.id)}">Excluir</button></div></td></tr>`).join('');
        root.innerHTML=pageHead('Modelos IA','Cadastre provedores e escolha modelos por agente.',action)+
          '<div class="inline-alert">Ao salvar, o sistema faz um teste curto de acesso ao modelo. Você também pode testar conexões existentes nesta lista. O teste pode consumir cota e não altera modelo padrão, alternativas, pausa por erro ou configuração da busca. Configure embeddings separadamente em Conhecimento.</div>'+table(['Conexão','Modelo e protocolo','Uso','Credenciais e busca','Ações'],rows,'Adicione uma conexão. A primeira será o padrão da empresa.')+
          '<section class="card panel"><h2>Adicionar outros provedores</h2><p>Escolha “Outro provedor / personalizado”, informe um identificador, o endpoint HTTPS e um dos protocolos disponíveis. Você pode cadastrar novos modelos e várias chaves do mesmo fornecedor. Um protocolo diferente exige um novo adaptador, não apenas uma nova URL.</p></section>';
        $('#new-llm-connection',root).onclick=()=>connectionForm(null,providers,()=>render(root));
        $$('[data-llm-edit]',root).forEach(b=>b.onclick=()=>connectionForm(data.find(c=>c.id===b.dataset.llmEdit),providers,()=>render(root)));
        $$('[data-llm-test]',root).forEach(b=>b.onclick=()=>testSavedConnection(b,b.dataset.llmTest));
        $$('[data-llm-default]',root).forEach(b=>b.onclick=()=>mutate(b,`/llm/connections/${encodeURIComponent(b.dataset.llmDefault)}/default`,'POST',root));
        $$('[data-llm-resume]',root).forEach(b=>b.onclick=()=>mutate(b,`/llm/connections/${encodeURIComponent(b.dataset.llmResume)}/resume`,'POST',root));
        $$('[data-llm-delete]',root).forEach(b=>b.onclick=async()=>{if(await askConfirm('Excluir esta conexão? Conexões padrão ou usadas por agentes não podem ser excluídas.',{title:'Excluir conexão',confirmLabel:'Excluir',danger:true}))mutate(b,`/llm/connections/${encodeURIComponent(b.dataset.llmDelete)}`,'DELETE',root);});
      }catch(e){if(getRoute()==='model')root.innerHTML=pageHead('Modelos IA','Conexões da empresa')+errorBox(e);}
    }
    async function mutate(button,path,method,root){button.disabled=true;try{await request(path,{method});await render(root);}catch(e){toast(e.message,'error');button.disabled=false;}}
    function describeTest(result){
      if(result.ok)return `Modelo ${result.model} respondeu (${result.elapsed_ms} ms).`;
      const status=result.status_code?` · HTTP ${result.status_code}`:'';
      return `Falha ao testar ${result.model}${status}: ${result.message} [${result.category}].`;
    }
    async function testSavedConnection(button,id){
      const label=button.textContent;button.disabled=true;button.textContent='Testando…';
      const resultBox=button.closest('tr')?.querySelector('[data-llm-test-result]');
      try{const result=await request(`/llm/connections/${encodeURIComponent(id)}/test`,{method:'POST'});const message=describeTest(result);if(resultBox){resultBox.hidden=false;resultBox.textContent=message;resultBox.className=result.ok?'form-help':'inline-alert';resultBox.setAttribute('role',result.ok?'status':'alert');}toast(message,result.ok?'success':'error');}
      catch(e){const message=`Não foi possível concluir o teste: ${e.message}`;if(resultBox){resultBox.hidden=false;resultBox.textContent=message;resultBox.className='inline-alert';resultBox.setAttribute('role','alert');}toast(message,'error');}
      finally{if(button.isConnected){button.disabled=false;button.textContent=label;}}
    }
    function connectionForm(row,providers,refresh){
      const c=row||{name:'',provider:'gemini',protocol:'gemini',base_url:'https://generativelanguage.googleapis.com/v1beta',model:'',enabled:true,max_output_tokens:2048,embedding_model:'text-embedding-3-small',embedding_base_url:''};
      const known=providers.presets.some(p=>p.id===c.provider);
      const options=providers.presets.map(p=>`<option value="${esc(p.id)}">${esc(p.label)}</option>`).join('')+'<option value="__custom__">Outro provedor / personalizado</option>';
      openModal(row?'Editar conexão IA':'Nova conexão IA',`<form id="llm-connection-form">
        <label class="field-label" for="connection-name">Nome desta conexão</label><input class="field-control" id="connection-name" name="name" maxlength="120" value="${esc(c.name)}" required placeholder="Ex.: Gemini principal">
        <label class="field-label" for="connection-provider">Provedor</label><select class="field-control" id="connection-provider" name="preset">${options}</select>
        <div id="custom-provider-fields"><label class="field-label" for="connection-provider-id">Identificador do provedor</label><input class="field-control" id="connection-provider-id" name="provider_id" maxlength="40" pattern="[a-zA-Z0-9_.-]+" value="${esc(known?'':c.provider)}" placeholder="Ex.: meu-provedor"></div>
        <label class="field-label" for="connection-protocol">Protocolo da API</label><select class="field-control" id="connection-protocol" name="protocol">${providers.protocols.map(p=>`<option value="${esc(p.id)}">${esc(p.label)}</option>`).join('')}</select>
        <label class="field-label" for="connection-url">URL base HTTPS</label><input class="field-control" id="connection-url" name="base_url" type="url" maxlength="500" value="${esc(c.base_url)}" required><p class="form-help">Informe a raiz da API; não acrescente /chat/completions, /responses, /messages ou :generateContent. Ao alterar a URL, informe a chave novamente.</p>
        <label class="field-label" for="connection-model">Identificador do modelo</label><input class="field-control" id="connection-model" name="model" maxlength="160" value="${esc(c.model)}" required><p class="form-help">Use o ID disponível na sua conta. No OpenRouter ele pode conter provedor/modelo. Salvar testa o acesso com uma solicitação curta; o fornecedor pode contabilizá-la na cota.</p>
        <label class="field-label" for="connection-key">Chave da geração ${row?'(vazio preserva a atual)':''}</label><input class="field-control" id="connection-key" name="api_key" type="password" maxlength="1000" autocomplete="new-password" ${row?'':'required'}><p class="form-help">O salvamento grava a configuração e depois testa o acesso. Se o teste falhar, os dados permanecem salvos para correção. Cada teste é uma chamada ao fornecedor e pode consumir cota.</p>
        <label class="field-label" for="connection-limit">Limite de tokens de saída</label><input class="field-control" id="connection-limit" name="max_output_tokens" type="number" min="128" max="32768" value="${esc(c.max_output_tokens)}" required>
        <label class="check-line"><input type="checkbox" name="enabled" ${c.enabled?'checked':''}> Habilitar esta conexão na cadeia de modelos</label>
        <details><summary>Busca nos documentos — embeddings</summary><p class="form-help">Configure a busca preferencialmente em Conhecimento → Configurar busca. Estes campos são usados apenas enquanto não existir uma configuração própria da base. Configure uma API compatível de embeddings de 1536 dimensões. Gemini/Claude nativos exigem URL separada. Alterar geração sem editar estes campos preserva a busca existente.</p>
          <label class="field-label" for="connection-embedding-url">URL base de embeddings</label><input class="field-control" id="connection-embedding-url" name="embedding_base_url" type="url" value="${esc(c.embedding_base_url||'')}" placeholder="https://provedor.example/v1">
          <label class="field-label" for="connection-embedding-model">Modelo de embeddings</label><input class="field-control" id="connection-embedding-model" name="embedding_model" value="${esc(c.embedding_model||'text-embedding-3-small')}" maxlength="160">
          <label class="field-label" for="connection-embedding-key">Chave de embeddings (vazio preserva a atual)</label><input class="field-control" id="connection-embedding-key" name="embedding_api_key" type="password" maxlength="1000" autocomplete="new-password"><p class="form-help">Ao mudar o endpoint, informe a chave de embeddings. Não reutilize uma chave de outro fornecedor. A mudança da busca com documentos indexados exige planejamento de reindexação.</p>
        </details>
        <p class="form-help" id="connection-test-result" hidden role="status" aria-live="polite"></p>
        <div class="form-actions"><button class="button button-secondary" type="button" data-close-modal>Cancelar</button><button class="button button-primary" type="submit">Salvar e testar modelo</button></div>
      </form>`);
      const f=$('#llm-connection-form');f.elements.preset.value=known?c.provider:'__custom__';f.elements.protocol.value=c.protocol||'auto';
      function customVisibility(){const custom=f.elements.preset.value==='__custom__';$('#custom-provider-fields',f).hidden=!custom;f.elements.provider_id.required=custom;}
      customVisibility();
      f.elements.preset.onchange=()=>{customVisibility();const p=providers.presets.find(p=>p.id===f.elements.preset.value);if(p){f.elements.protocol.value=p.protocol;f.elements.base_url.value=p.base_url;}else f.elements.protocol.value='chat-completions';};
      let embeddingEdited=false;
      for(const name of ['embedding_base_url','embedding_model','embedding_api_key'])f.elements[name].addEventListener('input',()=>embeddingEdited=true);
      formSubmit(f,async fd=>{
        const provider=fd.get('preset')==='__custom__'?String(fd.get('provider_id')).trim():fd.get('preset');
        const payload={name:fd.get('name'),provider,protocol:fd.get('protocol'),base_url:fd.get('base_url'),model:fd.get('model'),enabled:fd.get('enabled')==='on',max_output_tokens:Number(fd.get('max_output_tokens'))};
        if(String(fd.get('api_key')||'').trim())payload.api_key=String(fd.get('api_key')).trim();
        if(embeddingEdited){
          payload.embedding_base_url=String(fd.get('embedding_base_url')||'').trim()||null;payload.embedding_model=String(fd.get('embedding_model')||'').trim();
          if(['gemini','anthropic'].includes(payload.protocol)&&!payload.embedding_base_url)throw new Error('Para a busca, informe uma URL separada de embeddings compatíveis.');
          if(String(fd.get('embedding_api_key')||'').trim())payload.embedding_api_key=String(fd.get('embedding_api_key')).trim();
        }
        try{
          const saved=await request(row?`/llm/connections/${encodeURIComponent(row.id)}`:'/llm/connections',{method:row?'PUT':'POST',body:payload});
          const connectionId=row?.id||saved.id;const resultBox=$('#connection-test-result',f);resultBox.hidden=false;resultBox.setAttribute('role','status');resultBox.textContent='Conexão salva. Testando o acesso ao modelo…';
          const submit=f.querySelector('[type="submit"]');submit.textContent='Testando modelo…';
          let result;
          try{result=await request(`/llm/connections/${encodeURIComponent(connectionId)}/test`,{method:'POST'});}
          catch(error){resultBox.className='inline-alert';resultBox.setAttribute('role','alert');resultBox.textContent=`Conexão salva, mas o teste não pôde ser concluído: ${error.message}`;refresh();return;}
          resultBox.className=result.ok?'form-help':'inline-alert';resultBox.setAttribute('role',result.ok?'status':'alert');resultBox.textContent=describeTest(result);
          if(result.ok){closeModal();toast(describeTest(result),'success');refresh();}
          else{toast('Conexão salva, mas o teste do modelo falhou. Veja o motivo no formulário.','error');refresh();}
        }
        finally{payload.api_key='';payload.embedding_api_key='';fd.set('api_key','');fd.set('embedding_api_key','');}
      });
    }
    function agentFields(agent,rows){
      const defaultRow=rows.find(r=>r.is_default);
      return `<fieldset class="agent-models"><legend>Modelo e alternativas</legend><label class="field-label" for="agent-model-primary">Modelo principal</label><select class="field-control" id="agent-model-primary" name="llm_config_id"><option value="">${esc(defaultRow?'Usar padrão da empresa: '+label(defaultRow):'Usar padrão da empresa (ainda não cadastrado)')}</option>${rows.map(r=>`<option value="${esc(r.id)}">${esc(label(r))}</option>`).join('')}</select><label class="field-label" for="agent-model-alternative">Adicionar alternativa</label><select class="field-control" id="agent-model-alternative"><option value="">Selecione uma conexão</option>${rows.map(r=>`<option value="${esc(r.id)}">${esc(label(r))}</option>`).join('')}</select><button class="small-button" type="button" id="add-model-fallback">Adicionar alternativa</button><ol id="model-fallback-order"></ol><p class="form-help">Alternativas são tentadas na ordem acima apenas em falhas permitidas, usando o mesmo contexto. Recusas de segurança não acionam fallback. Habilitar um modelo não habilita envios de WhatsApp. Cadastre conexões em Modelo IA; conexões desativadas são ignoradas pelo roteador.</p></fieldset>`;
    }
    function wireAgentForm(form,agent,rows){
      const ordered=[...(agent.fallback_config_ids||[])];const primary=form.elements.llm_config_id;
      primary.value=agent.llm_config_id||'';
      if(agent.llm_config_id&&!rows.some(r=>r.id===agent.llm_config_id)){const option=document.createElement('option');option.value=agent.llm_config_id;option.textContent='Conexão indisponível — revise o vínculo';primary.append(option);primary.value=agent.llm_config_id;}
      function paint(){
        const list=$('#model-fallback-order',form);
        list.innerHTML=ordered.map((id,i)=>`<li><span>${esc(rows.find(r=>r.id===id)?label(rows.find(r=>r.id===id)):'Conexão indisponível')}</span> <button class="small-button" type="button" data-fallback-up="${i}" aria-label="Subir alternativa ${i+1}" ${i===0?'disabled':''}>↑</button><button class="small-button" type="button" data-fallback-down="${i}" aria-label="Descer alternativa ${i+1}" ${i===ordered.length-1?'disabled':''}>↓</button><button class="small-button" type="button" data-fallback-remove="${i}">Remover</button></li>`).join('');
        $$('[data-fallback-up]',list).forEach(b=>b.onclick=()=>{const i=Number(b.dataset.fallbackUp);[ordered[i-1],ordered[i]]=[ordered[i],ordered[i-1]];paint();});
        $$('[data-fallback-down]',list).forEach(b=>b.onclick=()=>{const i=Number(b.dataset.fallbackDown);[ordered[i+1],ordered[i]]=[ordered[i],ordered[i+1]];paint();});
        $$('[data-fallback-remove]',list).forEach(b=>b.onclick=()=>{ordered.splice(Number(b.dataset.fallbackRemove),1);paint();});
      }
      $('#add-model-fallback',form).onclick=()=>{const id=$('#agent-model-alternative',form).value;const effective=primary.value||rows.find(r=>r.is_default)?.id;
        if(!id)return;if(ordered.includes(id)||id===effective){toast('Não repita o modelo principal ou uma alternativa.','error');return;}if(ordered.length>=8){toast('Máximo de 8 alternativas.','error');return;}ordered.push(id);paint();};
      paint();
      return ()=>{const effective=primary.value||rows.find(r=>r.is_default)?.id;if(ordered.includes(effective))throw new Error('Remova o modelo principal da lista de alternativas.');return {llm_config_id:primary.value||null,fallback_config_ids:[...ordered]};};
    }
    return {render,connections,agentFields,wireAgentForm};
  }
})();
