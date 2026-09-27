(() => {
  const root = document.documentElement;
  const themeButton = document.getElementById('theme-toggle');
  const savedTheme = localStorage.getItem('ledgerly-theme');
  if (savedTheme === 'dark') root.dataset.theme = 'dark';

  function refreshIcons() {
    if (window.lucide) window.lucide.createIcons();
  }

  function setThemeIcon() {
    const icon = themeButton?.querySelector('[data-lucide]');
    if (icon) icon.setAttribute('data-lucide', root.dataset.theme === 'dark' ? 'sun' : 'moon');
    refreshIcons();
  }

  themeButton?.addEventListener('click', () => {
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('ledgerly-theme', root.dataset.theme);
    setThemeIcon();
  });

  const periodFilter = document.getElementById('period-filter');
  const customRange = document.querySelector('.custom-range');
  if (periodFilter) {
    periodFilter.value = periodFilter.dataset.selectedPeriod || 'month';
    const updateRangeVisibility = () => {
      if (customRange) customRange.hidden = periodFilter.value !== 'custom';
    };
    periodFilter.addEventListener('change', updateRangeVisibility);
    updateRangeVisibility();
  }

  document.querySelectorAll('[data-selected-value]').forEach((select) => {
    select.value = select.dataset.selectedValue;
  });

  const typeField = document.querySelector('[data-category-type]');
  const categoryField = document.querySelector('[data-category-select]');
  if (typeField && categoryField) {
    const incomeCategories = new Set(['Salary', 'Freelance', 'Scholarship', 'Allowance', 'Other']);
    const updateCategories = () => {
      const isIncome = typeField.value === 'income';
      for (const option of categoryField.options) {
        if (!option.value) continue;
        const allowed = isIncome ? incomeCategories.has(option.value) : !incomeCategories.has(option.value) || option.value === 'Other';
        option.hidden = !allowed;
      }
      const selected = categoryField.selectedOptions[0];
      if (selected?.hidden) categoryField.value = '';
    };
    typeField.addEventListener('change', updateCategories);
    updateCategories();
  }

  const chartDataNode = document.getElementById('dashboard-chart-data');
  const chartData = chartDataNode ? JSON.parse(chartDataNode.textContent) : null;
  const colors = ['#30775a', '#e29b70', '#d6bb68', '#7fa3a0', '#b185a2', '#96b45e', '#d47b6e', '#6986ad', '#b58d60', '#83a5c3'];
  const rupees = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });

  if (window.Chart && chartData) {
    Chart.defaults.font.family = "'DM Sans', sans-serif";
    Chart.defaults.color = getComputedStyle(root).getPropertyValue('--muted').trim();
    Chart.defaults.borderColor = getComputedStyle(root).getPropertyValue('--line').trim();

    const cashflow = document.getElementById('cashflow-chart');
    if (cashflow) new Chart(cashflow, {
      type: 'bar',
      data: { labels: chartData.monthly_labels, datasets: [
        { label: 'Income', data: chartData.monthly_income, backgroundColor: '#7cbd91', borderRadius: 4, maxBarThickness: 25 },
        { label: 'Expenses', data: chartData.monthly_expenses, backgroundColor: '#e19a72', borderRadius: 4, maxBarThickness: 25 },
      ] },
      options: chartOptions(true),
    });

    const category = document.getElementById('category-chart');
    if (category) new Chart(category, {
      type: 'doughnut',
      data: { labels: chartData.category_labels, datasets: [{ data: chartData.category_amounts, backgroundColor: colors, borderColor: getComputedStyle(root).getPropertyValue('--panel').trim(), borderWidth: 3, hoverOffset: 5 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: '69%', plugins: { legend: { display: false }, tooltip: { callbacks: { label: (item) => `${item.label}: ${rupees.format(item.raw)}` } } } },
    });

    const spending = document.getElementById('spending-chart');
    if (spending) new Chart(spending, {
      type: 'line',
      data: { labels: chartData.monthly_labels, datasets: [{ label: 'Expenses', data: chartData.monthly_expenses, borderColor: '#dc8667', backgroundColor: 'rgba(220,134,103,.12)', pointBackgroundColor: '#dc8667', pointRadius: 3, fill: true, tension: .35 }] },
      options: chartOptions(false),
    });

    const savings = document.getElementById('savings-chart');
    if (savings) new Chart(savings, {
      type: 'line',
      data: { labels: chartData.monthly_labels, datasets: [{ label: 'Savings', data: chartData.monthly_savings, borderColor: '#428d69', backgroundColor: 'rgba(66,141,105,.12)', pointBackgroundColor: '#428d69', pointRadius: 3, fill: true, tension: .35 }] },
      options: chartOptions(false),
    });
  }

  function chartOptions(showLegend) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: showLegend, position: 'top', align: 'end', labels: { usePointStyle: true, pointStyle: 'circle', boxWidth: 7, boxHeight: 7, padding: 14, font: { size: 9 } } },
        tooltip: { callbacks: { label: (item) => `${item.dataset.label}: ${rupees.format(item.raw)}` } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, font: { size: 9 } } },
        y: { beginAtZero: true, grid: { color: getComputedStyle(root).getPropertyValue('--line').trim() }, ticks: { font: { size: 9 }, callback: (value) => rupees.format(value) } },
      },
    };
  }

  refreshIcons();
  setThemeIcon();
})();