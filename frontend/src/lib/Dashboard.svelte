<script>
  import { fetchSmsFiles, fetchSmsFile, sendTestSms, createWebSocket, clearToken } from './api.js'

  let { onLogout } = $props()

  const FOLDERS = ['incoming', 'sent', 'failed', 'outgoing', 'checked']

  let activeFolder = $state('incoming')
  let files = $state([])
  let total = $state(0)
  let page = $state(1)
  let pages = $state(0)
  const perPage = 50
  let search = $state('')
  let sortBy = $state('modified')
  let sortOrder = $state('desc')
  let loading = $state(false)
  let selectedFile = $state(null)
  let fileContent = $state(null)
  let wsConnected = $state(false)

  let ws = null
  let searchTimeout = null

  // Load files when folder, sort, search, or page changes
  $effect(() => {
    const _folder = activeFolder
    const _sortBy = sortBy
    const _sortOrder = sortOrder
    const _search = search
    const _page = page

    clearTimeout(searchTimeout)
    searchTimeout = setTimeout(() => {
      loadFiles(_folder, _sortBy, _sortOrder, _search, _page)
    }, _search ? 300 : 0)

    return () => clearTimeout(searchTimeout)
  })

  // WebSocket connection with backoff
  let wsRetryDelay = 3000
  $effect(() => {
    connectWs()
    return () => { if (ws) ws.close() }
  })

  async function loadFiles(folder, sb, so, q, p) {
    loading = true
    try {
      const data = await fetchSmsFiles(folder, { sortBy: sb, sortOrder: so, search: q, page: p, perPage })
      files = data.files
      total = data.total
      pages = data.pages
    } catch (err) {
      if (err.message === 'UNAUTHORIZED') onLogout()
    } finally {
      loading = false
    }
  }

  function connectWs() {
    ws = createWebSocket()
    ws.onopen = () => { wsConnected = true; wsRetryDelay = 3000 }
    ws.onclose = (e) => {
      wsConnected = false
      // Stop reconnecting on auth error (code 4001)
      if (e.code === 4001) { onLogout(); return }
      // Exponential backoff: 3s → 6s → 12s → max 30s
      setTimeout(connectWs, wsRetryDelay)
      wsRetryDelay = Math.min(wsRetryDelay * 2, 30000)
    }
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.event === 'heartbeat') return
      if (msg.folder !== activeFolder) return

      if (msg.event === 'new_file') {
        // Insert new file and re-sort
        files = sortFiles([...files, msg.file])
        total = files.length
      } else if (msg.event === 'removed_file') {
        files = files.filter(f => f.filename !== msg.filename)
        total = files.length
      }
    }
  }

  function sortFiles(list) {
    const rev = sortOrder === 'desc' ? -1 : 1
    if (sortBy === 'name') {
      return list.sort((a, b) => rev * a.filename.localeCompare(b.filename))
    }
    return list.sort((a, b) => rev * (a.modified - b.modified))
  }

  function toggleSort(field) {
    if (sortBy === field) {
      sortOrder = sortOrder === 'desc' ? 'asc' : 'desc'
    } else {
      sortBy = field
      sortOrder = 'desc'
    }
  }

  async function openFile(file) {
    selectedFile = file
    try {
      fileContent = await fetchSmsFile(activeFolder, file.filename)
    } catch (err) {
      if (err.message === 'UNAUTHORIZED') onLogout()
      fileContent = null
    }
  }

  function closeFile() {
    selectedFile = null
    fileContent = null
  }

  function handleLogout() {
    clearToken()
    onLogout()
  }

  // Send test SMS
  let showSendForm = $state(false)
  let sendPhone = $state('')
  let sendMessage = $state('')
  let sending = $state(false)
  let sendResult = $state(null)

  async function handleSend() {
    if (!sendPhone.trim() || !sendMessage.trim()) return
    sending = true
    sendResult = null
    try {
      const data = await sendTestSms(sendPhone.trim(), sendMessage.trim())
      sendResult = { ok: true, file: data.file }
      sendPhone = ''
      sendMessage = ''
    } catch (err) {
      if (err.message === 'UNAUTHORIZED') { onLogout(); return }
      sendResult = { ok: false, error: err.message }
    } finally {
      sending = false
    }
  }

  function parsePhone(filename) {
    // sms_1740000001_0901234567.sms → 0901234567
    const match = filename.match(/_(\d{9,15})\./)
    return match ? match[1] : '—'
  }

  function formatDate(ts) {
    return new Date(ts * 1000).toLocaleString()
  }

  function sortIcon(field) {
    if (sortBy !== field) return '↕'
    return sortOrder === 'desc' ? '↓' : '↑'
  }
</script>

<div class="dashboard">
  <header>
    <h1>SMS Admin</h1>
    <div class="header-right">
      <span class="ws-status" class:connected={wsConnected}>{wsConnected ? 'Live' : 'Offline'}</span>
      <button class="btn-send" onclick={() => { showSendForm = !showSendForm; sendResult = null }}>Send SMS</button>
      <button class="btn-logout" onclick={handleLogout}>Logout</button>
    </div>
  </header>

  <!-- Send SMS form -->
  {#if showSendForm}
    <div class="send-form">
      <div class="send-fields">
        <input type="tel" bind:value={sendPhone} placeholder="Phone number" class="send-input" />
        <textarea bind:value={sendMessage} placeholder="Message..." class="send-textarea" rows="3"></textarea>
      </div>
      <div class="send-actions">
        <button class="btn-do-send" onclick={handleSend} disabled={sending || !sendPhone.trim() || !sendMessage.trim()}>
          {sending ? 'Sending...' : 'Send'}
        </button>
        {#if sendResult}
          <span class="send-result" class:ok={sendResult.ok}>
            {sendResult.ok ? `Sent → ${sendResult.file}` : sendResult.error}
          </span>
        {/if}
      </div>
    </div>
  {/if}

  <!-- Folder tabs -->
  <nav class="tabs">
    {#each FOLDERS as folder}
      <button
        class="tab"
        class:active={activeFolder === folder}
        onclick={() => { activeFolder = folder; page = 1; selectedFile = null; fileContent = null }}
      >
        {folder}
      </button>
    {/each}
  </nav>

  <!-- Search bar -->
  <div class="toolbar">
    <input
      type="text"
      bind:value={search}
      placeholder="Search filename..."
      class="search-input"
    />
    <span class="file-count">{total} files</span>
  </div>

  <!-- File list -->
  <div class="file-list">
    <div class="file-header desktop-only">
      <button class="col-phone" onclick={() => toggleSort('name')}>
        Phone {sortIcon('name')}
      </button>
      <button class="col-name" onclick={() => toggleSort('name')}>
        Filename {sortIcon('name')}
      </button>
      <button class="col-date" onclick={() => toggleSort('modified')}>
        Date {sortIcon('modified')}
      </button>
    </div>

    {#if loading}
      <div class="loading">Loading...</div>
    {:else if files.length === 0}
      <div class="empty">No SMS files in /{activeFolder}</div>
    {:else}
      {#each files as file}
        <button class="file-row" class:selected={selectedFile?.filename === file.filename} onclick={() => openFile(file)}>
          <span class="col-phone desktop-only">{parsePhone(file.filename)}</span>
          <span class="col-name desktop-only">{file.filename}</span>
          <span class="col-date desktop-only">{formatDate(file.modified)}</span>
          <span class="mobile-only mobile-cell">
            <span class="mobile-phone">{parsePhone(file.filename)}</span>
            <span class="mobile-meta">{file.filename} · {formatDate(file.modified)}</span>
          </span>
        </button>
      {/each}
    {/if}
  </div>

  <!-- Pagination -->
  {#if pages > 1}
    <div class="pagination">
      <button disabled={page <= 1} onclick={() => page--}>Prev</button>
      <span>{page} / {pages}</span>
      <button disabled={page >= pages} onclick={() => page++}>Next</button>
    </div>
  {/if}

  <!-- File content modal -->
  {#if selectedFile && fileContent}
    <div class="modal-backdrop" onclick={closeFile} role="presentation">
      <div class="modal" onclick={(e) => e.stopPropagation()} onkeydown={(e) => { if (e.key === 'Escape') closeFile() }} role="dialog" tabindex="-1">
        <div class="modal-header">
          <h2>{fileContent.filename}</h2>
          <button class="btn-close" onclick={closeFile}>×</button>
        </div>
        <div class="modal-meta">
          <span>Folder: {fileContent.folder}</span>
          <span>Size: {fileContent.size}B</span>
          <span>Modified: {fileContent.modified_iso}</span>
        </div>
        <pre class="modal-content">{fileContent.content}</pre>
      </div>
    </div>
  {/if}
</div>

<style>
  .dashboard {
    min-height: 100vh;
    background: #0f172a;
    color: #e2e8f0;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.5rem;
    background: #1e293b;
    border-bottom: 1px solid #334155;
  }
  h1 { margin: 0; font-size: 1.25rem; }
  .header-right { display: flex; align-items: center; gap: 1rem; }
  .ws-status {
    font-size: 0.75rem;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    background: #991b1b;
  }
  .ws-status.connected { background: #166534; }
  .btn-logout {
    padding: 0.4rem 0.75rem;
    background: #334155;
    color: #e2e8f0;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
  }
  .btn-send {
    padding: 0.4rem 0.75rem;
    background: #1d4ed8;
    color: #e2e8f0;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
  }
  .btn-send:hover { background: #2563eb; }
  .btn-logout:hover { background: #475569; }

  /* Send form */
  .send-form {
    padding: 1rem 1.5rem;
    background: #1e293b;
    border-bottom: 1px solid #334155;
    display: flex;
    gap: 1rem;
    align-items: flex-start;
  }
  .send-fields {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-width: 500px;
  }
  .send-input, .send-textarea {
    padding: 0.5rem 0.75rem;
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #e2e8f0;
    font-size: 0.875rem;
    font-family: inherit;
  }
  .send-input:focus, .send-textarea:focus { outline: none; border-color: #3b82f6; }
  .send-textarea { resize: vertical; }
  .send-actions {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    align-items: flex-start;
  }
  .btn-do-send {
    padding: 0.5rem 1.25rem;
    background: #1d4ed8;
    color: #fff;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
  }
  .btn-do-send:hover:not(:disabled) { background: #2563eb; }
  .btn-do-send:disabled { opacity: 0.4; cursor: not-allowed; }
  .send-result {
    font-size: 0.75rem;
    color: #ef4444;
  }
  .send-result.ok { color: #22c55e; }

  /* Tabs */
  .tabs {
    display: flex;
    gap: 0;
    background: #1e293b;
    padding: 0 1rem;
    overflow-x: auto;
  }
  .tab {
    padding: 0.75rem 1.25rem;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: #94a3b8;
    cursor: pointer;
    font-size: 0.875rem;
    text-transform: capitalize;
    white-space: nowrap;
  }
  .tab:hover { color: #e2e8f0; }
  .tab.active { color: #3b82f6; border-bottom-color: #3b82f6; }

  /* Toolbar */
  .toolbar {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem 1.5rem;
  }
  .search-input {
    flex: 1;
    max-width: 400px;
    padding: 0.5rem 0.75rem;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #e2e8f0;
    font-size: 0.875rem;
  }
  .search-input:focus { outline: none; border-color: #3b82f6; }
  .file-count { color: #64748b; font-size: 0.875rem; }

  /* File list */
  .file-list {
    margin: 0 1.5rem;
    border: 1px solid #334155;
    border-radius: 8px;
    overflow: hidden;
  }
  .file-header {
    display: flex;
    background: #1e293b;
    border-bottom: 1px solid #334155;
    font-size: 0.75rem;
    text-transform: uppercase;
    color: #94a3b8;
  }
  .file-header button {
    background: none;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    padding: 0.6rem 1rem;
    font-size: 0.75rem;
    text-transform: uppercase;
    text-align: left;
  }
  .file-header button:hover { color: #e2e8f0; }
  .col-phone { width: 130px; flex-shrink: 0; }
  .col-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  .col-date { width: 220px; flex-shrink: 0; white-space: nowrap; }
  .mobile-only { display: none; }

  @media (max-width: 640px) {
    .desktop-only { display: none !important; }
    .mobile-only { display: flex !important; }
    .file-row { padding: 0.5rem 1rem; }
    .mobile-cell {
      display: flex;
      flex-direction: column;
      gap: 0.15rem;
      width: 100%;
    }
    .mobile-phone {
      font-size: 0.9rem;
      font-weight: 500;
    }
    .mobile-meta {
      font-size: 0.7rem;
      color: #64748b;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .file-list { margin: 0 0.75rem; }
    .toolbar { padding: 0.75rem; }
    .search-input { max-width: none; }
  }

  .file-row {
    display: flex;
    width: 100%;
    padding: 0;
    background: none;
    border: none;
    border-bottom: 1px solid #1e293b;
    color: #e2e8f0;
    cursor: pointer;
    font-size: 0.875rem;
    text-align: left;
  }
  .file-row span { padding: 0.6rem 1rem; }
  .file-row:hover { background: #1e293b; }
  .file-row.selected { background: #1e3a5f; }

  .loading, .empty {
    padding: 2rem;
    text-align: center;
    color: #64748b;
  }

  /* Pagination */
  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    padding: 1rem;
    font-size: 0.875rem;
  }
  .pagination button {
    padding: 0.4rem 0.75rem;
    background: #334155;
    color: #e2e8f0;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
  }
  .pagination button:hover:not(:disabled) { background: #475569; }
  .pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
  .pagination span { color: #94a3b8; }

  /* Modal */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }
  .modal {
    background: #1e293b;
    border-radius: 12px;
    width: 90%;
    max-width: 700px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid #334155;
  }
  .modal-header h2 {
    margin: 0;
    font-size: 1rem;
    word-break: break-all;
  }
  .btn-close {
    background: none;
    border: none;
    color: #94a3b8;
    font-size: 1.5rem;
    cursor: pointer;
    line-height: 1;
  }
  .btn-close:hover { color: #e2e8f0; }
  .modal-meta {
    display: flex;
    gap: 1.5rem;
    padding: 0.75rem 1.25rem;
    font-size: 0.75rem;
    color: #64748b;
    border-bottom: 1px solid #334155;
  }
  .modal-content {
    padding: 1.25rem;
    margin: 0;
    overflow: auto;
    font-size: 0.875rem;
    white-space: pre-wrap;
    word-break: break-word;
    color: #cbd5e1;
    flex: 1;
  }
</style>
