<script lang="ts">
  import { onMount } from 'svelte';
  import { createProject, listProjects, type Project } from '$lib/api/client';
  import { readAccessToken } from '$lib/stores/auth';

  let projects = $state<Project[]>([]);
  let token = $state('');
  let name = $state('');
  let error = $state('');
  let loading = $state(true);
  let saving = $state(false);

  async function loadProjects() {
    token = readAccessToken();
    if (!token) {
      loading = false;
      return;
    }
    try {
      projects = await listProjects(token);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to load projects';
    } finally {
      loading = false;
    }
  }

  async function handleCreate(event: SubmitEvent) {
    event.preventDefault();
    saving = true;
    error = '';
    try {
      const project = await createProject(token, { name });
      projects = [project, ...projects];
      name = '';
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unable to create project';
    } finally {
      saving = false;
    }
  }

  onMount(loadProjects);
</script>

<section class="space-y-6">
  <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div>
      <h1 class="text-3xl font-semibold">Projects</h1>
      <p class="mt-2 text-slate-600">Create monitored applications and open settings to manage API keys.</p>
    </div>
  </div>

  {#if !token && !loading}
    <div class="surface rounded-lg p-8 text-center">
      <h2 class="text-lg font-semibold">Login Required</h2>
      <p class="mt-2 text-sm text-slate-500">Projects are scoped to your account.</p>
      <a class="mt-4 inline-flex rounded bg-signal px-4 py-2 font-medium text-white" href="/login">Go to Login</a>
    </div>
  {:else}
    <form class="surface flex flex-col gap-3 rounded-lg p-5 sm:flex-row sm:items-end" onsubmit={handleCreate}>
      <div class="flex-1">
        <label class="block text-sm font-medium" for="name">Project Name</label>
        <input
          id="name"
          class="mt-2 w-full rounded border border-slate-300 px-3 py-2 outline-none focus:border-signal"
          bind:value={name}
          placeholder="Checkout Service Demo"
          required
          minlength="2"
        />
      </div>
      <button class="rounded bg-signal px-4 py-2 font-medium text-white disabled:bg-slate-300" disabled={saving}>
        {saving ? 'Creating...' : 'New Project'}
      </button>
    </form>
  {/if}

  {#if error}
    <div class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
  {/if}

  <div class="surface overflow-hidden rounded-lg">
    <table class="w-full border-collapse text-left text-sm">
      <thead class="bg-slate-50 text-slate-500">
        <tr>
          <th class="px-4 py-3 font-medium">Name</th>
          <th class="px-4 py-3 font-medium">Environment</th>
          <th class="px-4 py-3 font-medium">Status</th>
        </tr>
      </thead>
      <tbody>
        {#if loading}
          <tr>
            <td class="px-4 py-8 text-center text-slate-500" colspan="3">Loading projects...</td>
          </tr>
        {:else if projects.length === 0}
          <tr>
            <td class="px-4 py-8 text-center text-slate-500" colspan="3">No projects yet.</td>
          </tr>
        {:else}
          {#each projects as project}
            <tr class="border-t border-slate-100">
              <td class="px-4 py-3">
                <a class="font-medium text-signal hover:underline" href={`/projects/${project.id}`}>
                  {project.name}
                </a>
                <p class="text-xs text-slate-500">{project.slug}</p>
              </td>
              <td class="px-4 py-3">{project.environment_default}</td>
              <td class="px-4 py-3">
                <span class="rounded bg-emerald-50 px-2 py-1 text-xs font-medium text-signal">Active</span>
              </td>
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</section>
