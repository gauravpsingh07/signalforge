<section class="space-y-6">
  <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div>
      <h1 class="text-3xl font-semibold">Projects</h1>
      <p class="mt-2 text-slate-600">Project CRUD and API key management arrive in Phase 1.</p>
    </div>
    <button class="rounded bg-slate-300 px-4 py-2 font-medium text-slate-600" type="button" disabled>
      New Project
    </button>
  </div>

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
        <tr>
          <td class="px-4 py-8 text-center text-slate-500" colspan="3">
            No projects yet.
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</section>
