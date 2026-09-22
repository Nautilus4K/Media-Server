const getCssVar = (varName) => {
    return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
};

const MAX_SECONDS = 1800; // 30 minutes
const SECONDS_INBETWEEN = 10; // 10 seconds apart between updates

const time_lables = [];
for (let i = -MAX_SECONDS; i <= -SECONDS_INBETWEEN; i += SECONDS_INBETWEEN) {
    time_lables.push(String(i));
}

Chart.defaults.font.family = "'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace";

// -----------------------------------------------------------------------
// Synced crosshair + tooltip, mirroring CanvasJS's "Synchronized Charts":
// hovering any one of the time-series charts draws a shared vertical
// crosshair and raises the tooltip at the same index on all of them.
// -----------------------------------------------------------------------
const syncGroup = [];
let syncedIndex = null;

const syncedCrosshairPlugin = {
    id: "syncedCrosshair",
    afterDatasetsDraw(chart) {
        if (syncedIndex === null) return;
        const { ctx, chartArea, scales } = chart;
        const xScale = scales.x;
        if (!xScale) return;
        const xPos = xScale.getPixelForValue(syncedIndex);
        if (xPos === undefined || xPos === null || Number.isNaN(xPos)) return;

        ctx.save();
        ctx.beginPath();
        ctx.moveTo(xPos, chartArea.top);
        ctx.lineTo(xPos, chartArea.bottom);
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = getCssVar("--crosshair-color");
        ctx.stroke();
        ctx.restore();
    }
};
Chart.register(syncedCrosshairPlugin);

function registerSync(chart) {
    syncGroup.push(chart);
    chart.canvas.addEventListener("mousemove", (evt) => onSyncMove(chart, evt));
    chart.canvas.addEventListener("mouseleave", onSyncLeave);
}

// A fast mouse can fire many mousemove events per animation frame. Without
// throttling, every one of them calls setActiveElements() and restarts the
// tooltip's own position animation (see makeTooltip() below) before it has
// a chance to finish, which is what made it look stuck mid-ease. Capping
// this to one update per animation frame matches the rate Chart.js's own
// (non-synced) hover handling already runs at.
let syncRafId = null;
let pendingSync = null;

function onSyncMove(sourceChart, evt) {
    pendingSync = { sourceChart, evt };
    if (syncRafId !== null) return;
    syncRafId = requestAnimationFrame(() => {
        syncRafId = null;
        applySyncMove(pendingSync.sourceChart, pendingSync.evt);
    });
}

function applySyncMove(sourceChart, evt) {
    const points = sourceChart.getElementsAtEventForMode(evt, "index", { intersect: false }, false);
    if (!points.length) return;
    syncedIndex = points[0].index;

    syncGroup.forEach((chart) => {
        if (chart === sourceChart) {
            chart.update("none");
            return;
        }
        const active = chart.data.datasets.map((_, datasetIndex) => ({ datasetIndex, index: syncedIndex }));
        chart.tooltip.setActiveElements(active, { x: evt.offsetX, y: evt.offsetY });
        chart.update("none");
    });
}

function onSyncLeave() {
    if (syncRafId !== null) {
        cancelAnimationFrame(syncRafId);
        syncRafId = null;
    }
    syncedIndex = null;
    syncGroup.forEach((chart) => {
        chart.tooltip.setActiveElements([], { x: 0, y: 0 });
        chart.update("none");
    });
}

// -----------------------------------------------------------------------
// Shared chart-option builders (CanvasJS "light2"-style layout: titled
// panels, square legend markers, smooth spline-area series)
// -----------------------------------------------------------------------
function makeDataset(label, colorVar) {
    const color = getCssVar(colorVar);
    return {
        label,
        data: [],
        fill: true,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 0,                // Hides points by default
        pointHoverRadius: 6,     // Shows point with size 6px when hovered
        pointHitRadius: 10,
        backgroundColor: color + "33",
        borderColor: color
    };
}

function baseScales(yFormatter, { max } = {}) {
    const yScale = {
        min: 0,
        ticks: {
            color: getCssVar("--text-color"),
            callback: yFormatter
        },
        grid: { color: "#77777733" }
    };
    if (max !== undefined) yScale.max = max;

    return {
        y: yScale,
        x: {
            ticks: { color: getCssVar("--text-color") },
            grid: { color: "#77777733" }
        }
    };
}

function baseTitle(text) {
    return {
        display: true,
        text,
        color: getCssVar("--text-color"),
        font: { size: 15, weight: "600" }
    };
}

function baseLegend() {
    return {
        labels: {
            color: getCssVar("--text-color"),
            usePointStyle: true,
            pointStyle: "rect"
        }
    };
}

function makeTooltip(accentVar, suffix) {
    return {
        enabled: true,
        backgroundColor: getCssVar("--background"),
        titleColor: getCssVar("--text-color"),
        bodyColor: getCssVar("--text-color"),
        borderColor: getCssVar(accentVar),
        borderWidth: 1,
        cornerRadius: 0,
        // The tooltip's own position/opacity animation - independent of the
        // "none" mode passed to chart.update(), and the thing that felt laggy
        // under fast mouse movement before the rAF throttle above. Tune it
        // here (per chart, since each chart gets its own makeTooltip() call),
        // or copy this block into baseInteraction-adjacent code to share one
        // setting across all charts. "easeOutQuart" + 400ms is Chart.js's own
        // built-in default, restored explicitly rather than left implicit.
        // Full easing list: https://www.chartjs.org/docs/latest/configuration/animations.html#easing
        animation: {
            duration: 400,
            easing: "easeOutQuart"
        },
        callbacks: {
            // Change the title line at the top of the tooltip
            title(tooltipItems) {
                return `${Math.abs(tooltipItems[0].label)} seconds ago`;
            },
            // Custom label formatting for each data item
            label(context) {
                let label = context.dataset.label || "";
                if (label) label += ": ";
                if (context.parsed.y !== null) label += `${context.parsed.y}${suffix}`;
                return label;
            }
        }
    };
}

const baseInteraction = {
    // Controls general chart interactions (tooltips)
    interaction: { mode: "index", intersect: false },
    // Explicitly forces element hover (points) to trigger anywhere along the X column
    hover: { mode: "index", intersect: false }
};

// -----------------------------------------------------------------------
// CPU — total / user / system, in blues
// -----------------------------------------------------------------------
const cpu_chart = new Chart(document.getElementById("cpu_chart"), {
    type: "line",
    data: {
        labels: time_lables,
        datasets: [
            makeDataset("Total", "--cpu-total-color"),
            makeDataset("User", "--cpu-user-color"),
            makeDataset("System", "--cpu-system-color")
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        ...baseInteraction,
        scales: baseScales((value) => value + "%", { max: 100 }),
        plugins: {
            title: baseTitle("CPU Utilization"),
            legend: baseLegend(),
            tooltip: makeTooltip("--cpu-total-color", "%")
        }
    }
});

// -----------------------------------------------------------------------
// Memory — used / buffers / cached / free, in reds
// -----------------------------------------------------------------------
const ram_chart = new Chart(document.getElementById("ram_chart"), {
    type: "line",
    data: {
        labels: time_lables,
        datasets: [
            makeDataset("Used", "--ram-used-color"),
            makeDataset("Buffers", "--ram-buffers-color"),
            makeDataset("Cached", "--ram-cached-color"),
            makeDataset("Free", "--ram-free-color")
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        ...baseInteraction,
        scales: baseScales((value) => value + " GiB"),
        plugins: {
            title: baseTitle("Memory Usage"),
            legend: baseLegend(),
            tooltip: makeTooltip("--ram-used-color", " GiB")
        }
    }
});

// -----------------------------------------------------------------------
// Network — down / up, in greens (unchanged metrics, restyled)
// -----------------------------------------------------------------------
const net_chart = new Chart(document.getElementById("net_chart"), {
    type: "line",
    data: {
        labels: time_lables,
        datasets: [
            makeDataset("Network Down", "--net-down-color"),
            makeDataset("Network Up", "--net-up-color")
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        ...baseInteraction,
        scales: baseScales((value) => value + " Mbps"),
        plugins: {
            title: baseTitle("Network Traffic"),
            legend: baseLegend(),
            tooltip: makeTooltip("--net-down-color", " Mbps")
        }
    }
});

// -----------------------------------------------------------------------
// Disk I/O — write / read throughput, in oranges
// -----------------------------------------------------------------------
const diskio_chart = new Chart(document.getElementById("diskio_chart"), {
    type: "line",
    data: {
        labels: time_lables,
        datasets: [
            makeDataset("Write", "--disk-write-color"),
            makeDataset("Read", "--disk-read-color")
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        ...baseInteraction,
        scales: baseScales((value) => value + " MB/s"),
        plugins: {
            title: baseTitle("Disk I/O"),
            legend: baseLegend(),
            tooltip: makeTooltip("--disk-write-color", " MB/s")
        }
    }
});

// -----------------------------------------------------------------------
// Disk space — used / free, pie (no time axis, so it sits outside the sync
// group; restyled to the same orange family as disk I/O)
// -----------------------------------------------------------------------
const disk_chart = new Chart(document.getElementById("disk_chart"), {
    type: "pie",
    data: {
        labels: ["Used", "Free"],
        datasets: [{
            label: "Disk Space",
            data: [0.0, 0.0],
            backgroundColor: [getCssVar("--disk-used-color") + "aa", getCssVar("--disk-free-color") + "aa"],
            borderColor: [getCssVar("--disk-used-color"), getCssVar("--disk-free-color")],
            hoverOffset: 4
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            title: baseTitle("Disk Space"),
            legend: baseLegend(),
            tooltip: {
                enabled: true,
                backgroundColor: getCssVar("--background"),
                titleColor: getCssVar("--text-color"),
                bodyColor: getCssVar("--text-color"),
                borderColor: getCssVar("--disk-used-color"),
                borderWidth: 1,
                cornerRadius: 0,
                callbacks: {
                    label(context) {
                        let label = context.label || "";
                        if (label) label += ": ";
                        label += context.formattedValue + " GB";
                        return label;
                    }
                }
            }
        }
    }
});

// Only the four rolling time-series charts share the crosshair/tooltip sync
registerSync(cpu_chart);
registerSync(ram_chart);
registerSync(net_chart);
registerSync(diskio_chart);

// -----------------------------------------------------------------------
// Polling
// -----------------------------------------------------------------------
const URL = "/get-status";
const FIXED_INTERVAL = SECONDS_INBETWEEN * 1000; // Strictly target every SECONDS_INBETWEEN seconds
var boottime = 0;

function padTo(arr, length) {
    const out = (arr || []).slice(-length);
    while (out.length < length) out.unshift(0);
    return out;
}

const round2 = (n) => Math.round(n * 100) / 100;

async function pollData() {
    const startTime = Date.now(); // 1. Record when the request started

    try {
        const response = await fetch(URL);
        const data = await response.json();

        const len = time_lables.length;

        // CPU
        cpu_chart.data.datasets[0].data = padTo(data["cpu_total"], len);
        cpu_chart.data.datasets[1].data = padTo(data["cpu_user"], len);
        cpu_chart.data.datasets[2].data = padTo(data["cpu_system"], len);
        cpu_chart.update();

        // Memory
        ram_chart.options.scales.y.max = Math.round(data["total_ram"] * 10) / 10;
        ram_chart.data.datasets[0].data = padTo(data["ram_used"], len).map(round2);
        ram_chart.data.datasets[1].data = padTo(data["ram_buffers"], len).map(round2);
        ram_chart.data.datasets[2].data = padTo(data["ram_cached"], len).map(round2);
        ram_chart.data.datasets[3].data = padTo(data["ram_free"], len).map(round2);
        ram_chart.update();

        // Network
        net_chart.data.datasets[0].data = padTo(data["net_down"], len);
        net_chart.data.datasets[1].data = padTo(data["net_up"], len);
        net_chart.update();

        // Disk I/O
        diskio_chart.data.datasets[0].data = padTo(data["disk_write"], len).map(round2);
        diskio_chart.data.datasets[1].data = padTo(data["disk_read"], len).map(round2);
        diskio_chart.update();

        // Disk space
        const disk_used = data["disk"];
        const disk_free = data["disk_total"] - data["disk"];
        disk_chart.data.datasets[0].data[0] = disk_used;
        disk_chart.data.datasets[0].data[1] = disk_free;
        disk_chart.update();

        boottime = data["boot"];
    } catch (error) {
        console.error("Fetch error:", error);
    } finally {
        // 2. Calculate how long the execution took
        const duration = Date.now() - startTime;

        // 3. Subtract duration from your fixed interval target
        const nextDelay = Math.max(0, FIXED_INTERVAL - duration);

        setTimeout(pollData, nextDelay);
    }
}

var prev = getCookie("mode");
async function checkVisualMode() {
    if (getCookie("mode") != prev) window.location = window.location;
    setTimeout(checkVisualMode, 200);
}

function formatSeconds(totalSeconds) {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    const hh = String(hours).padStart(2, "0");
    const mm = String(minutes).padStart(2, "0");
    const ss = String(seconds).padStart(2, "0");

    return `${hh}:${mm}:${ss}`;
}

async function updateUptime() {
    document.getElementById("uptime").textContent = formatSeconds(Math.floor(Date.now() / 1000) - boottime);
    setTimeout(updateUptime, 1000);
}

// Start
setTimeout(pollData, 300);
setTimeout(checkVisualMode, 200);
setTimeout(updateUptime, 1000);