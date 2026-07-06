<script lang="ts">
  import { goto } from '$app/navigation';
  import { env } from '$env/dynamic/public';
  import { login, register } from '$lib/api/client';
  import { setAccessToken } from '$lib/stores/auth';

  let mode = $state<'login' | 'register'>('login');
  let email = $state('');
  let password = $state('');
  let error = $state('');
  let loading = $state(false);

  const demoEmail = env.PUBLIC_DEMO_EMAIL || '';
  const demoPassword = env.PUBLIC_DEMO_PASSWORD || '';
  const demoAvailable = Boolean(demoEmail && demoPassword);

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    loading = true;
    error = '';

    try {
      const response =
        mode === 'login' ? await login(email, password) : await register(email, password);
      setAccessToken(response.access_token);
      await goto('/dashboard');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to complete request';
    } finally {
      loading = false;
    }
  }

  let demoStatus = $state('');

  async function handleDemoLogin() {
    loading = true;
    error = '';
    const maxAttempts = 4;

    // The free-tier API and database sleep when idle; the first login after a
    // cold start can fail until they wake, so retry before giving up.
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      demoStatus =
        attempt === 1
          ? 'Opening the demo dashboard...'
          : `Waking the free-tier services (attempt ${attempt} of ${maxAttempts})...`;

      try {
        const response = await login(demoEmail, demoPassword);
        setAccessToken(response.access_token);
        await goto('/dashboard');
        return;
      } catch (err) {
        const message = err instanceof Error ? err.message : '';
        if (message.includes('Invalid email')) {
          error = message;
          break;
        }
        if (attempt === maxAttempts) {
          error =
            'The free-tier services are still waking up. Give it a few seconds and click the demo button again.';
        } else {
          await new Promise((resolve) => setTimeout(resolve, 4000));
        }
      }
    }

    demoStatus = '';
    loading = false;
  }
</script>

<section class="mx-auto max-w-xl">
  <div class="surface rounded-lg p-6">
    <div class="mb-6">
      <h1 class="text-2xl font-semibold">Account Access</h1>
      <p class="mt-2 text-sm text-slate-500">
        Register or sign in to manage SignalForge projects and ingestion keys.
      </p>
    </div>

    <div class="mb-5 grid grid-cols-2 rounded border border-slate-200 bg-slate-50 p-1">
      <button
        class="rounded px-3 py-2 text-sm font-medium {mode === 'login' ? 'bg-white shadow-sm' : 'text-slate-500'}"
        type="button"
        onclick={() => (mode = 'login')}
      >
        Login
      </button>
      <button
        class="rounded px-3 py-2 text-sm font-medium {mode === 'register' ? 'bg-white shadow-sm' : 'text-slate-500'}"
        type="button"
        onclick={() => (mode = 'register')}
      >
        Register
      </button>
    </div>

    <form class="space-y-4" onsubmit={handleSubmit}>
      <label class="block text-sm font-medium text-slate-700" for="email">Email</label>
      <input
        id="email"
        class="w-full rounded border border-slate-300 bg-white px-3 py-2 outline-none focus:border-signal"
        type="email"
        placeholder="developer@example.com"
        bind:value={email}
        required
      />

      <label class="block text-sm font-medium text-slate-700" for="password">Password</label>
      <input
        id="password"
        class="w-full rounded border border-slate-300 bg-white px-3 py-2 outline-none focus:border-signal"
        type="password"
        placeholder="********"
        bind:value={password}
        minlength="8"
        required
      />

      {#if error}
        <div class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      {/if}

      <button
        class="w-full rounded bg-signal px-4 py-2 font-medium text-white disabled:bg-slate-300"
        type="submit"
        disabled={loading}
      >
        {loading ? 'Working...' : mode === 'login' ? 'Login' : 'Create Account'}
      </button>
    </form>

    {#if demoAvailable}
      <div class="mt-6 border-t border-slate-200 pt-5">
        <button
          class="w-full rounded border border-signal px-4 py-2 font-medium text-signal hover:bg-slate-50 disabled:opacity-50"
          type="button"
          disabled={loading}
          onclick={handleDemoLogin}
        >
          {loading && demoStatus ? demoStatus : 'Explore the live demo (read-only)'}
        </button>
        <p class="mt-2 text-xs text-slate-500">
          Opens a shared demo project with pre-seeded events, anomalies, an incident, and alert
          history. No registration required. Free-tier services may take up to a minute to wake on
          the first visit.
        </p>
      </div>
    {/if}
  </div>
</section>
