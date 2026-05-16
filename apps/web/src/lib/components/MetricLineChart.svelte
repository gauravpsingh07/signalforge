<script lang="ts">
  import { onMount } from 'svelte';

  let {
    title,
    labels,
    values,
    color = '#0f766e'
  }: {
    title: string;
    labels: string[];
    values: number[];
    color?: string;
  } = $props();

  let canvas = $state<HTMLCanvasElement>();
  let chart: any;
  let ChartModule: any;
  const hasData = $derived(labels.length > 0 && values.length > 0);

  function updateChart() {
    if (!chart) return;
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.update();
  }

  onMount(() => {
    async function createChart() {
      if (!hasData) return;
      ChartModule = await import('chart.js');
      ChartModule.Chart.register(...ChartModule.registerables);
      if (!canvas) return;
      chart = new ChartModule.Chart(canvas, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: title,
              data: values,
              borderColor: color,
              backgroundColor: `${color}22`,
              tension: 0.25,
              fill: true,
              pointRadius: 2
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false }
          },
          scales: {
            x: { ticks: { maxTicksLimit: 5 } },
            y: { beginAtZero: true }
          }
        }
      });
    }

    createChart();
    return () => chart?.destroy();
  });

  $effect(() => {
    labels;
    values;
    updateChart();
  });
</script>

<div class="surface rounded-lg p-5">
  <h2 class="text-lg font-semibold">{title}</h2>
  {#if hasData}
    <div class="mt-4 h-56">
      <canvas bind:this={canvas} aria-label={title}></canvas>
    </div>
  {:else}
    <div class="mt-4 flex h-56 items-center justify-center rounded border border-dashed border-slate-300 bg-white text-sm text-slate-500">
      No chart data yet. Send demo events and run the worker to populate this view.
    </div>
  {/if}
</div>
