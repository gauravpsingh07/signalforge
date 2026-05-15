<script lang="ts">
  import { onMount } from 'svelte';
  import { createProject, getProjectMetrics, listProjects, type MetricsResponse, type Project } from '$lib/api/client';
  import { readAccessToken } from '$lib/stores/auth';

  let projects = $state<Project[]>([]);
  let token = $state('');
  let name = $state('');
  let description = $state('');
  let error = $state('');
  let loading = $state(true);
  let saving = $state(false);
  let projectMetrics = $state<Record<string, MetricsResponse>>({});

  async function loadProjects() {
    token = readAccessToken();
    if (!token) {
      loading = false;
      return;
    }

    try {
      projects = await listProjects(token);
      const entries = await Promise.all(
        projects.map(async (project) => {
          try {
            return [project.id, await getProjectMetrics(token, project.id)] as const;
          } catch {
            return [project.id, null] as const;
          }
        })
      );
      projectMetrics = Object.fromEntries(entries.filter((entry) => entry[1] !== null));
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to load projects';
    } finally {
      loading = false;
    }
  }

  async function handleCreate(event: SubmitEvent) {
    event.preventDefault();
    if (!token) return;

    saving = true;
    error = '';
    try {
      const project = await createProject(token, {
        name,
        description: description || undefined
      });
      projects = [project, ...projects];
      projectMetrics = { ...projectMetrics, [project.id]: await getProjectMetrics(token, project.id) };
      name = '';
      description = '';
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to create project';
    } finally {
      saving = false;
    }
  }

  onMount(loadProjects);
</script>

<section class="space-y-6">
  <div>
    <h1 class="text-3xl font-semibold">Dashboard</h1>
    <p class="mt-2 text-slate-600">Manage monitored applications and their metadata foundation.</p>
  </div>

  <div class="grid gap-4 md:grid-cols-3">
    <article class="surface rounded-lg p-5">
      <p class="text-sm text-slate-500">Projects</p>
      <p class="mt-3 text-3xl font-semibold">{projects.length}</p>
      <p class="mt-2 text-sm text-slate-500">Metadata foundation</p>
    </article>
    <article class="surface rounded-lg p-5">
      <p class="text-sm text-slate-500">Active Incidents</p>
      <p class="mt-3 text-3xl font-semibold">0</p>
      <p class="mt-2 text-sm text-slate-500">Planned for Phase 6</p>
    </article>
    <article class="surface rounded-lg p-5">
      <p class="text-sm text-slate-500">Events Today</p>
      <p class="mt-3 text-3xl font-semibold">
        {Object.values(projectMetrics).reduce((sum, metric) => sum + metric.summary.totalEvents, 0)}
      </p>
      <p class="mt-2 text-sm text-slate-500">Processed rollups</p>
    </article>
  </div>

  {#if !token && !loading}
    <div class="surface rounded-lg p-8 text-center">
      <h2 class="text-lg font-semibold">Login Required</h2>
      <p class="mt-2 text-sm text-slate-500">Sign in to create projects and manage API keys.</p>
      <a class="mt-4 inline-flex rounded bg-signal px-4 py-2 font-medium text-white" href="/login">Go to Login</a>
    </div>
  {:else}
    <div class="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
      <form class="surface rounded-lg p-5" onsubmit={handleCreate}>
        <h2 class="text-lg font-semibold">Create Project</h2>
        <div class="mt-4 space-y-3">
          <label class="block text-sm font-medium" for="project-name">Name</label>
          <input
            id="project-name"
            class="w-full rounded border border-slate-300 px-3 py-2 outline-none focus:border-signal"
            bind:value={name}
            placeholder="Checkout Service Demo"
            required
            minlength="2"
          />
          <label class="block text-sm font-medium" for="project-description">Description</label>
          <textarea
            id="project-description"
            class="min-h-24 w-full rounded border border-slate-300 px-3 py-2 outline-none focus:border-signal"
            bind:value={description}
            placeholder="Optional project context"
          ></textarea>
          {#if error}
            <div class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
          {/if}
          <button class="rounded bg-signal px-4 py-2 font-medium text-white disabled:bg-slate-300" disabled={saving}>
            {saving ? 'Creating...' : 'Create Project'}
          </button>
        </div>
      </form>

      <div class="surface rounded-lg p-5">
        <h2 class="text-lg font-semibold">Projects</h2>
        {#if loading}
          <div class="mt-4 rounded border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
            Loading projects...
          </div>
        {:else if projects.length === 0}
          <div class="mt-4 rounded border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
            No projects yet. Create one to generate ingestion API keys.
          </div>
        {:else}
          <div class="mt-4 grid gap-3">
            {#each projects as project}
              <a class="rounded border border-slate-200 bg-white p-4 hover:border-signal" href={`/projects/${project.id}`}>
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <p class="font-semibold">{project.name}</p>
                    <p class="text-sm text-slate-500">{project.slug}</p>
                  </div>
                  <div class="text-right text-sm">
                    <p class="font-semibold">{projectMetrics[project.id]?.summary.totalEvents ?? 0} events</p>
                    <p class="text-slate-500">
                      {Math.round(((projectMetrics[project.id]?.summary.errorRate ?? 0) * 1000)) / 10}% errors
                    </p>
                  </div>
                </div>
                <p class="mt-3 text-xs text-slate-500">Incident status placeholder: none active</p>
              </a>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  {/if}
</section>
