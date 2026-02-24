<script>
  import { getToken } from './lib/api.js'
  import Login from './lib/Login.svelte'
  import Dashboard from './lib/Dashboard.svelte'

  let loggedIn = $state(!!getToken())
</script>

{#if loggedIn}
  <Dashboard onLogout={() => { loggedIn = false }} />
{:else}
  <Login onLogin={() => { loggedIn = true }} />
{/if}
