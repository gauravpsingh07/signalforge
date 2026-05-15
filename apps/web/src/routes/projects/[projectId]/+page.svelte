<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import MetricLineChart from '$lib/components/MetricLineChart.svelte';
  import { getProjectMetrics, type MetricsResponse } from '$lib/api/client';
  import { readAccessToken } from '$lib/stores/auth';

  const projectId = $derived(page.params.projectId ?? '');
  let token = $state('');
  let metrics = $state<MetricsResponse | null>(null);
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
        <p class="mt-3 text-3xl font-semibold">{metrics.summary.activeIncidents}</p>
        <p class="mt-2 text-xs text-slate-500">Placeholder until Phase 6</p>
      </article>
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
