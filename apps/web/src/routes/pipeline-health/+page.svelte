<script lang="ts">
  import { getHealth, type ApiHealth } from '$lib/api/client';

  let health = $state<ApiHealth | null>(null);
  let error = $state('');
  let loading = $state(true);

  async function loadHealth() {
    loading = true;
    error = '';

    try {
      health = await getHealth();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to reach API';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    loadHealth();
  });
</script>

<section class="space-y-6">
  <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div>
      <h1 class="text-3xl font-semibold">Pipeline Health</h1>
      <p class="mt-2 text-slate-600">Phase 0 checks the API service boundary.</p>
    </div>
    <button class="rounded border border-slate-300 bg-white px-4 py-2 font-medium" type="button" onclick={loadHealth}>
      Refresh
    </button>
  </div>

  {#if loading}
    <div class="surface rounded-lg p-6 text-slate-500">Loading service status...</div>
  {:else if error}
    <div class="surface rounded-lg border-red-200 p-6 text-red-700">{error}</div>
  {:else if health}
    <div class="grid gap-4 md:grid-cols-4">
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Service</p>
        <p class="mt-3 text-xl font-semibold">{health.service}</p>
      </article>
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Status</p>
        <p class="mt-3 text-xl font-semibold capitalize text-signal">{health.status}</p>
      </article>
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Version</p>
        <p class="mt-3 text-xl font-semibold">{health.version}</p>
      </article>
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">Timestamp</p>
        <p class="mt-3 text-sm font-medium text-slate-700">{health.timestamp}</p>
      </article>
    </div>
  {/if}

  <div class="surface rounded-lg p-5">
    <h2 class="text-lg font-semibold">Worker Pipeline</h2>
    <div class="mt-4 rounded border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
      Queue depth, worker jobs, failures, and processing latency are planned for later phases.
    </div>
  </div>
</section>
