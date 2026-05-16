<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import {
    createApiKey,
    listApiKeys,
    listAlerts,
    revokeApiKey,
    type AlertRecord,
    type ApiKey,
    type ApiKeyCreateResponse
  } from '$lib/api/client';
  import { readAccessToken } from '$lib/stores/auth';

  const projectId = $derived(page.params.projectId ?? '');
  const curlExample =
    'curl -X POST http://localhost:8000/v1/events \\\n' +
    '  -H "Authorization: Bearer sf_demo_your_key" \\\n' +
    '  -H "Content-Type: application/json" \\\n' +
    '  -d \'{"eventId":"evt_123","service":"payment-api","environment":"production","level":"error","message":"Checkout timeout","statusCode":504,"latencyMs":2380,"metadata":{"route":"/checkout"}}\'';

  let token = $state('');
  let keys = $state<ApiKey[]>([]);
  let keyName = $state('Local demo key');
  let mode = $state<'demo' | 'live'>('demo');
  let createdKey = $state<ApiKeyCreateResponse | null>(null);
  let alerts = $state<AlertRecord[]>([]);
  let discordConfigured = $state(false);
  let error = $state('');
  let loading = $state(true);
  let saving = $state(false);

  async function loadKeys() {
    token = readAccessToken();
    if (!token) {
      loading = false;
      return;
    }
    try {
      keys = await listApiKeys(token, projectId);
      const alertResponse = await listAlerts(token, projectId);
      alerts = alertResponse.alerts.slice(0, 5);
      discordConfigured = alertResponse.discordConfigured;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to load API keys';
    } finally {
      loading = false;
    }
  }

  async function handleCreate(event: SubmitEvent) {
    event.preventDefault();
    saving = true;
    error = '';
    createdKey = null;
    try {
      createdKey = await createApiKey(token, projectId, { name: keyName, mode });
      keys = await listApiKeys(token, projectId);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to create API key';
    } finally {
      saving = false;
    }
  }

  async function handleRevoke(keyId: string) {
    error = '';
    try {
      const revoked = await revokeApiKey(token, keyId);
      keys = keys.map((key) => (key.id === revoked.id ? revoked : key));
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to revoke API key';
    }
  }

  onMount(loadKeys);
</script>

<section class="space-y-6">
  <div>
    <a class="text-sm font-medium text-signal hover:underline" href="/projects">Back to projects</a>
    <h1 class="mt-3 text-3xl font-semibold">Project Settings</h1>
    <p class="mt-2 text-slate-600">Manage hashed ingestion API keys for this project.</p>
  </div>

  {#if !token && !loading}
    <div class="surface rounded-lg p-8 text-center">
      <h2 class="text-lg font-semibold">Login Required</h2>
      <p class="mt-2 text-sm text-slate-500">Sign in to manage API keys.</p>
      <a class="mt-4 inline-flex rounded bg-signal px-4 py-2 font-medium text-white" href="/login">Go to Login</a>
    </div>
  {:else}
    <form class="surface grid gap-4 rounded-lg p-5 md:grid-cols-[1fr_160px_auto]" onsubmit={handleCreate}>
      <div>
        <label class="block text-sm font-medium" for="key-name">Key Name</label>
        <input
          id="key-name"
          class="mt-2 w-full rounded border border-slate-300 px-3 py-2 outline-none focus:border-signal"
          bind:value={keyName}
          required
          minlength="2"
        />
      </div>
      <div>
        <label class="block text-sm font-medium" for="key-mode">Mode</label>
        <select
          id="key-mode"
          class="mt-2 w-full rounded border border-slate-300 px-3 py-2 outline-none focus:border-signal"
          bind:value={mode}
        >
          <option value="demo">Demo</option>
          <option value="live">Live</option>
        </select>
      </div>
      <button class="self-end rounded bg-signal px-4 py-2 font-medium text-white disabled:bg-slate-300" disabled={saving}>
        {saving ? 'Creating...' : 'Create Key'}
      </button>
    </form>
  {/if}

  <div class="surface rounded-lg p-5">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h2 class="text-lg font-semibold">Ingestion</h2>
        <p class="mt-2 text-sm text-slate-500">
          Send events to the FastAPI ingestion endpoint with a project API key. The API validates,
          rate-limits, queues, and returns before worker processing.
        </p>
      </div>
      <a class="rounded border border-slate-300 px-3 py-2 text-sm font-medium" href={`/projects/${projectId}/events`}>
        Events
      </a>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <pre class="overflow-x-auto rounded bg-slate-950 p-4 text-xs leading-6 text-slate-100"><code>{curlExample}</code></pre>
      <div class="rounded border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
        Keep ingestion keys server-side. Do not ship them in public frontend code, mobile apps, or
        screenshots. Raw keys are shown only once when created; the list below only shows masked
        prefixes.
      </div>
    </div>
  </div>

  <div class="surface rounded-lg p-5">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h2 class="text-lg font-semibold">Discord Alerts</h2>
        <p class="mt-2 text-sm text-slate-500">
          Discord is used for free demo alerting when high or critical incidents open, escalate, or resolve.
        </p>
      </div>
      <span class="rounded px-2 py-1 text-xs font-semibold {discordConfigured ? 'bg-emerald-50 text-signal' : 'bg-slate-100 text-slate-700'}">
        {discordConfigured ? 'Webhook configured' : 'Global webhook not configured'}
      </span>
    </div>
    <p class="mt-4 text-sm text-slate-600">
      Configure <code class="rounded bg-slate-100 px-1">DISCORD_WEBHOOK_URL</code> on the API and worker services.
      Missing webhooks are logged as skipped alerts so the ingestion pipeline keeps running.
    </p>
    {#if alerts.length > 0}
      <div class="mt-4 overflow-hidden rounded border border-slate-200">
        <table class="w-full border-collapse text-left text-sm">
          <thead class="bg-slate-50 text-slate-500">
            <tr>
              <th class="px-3 py-2 font-medium">Channel</th>
              <th class="px-3 py-2 font-medium">Type</th>
              <th class="px-3 py-2 font-medium">Status</th>
              <th class="px-3 py-2 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {#each alerts as alert}
              <tr class="border-t border-slate-100">
                <td class="px-3 py-2">{alert.channel}</td>
                <td class="px-3 py-2">{String(alert.payload.alert_type ?? 'update')}</td>
                <td class="px-3 py-2">{alert.status}</td>
                <td class="px-3 py-2 text-xs">{alert.created_at}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>

  {#if createdKey}
    <div class="rounded-lg border border-amber-200 bg-amber-50 p-5 text-amber-900">
      <h2 class="font-semibold">API key created</h2>
      <p class="mt-2 text-sm">This raw key is shown only once. Store it before leaving this page.</p>
      <code class="mt-3 block overflow-x-auto rounded bg-white px-3 py-2 text-sm text-slate-900">
        {createdKey.raw_key}
      </code>
    </div>
  {/if}

  {#if error}
    <div class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
  {/if}

  <div class="surface overflow-hidden rounded-lg">
    <table class="w-full border-collapse text-left text-sm">
      <thead class="bg-slate-50 text-slate-500">
        <tr>
          <th class="px-4 py-3 font-medium">Name</th>
          <th class="px-4 py-3 font-medium">Key</th>
          <th class="px-4 py-3 font-medium">Status</th>
          <th class="px-4 py-3 font-medium">Action</th>
        </tr>
      </thead>
      <tbody>
        {#if loading}
          <tr>
            <td class="px-4 py-8 text-center text-slate-500" colspan="4">Loading API keys...</td>
          </tr>
        {:else if keys.length === 0}
          <tr>
            <td class="px-4 py-8 text-center text-slate-500" colspan="4">No API keys yet.</td>
          </tr>
        {:else}
          {#each keys as key}
            <tr class="border-t border-slate-100">
              <td class="px-4 py-3 font-medium">{key.name}</td>
              <td class="px-4 py-3 font-mono text-xs">{key.masked_key}</td>
              <td class="px-4 py-3">
                <span class="rounded px-2 py-1 text-xs font-medium {key.is_revoked ? 'bg-slate-100 text-slate-500' : 'bg-emerald-50 text-signal'}">
                  {key.is_revoked ? 'Revoked' : 'Active'}
                </span>
              </td>
              <td class="px-4 py-3">
                <button
                  class="rounded border border-slate-300 px-3 py-1 text-sm disabled:text-slate-400"
                  type="button"
                  disabled={key.is_revoked}
                  onclick={() => handleRevoke(key.id)}
                >
                  Revoke
                </button>
              </td>
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</section>
