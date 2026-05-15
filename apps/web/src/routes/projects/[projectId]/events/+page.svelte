<script lang="ts">
  import { page } from '$app/state';

  const projectId = $derived(page.params.projectId ?? '');
</script>

<section class="space-y-6">
  <div>
    <a class="text-sm font-medium text-signal hover:underline" href={`/projects/${projectId}/settings`}>
      Back to settings
    </a>
    <h1 class="mt-3 text-3xl font-semibold">Events</h1>
    <p class="mt-2 text-slate-600">
      Events are accepted and queued in Phase 2. Search, storage, and worker-processed event rows
      arrive in later phases.
    </p>
  </div>

  <div class="surface rounded-lg p-8 text-center">
    <h2 class="text-lg font-semibold">Worker Processing Coming Later</h2>
    <p class="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-500">
      Use the project API key to send events to <code>/v1/events</code>. They are validated,
      rate-limited, and queued now; the event explorer will populate after worker processing and
      event storage are implemented.
    </p>
  </div>
</section>
