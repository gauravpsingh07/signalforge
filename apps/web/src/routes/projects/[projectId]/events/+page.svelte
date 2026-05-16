<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { listEvents, type ProcessedEvent } from '$lib/api/client';
  import { readAccessToken } from '$lib/stores/auth';

  const projectId = $derived(page.params.projectId ?? '');
  let token = $state('');
  let events = $state<ProcessedEvent[]>([]);
  let selected = $state<ProcessedEvent | null>(null);
  let loading = $state(true);
  let error = $state('');
  let service = $state('');
  let environment = $state('');
  let level = $state('');
  let search = $state('');

  function safeText(value: string) {
    return value.replace(/[\u0000-\u001f\u007f]/g, ' ').trim();
  }

  async function loadEvents() {
    token = readAccessToken();
    if (!token) {
      loading = false;
      return;
    }
    loading = true;
    error = '';
    try {
      const response = await listEvents(token, projectId, {
        service,
        environment,
        level,
        search
      });
      events = response.events;
      selected = events[0] ?? null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to load events';
    } finally {
      loading = false;
    }
  }

  onMount(loadEvents);
</script>

<section class="space-y-6">
  <div>
    <a class="text-sm font-medium text-signal hover:underline" href={`/projects/${projectId}/settings`}>
      Back to settings
    </a>
    <h1 class="mt-3 text-3xl font-semibold">Events</h1>
    <p class="mt-2 text-slate-600">Explore processed worker events stored by the Phase 3 fallback event store.</p>
  </div>

  <form class="surface grid gap-3 rounded-lg p-5 md:grid-cols-5" onsubmit={(event) => { event.preventDefault(); loadEvents(); }}>
    <label class="sr-only" for="event-service">Service</label>
    <input id="event-service" class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={service} placeholder="service" />
    <label class="sr-only" for="event-environment">Environment</label>
    <input id="event-environment" class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={environment} placeholder="environment" />
    <label class="sr-only" for="event-level">Level</label>
    <select id="event-level" class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={level}>
      <option value="">all levels</option>
      <option value="debug">debug</option>
      <option value="info">info</option>
      <option value="warn">warn</option>
      <option value="error">error</option>
      <option value="fatal">fatal</option>
    </select>
    <label class="sr-only" for="event-search">Message search</label>
    <input id="event-search" class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={search} placeholder="message search" />
    <button class="rounded bg-signal px-4 py-2 text-sm font-medium text-white">Filter</button>
  </form>

  {#if !token && !loading}
    <div class="surface rounded-lg p-8 text-center">
      <h2 class="text-lg font-semibold">Login Required</h2>
      <p class="mt-2 text-sm text-slate-500">Sign in to inspect processed events.</p>
      <a class="mt-4 inline-flex rounded bg-signal px-4 py-2 font-medium text-white" href="/login">Go to Login</a>
    </div>
  {:else if error}
    <div class="flex flex-wrap items-center justify-between gap-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      <span>{error}</span>
      <button class="rounded border border-red-300 px-3 py-1 font-medium" type="button" onclick={loadEvents}>Retry</button>
    </div>
  {:else}
    <div class="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
      <div class="surface overflow-hidden rounded-lg">
        <table class="w-full border-collapse text-left text-sm">
          <thead class="bg-slate-50 text-slate-500">
            <tr>
              <th class="px-4 py-3 font-medium">Timestamp</th>
              <th class="px-4 py-3 font-medium">Service</th>
              <th class="px-4 py-3 font-medium">Env</th>
              <th class="px-4 py-3 font-medium">Level</th>
              <th class="px-4 py-3 font-medium">Status</th>
              <th class="px-4 py-3 font-medium">Latency</th>
              <th class="px-4 py-3 font-medium">Message</th>
            </tr>
          </thead>
          <tbody>
            {#if loading}
              <tr><td class="px-4 py-8 text-center text-slate-500" colspan="7">Loading events...</td></tr>
            {:else if events.length === 0}
              <tr><td class="px-4 py-8 text-center text-slate-500" colspan="7">No processed events yet. Send demo events, then run the worker.</td></tr>
            {:else}
              {#each events as event}
                <tr class="cursor-pointer border-t border-slate-100 hover:bg-slate-50" onclick={() => (selected = event)}>
                  <td class="px-4 py-3 text-xs">{event.timestamp}</td>
                  <td class="px-4 py-3">{event.service}</td>
                  <td class="px-4 py-3">{event.environment}</td>
                  <td class="px-4 py-3">{event.level}</td>
                  <td class="px-4 py-3">{event.status_code ?? '-'}</td>
                  <td class="px-4 py-3">{event.latency_ms ?? '-'}</td>
                  <td class="px-4 py-3">{safeText(event.message)}</td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>

      <aside class="surface rounded-lg p-5">
        <h2 class="text-lg font-semibold">Event Details</h2>
        {#if selected}
          <dl class="mt-4 space-y-3 text-sm">
            <div><dt class="text-slate-500">Event ID</dt><dd class="font-mono text-xs">{selected.event_id}</dd></div>
            <div><dt class="text-slate-500">Fingerprint</dt><dd class="break-all font-mono text-xs">{selected.fingerprint_hash}</dd></div>
            <div><dt class="text-slate-500">Trace</dt><dd class="font-mono text-xs">{selected.trace_id ?? '-'}</dd></div>
            <div><dt class="text-slate-500">Request</dt><dd class="font-mono text-xs">{selected.request_id ?? '-'}</dd></div>
          </dl>
          <pre class="mt-4 overflow-x-auto rounded bg-slate-950 p-4 text-xs text-slate-100">{JSON.stringify(selected.metadata, null, 2)}</pre>
        {:else}
          <p class="mt-4 text-sm text-slate-500">Select an event to inspect metadata and identifiers.</p>
        {/if}
      </aside>
    </div>
  {/if}
</section>
