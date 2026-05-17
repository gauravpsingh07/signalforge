<script lang="ts">
  const productCards = [
    {
      title: 'Ingest Events',
      detail: 'Send logs, errors, latency data, and service events through the ingestion API.'
    },
    {
      title: 'Detect Anomalies',
      detail:
        'Identify error spikes, latency regressions, repeated failures, and fatal bursts using deterministic detection.'
    },
    {
      title: 'Investigate Incidents',
      detail:
        'View grouped incidents, timelines, AI/fallback summaries, recommended actions, and alert history.'
    }
  ];

  const workflowSteps = [
    'FastAPI validates API keys and accepts events.',
    'Events are queued so ingestion stays fast.',
    'The worker normalizes events, updates rollups, and detects anomalies.',
    'Related anomalies become incidents with summaries and alert history.'
  ];
</script>

<section class="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-start">
  <div class="space-y-6">
    <div class="space-y-4">
      <p class="text-sm font-semibold uppercase tracking-wide text-signal">Distributed AI Observability</p>
      <h1 class="max-w-3xl text-4xl font-semibold leading-tight text-ink sm:text-5xl">
        Turn application events into incident intelligence.
      </h1>
      <p class="max-w-2xl text-lg leading-8 text-slate-600">
        SignalForge ingests application events, processes them asynchronously, detects error
        and latency anomalies, groups related failures into incidents, and summarizes what
        happened so teams can debug faster.
      </p>
    </div>

    <div class="grid gap-4 sm:grid-cols-3">
      {#each productCards as card}
        <article class="surface rounded-lg p-5">
          <h2 class="text-lg font-semibold text-ink">{card.title}</h2>
          <p class="mt-3 text-sm leading-6 text-slate-600">{card.detail}</p>
        </article>
      {/each}
    </div>

    <div class="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
      <p class="font-semibold">Free-tier demo note</p>
      <p class="mt-1">
        The frontend and API are deployed on Vercel and Render. Background processing uses
        the separate worker service, which can be run locally during free-tier demos.
      </p>
    </div>
  </div>

  <aside class="surface rounded-lg p-5">
    <div class="flex items-center justify-between border-b border-slate-200 pb-4">
      <div>
        <h2 class="text-lg font-semibold">How SignalForge Works</h2>
        <p class="text-sm text-slate-500">From ingestion to incident context</p>
      </div>
      <span class="rounded bg-emerald-50 px-3 py-1 text-sm font-medium text-signal">Live</span>
    </div>

    <div class="mt-5 space-y-3">
      {#each workflowSteps as step, index}
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
