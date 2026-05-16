<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { listAnomalies, type Anomaly } from '$lib/api/client';
  import { readAccessToken } from '$lib/stores/auth';

  const projectId = $derived(page.params.projectId ?? '');
  let token = $state('');
  let anomalies = $state<Anomaly[]>([]);
  let service = $state('');
  let environment = $state('');
  let severity = $state('');
  let status = $state('open');
  let anomalyType = $state('');
  let loading = $state(true);
  let error = $state('');

  async function loadAnomalies() {
    token = readAccessToken();
    if (!token) {
      loading = false;
      return;
    }
    loading = true;
    error = '';
    try {
      anomalies = (await listAnomalies(token, projectId, {
        service,
        environment,
        severity,
        status,
        anomaly_type: anomalyType
      })).anomalies;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to load anomalies';
    } finally {
      loading = false;
    }
  }

  function formatType(value: string) {
    return value.replaceAll('_', ' ');
  }

  onMount(loadAnomalies);
</script>

<section class="space-y-6">
  <div>
    <a class="text-sm font-medium text-signal hover:underline" href={`/projects/${projectId}`}>Back to overview</a>
    <h1 class="mt-3 text-3xl font-semibold">Anomalies</h1>
    <p class="mt-2 text-slate-600">Deterministic anomaly detections from rollups and fingerprints.</p>
  </div>

  <form class="surface grid gap-3 rounded-lg p-5 md:grid-cols-6" onsubmit={(event) => { event.preventDefault(); loadAnomalies(); }}>
    <input class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={service} placeholder="service" />
    <input class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={environment} placeholder="environment" />
    <select class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={severity}>
      <option value="">all severities</option>
      <option value="high">high</option>
      <option value="critical">critical</option>
    </select>
    <select class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={status}>
      <option value="">all statuses</option>
      <option value="open">open</option>
    </select>
    <select class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={anomalyType}>
      <option value="">all types</option>
      <option value="error_rate_spike">error rate spike</option>
      <option value="latency_spike">latency spike</option>
      <option value="new_repeated_error">new repeated error</option>
      <option value="fatal_event_burst">fatal event burst</option>
    </select>
    <button class="rounded bg-signal px-4 py-2 text-sm font-medium text-white">Filter</button>
  </form>

  {#if !token && !loading}
    <div class="surface rounded-lg p-8 text-center">
      <h2 class="text-lg font-semibold">Login Required</h2>
      <p class="mt-2 text-sm text-slate-500">Sign in to inspect anomalies.</p>
      <a class="mt-4 inline-flex rounded bg-signal px-4 py-2 font-medium text-white" href="/login">Go to Login</a>
    </div>
  {:else if error}
    <div class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
  {:else}
    <div class="surface overflow-hidden rounded-lg">
      <table class="w-full border-collapse text-left text-sm">
        <thead class="bg-slate-50 text-slate-500">
          <tr>
            <th class="px-4 py-3 font-medium">Window</th>
            <th class="px-4 py-3 font-medium">Service</th>
            <th class="px-4 py-3 font-medium">Type</th>
            <th class="px-4 py-3 font-medium">Severity</th>
            <th class="px-4 py-3 font-medium">Observed</th>
            <th class="px-4 py-3 font-medium">Baseline</th>
            <th class="px-4 py-3 font-medium">Score</th>
          </tr>
        </thead>
        <tbody>
          {#if loading}
            <tr><td class="px-4 py-8 text-center text-slate-500" colspan="7">Loading anomalies...</td></tr>
          {:else if anomalies.length === 0}
            <tr><td class="px-4 py-8 text-center text-slate-500" colspan="7">No anomalies match these filters.</td></tr>
          {:else}
            {#each anomalies as anomaly}
              <tr class="border-t border-slate-100">
                <td class="px-4 py-3 text-xs">{anomaly.window_start}</td>
                <td class="px-4 py-3">{anomaly.service}</td>
                <td class="px-4 py-3">{formatType(anomaly.anomaly_type)}</td>
                <td class="px-4 py-3">
                  <span class="rounded px-2 py-1 text-xs font-semibold {anomaly.severity === 'critical' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-800'}">
                    {anomaly.severity}
                  </span>
                </td>
                <td class="px-4 py-3">{Math.round(anomaly.observed_value * 1000) / 1000}</td>
                <td class="px-4 py-3">{anomaly.baseline_value === null ? 'n/a' : Math.round(anomaly.baseline_value * 1000) / 1000}</td>
                <td class="px-4 py-3">{Math.round(anomaly.score * 100) / 100}</td>
              </tr>
            {/each}
          {/if}
        </tbody>
      </table>
    </div>
  {/if}
</section>
