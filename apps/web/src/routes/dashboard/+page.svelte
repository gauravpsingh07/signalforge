<script lang="ts">
  const summaries = [
    { label: 'Projects', value: '0', trend: 'Create projects in Phase 1' },
    { label: 'Active Incidents', value: '0', trend: 'Incident lifecycle is planned' },
    { label: 'Events Today', value: '0', trend: 'Ingestion starts in Phase 2' }
  ];
</script>

<section class="space-y-6">
  <div>
    <h1 class="text-3xl font-semibold">Dashboard</h1>
    <p class="mt-2 text-slate-600">Phase 0 dashboard shell for the SignalForge control plane.</p>
  </div>

  <div class="grid gap-4 md:grid-cols-3">
    {#each summaries as summary}
      <article class="surface rounded-lg p-5">
        <p class="text-sm text-slate-500">{summary.label}</p>
        <p class="mt-3 text-3xl font-semibold">{summary.value}</p>
        <p class="mt-2 text-sm text-slate-500">{summary.trend}</p>
      </article>
    {/each}
  </div>

  <div class="surface rounded-lg p-5">
    <div class="mb-4 flex items-center justify-between">
      <h2 class="text-lg font-semibold">Recent Activity</h2>
      <span class="rounded bg-slate-100 px-3 py-1 text-sm text-slate-500">Empty</span>
    </div>
    <div class="rounded border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
      Event activity will appear after ingestion and worker processing are implemented.
    </div>
  </div>
</section>
