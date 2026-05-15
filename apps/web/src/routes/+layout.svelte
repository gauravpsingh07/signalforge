<script lang="ts">
  import '../app.css';

  const navItems = [
    { href: '/', label: 'Overview' },
    { href: '/dashboard', label: 'Dashboard' },
    { href: '/projects', label: 'Projects' },
    { href: '/pipeline-health', label: 'Pipeline' }
  ];
</script>

<svelte:head>
  <title>SignalForge</title>
  <meta
    name="description"
    content="SignalForge distributed AI observability platform foundation"
  />
</svelte:head>

<div class="min-h-screen bg-[#f4f7f9] text-ink">
  <header class="border-b border-black/10 bg-white/85 backdrop-blur">
    <div class="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <a href="/" class="flex items-center gap-3 font-semibold text-ink">
        <span class="grid size-9 place-items-center rounded bg-signal text-sm font-bold text-white">SF</span>
        <span>SignalForge</span>
      </a>

      <nav class="flex flex-wrap items-center gap-2 text-sm text-slate-600">
        {#each navItems as item}
          <a class="rounded px-3 py-2 hover:bg-slate-100 hover:text-ink" href={item.href}>{item.label}</a>
        {/each}
        <a class="rounded border border-slate-300 px-3 py-2 text-ink hover:bg-slate-100" href="/login">Login</a>
      </nav>
    </div>
  </header>

  <main class="mx-auto max-w-7xl px-5 py-8">
    <slot />
  </main>
</div>
