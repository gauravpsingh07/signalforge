<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import MetricLineChart from '$lib/components/MetricLineChart.svelte';
  import {
    getProjectMetrics,
    listAnomalies,
    listIncidents,
    type Anomaly,
    type Incident,
    type MetricsResponse
  } from '$lib/api/client';
  import { readAccessToken } from '$lib/stores/auth';

  const projectId = $derived(page.params.projectId ?? '');
  let token = $state('');
  let metrics = $state<MetricsResponse | null>(null);
  let anomalies = $state<Anomaly[]>([]);
  let incidents = $state<Incident[]>([]);
  let range = $state('1h');
  let service = $state('');
  let environment = $state('');
  let loading = $state(true);
  let error = $state('');

  const labels = $derived(metrics?.series.map((bucket) => new Date(bucket.bucketStart).toLocaleTimeString()) ?? []);
  const eventValues = $derived(metrics?.series.map((bucket) => bucket.totalEvents) ?? []);
  const errorValues = $derived(metrics?.series.map((bucket) => Math.round(bucket.errorRate * 100)) ?? []);
  const latencyValues = $derived(metrics?.series.map((bucket) => bucket.latencyP95Ms ?? 0) ?? []);

  async function loadMetrics() {
    token = readAccessToken();
    if (!token) {
      loading = false;
      return;
    }

    loading = true;
    error = '';
    try {
      metrics = await getProjectMetrics(token, projectId, {
        range,
        service,
        environment
      });
      anomalies = (await listAnomalies(token, projectId, { status: 'open' })).anomalies;
      incidents = (await listIncidents(token, projectId, { status: 'open' })).incidents;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to load metrics';
    } finally {
      loading = false;
    }
  }

  function pct(value: number) {
    return `${Math.round(value * 1000) / 10}%`;
  }

  onMount(loadMetrics);
</script>

<section class="space-y-6">
  <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
    <div>
      <a class="text-sm font-medium text-signal hover:underline" href="/projects">Back to projects</a>
      <h1 class="mt-3 text-3xl font-semibold">Project Overview</h1>
      <p class="mt-2 text-slate-600">Service-level rollups from processed events.</p>
    </div>
    <div class="flex flex-wrap gap-2">
      <select class="rounded border border-slate-300 bg-white px-3 py-2 text-sm" bind:value={range} onchange={loadMetrics}>
        <option value="1h">1h</option>
        <option value="6h">6h</option>
        <option value="24h">24h</option>
      </select>
      <input class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={service} placeholder="service" />
      <input class="rounded border border-slate-300 px-3 py-2 text-sm" bind:value={environment} placeholder="environment" />
      <button class="rounded bg-signal px-4 py-2 text-sm font-medium text-white" onclick={loadMetrics}>Apply</button>
      <a class="rounded border border-slate-300 px-4 py-2 text-sm font-medium" href={`/projects/${projectId}/events`}>Events</a>
      <a class="rounded border border-slate-300 px-4 py-2 text-sm font-medium" href={`/projects/${projectId}/anomalies`}>Anomalies</a>
      <a class="rounded border border-slate-300 px-4 py-2 text-sm font-medium" href={`/projects/${projectId}/incidents`}>Incidents</a>
    </div>
  </div>

  {#if !token && !loading}
    <div class="surface rounded-lg p-8 text-center">
      <h2 class="text-lg font-semibold">Login Required</h2>
      <p class="mt-2 text-sm text-slate-500">Sign in to view project metrics.</p>
      <a class="mt-4 inline-flex rounded bg-signal px-4 py-2 font-medium text-white" href="/login">Go to Login</a>
    </div>
  {:else if error}
    <div class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
  {:else if loading}
    <div class="surface rounded-lg p-8 text-center text-sm text-slate-500">Loading metrics...</div>
  {:else if metrics}
    <div class="grid gap-4 md:grid-cols-4">
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Total Events</p>
        <p class="mt-3 text-3xl font-semibold">{metrics.summary.totalEvents}</p>
      </article>
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Error Rate</p>
        <p class="mt-3 text-3xl font-semibold">{pct(metrics.summary.errorRate)}</p>
      </article>
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">p95 Latency</p>
        <p class="mt-3 text-3xl font-semibold">{metrics.summary.latencyP95Ms ?? 0}ms</p>
      </article>
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Active Incidents</p>
        <p class="mt-3 text-3xl font-semibold">{incidents.length}</p>
        <p class="mt-2 text-xs text-slate-500">Grouped from open anomalies</p>
      </article>
    </div>

    <div class="surface rounded-lg p-5">
      <div class="flex items-center justify-between gap-3">
        <h2 class="text-lg font-semibold">Recent Incidents</h2>
        <a class="text-sm font-medium text-signal hover:underline" href={`/projects/${projectId}/incidents`}>View all</a>
      </div>
      {#if incidents.length === 0}
        <div class="mt-4 rounded border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
          No open incidents. New anomalies will be grouped here for investigation.
        </div>
      {:else}
        <div class="mt-4 grid gap-3 md:grid-cols-2">
          {#each incidents.slice(0, 4) as incident}
            <a class="rounded border border-slate-200 bg-white p-4 hover:border-signal" href={`/projects/${projectId}/incidents/${incident.id}`}>
              <div class="flex flex-wrap items-center justify-between gap-3">
                <p class="font-semibold">{incident.title}</p>
                <span class="rounded px-2 py-1 text-xs font-semibold {incident.severity === 'critical' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-800'}">
                  {incident.severity}
                </span>
              </div>
              <p class="mt-2 text-sm text-slate-500">{incident.service} - {incident.environment} - {incident.related_anomaly_count} anomalies</p>
            </a>
          {/each}
        </div>
      {/if}
    </div>

    <div class="surface rounded-lg p-5">
      <div class="flex items-center justify-between gap-3">
        <h2 class="text-lg font-semibold">Anomaly Timeline</h2>
        <a class="text-sm font-medium text-signal hover:underline" href={`/projects/${projectId}/anomalies`}>View all</a>
      </div>
      {#if anomalies.length === 0}
        <div class="mt-4 rounded border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
          No open anomalies detected.
        </div>
      {:else}
        <div class="mt-4 grid gap-3">
          {#each anomalies.slice(0, 5) as anomaly}
            <div class="rounded border border-slate-200 bg-white p-4">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p class="font-semibold">{anomaly.anomaly_type.replaceAll('_', ' ')}</p>
                  <p class="text-sm text-slate-500">{anomaly.service} - {anomaly.environment} - {anomaly.window_start}</p>
                </div>
                <span class="rounded px-2 py-1 text-xs font-semibold {anomaly.severity === 'critical' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-800'}">
                  {anomaly.severity}
                </span>
              </div>
              <p class="mt-2 text-sm text-slate-600">
                Observed {Math.round(anomaly.observed_value * 1000) / 1000}
                vs baseline {anomaly.baseline_value === null ? 'n/a' : Math.round(anomaly.baseline_value * 1000) / 1000}.
              </p>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    {#if metrics.series.length === 0}
      <div class="surface rounded-lg p-8 text-center text-sm text-slate-500">
        No rollups yet. Send demo events and run the worker to populate charts.
      </div>
    {:else}
      <div class="grid gap-6 xl:grid-cols-3">
        <MetricLineChart title="Event Volume" labels={labels} values={eventValues} color="#0f766e" />
        <MetricLineChart title="Error Rate %" labels={labels} values={errorValues} color="#dc2626" />
        <MetricLineChart title="p95 Latency ms" labels={labels} values={latencyValues} color="#d97706" />
      </div>

      <div class="surface overflow-hidden rounded-lg">
        <table class="w-full border-collapse text-left text-sm">
          <thead class="bg-slate-50 text-slate-500">
            <tr>
              <th class="px-4 py-3 font-medium">Service</th>
              <th class="px-4 py-3 font-medium">Events</th>
              <th class="px-4 py-3 font-medium">Errors</th>
              <th class="px-4 py-3 font-medium">Error Rate</th>
            </tr>
          </thead>
          <tbody>
            {#each metrics.topServices as row}
              <tr class="border-t border-slate-100">
                <td class="px-4 py-3 font-medium">{row.service}</td>
                <td class="px-4 py-3">{row.totalEvents}</td>
                <td class="px-4 py-3">{row.errorEvents + row.fatalEvents}</td>
                <td class="px-4 py-3">{pct(row.errorRate)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</section>
