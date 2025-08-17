// Main application class
class SwarmAutoscalerDashboard {
    constructor() {
        this.events = [];
        this.filteredEvents = [];
        this.chart = null;
        this.liveMode = false;
        this.liveInterval = null;
        this.currentPage = 1;
        this.itemsPerPage = 10;
        this.sortField = 'created_at';
        this.sortDirection = 'desc';
        this.timeRange = '1d';
        this.serviceFilter = '';
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupTheme();
        this.loadEvents();
        this.setupChart();
    }

    setupEventListeners() {
        // Live toggle
        document.getElementById('liveToggle').addEventListener('click', () => {
            this.toggleLiveMode();
        });

        // Dark mode toggle
        document.getElementById('darkModeToggle').addEventListener('click', () => {
            this.toggleDarkMode();
        });

        // Time range filter
        document.getElementById('timeRange').addEventListener('change', (e) => {
            this.timeRange = e.target.value;
            this.handleCustomDateRange();
            this.loadEvents();
        });

        // Custom date inputs
        document.getElementById('startDate').addEventListener('change', () => {
            this.loadEvents();
        });
        document.getElementById('endDate').addEventListener('change', () => {
            this.loadEvents();
        });

        // Service filter
        document.getElementById('serviceFilter').addEventListener('change', (e) => {
            this.serviceFilter = e.target.value;
            this.filterAndRender();
        });

        // Refresh button
        document.getElementById('refreshChart').addEventListener('click', () => {
            this.loadEvents();
        });

        // Pagination
        document.getElementById('prevPage').addEventListener('click', () => {
            this.changePage(-1);
        });
        document.getElementById('nextPage').addEventListener('click', () => {
            this.changePage(1);
        });

        // Table sorting
        document.querySelectorAll('.sortable').forEach(th => {
            th.addEventListener('click', () => {
                this.handleSort(th.dataset.sort);
            });
        });
    }

    setupTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        this.updateThemeIcon(savedTheme);
    }

    toggleDarkMode() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        this.updateThemeIcon(newTheme);
        
        // Update chart colors if chart exists
        if (this.chart) {
            this.updateChartTheme();
        }
    }

    updateThemeIcon(theme) {
        const icon = document.querySelector('#darkModeToggle .btn-icon');
        icon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }

    handleCustomDateRange() {
        const customRange = document.getElementById('customDateRange');
        if (this.timeRange === 'custom') {
            customRange.style.display = 'flex';
            // Set default dates
            const now = new Date();
            const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
            
            document.getElementById('endDate').value = now.toISOString().slice(0, 16);
            document.getElementById('startDate').value = yesterday.toISOString().slice(0, 16);
        } else {
            customRange.style.display = 'none';
        }
    }

    async loadEvents() {
        try {
            const params = new URLSearchParams();
            
            if (this.timeRange === 'custom') {
                const startDate = document.getElementById('startDate').value;
                const endDate = document.getElementById('endDate').value;
                if (startDate && endDate) {
                    params.append('start', startDate);
                    params.append('end', endDate);
                }
            } else {
                params.append('range', this.timeRange);
            }

            // Add service filter if selected
            if (this.serviceFilter) {
                params.append('service', this.serviceFilter);
            }

            const response = await fetch(`/api/events?${params.toString()}`);
            if (!response.ok) throw new Error('Failed to fetch events');
            
            this.events = await response.json();
            this.filterAndRender();
            this.updateServiceFilter();
        } catch (error) {
            console.error('Error loading events:', error);
            this.showError('Failed to load events');
        }
    }

    updateServiceFilter() {
        const services = [...new Set(this.events.map(e => e.service_name))];
        const select = document.getElementById('serviceFilter');
        
        // Keep current selection if it still exists
        const currentValue = select.value;
        
        // Clear existing options except "All services"
        select.innerHTML = '<option value="">All services</option>';
        
        // Add service options
        services.forEach(service => {
            const option = document.createElement('option');
            option.value = service;
            option.textContent = service;
            select.appendChild(option);
        });
        
        // Restore selection if it still exists
        if (services.includes(currentValue)) {
            select.value = currentValue;
            this.serviceFilter = currentValue;
        }
    }

    filterAndRender() {
        this.filteredEvents = this.events.filter(event => {
            if (this.serviceFilter && event.service_name !== this.serviceFilter) {
                return false;
            }
            return true;
        });

        this.sortEvents();
        this.renderTable();
        this.updateChart();
        this.updatePagination();
    }

    sortEvents() {
        this.filteredEvents.sort((a, b) => {
            let aVal = a[this.sortField];
            let bVal = b[this.sortField];
            
            // Handle date sorting
            if (this.sortField === 'created_at') {
                aVal = new Date(aVal);
                bVal = new Date(bVal);
            }
            
            // Handle numeric sorting
            if (['id', 'from_replicas', 'to_replicas'].includes(this.sortField)) {
                aVal = parseInt(aVal);
                bVal = parseInt(bVal);
            }
            
            if (this.sortDirection === 'asc') {
                return aVal > bVal ? 1 : -1;
            } else {
                return aVal < bVal ? 1 : -1;
            }
        });
    }

    handleSort(field) {
        if (this.sortField === field) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortField = field;
            this.sortDirection = 'desc';
        }
        
        // Update sort indicators
        document.querySelectorAll('.sortable').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
        });
        
        const currentTh = document.querySelector(`[data-sort="${field}"]`);
        currentTh.classList.add(`sort-${this.sortDirection}`);
        
        this.filterAndRender();
    }

    renderTable() {
        const tbody = document.getElementById('eventsTableBody');
        const startIndex = (this.currentPage - 1) * this.itemsPerPage;
        const endIndex = startIndex + this.itemsPerPage;
        const pageEvents = this.filteredEvents.slice(startIndex, endIndex);

        if (pageEvents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading">No events found</td></tr>';
            return;
        }

        tbody.innerHTML = pageEvents.map(event => `
            <tr>
                <td class="text-muted">${event.id}</td>
                <td>${event.service_name}</td>
                <td>${event.from_replicas}</td>
                <td>${event.to_replicas}</td>
                <td>${this.formatReason(event.reason)}</td>
                <td class="text-muted">${this.formatDate(event.created_at)}</td>
            </tr>
        `).join('');
    }

    formatReason(reason) {
        if (reason.includes('>')) {
            return `<span class="badge badge-success">${reason}</span>`;
        } else if (reason.includes('<')) {
            return `<span class="badge badge-warning">${reason}</span>`;
        }
        return reason;
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString();
    }

    updatePagination() {
        const totalPages = Math.ceil(this.filteredEvents.length / this.itemsPerPage);
        const startItem = (this.currentPage - 1) * this.itemsPerPage + 1;
        const endItem = Math.min(this.currentPage * this.itemsPerPage, this.filteredEvents.length);
        
        document.getElementById('paginationInfo').textContent = 
            `Showing ${startItem}-${endItem} of ${this.filteredEvents.length} events`;
        
        document.getElementById('prevPage').disabled = this.currentPage <= 1;
        document.getElementById('nextPage').disabled = this.currentPage >= totalPages;
    }

    changePage(delta) {
        const newPage = this.currentPage + delta;
        const totalPages = Math.ceil(this.filteredEvents.length / this.itemsPerPage);
        
        if (newPage >= 1 && newPage <= totalPages) {
            this.currentPage = newPage;
            this.renderTable();
            this.updatePagination();
        }
    }

    setupChart() {
        const ctx = document.getElementById('scalingChart').getContext('2d');
        
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                return new Date(context[0].parsed.x).toLocaleString();
                            },
                            label: function(context) {
                                return `${context.dataset.label}: ${context.parsed.y} replicas`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute'
                        },
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Replicas'
                        }
                    }
                }
            }
        });
    }

    updateChart() {
        if (!this.chart) return;

        // Group events by service
        const serviceGroups = {};
        this.filteredEvents.forEach(event => {
            if (!serviceGroups[event.service_name]) {
                serviceGroups[event.service_name] = [];
            }
            serviceGroups[event.service_name].push(event);
        });

        // Create datasets for each service
        const datasets = Object.entries(serviceGroups).map(([serviceName, events], index) => {
            const colors = [
                '#774aa4', '#28a745', '#ffc107', '#dc3545', '#17a2b8',
                '#6f42c1', '#fd7e14', '#20c997', '#e83e8c', '#6c757d'
            ];
            
            // Create timeline data points
            const dataPoints = [];
            let currentReplicas = events[0]?.from_replicas || 1;
            
            events.forEach(event => {
                // Add point before scaling
                dataPoints.push({
                    x: new Date(event.created_at),
                    y: event.from_replicas
                });
                
                // Add point after scaling
                dataPoints.push({
                    x: new Date(event.created_at),
                    y: event.to_replicas
                });
                
                currentReplicas = event.to_replicas;
            });

            return {
                label: serviceName,
                data: dataPoints,
                borderColor: colors[index % colors.length],
                backgroundColor: colors[index % colors.length] + '20',
                borderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                tension: 0.1
            };
        });

        this.chart.data.datasets = datasets;
        this.chart.update();
    }

    updateChartTheme() {
        if (!this.chart) return;
        
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        const textColor = isDark ? '#ffffff' : '#1a1a1a';
        const gridColor = isDark ? '#404040' : '#e1e5e9';
        
        this.chart.options.plugins.legend.labels.color = textColor;
        this.chart.options.scales.x.grid.color = gridColor;
        this.chart.options.scales.y.grid.color = gridColor;
        this.chart.options.scales.x.ticks.color = textColor;
        this.chart.options.scales.y.ticks.color = textColor;
        this.chart.options.scales.x.title.color = textColor;
        this.chart.options.scales.y.title.color = textColor;
        
        this.chart.update();
    }

    toggleLiveMode() {
        this.liveMode = !this.liveMode;
        const button = document.getElementById('liveToggle');
        
        if (this.liveMode) {
            button.classList.add('live-active');
            button.querySelector('.btn-text').textContent = 'Live Events';
            this.startLiveUpdates();
        } else {
            button.classList.remove('live-active');
            button.querySelector('.btn-text').textContent = 'Live Events';
            this.stopLiveUpdates();
        }
    }

    startLiveUpdates() {
        this.liveInterval = setInterval(() => {
            this.loadEvents();
        }, 5000); // Update every 5 seconds
    }

    stopLiveUpdates() {
        if (this.liveInterval) {
            clearInterval(this.liveInterval);
            this.liveInterval = null;
        }
    }

    showError(message) {
        // Simple error display - could be enhanced with a toast notification
        console.error(message);
        const tbody = document.getElementById('eventsTableBody');
        tbody.innerHTML = `<tr><td colspan="6" class="loading" style="color: var(--error);">${message}</td></tr>`;
    }
}

// Initialize the dashboard when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new SwarmAutoscalerDashboard();
});
