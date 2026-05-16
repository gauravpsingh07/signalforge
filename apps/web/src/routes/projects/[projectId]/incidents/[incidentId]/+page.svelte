<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { getIncident, resolveIncident, type IncidentDetail } from '$lib/api/client';
  import { readAccessToken } from '$lib/stores/auth';

  const projectId = $derived(page.params.projectId ?? '');
  const incidentId = $derived(page.params.incidentId ?? '');
  let token = $state('');
  let detail = $state<IncidentDetail | null>(null);
  let loading = $state(true);
  let resolving = $state(false);
  let error = $state('');

  async function loadIncident() {
    token = readAccessToken();
    if (!token) {
      loading = false;
      return;
    }
    loading = true;
    error = '';
    try {
      detail = await getIncident(token, incidentId);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to load incident';
    } finally {
      loading = false;
    }
  }

  async function handleResolve() {
    if (!token || !detail) return;
    resolving = true;
    error = '';
    try {
      const response = await resolveIncident(token, detail.incident.id);
      detail = { ...detail, incident: response.incident };
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to resolve incident';
    } finally {
      resolving = false;
    }
  }

  function formatType(value: string) {
    return value.replaceAll('_', ' ');
  }

  onMount(loadIncident);
</script>

<section class="space-y-6">
  <div>
    <a class="text-sm font-medium text-signal hover:underline" href={`/projects/${projectId}/incidents`}>Back to incidents</a>
  </div>

  {#if !token && !loading}
    <div class="surface rounded-lg p-8 text-center">
      <h1 class="text-lg font-semibold">Login Required</h1>
      <p class="mt-2 text-sm text-slate-500">Sign in to inspect incident details.</p>
      <a class="mt-4 inline-flex rounded bg-signal px-4 py-2 font-medium text-white" href="/login">Go to Login</a>
    </div>
  {:else if error}
    <div class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
  {:else if loading}
    <div class="surface rounded-lg p-8 text-center text-sm text-slate-500">Loading incident...</div>
  {:else if detail}
    <div class="surface rounded-lg p-5">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 class="text-3xl font-semibold">{detail.incident.title}</h1>
          <p class="mt-2 text-slate-600">{detail.incident.service} - {detail.incident.environment}</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <span class="rounded px-2 py-1 text-xs font-semibold {detail.incident.severity === 'critical' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-800'}">
            {detail.incident.severity}
          </span>
          <span class="rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">{detail.incident.status}</span>
          {#if detail.incident.status !== 'resolved'}
            <button class="rounded bg-signal px-4 py-2 text-sm font-medium text-white disabled:bg-slate-300" disabled={resolving} onclick={handleResolve}>
              {resolving ? 'Resolving...' : 'Resolve'}
            </button>
          {/if}
        </div>
      </div>
    </div>

    <div class="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
      <aside class="surface rounded-lg p-5">
        <h2 class="text-lg font-semibold">Timeline</h2>
        <div class="mt-4 space-y-4">
          {#each detail.timeline as item}
            <div class="border-l-2 border-signal pl-4">
              <p class="text-xs text-slate-500">{item.time}</p>
              <p class="font-semibold">{item.label}</p>
              <p class="text-sm text-slate-600">{item.description}</p>
            </div>
          {/each}
        </div>
      </aside>

      <div class="space-y-6">
        <section class="surface rounded-lg p-5">
          <h2 class="text-lg font-semibold">AI Summary</h2>
          <div class="mt-4 rounded border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-500">
            Gemini incident summaries are available after Phase 7. This phase stores nullable summary fields without generating AI output.
          </div>
        </section>

        <section class="surface overflow-hidden rounded-lg">
          <div class="border-b border-slate-100 px-5 py-4">
            <h2 class="text-lg font-semibold">Related Anomalies</h2>
          </div>
          <table class="w-full border-collapse text-left text-sm">
            <thead class="bg-slate-50 text-slate-500">
              <tr>
                <th class="px-4 py-3 font-medium">Window</th>
                <th class="px-4 py-3 font-medium">Type</th>
                <th class="px-4 py-3 font-medium">Severity</th>
                <th class="px-4 py-3 font-medium">Observed</th>
              </tr>
            </thead>
            <tbody>
              {#each detail.related_anomalies as anomaly}
                <tr class="border-t border-slate-100">
                  <td class="px-4 py-3 text-xs">{anomaly.window_start}</td>
                  <td class="px-4 py-3">{formatType(anomaly.anomaly_type)}</td>
                  <td class="px-4 py-3">{anomaly.severity}</td>
                  <td class="px-4 py-3">{Math.round(anomaly.observed_value * 1000) / 1000}</td>
                </tr>
              {:else}
                <tr><td class="px-4 py-8 text-center text-slate-500" colspan="4">No related anomalies found.</td></tr>
              {/each}
            </tbody>
          </table>
        </section>

        <section class="surface rounded-lg p-5">
          <h2 class="text-lg font-semibold">Related Fingerprints</h2>
          {#if detail.related_fingerprints.length === 0}
            <p class="mt-4 text-sm text-slate-500">No fingerprint was linked to this incident.</p>
          {:else}
            <div class="mt-4 space-y-2">
              {#each detail.related_fingerprints as fingerprint}
                <code class="block break-all rounded bg-slate-100 px-3 py-2 text-xs">{fingerprint}</code>
              {/each}
            </div>
          {/if}
        </section>
      </div>
    </div>
  {/if}
</section>
