// 评分分布直方图：数据由 <script type="application/json"> 注入，
// Chart.js 由本地 static/vendor 提供（CSP script-src 'self' 兼容）
(function () {
    const dataEl = document.getElementById("rating-histogram-data");
    const canvas = document.getElementById("rating-histogram");
    if (!dataEl || !canvas || typeof Chart === "undefined") return;
    const rows = JSON.parse(dataEl.textContent);
    if (!rows.length) return;
    new Chart(canvas, {
        type: "bar",
        data: {
            labels: rows.map((row) => row.bucket),
            datasets: [{
                label: "电影数量",
                data: rows.map((row) => row.count),
                backgroundColor: "rgba(229, 169, 0, .75)",
                borderColor: "#8a6600",
                borderWidth: 1,
                borderRadius: 6,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (c) => c.parsed.y + " 部",
                    },
                },
            },
            scales: {
                y: { beginAtZero: true, ticks: { precision: 0 } },
                x: { grid: { display: false } },
            },
        },
    });
})();
