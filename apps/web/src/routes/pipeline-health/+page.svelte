<script lang="ts">
  import { onMount } from 'svelte';
  import {
    getPipelineHealth,
    listPipelineJobs,
    retryPipelineJob,
    type PipelineHealth,
    type PipelineJob
  } from '$lib/api/client';
  import { readAccessToken } from '$lib/stores/auth';

  const statuses = ['all', 'queued', 'processing', 'failed', 'dead_letter', 'completed'];

  let token = $state('');
  let health = $state<PipelineHealth | null>(null);
  let jobs = $state<PipelineJob[]>([]);
  let statusFilter = $state('all');
  let error = $state('');
  let loading = $state(true);
  let retryingJobId = $state('');

  const counts = $derived(health?.jobs.counts ?? {});
  const visibleFailures = $derived(jobs.filter((job) => job.error_message).slice(0, 4));

  async function loadPipeline() {
    token = readAccessToken();
    if (!token) {
      loading = false;
      return;
    }

    loading = true;
    error = '';
    try {
      const filters = statusFilter === 'all' ? { limit: 100 } : { status: statusFilter, limit: 100 };
      const [healthResponse, jobsResponse] = await Promise.all([
        getPipelineHealth(token),
        listPipelineJobs(token, filters)
      ]);
      health = healthResponse;
      jobs = jobsResponse.jobs;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to load pipeline health';
    } finally {
      loading = false;
    }
  }

  async function handleRetry(jobId: string) {
    retryingJobId = jobId;
    error = '';
    try {
      await retryPipelineJob(token, jobId);
      await loadPipeline();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to retry job';
    } finally {
      retryingJobId = '';
    }
  }

  function formatDate(value: string | null) {
    if (!value) return 'n/a';
    return new Date(value).toLocaleString();
  }

  function formatLatency(value: number | null) {
    if (value === null) return 'n/a';
    return `${Math.round(value)}ms`;
  }

  function statusClass(status: string) {
    if (status === 'completed') return 'bg-emerald-50 text-emerald-700';
    if (status === 'processing') return 'bg-blue-50 text-blue-700';
    if (status === 'queued') return 'bg-slate-100 text-slate-700';
    if (status === 'dead_letter') return 'bg-red-100 text-red-700';
    return 'bg-amber-100 text-amber-800';
  }

  onMount(loadPipeline);
</script>

<section class="space-y-6">
  <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
    <div>
      <h1 class="text-3xl font-semibold">Pipeline Health</h1>
      <p class="mt-2 text-slate-600">Worker status, queue depth, processing latency, and failed-job visibility.</p>
    </div>
    <div class="flex flex-wrap gap-2">
      <select class="rounded border border-slate-300 bg-white px-3 py-2 text-sm" bind:value={statusFilter} onchange={loadPipeline}>
        {#each statuses as status}
          <option value={status}>{status.replace('_', ' ')}</option>
        {/each}
      </select>
      <button class="rounded bg-signal px-4 py-2 text-sm font-medium text-white" type="button" onclick={loadPipeline}>
        Refresh
      </button>
    </div>
  </div>

  {#if !token && !loading}
    <div class="surface rounded-lg p-8 text-center">
      <h2 class="text-lg font-semibold">Login Required</h2>
      <p class="mt-2 text-sm text-slate-500">Pipeline health is scoped to your projects.</p>
      <a class="mt-4 inline-flex rounded bg-signal px-4 py-2 font-medium text-white" href="/login">Go to Login</a>
    </div>
  {:else if error}
    <div class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
  {/if}

  {#if loading}
    <div class="surface rounded-lg p-8 text-center text-sm text-slate-500">Loading pipeline health...</div>
  {:else if health}
    <div class="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Queued</p>
        <p class="mt-3 text-3xl font-semibold">{counts.queued ?? 0}</p>
      </article>
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Processing</p>
        <p class="mt-3 text-3xl font-semibold">{counts.processing ?? 0}</p>
      </article>
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Failed</p>
        <p class="mt-3 text-3xl font-semibold">{counts.failed ?? 0}</p>
      </article>
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Dead Letter</p>
        <p class="mt-3 text-3xl font-semibold">{counts.dead_letter ?? 0}</p>
      </article>
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Completed 1h</p>
        <p class="mt-3 text-3xl font-semibold">{health.jobs.completedLastHour}</p>
      </article>
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Avg Latency</p>
        <p class="mt-3 text-3xl font-semibold">{formatLatency(health.jobs.averageProcessingLatencyMs)}</p>
      </article>
    </div>

    <div class="grid gap-4 lg:grid-cols-3">
      <article class="surface rounded-lg p-5">
        <h2 class="text-lg font-semibold">Queue</h2>
        <dl class="mt-4 space-y-3 text-sm">
          <div class="flex justify-between gap-3">
            <dt class="text-slate-500">Provider</dt>
            <dd class="font-medium capitalize">{health.queue.provider}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-slate-500">Depth</dt>
            <dd class="font-medium">{health.queue.depth ?? 'n/a'}</dd>
          </div>
        </dl>
      </article>
      <article class="surface rounded-lg p-5">
        <h2 class="text-lg font-semibold">Throughput</h2>
        <dl class="mt-4 space-y-3 text-sm">
          <div class="flex justify-between gap-3">
            <dt class="text-slate-500">Accepted 1h</dt>
            <dd class="font-medium">{health.ingestion.eventsAcceptedLastHour}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-slate-500">Last processed</dt>
            <dd class="font-medium">{formatDate(health.jobs.lastProcessedAt)}</dd>
          </div>
        </dl>
      </article>
      <article class="surface rounded-lg p-5">
        <h2 class="text-lg font-semibold">Failures</h2>
        <dl class="mt-4 space-y-3 text-sm">
          <div class="flex justify-between gap-3">
            <dt class="text-slate-500">Failed or dead-letter</dt>
            <dd class="font-medium">{health.jobs.failedOrDeadLetter}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-slate-500">Alert delivery failures</dt>
            <dd class="font-medium">{health.alerts.failedDeliveries}</dd>
          </div>
        </dl>
      </article>
    </div>

    {#if visibleFailures.length > 0}
      <div class="surface rounded-lg p-5">
        <h2 class="text-lg font-semibold">Recent Error Messages</h2>
        <div class="mt-4 grid gap-3">
          {#each visibleFailures as job}
            <div class="rounded border border-red-100 bg-red-50 p-3 text-sm text-red-800">
              <p class="font-medium">{job.id}</p>
              <p class="mt-1 break-words">{job.error_message}</p>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <div class="surface overflow-hidden rounded-lg">
      <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <h2 class="text-lg font-semibold">Recent Worker Jobs</h2>
        <p class="text-sm text-slate-500">{jobs.length} shown</p>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full min-w-[920px] border-collapse text-left text-sm">
          <thead class="bg-slate-50 text-slate-500">
            <tr>
              <th class="px-4 py-3 font-medium">Job</th>
              <th class="px-4 py-3 font-medium">Status</th>
              <th class="px-4 py-3 font-medium">Type</th>
              <th class="px-4 py-3 font-medium">Attempts</th>
              <th class="px-4 py-3 font-medium">Latency</th>
              <th class="px-4 py-3 font-medium">Created</th>
              <th class="px-4 py-3 font-medium">Error</th>
              <th class="px-4 py-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {#if jobs.length === 0}
              <tr>
                <td class="px-4 py-8 text-center text-slate-500" colspan="8">No worker jobs match the current filter.</td>
              </tr>
            {:else}
              {#each jobs as job}
                <tr class="border-t border-slate-100">
                  <td class="px-4 py-3 font-medium">{job.id}</td>
                  <td class="px-4 py-3">
                    <span class="rounded px-2 py-1 text-xs font-semibold {statusClass(job.status)}">
                      {job.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td class="px-4 py-3">{job.job_type ?? 'n/a'}</td>
                  <td class="px-4 py-3">{job.attempts}/{job.max_attempts}</td>
                  <td class="px-4 py-3">{formatLatency(job.processing_latency_ms)}</td>
                  <td class="px-4 py-3">{formatDate(job.created_at)}</td>
                  <td class="max-w-[260px] truncate px-4 py-3 text-slate-600">{job.error_message ?? 'n/a'}</td>
                  <td class="px-4 py-3">
                    {#if job.status === 'failed' || job.status === 'dead_letter'}
                      <button
                        class="rounded border border-slate-300 px-3 py-1.5 text-xs font-medium disabled:bg-slate-100 disabled:text-slate-400"
                        type="button"
                        disabled={retryingJobId === job.id || !job.has_payload}
                        onclick={() => handleRetry(job.id)}
                      >
                        {retryingJobId === job.id ? 'Retrying...' : 'Retry'}
                      </button>
                    {:else}
                      <span class="text-xs text-slate-400">n/a</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
</section>
