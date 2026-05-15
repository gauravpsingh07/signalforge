<script lang="ts">
  const metrics = [
    { label: 'Ingestion API', value: 'Phase 0', detail: 'Skeleton health endpoint' },
    { label: 'Queue + Worker', value: 'Planned', detail: 'Async processing foundation' },
    { label: 'AI Summaries', value: 'Planned', detail: 'Gemini integration in later phases' }
  ];
</script>

<section class="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-start">
  <div class="space-y-6">
    <div class="space-y-4">
      <p class="text-sm font-semibold uppercase tracking-wide text-signal">Distributed AI Observability</p>
      <h1 class="max-w-3xl text-4xl font-semibold leading-tight text-ink sm:text-5xl">
        SignalForge turns application events into incident intelligence.
      </h1>
      <p class="max-w-2xl text-lg leading-8 text-slate-600">
        Phase 0 establishes the monorepo, frontend shell, FastAPI service, worker skeleton,
        docs, and local development configuration for the full event pipeline.
      </p>
    </div>

    <div class="grid gap-4 sm:grid-cols-3">
      {#each metrics as metric}
        <article class="surface rounded-lg p-5">
          <p class="text-sm text-slate-500">{metric.label}</p>
          <p class="mt-3 text-2xl font-semibold text-ink">{metric.value}</p>
          <p class="mt-2 text-sm text-slate-500">{metric.detail}</p>
        </article>
      {/each}
    </div>
  </div>

  <aside class="surface rounded-lg p-5">
    <div class="flex items-center justify-between border-b border-slate-200 pb-4">
      <div>
        <h2 class="text-lg font-semibold">Pipeline Blueprint</h2>
        <p class="text-sm text-slate-500">Foundation status</p>
      </div>
      <span class="rounded bg-emerald-50 px-3 py-1 text-sm font-medium text-signal">Ready</span>
    </div>

    <div class="mt-5 space-y-3">
      {#each ['FastAPI validates and enqueues events', 'Worker processes jobs outside request path', 'Rollups and anomaly detection feed incidents', 'Gemini summaries and Discord alerts complete the loop'] as step, index}
        <div class="flex gap-3 rounded border border-slate-200 bg-white p-3">
          <span class="grid size-7 shrink-0 place-items-center rounded bg-slate-100 text-sm font-semibold">
            {index + 1}
          </span>
          <p class="text-sm leading-6 text-slate-700">{step}</p>
        </div>
      {/each}
    </div>
  </aside>
</section>
