<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { listIncidents, type Incident } from '$lib/api/client';
  import { readAccessToken } from '$lib/stores/auth';

  const projectId = $derived(page.params.projectId ?? '');
  let token = $state('');
  let incidents = $state<Incident[]>([]);
  let service = $state('');
  let environment = $state('');
  let severity = $state('');
  let status = $state('open');
  let loading = $state(true);
  let error = $state('');

  async function loadIncidents() {
    token = readAccessToken();
    if (!token) {
      loading = false;
      return;
    }
    loading = true;
    error = '';
    try {
      incidents = (await listIncidents(token, projectId, {
        service,
        environment,
        severity,
        status
      })).incidents;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to load incidents';
    } finally {
      loading = false;
    }
  }

  onMount(loadIncidents);
</script>

<section class="space-y-6">
  <div>
    <a class="text-sm font-medium text-signal hover:underline" href={`/projects/${projectId}`}>Back to overview</a>
    <h1 class="mt-3 text-3xl font-semibold">Incidents</h1>
    <p class="mt-2 text-slate-600">Grouped anomaly investigations with lifecycle status.</p>
  </div>

  <form class="surface grid gap-3 rounded-lg p-5 md:grid-cols-5" onsubmit={(event) => { event.preventDefault(); loadIncidents(); }}>
    <label class="sr-only" for="incident-service">Service</label>
    <input id="incident-service" class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={service} placeholder="service" />
    <label class="sr-only" for="incident-environment">Environment</label>
    <input id="incident-environment" class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={environment} placeholder="environment" />
    <label class="sr-only" for="incident-severity">Severity</label>
    <select id="incident-severity" class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={severity}>
      <option value="">all severities</option>
      <option value="high">high</option>
      <option value="critical">critical</option>
    </select>
    <label class="sr-only" for="incident-status">Status</label>
    <select id="incident-status" class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={status}>
      <option value="">all statuses</option>
      <option value="open">open</option>
      <option value="resolved">resolved</option>
    </select>
    <button class="rounded bg-signal px-4 py-2 text-sm font-medium text-white">Filter</button>
  </form>

  {#if !token && !loading}
    <div class="surface rounded-lg p-8 text-center">
      <h2 class="text-lg font-semibold">Login Required</h2>
      <p class="mt-2 text-sm text-slate-500">Sign in to inspect incidents.</p>
      <a class="mt-4 inline-flex rounded bg-signal px-4 py-2 font-medium text-white" href="/login">Go to Login</a>
    </div>
  {:else if error}
    <div class="flex flex-wrap items-center justify-between gap-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      <span>{error}</span>
      <button class="rounded border border-red-300 px-3 py-1 font-medium" type="button" onclick={loadIncidents}>Retry</button>
    </div>
  {:else if loading}
    <div class="surface rounded-lg p-8 text-center text-sm text-slate-500">Loading incidents...</div>
  {:else if incidents.length === 0}
    <div class="surface rounded-lg p-8 text-center text-sm text-slate-500">
      No incidents match these filters. Generate an error or latency spike and run the worker to create incidents.
    </div>
  {:else}
    <div class="grid gap-4">
      {#each incidents as incident}
        <a class="surface rounded-lg p-5 hover:border-signal" href={`/projects/${projectId}/incidents/${incident.id}`}>
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold">{incident.title}</h2>
              <p class="mt-1 text-sm text-slate-500">{incident.service} - {incident.environment} - started {incident.started_at}</p>
            </div>
            <div class="flex flex-wrap gap-2">
              <span class="rounded px-2 py-1 text-xs font-semibold {incident.severity === 'critical' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-800'}">
                {incident.severity}
              </span>
              <span class="rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">{incident.status}</span>
            </div>
          </div>
          <p class="mt-3 text-sm text-slate-600">{incident.related_anomaly_count} related anomalies</p>
        </a>
      {/each}
    </div>
  {/if}
</section>
