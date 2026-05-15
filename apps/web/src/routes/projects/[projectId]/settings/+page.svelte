<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import {
    createApiKey,
    listApiKeys,
    revokeApiKey,
    type ApiKey,
    type ApiKeyCreateResponse
  } from '$lib/api/client';
  import { readAccessToken } from '$lib/stores/auth';

  const projectId = $derived(page.params.projectId ?? '');

  let token = $state('');
  let keys = $state<ApiKey[]>([]);
  let keyName = $state('Local demo key');
  let mode = $state<'demo' | 'live'>('demo');
  let createdKey = $state<ApiKeyCreateResponse | null>(null);
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
