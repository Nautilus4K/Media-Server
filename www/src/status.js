// import Chart from 'chart.js/auto';
// import { getRelativePosition } from 'chart.js/helpers';
const getCssVar = (varName) => {
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
};

const MAX_SECONDS = 1800 // 30 minutes
const SECONDS_INBETWEEN = 10 // 10 seconds apart between updates

const cpu_ctx = document.getElementById("cpu_chart")
const ram_ctx = document.getElementById("ram_chart")
const net_ctx = document.getElementById("net_chart")
const disk_ctx = document.getElementById("disk_chart")

time_lables = []
for (let i = -MAX_SECONDS; i <= -SECONDS_INBETWEEN; i += SECONDS_INBETWEEN) {
    time_lables.push(String(i))
}

Chart.defaults.font.family = "'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace"
const cpu_chart = new Chart(cpu_ctx, {
    type: 'line',
    data: {
        labels: time_lables,
        datasets: [{
            label: "CPU Usage",
            data: [],
            fill: true,
            backgroundColor: getCssVar("--cpu-color") + "55",
            borderColor: getCssVar("--cpu-color"),

            pointRadius: 0,        // Hides points by default
            pointHoverRadius: 6,   // Shows point with size 6px when hovered
            pointHitRadius: 10
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                min: 0,
                max: 100,
                ticks: {
                    callback: function(value, index, ticks) {
                        return value + '%'
                    },
                    color: getCssVar("--text-color")
                },
                grid: {
                    color: '#77777733'
                }
            },
            x: {
                ticks: {
                    color: getCssVar("--text-color")
                },
                grid: {
                    color: '#77777733'
                }
            }
        },

        // 1. Controls general chart interactions (tooltips)
        interaction: {
            mode: 'index',
            intersect: false,
        },

        // 2. Explicitly forces element hover (points) to trigger anywhere along the X column
        hover: {
            mode: 'index',
            intersect: false
        },

        plugins: {
            legend: {
                labels: {
                    color: getCssVar("--text-color")
                }  
            },
            tooltip: {
                enabled: true,
                // mode: 'index',
                // intersect: false,
                backgroundColor: getCssVar("--background"),
                titleColor: getCssVar('--text-color'),
                bodyColor: getCssVar('--text-color'),
                borderColor: getCssVar('--cpu-color'),
                borderWidth: 1,
                cornerRadius: 0,
                callbacks: {
                    // Change the title line at the top of the tooltip
                    title: function(tooltipItems) {
                        const item = tooltipItems[0];
                        return `${Math.abs(item.label)} seconds ago`;
                    },

                    // Custom label formatting for each data item
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) {
                            label += ': ';
                        }
                        if (context.parsed.y !== null) {
                            label += `${context.parsed.y}%`; // Add percent sign
                        }
                        return label;
                    },
                }
            }
        }
    }
})


const ram_chart = new Chart(ram_ctx, {
    type: 'line',
    data: {
        labels: time_lables,
        datasets: [{
            label: "RAM Usage",
            data: [],
            fill: true,
            backgroundColor: getCssVar("--ram-color") + "55",
            borderColor: getCssVar("--ram-color"),

            pointRadius: 0,        // Hides points by default
            pointHoverRadius: 6,   // Shows point with size 6px when hovered
            pointHitRadius: 10
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                min: 0,
                max: 0,
                ticks: {
                    callback: function(value, index, ticks) {
                        return value + ' GiB'
                    },
                    // precision: 2
                    color: getCssVar("--text-color")
                },
                grid: {
                    color: '#77777733'
                }
            },
            x: {
                ticks: {
                    color: getCssVar("--text-color")
                },
                grid: {
                    color: '#77777733'
                }
            }
        },

        // 1. Controls general chart interactions (tooltips)
        interaction: {
            mode: 'index',
            intersect: false,
        },

        // 2. Explicitly forces element hover (points) to trigger anywhere along the X column
        hover: {
            mode: 'index',
            intersect: false
        },

        plugins: {
            legend: {
                labels: {
                    color: getCssVar("--text-color")
                }  
            },
            tooltip: {
                enabled: true,
                // mode: 'index',
                // intersect: false,
                backgroundColor: getCssVar("--background"),
                titleColor: getCssVar('--text-color'),
                bodyColor: getCssVar('--text-color'),
                borderColor: getCssVar('--ram-color'),
                borderWidth: 1,
                cornerRadius: 0,
                callbacks: {
                    // Change the title line at the top of the tooltip
                    title: function(tooltipItems) {
                        const item = tooltipItems[0];
                        return `${Math.abs(item.label)} seconds ago`;
                    },

                    // Custom label formatting for each data item
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) {
                            label += ': ';
                        }
                        if (context.parsed.y !== null) {
                            label += `${context.parsed.y} GiB`; // Add percent sign
                        }
                        return label;
                    },
                }
            }
        }
    }
})

const net_chart = new Chart(net_ctx, {
    type: 'line',
    data: {
        labels: time_lables,
        datasets: [{
            label: "Network Down",
            data: [],
            fill: true,
            backgroundColor: getCssVar("--net-down-color") + "55",
            borderColor: getCssVar("--net-down-color"),

            pointRadius: 0,        // Hides points by default
            pointHoverRadius: 6,   // Shows point with size 6px when hovered
            pointHitRadius: 10
        },{
            label: "Network Up",
            data: [],
            fill: true,
            backgroundColor: getCssVar("--net-up-color") + "55",
            borderColor: getCssVar("--net-up-color"),

            pointRadius: 0,        // Hides points by default
            pointHoverRadius: 6,   // Shows point with size 6px when hovered
            pointHitRadius: 10
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                min: 0,
                // max: 0,
                ticks: {
                    callback: function(value, index, ticks) {
                        return value + ' Mbps'
                    },
                    color: getCssVar("--text-color")
                    // precision: 2
                },
                grid: {
                    color: '#77777733'
                }
            },
            x: {
                ticks: {
                    color: getCssVar("--text-color")
                },
                grid: {
                    color: '#77777733'
                }
            }
        },

        // 1. Controls general chart interactions (tooltips)
        interaction: {
            mode: 'index',
            intersect: false,
        },

        // 2. Explicitly forces element hover (points) to trigger anywhere along the X column
        hover: {
            mode: 'index',
            intersect: false
        },

        plugins: {
            legend: {
                labels: {
                    color: getCssVar("--text-color")
                }  
            },
            tooltip: {
                enabled: true,
                // mode: 'index',
                // intersect: false,
                backgroundColor: getCssVar("--background"),
                titleColor: getCssVar('--text-color'),
                bodyColor: getCssVar('--text-color'),
                borderColor: getCssVar('--net-neutral-color'),
                borderWidth: 1,
                cornerRadius: 0,
                callbacks: {
                    // Change the title line at the top of the tooltip
                    title: function(tooltipItems) {
                        const item = tooltipItems[0];
                        return `${Math.abs(item.label)} seconds ago`;
                    },

                    // Custom label formatting for each data item
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) {
                            label += ': ';
                        }
                        if (context.parsed.y !== null) {
                            label += `${context.parsed.y} Mbps`; // Add percent sign
                        }
                        return label;
                    },
                }
            }
        }
    }
})

const disk_chart = new Chart(disk_ctx, {
    type: 'pie',
    data: {
        labels: ['Used', 'Free'],
        datasets: [{
            label: "Disk Usage",
            data: [0.0, 0.0],
            fill: true,
            backgroundColor: [getCssVar("--disk-used-color") + "55", getCssVar("--disk-free-color") + "55"],
            borderColor: [getCssVar("--disk-used-color"), getCssVar("--disk-free-color")],

            hoverOffset: 4
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,

        // 1. Controls general chart interactions (tooltips)
        interaction: {
            mode: 'index',
            intersect: false,
        },

        // 2. Explicitly forces element hover (points) to trigger anywhere along the X column
        hover: {
            mode: 'index',
            intersect: false
        },

        plugins: {
            legend: {
                labels: {
                    color: getCssVar("--text-color")
                }
            },
            tooltip: {
                enabled: true,
                // mode: 'index',
                // intersect: false,
                backgroundColor: getCssVar("--background"),
                titleColor: getCssVar('--text-color'),
                bodyColor: getCssVar('--text-color'),
                borderColor: getCssVar('--net-neutral-color'),
                borderWidth: 1,
                cornerRadius: 0,
                callbacks: {
                    label: function(context) {
                        // context.label is the segment name (e.g., 'Red')
                        // context.formattedValue is the corresponding data value
                        let label = context.label || '';
                        if (label) {
                            label += ': ';
                        }
                        // Append your custom unit here (e.g., ' kg')
                        label += context.formattedValue + ' GB';
                        return label;
                    }
                }
            }
        }
    }
})

const URL = '/get-status';
const FIXED_INTERVAL = SECONDS_INBETWEEN * 1000; // Strictly target every SECONDS+INBETWEEN seconds
var boottime = 0;

async function pollData() {
    const startTime = Date.now(); // 1. Record when the request started

    try {
        const response = await fetch(URL);
        const data = await response.json();
        // console.log('Data fetched:', data);

        let cpu_points = data["cpu"].slice(-time_lables.length);
        while (cpu_points.length < 180) cpu_points.unshift(0)

        cpu_chart.data.datasets.forEach((dataset) => {
            // dataset.data = cpu_points;
            // if (dataset.data.length == (MAX_SECONDS / SECONDS_INBETWEEN)) dataset.data.push(cpu_points.at(-1))
            dataset.data = cpu_points
        });
        cpu_chart.update();

        let ram_points = data["ram"].slice(-time_lables.length);
        while (ram_points.length < 180) ram_points.unshift(0);
        ram_chart.options.scales.y.max = Math.round(data["total_ram"] * 10) / 10;
        ram_chart.data.datasets.forEach((dataset) => {
            // dataset.data = cpu_points;
            if (dataset.data.length == (MAX_SECONDS / SECONDS_INBETWEEN)) dataset.data.push(Math.round(ram_points.at(-1) * 100) / 100)
            else {
                for (let i = 0; i < ram_points.length; i++) {
                    ram_points[i] = Math.round(ram_points[i] * 100) / 100;
                }
                dataset.data = ram_points;
            }
        });
        ram_chart.update();

        let net_down_points = data["net_down"].slice(-time_lables.length);
        let net_up_points = data["net_up"].slice(-time_lables.length);
        while (net_down_points.length < 180) net_down_points.unshift(0);
        while (net_up_points.length < 180) net_up_points.unshift(0);
        net_chart.data.datasets[0].data = net_down_points;
        net_chart.data.datasets[1].data = net_up_points;
        net_chart.update();

        let disk_used = data["disk"]
        let disk_free = data["disk_total"] - data["disk"]
        disk_chart.data.datasets.forEach((dataset) => {
            dataset.data[0] = disk_used;
            dataset.data[1] = disk_free;
        });

        disk_chart.update();

        boottime = data["boot"]
    } catch (error) {
        console.error('Fetch error:', error);
    } finally {
        // 2. Calculate how long the execution took
        const duration = Date.now() - startTime; 
        
        // 3. Subtract duration from your fixed interval target
        // If the request took 1 second (1000ms), the next delay will be 4000ms.
        // If it lagged and took 6 seconds, it fires the next one instantly (0ms).
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

  // Pad single digits with a leading zero
  const hh = String(hours).padStart(2, '0');
  const mm = String(minutes).padStart(2, '0');
  const ss = String(seconds).padStart(2, '0');

  return `${hh}:${mm}:${ss}`;
}

async function updateUptime() {
    document.getElementById("uptime").textContent = formatSeconds(Math.floor(Date.now() / 1000) - boottime);
    setTimeout(updateUptime, 1000);z
}

// Start
setTimeout(pollData, 300);
setTimeout(checkVisualMode, 200);
setTimeout(updateUptime, 1000);