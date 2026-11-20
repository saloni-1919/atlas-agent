const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const labels = { overview: 'Overview', knowledge: 'Knowledge base', assistant: 'AI assistant', actions: 'Action center', settings: 'System status' };

async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, { ...options, headers: options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' } }); }
  catch { throw new Error('Cannot reach Atlas. Check that the server is running.'); }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`);
  return body;
}

let toastTimer;
function notify(message) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3700);
}
function element(tag, className, content) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (content !== undefined) el.textContent = content;
  return el;
}
function empty(title, description) {
  const box = element('div', 'empty-state');
  box.append(element('strong', '', title), element('span', '', description));
  return box;
}
function actionButton(label, className, handler) {
  const button = element('button', `mini-btn ${className}`, label);
  button.type = 'button';
  button.addEventListener('click', async () => {
    button.disabled = true;
    try { await handler(); } catch (error) { notify(error.message); } finally { button.disabled = false; }
  });
  return button;
}
function navigate(view) {
  $$('.view').forEach((el) => el.classList.toggle('active', el.id === view));
  $$('.nav-item').forEach((el) => {
    el.classList.toggle('active', el.dataset.view === view);
    if (el.dataset.view === view) el.setAttribute('aria-current', 'page');
    else el.removeAttribute('aria-current');
  });
  $('#current-location').textContent = labels[view];
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (view === 'overview') loadOverview();
  if (view === 'knowledge') loadDocuments();
  if (view === 'actions') loadActions();
  if (view === 'assistant') initConversations();
  if (view === 'settings') loadSystemStatus();
}
$$('[data-view], [data-go]').forEach((button) => button.addEventListener('click', () => navigate(button.dataset.view || button.dataset.go)));

async function loadOverview() {
  try {
    const [data, health] = await Promise.all([api('/overview'), api('/health')]);
    const count = Object.values(data.actions).reduce((sum, value) => sum + value, 0);
    $('#stat-docs').textContent = data.documents;
    $('#stat-actions').textContent = count;
    $('#stat-pending').textContent = data.actions.pending || 0;
    $('#pending-pill').textContent = data.actions.pending || 0;
    $('#pending-pill').hidden = !(data.actions.pending > 0);
    $('#mode-indicator').textContent = health.provider === 'ollama' ? '● Local Ollama AI' : health.provider === 'openai' ? '● OpenAI mode' : '● Offline mode';
    $('#chat-mode').textContent = health.retrieval === 'ollama' ? '● Semantic retrieval' : '● Lexical retrieval';
  } catch (error) { notify(error.message); }
}
async function loadSystemStatus() {
  try {
    const status = await api('/system/status');
    $('#system-provider').textContent = status.provider === 'ollama' ? 'Ollama (local)' : status.provider === 'openai' ? 'OpenAI API' : 'Offline excerpts';
    $('#system-retrieval').textContent = status.retrieval === 'ollama' ? 'Semantic embeddings' : 'Lexical matching';
    $('#system-readiness').textContent = status.ready ? 'Ready ✓' : 'Needs attention';
    $('#system-readiness').className = status.ready ? 'ready' : 'not-ready';
    $('#system-detail').textContent = status.message;
  } catch (error) { notify(error.message); }
}
$('#refresh-system').addEventListener('click', loadSystemStatus);
$('#export-chat').addEventListener('click', async () => {
  if (!activeConversation) return notify('Open a saved conversation before exporting.');
  try {
    const chat = await api(`/conversations/${activeConversation}`);
    const markdown = `# ${chat.title}\n\n` + chat.messages.map(message =>
      `## ${message.role === 'user' ? 'You' : 'Atlas'}\n\n${message.content}\n` +
      (message.sources?.length ? '\n' + message.sources.map((src,index)=>
        `[${index+1}] ${src.title}: ${src.text}`).join('\n') : '')
    ).join('\n\n');
    const url = URL.createObjectURL(new Blob([markdown], {type:'text/markdown'}));
    const link = document.createElement('a');
    link.href = url; link.download = `atlas-chat-${chat.id.slice(0,8)}.md`; link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    notify('Conversation exported.');
  } catch (error) { notify(error.message); }
});

async function loadDocuments() {
  const list = $('#documents-list');
  try {
    const docs = await api('/documents');
    $('#document-count').textContent = `${docs.length} document${docs.length === 1 ? '' : 's'}`;
    allDocuments = docs;
    renderDocuments();
  } catch (error) { list.replaceChildren(empty('Unable to load documents', error.message)); }
}
function renderDocuments() {
  const list = $('#documents-list');
  const query = $('#document-filter').value.trim().toLowerCase();
  const docs = allDocuments.filter(doc => doc.title.toLowerCase().includes(query));
  list.replaceChildren();
  if (!docs.length) list.append(empty(query ? 'No matching documents' : 'No documents yet', query ? 'Try a different search.' : 'Add a document to start asking questions.'));
  docs.forEach((doc) => {
      const row = element('div', 'list-item');
      const info = element('div');
      info.append(element('div', 'item-title', doc.title), element('small', '', new Date(doc.created_at).toLocaleString()));
      row.append(info, actionButton('View', '', async () => {
        const detail = await api(`/documents/${encodeURIComponent(doc.id)}`);
        $('#preview-title').textContent = detail.title;
        $('#preview-body').textContent = detail.content;
        $('#document-dialog').showModal();
      }), actionButton('Delete', 'danger', async () => {
        if (!confirm(`Delete "${doc.title}"?`)) return;
        await api(`/documents/${encodeURIComponent(doc.id)}`, { method: 'DELETE' });
        notify('Document deleted');
        await loadDocuments();
      }));
      list.append(row);
    });
}
let selectedPdf = null;
let allDocuments = [];
$('#document-filter').addEventListener('input', () => renderDocuments());
$('.upload-area').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); $('#doc-file').click(); }
});
$('#doc-file').addEventListener('change', async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  const extension = file.name.split('.').pop().toLowerCase();
  if (!['txt', 'md', 'pdf'].includes(extension)) { notify('Choose a .txt, .md, or .pdf file.'); return; }
  if (file.size > 3_000_000) { event.target.value = ''; notify('Maximum file size is 3 MB.'); return; }
  $('#doc-title').value = file.name.replace(/\.[^.]+$/, '').slice(0, 120);
  $('#file-label').textContent = file.name;
  selectedPdf = extension === 'pdf' ? file : null;
  const area = $('#doc-content');
  area.disabled = Boolean(selectedPdf);
  area.required = !selectedPdf;
  if (selectedPdf) { area.value = ''; area.placeholder = 'PDF text will be extracted securely on the local server.'; }
  else {
    const content = await file.text();
    if (content.length > 40_000) { notify('Document exceeds the 40,000-character limit.'); event.target.value = ''; return; }
    area.value = content;
  }
});
$('#document-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const submit = event.target.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    if (selectedPdf) {
      const data = new FormData();
      data.append('file', selectedPdf);
      data.append('title', $('#doc-title').value.trim());
      await api('/documents/upload', { method: 'POST', body: data });
    } else {
      await api('/documents', { method: 'POST', body: JSON.stringify({ title: $('#doc-title').value.trim(), content: $('#doc-content').value.trim() }) });
    }
    selectedPdf = null;
    event.target.reset();
    $('#doc-content').disabled = false;
    $('#doc-content').required = true;
    $('#doc-content').placeholder = 'Paste the text you want Atlas to understand...';
    $('#file-label').textContent = 'Up to 3 MB · Text-based PDFs supported';
    notify('Document saved to your knowledge base.');
    await loadDocuments(); await loadOverview();
  } catch (error) { notify(error.message); }
  finally { submit.disabled = false; }
});
$('#sample-button').addEventListener('click', async (event) => {
  event.target.disabled = true;
  try {
    await api('/documents/sample', { method: 'POST' });
    notify('Sample policy is available in your knowledge base.');
    await loadDocuments(); await loadOverview();
  } catch (error) { notify(error.message); }
  finally { event.target.disabled = false; }
});
$('#close-preview').addEventListener('click', () => $('#document-dialog').close());
$('#document-dialog').addEventListener('click', (event) => {
  if (event.target === $('#document-dialog')) $('#document-dialog').close();
});

let activeConversation = null;
let conversationsInitialized = false;
let asking = false;
const welcomeMarkup = $('#messages').innerHTML;

async function initConversations() {
  if (conversationsInitialized) return;
  conversationsInitialized = true;
  try { await refreshConversations(); } catch (error) { notify(error.message); conversationsInitialized = false; }
}

async function refreshConversations() {
  const entries = await api('/conversations');
  const list = $('#conversation-list');
  list.replaceChildren();
  if (!entries.length) list.append(element('div','history-empty','No conversations yet. Start a chat to save your questions and answers.'));
  for (const conversation of entries) {
    const row = element('div', `history-entry ${conversation.id === activeConversation ? 'selected' : ''}`);
    const open = element('button','history-open',conversation.title);
    open.type = 'button'; open.title = conversation.title;
    open.addEventListener('click',()=>selectConversation(conversation.id));
    const del = element('button','history-delete','×');
    del.type='button'; del.title='Delete conversation'; del.setAttribute('aria-label',`Delete ${conversation.title}`);
    del.addEventListener('click', async()=>{
      if (asking) return notify('Finish the current answer before deleting a conversation.');
      if (!confirm(`Delete conversation "${conversation.title}"? This cannot be undone.`)) return;
      try {
        await api(`/conversations/${conversation.id}`,{method:'DELETE'});
        if (activeConversation === conversation.id) { activeConversation = null; resetChat(); }
        await refreshConversations();
      } catch (error) { notify(error.message); }
    });
    row.append(open,del); list.append(row);
  }
}

function resetChat() {
  $('#chat-title').textContent='New conversation';
  $('#messages').innerHTML=welcomeMarkup;
  $('#chat-status').textContent='Ask about your documents';
  $('#question').value='';
}
async function selectConversation(id) {
  if (asking) return notify('Wait for the current answer before changing conversations.');
  try {
    const detail=await api(`/conversations/${id}`);
    activeConversation=id;
    $('#messages').replaceChildren();
    $('#chat-title').textContent=detail.title;
    $('#chat-status').textContent=`${detail.messages.length/2} question${detail.messages.length===2?'':'s'} · Saved locally`;
    if (!detail.messages.length) resetChat();
    for (const message of detail.messages) addMessage(message.role,message.content,message.sources,message.mode,message.action_id);
    await refreshConversations();
  } catch (error) { notify(error.message); }
}
$('#new-chat').addEventListener('click',()=>{
  if (asking) return notify('Finish the current answer before starting a new conversation.');
  activeConversation=null;resetChat();refreshConversations().catch(error=>notify(error.message));$('#question').focus();
});

function addMessage(who, content, sources = [], mode=null, actionId=null) {
  const welcome = $('#messages .welcome');
  if (welcome) welcome.remove();
  const row = element('div', `chat-message ${who}`);
  const bubble = element('div', 'bubble', content);
  if (sources?.length) {
    const group = element('div','message-sources');
    group.append(element('div','message-mode',`${sources.length} SOURCE${sources.length>1?'S':''} · CLICK TO INSPECT`));
    sources.forEach((source, index)=>{
      const btn=element('button','source-toggle'); btn.type='button';
      btn.append(element('span','source-label',`SOURCE ${index+1}`),element('strong','',source.title),element('span','',source.text));
      btn.addEventListener('click',async()=>{
        try {
          const doc=await api(`/documents/${encodeURIComponent(source.document_id)}`);
          $('#preview-title').textContent=doc.title;
          $('#preview-body').textContent=doc.content;
        } catch {
          $('#preview-title').textContent=`${source.title} (archived excerpt)`;
          $('#preview-body').textContent=source.text;
        }
        $('#document-dialog').showModal();
      });
      group.append(btn);
    });
    bubble.append(group);
  }
  if (mode==='abstain') bubble.append(element('div','message-mode','NO SUPPORTING EVIDENCE'));
  if (mode==='extractive') bubble.append(element('div','message-mode','OFFLINE · EXACT SOURCE EXCERPTS'));
  if (mode==='model') bubble.append(element('div','message-mode','AI-GENERATED · VERIFY CITATIONS'));
  if (mode==='tool-proposed') {
    const card = element('div','tool-card');
    card.append(element('strong','','Approval needed'), element('p','','This action is pending. No calculation has run.'));
    const review = actionButton('Review in Action center ↗','',()=>navigate('actions'));
    card.append(review);
    bubble.append(card);
  }
  row.append(bubble);$('#messages').append(row);
  requestAnimationFrame(() => { $('#messages').scrollTop = $('#messages').scrollHeight; });
  return row;
}
$('#ask-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (asking) return;
  const question = $('#question').value.trim();
  if (question.length < 2) return notify('Please enter a longer question.');
  asking=true;
  const button = event.target.querySelector('button');
  button.disabled = true;
  addMessage('user',question);
  $('#question').value='';
  $('#chat-status').textContent='Checking your documents...';
  const spinner=addMessage('pending','Finding supporting evidence…');
  try {
    if (!activeConversation) {
      const created=await api('/conversations',{method:'POST'});
      activeConversation=created.id;
    }
    const result=await api(`/conversations/${activeConversation}/messages`,{
      method:'POST',body:JSON.stringify({question})
    });
    spinner.remove();
    addMessage('assistant',result.answer,result.sources,result.mode,result.action_id);
    if (result.warning) notify(result.warning);
    $('#chat-status').textContent=result.mode==='model'?'AI answer · Sources attached':result.mode==='abstain'?'No evidence found':'Offline excerpts · Sources attached';
    await refreshConversations();
    const record=await api(`/conversations/${activeConversation}`);
    $('#chat-title').textContent=record.title;
  } catch (error) {
    spinner.remove();
    addMessage('assistant',`Something went wrong: ${error.message}. Your question was not saved. Please try again.`);
    $('#chat-status').textContent='Request failed';
  } finally { asking=false;button.disabled=false;$('#question').focus(); }
});
$('#question').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault(); $('#ask-form').requestSubmit();
  }
});
$('#messages').addEventListener('click', (event) => {
  const prompt = event.target.closest('[data-prompt]');
  if (!prompt) return;
  $('#question').value = prompt.dataset.prompt;
  $('#ask-form').requestSubmit();
});

async function loadActions() {
  const list = $('#actions-list');
  try {
    const items = await api('/actions');
    list.replaceChildren();
    if (!items.length) list.append(empty('No actions yet', 'Propose a calculation to see the approval process.'));
    items.forEach((action) => {
      const row = element('div', 'list-item');
      const info = element('div');
      info.append(element('div', 'item-title', action.expression));
      const detail = element('small', '', action.result !== null ? `Result: ${action.result}` : 'Not executed');
      info.append(detail, element('span', `status ${action.status}`, action.status));
      row.append(info);
      if (action.status === 'pending') {
        const controls = element('div', 'btn-group');
        controls.append(actionButton('Approve', 'success', async () => {
          await api(`/actions/${encodeURIComponent(action.id)}/approve`, { method: 'POST' });
          notify('Calculation approved and executed'); await loadActions(); await loadOverview();
        }), actionButton('Reject', 'danger', async () => {
          await api(`/actions/${encodeURIComponent(action.id)}/reject`, { method: 'POST' });
          notify('Action rejected without execution'); await loadActions(); await loadOverview();
        }));
        row.append(controls);
      }
      list.append(row);
    });
  } catch (error) { list.replaceChildren(empty('Unable to load actions', error.message)); }
}
$('#action-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = event.target.querySelector('[type="submit"]');
  button.disabled = true;
  try {
    await api('/actions/calculation', { method: 'POST', body: JSON.stringify({ expression: $('#expression').value.trim() }) });
    event.target.reset();
    notify('Action submitted for approval');
    await loadActions(); await loadOverview();
  } catch (error) { notify(error.message); } finally { button.disabled = false; }
});
loadOverview();
