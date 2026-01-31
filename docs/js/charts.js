/**
 * Silver Metrics Tracker - Dashboard Charts & Data Loading
 */

// Configuration
const DATA_URL = 'data/latest.json';
const HISTORICAL_URL = 'data/historical.json';
const REFRESH_INTERVAL = 4000; // 4 seconds

// Chart instances storage
const charts = {};

// Color scheme
const COLORS = {
    green: '#22c55e',
    yellow: '#eab308',
    orange: '#f97316',
    red: '#ef4444',
    gray: '#6b7280',
    primary: '#3b82f6',
    silver: '#c0c0c0'
};

// Chart.js default configuration
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#334155';
Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';

/**
 * Initialize the dashboard
 */
async function initDashboard() {
    try {
        // Load current data
        const data = await fetchData(DATA_URL);
        if (data && data.metrics) {
            updateDashboard(data.metrics);
        }
        
        // Load historical data for charts
        const historical = await fetchData(HISTORICAL_URL);
        if (historical && historical.data) {
            updateCharts(historical.data);
        }
        
    } catch (error) {
        console.error('Error initializing dashboard:', error);
        showError('Failed to load dashboard data. Please try again later.');
    }
}

/**
 * Fetch JSON data from URL
 */
async function fetchData(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Error fetching ${url}:`, error);
        return null;
    }
}

/**
 * Update dashboard with latest metrics
 */
function updateDashboard(metrics) {
    // Update last updated time
    if (metrics.last_updated) {
        const date = new Date(metrics.last_updated);
        document.getElementById('last-updated').textContent = date.toLocaleString();
    }
    
    // Update composite score
    updateComposite(metrics.composite);
    
    // Update spot price
    updateSpotPrice(metrics.spot_price);
    
    // Update individual panels
    updatePanel('lease', metrics.lease_rate);
    updatePanel('premium', metrics.premium);
    updatePanel('inventory', metrics.inventory);
    updatePanel('margin', metrics.margin);
    updatePanel('shanghai', metrics.shanghai_premium);
}

/**
 * Update composite score banner
 */
function updateComposite(composite) {
    if (!composite) return;
    
    const banner = document.getElementById('composite-banner');
    const scoreEl = document.getElementById('composite-score');
    const statusEl = document.getElementById('composite-status');
    
    scoreEl.textContent = composite.score || 0;
    statusEl.textContent = composite.status_label || 'Unknown';
    
    // Update banner class for styling
    banner.className = 'composite-banner';
    if (composite.status_color) {
        banner.classList.add(`status-${composite.status_color}`);
    }
}

/**
 * Update spot price display
 */
function updateSpotPrice(spotData) {
    if (!spotData) return;
    
    const priceEl = document.getElementById('spot-price');
    const changeEl = document.getElementById('spot-change');
    
    if (spotData.value) {
        priceEl.textContent = `$${spotData.value.toFixed(2)}`;
    }
    
    if (spotData.change_24h !== null && spotData.change_24h !== undefined) {
        const change = spotData.change_24h;
        const sign = change >= 0 ? '+' : '';
        changeEl.textContent = `${sign}${change.toFixed(2)}%`;
        changeEl.className = 'spot-change ' + (change >= 0 ? 'positive' : 'negative');
    }
}

/**
 * Update a metric panel
 */
function updatePanel(name, data) {
    if (!data) return;
    
    const panel = document.getElementById(`panel-${name}`);
    const statusBadge = document.getElementById(`status-${name}`);
    const valueEl = document.getElementById(`value-${name}`);
    
    // Update panel status class
    panel.className = 'metric-panel';
    if (data.status_color) {
        panel.classList.add(`status-${data.status_color}`);
    }
    
    // Update status badge
    statusBadge.textContent = data.status_label || '--';
    statusBadge.className = 'status-badge';
    if (data.status_color) {
        statusBadge.classList.add(data.status_color);
    }
    
    // Update value
    if (name === 'margin') {
        // For margin, show days stable
        valueEl.textContent = data.days_since_change || '--';
        
        // Also show actual margin value
        const detailEl = document.getElementById('margin-detail');
        if (detailEl && data.value) {
            detailEl.textContent = `Initial margin: $${data.value.toLocaleString()}`;
        }
    } else if (name === 'shanghai') {
        // For Shanghai, show premium in USD with 2 decimals
        valueEl.textContent = data.value !== null ? data.value.toFixed(2) : '--';
    } else {
        valueEl.textContent = data.value !== null ? data.value.toFixed(1) : '--';
    }
    
    // Update inventory trend
    if (name === 'inventory' && data.trend) {
        const trendEl = document.getElementById('inventory-trend');
        if (trendEl) {
            const arrow = data.trend === 'recovering' ? '↑' : 
                         data.trend === 'declining' ? '↓' : '→';
            const change = data.trend_change_moz ? 
                `${data.trend_change_moz > 0 ? '+' : ''}${data.trend_change_moz}M oz` : '';
            trendEl.textContent = `${arrow} ${data.trend} ${change}`;
            trendEl.className = 'panel-trend';
            if (data.trend === 'recovering') trendEl.classList.add('up');
            if (data.trend === 'declining') trendEl.classList.add('down');
        }
    }
}

/**
 * Update all charts with historical data
 */
function updateCharts(historicalData) {
    if (!historicalData.snapshots || !historicalData.snapshots.charts) return;
    
    const chartData = historicalData.snapshots.charts;
    
    // Create individual charts
    if (chartData.shanghai_premium) {
        createMiniChart('chart-shanghai', chartData.shanghai_premium, COLORS.red);
    }
    createMiniChart('chart-lease', chartData.lease_rate, COLORS.primary);
    createMiniChart('chart-premium', chartData.premium_pct, COLORS.orange);
    createMiniChart('chart-inventory', chartData.inventory_total, COLORS.green);
    createMiniChart('chart-margin', chartData.margin_initial, COLORS.yellow);
}

/**
 * Create a mini sparkline chart
 */
function createMiniChart(canvasId, data, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !data || !data.labels || !data.datasets) return;
    
    // Destroy existing chart if present
    if (charts[canvasId]) {
        charts[canvasId].destroy();
    }
    
    const ctx = canvas.getContext('2d');
    
    // Create gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, 120);
    gradient.addColorStop(0, `${color}40`);
    gradient.addColorStop(1, `${color}05`);
    
    charts[canvasId] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.datasets[0].data,
                borderColor: color,
                backgroundColor: gradient,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#1e293b',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8',
                    borderColor: '#334155',
                    borderWidth: 1,
                    padding: 10,
                    displayColors: false
                }
            },
            scales: {
                x: {
                    display: false,
                    grid: { display: false }
                },
                y: {
                    display: false,
                    grid: { display: false }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

/**
 * Show error message
 */
function showError(message) {
    const container = document.querySelector('.container');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    container.insertBefore(errorDiv, container.firstChild.nextSibling);
}

/**
 * Format number with appropriate precision
 */
function formatNumber(value, decimals = 2) {
    if (value === null || value === undefined) return '--';
    return Number(value).toFixed(decimals);
}

/**
 * Format date for display
 */
function formatDate(dateString) {
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return dateString;
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', initDashboard);
