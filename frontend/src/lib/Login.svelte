<script>
  import { login } from './api.js'

  let { onLogin } = $props()
  let adminKey = $state('')
  let error = $state('')
  let loading = $state(false)

  async function handleSubmit(e) {
    e.preventDefault()
    error = ''
    loading = true
    try {
      await login(adminKey)
      onLogin()
    } catch (err) {
      error = err.message === 'INVALID_ADMIN_KEY' ? 'Wrong admin key' : 'Login failed'
    } finally {
      loading = false
    }
  }
</script>

<div class="login-container">
  <div class="login-card">
    <h1>SMS Admin</h1>
    <form onsubmit={handleSubmit}>
      <input
        type="password"
        bind:value={adminKey}
        placeholder="Admin Key"
        required
        disabled={loading}
      />
      <button type="submit" disabled={loading || !adminKey}>
        {loading ? 'Logging in...' : 'Login'}
      </button>
      {#if error}
        <p class="error">{error}</p>
      {/if}
    </form>
  </div>
</div>

<style>
  .login-container {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: #0f172a;
  }
  .login-card {
    background: #1e293b;
    border-radius: 12px;
    padding: 2.5rem;
    width: 100%;
    max-width: 380px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
  }
  h1 {
    color: #e2e8f0;
    text-align: center;
    margin: 0 0 1.5rem;
    font-size: 1.5rem;
  }
  input {
    width: 100%;
    padding: 0.75rem 1rem;
    border: 1px solid #334155;
    border-radius: 8px;
    background: #0f172a;
    color: #e2e8f0;
    font-size: 1rem;
    margin-bottom: 1rem;
    box-sizing: border-box;
  }
  input:focus {
    outline: none;
    border-color: #3b82f6;
  }
  button {
    width: 100%;
    padding: 0.75rem;
    background: #3b82f6;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    cursor: pointer;
    transition: background 0.2s;
  }
  button:hover:not(:disabled) {
    background: #2563eb;
  }
  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .error {
    color: #f87171;
    text-align: center;
    margin: 0.75rem 0 0;
    font-size: 0.875rem;
  }
</style>
