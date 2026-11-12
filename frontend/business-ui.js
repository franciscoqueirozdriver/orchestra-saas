/* Business profile, catalog, processes and supporting documents. No provider calls from the browser. */
(() => {
  'use strict';
  function create(ui){
    const {request,esc,pageHead,table,openModal,closeModal,formSubmit,toast,askConfirm,loading,errorBox,getRoute}=ui;
    async function render(){
      const root=document.querySelector('#page-content');
      root.innerHTML=pageHead('Negócio','Configure o que a empresa vende, como opera e quais documentos sustentam o atendimento.')+loading();
      try{
        const [profile,products,processes,documents]=await Promise.all([
          request('/business/profile'),request('/business/products'),
          request('/business/processes'),request('/knowledge/documents')]);
        if(getRoute()!=='business')return;
        const productRows=products.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.price_text||'—')}</td><td>${x.active?'Ativo':'Inativo'}</td><td><button class="small-button" data-edit-product="${esc(x.id)}">Editar</button> <button class="small-button" data-delete-product="${esc(x.id)}">Excluir</button></td></tr>`).join('');
        const processRows=processes.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc((x.steps||[]).join(' → '))}</td><td>${esc(x.sla_text||'—')}</td><td><button class="small-button" data-edit-process="${esc(x.id)}">Editar</button> <button class="small-button" data-delete-process="${esc(x.id)}">Excluir</button></td></tr>`).join('');
        const docRows=documents.map(x=>`<tr><td>${esc(x.filename)}</td><td>${x.status==='indexed'?'Disponível para busca':esc(x.status)}</td><td>${x.status==='indexed'?'':`<button class="small-button" data-index-doc="${esc(x.id)}">Indexar</button>`}</td></tr>`).join('');
        const data=profile.data||{};
        root.innerHTML=pageHead('Negócio','Configure o que a empresa vende, como opera e quais documentos sustentam o atendimento.')+
          `<section class="card panel"><h2>Perfil da empresa</h2><p><strong>${esc(data.name||'Não configurado')}</strong> · ${esc(data.hours||'Horário não informado')}</p><p>${esc(data.description||'')}</p><button class="small-button" id="edit-business-profile">Editar perfil</button></section>`+
          `<section class="card panel"><div class="panel-head"><div><h2>Produtos e serviços</h2><p>Preço e condições são textos aprovados; o agente não calcula desconto.</p></div><button class="small-button" id="add-product">Novo produto</button></div>${table(['Nome','Preço','Status','Ações'],productRows,'Nenhum produto cadastrado.')}</section>`+
          `<section class="card panel"><div class="panel-head"><div><h2>Processos</h2><p>Etapas e prazos usados pelo atendimento.</p></div><button class="small-button" id="add-process">Novo processo</button></div>${table(['Nome','Etapas','Prazo','Ações'],processRows,'Nenhum processo cadastrado.')}</section>`+
          `<section class="card panel"><div class="panel-head"><div><h2>Documentos</h2><p>Somente documentos indexados entram na busca.</p></div><a class="button button-secondary" href="#knowledge">Gerenciar documentos</a></div>${table(['Documento','Status','Ação'],docRows,'Nenhum documento enviado.')}</section>`;
        document.querySelector('#edit-business-profile').onclick=()=>profileForm(data);
        document.querySelector('#add-product').onclick=()=>productForm(null);
        document.querySelector('#add-process').onclick=()=>processForm(null);
        document.querySelectorAll('[data-edit-product]').forEach(b=>b.onclick=()=>productForm(products.find(x=>String(x.id)===b.dataset.editProduct)));
        document.querySelectorAll('[data-edit-process]').forEach(b=>b.onclick=()=>processForm(processes.find(x=>String(x.id)===b.dataset.editProcess)));
        document.querySelectorAll('[data-delete-product]').forEach(b=>b.onclick=()=>remove('produto',`/business/products/${encodeURIComponent(b.dataset.deleteProduct)}`));
        document.querySelectorAll('[data-delete-process]').forEach(b=>b.onclick=()=>remove('processo',`/business/processes/${encodeURIComponent(b.dataset.deleteProcess)}`));
        document.querySelectorAll('[data-index-doc]').forEach(b=>b.onclick=async()=>{
          if(!(await askConfirm('Indexar envia o texto extraído ao serviço de embeddings configurado. Continuar?',{title:'Indexar documento',confirmLabel:'Indexar'})))return;
          b.disabled=true;try{await request('/knowledge/documents/'+encodeURIComponent(b.dataset.indexDoc)+'/index',{method:'POST'});toast('Documento indexado.','success');render();}catch(e){toast(e.message,'error');b.disabled=false;}
        });
      }catch(e){if(getRoute()==='business')root.innerHTML=pageHead('Negócio','Configuração do negócio.')+errorBox(e)}
    }
    async function remove(label,path){
      if(!(await askConfirm(`Excluir este ${label}?`,{title:'Excluir',confirmLabel:'Excluir',danger:true})))return;
      try{await request(path,{method:'DELETE'});toast(`${label[0].toUpperCase()+label.slice(1)} excluído.`,'success');render();}catch(e){toast(e.message,'error')}
    }
    function profileForm(data){
      openModal('Perfil da empresa',`<form id="business-profile-form">
        <label class="field-label">Nome<input class="field-control" name="name" maxlength="160" value="${esc(data.name||'')}"></label>
        <label class="field-label">Descrição<textarea class="field-control" name="description" maxlength="2000">${esc(data.description||'')}</textarea></label>
        <label class="field-label">Segmento<input class="field-control" name="segment" maxlength="160" value="${esc(data.segment||'')}"></label>
        <label class="field-label">Regiões (uma por linha)<textarea class="field-control" name="regions">${esc((data.regions||[]).join('\n'))}</textarea></label>
        <label class="field-label">Horário<input class="field-control" name="hours" maxlength="1000" value="${esc(data.hours||'')}"></label>
        <label class="field-label">Políticas (uma por linha)<textarea class="field-control" name="policies">${esc((data.policies||[]).join('\n'))}</textarea></label>
        <label class="field-label">Contato<input class="field-control" name="contact" maxlength="300" value="${esc(data.contact||'')}"></label>
        <label class="field-label">Observações<textarea class="field-control" name="notes" maxlength="4000">${esc(data.notes||'')}</textarea></label>
        <div class="form-actions"><button class="button button-secondary" type="button" data-close-modal>Cancelar</button><button class="button button-primary" type="submit">Salvar perfil</button></div></form>`);
      formSubmit(document.querySelector('#business-profile-form'),async fd=>{
        await request('/business/profile',{method:'PUT',body:{
          name:String(fd.get('name')),description:String(fd.get('description')),segment:String(fd.get('segment')),
          regions:String(fd.get('regions')).split('\n').map(x=>x.trim()).filter(Boolean),
          hours:String(fd.get('hours')),policies:String(fd.get('policies')).split('\n').map(x=>x.trim()).filter(Boolean),
          contact:String(fd.get('contact')),notes:String(fd.get('notes'))}});
        closeModal();toast('Perfil salvo.','success');render();
      });
    }
    function productForm(item){
      const data=item||{name:'',description:'',price_text:'',conditions:'',active:true};
      openModal(item?'Editar produto':'Novo produto',`<form id="product-form">
        <label class="field-label">Nome<input class="field-control" name="name" required maxlength="160" value="${esc(data.name)}"></label>
        <label class="field-label">Preço (texto aprovado)<input class="field-control" name="price_text" maxlength="200" value="${esc(data.price_text)}"></label>
        <label class="field-label">Condições<textarea class="field-control" name="conditions" maxlength="1000">${esc(data.conditions)}</textarea></label>
        <label class="field-label">Descrição<textarea class="field-control" name="description" maxlength="2000">${esc(data.description)}</textarea></label>
        <label class="check-line"><input type="checkbox" name="active" ${data.active?'checked':''}> Ativo</label>
        <div class="form-actions"><button class="button button-secondary" type="button" data-close-modal>Cancelar</button><button class="button button-primary" type="submit">Salvar</button></div></form>`);
      formSubmit(document.querySelector('#product-form'),async fd=>{
        const body={name:String(fd.get('name')),price_text:String(fd.get('price_text')),conditions:String(fd.get('conditions')),description:String(fd.get('description')),active:fd.get('active')==='on'};
        await request(item?`/business/products/${encodeURIComponent(item.id)}`:'/business/products',{method:item?'PATCH':'POST',body});
        closeModal();toast('Produto salvo.','success');render();
      });
    }
    function processForm(item){
      const data=item||{name:'',description:'',steps:[],sla_text:'',active:true};
      openModal(item?'Editar processo':'Novo processo',`<form id="process-form">
        <label class="field-label">Nome<input class="field-control" name="name" required maxlength="160" value="${esc(data.name)}"></label>
        <label class="field-label">Etapas (uma por linha)<textarea class="field-control" name="steps">${esc((data.steps||[]).join('\n'))}</textarea></label>
        <label class="field-label">Prazo<input class="field-control" name="sla_text" maxlength="500" value="${esc(data.sla_text)}"></label>
        <label class="field-label">Descrição<textarea class="field-control" name="description" maxlength="2000">${esc(data.description)}</textarea></label>
        <label class="check-line"><input type="checkbox" name="active" ${data.active?'checked':''}> Ativo</label>
        <div class="form-actions"><button class="button button-secondary" type="button" data-close-modal>Cancelar</button><button class="button button-primary" type="submit">Salvar</button></div></form>`);
      formSubmit(document.querySelector('#process-form'),async fd=>{
        const body={name:String(fd.get('name')),steps:String(fd.get('steps')).split('\n').map(x=>x.trim()).filter(Boolean),sla_text:String(fd.get('sla_text')),description:String(fd.get('description')),active:fd.get('active')==='on'};
        await request(item?`/business/processes/${encodeURIComponent(item.id)}`:'/business/processes',{method:item?'PATCH':'POST',body});
        closeModal();toast('Processo salvo.','success');render();
      });
    }
    return {render};
  }
  window.OrchestraBusinessUI={create};
})();
