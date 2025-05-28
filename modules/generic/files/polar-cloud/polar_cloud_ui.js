/*!
 * Polar Cloud UI Plugin for Mainsail
 * Provides UI for configuring and managing Polar Cloud connection
 */

(function() {
    'use strict';

    // Plugin configuration
    const PLUGIN_NAME = 'polar_cloud';
    const API_BASE = '/server/polar_cloud';
    
    // State management
    let polarCloudState = {
        connected: false,
        registered: false,
        service_status: 'inactive',
        username: '',
        serial_number: '',
        machine_type: 'Cartesian',
        printer_type: 'Cartesian'
    };

    // UI Elements
    let settingsPanel = null;
    let statusDisplay = null;

    /**
     * Initialize the Polar Cloud plugin
     */
    function initPolarCloudPlugin() {
        console.log('Initializing Polar Cloud Plugin');
        
        // Add settings tab
        addSettingsTab();
        
        // Load initial status
        loadPolarCloudStatus();
        
        // Set up periodic status updates
        setInterval(loadPolarCloudStatus, 30000); // Update every 30 seconds
    }

    /**
     * Add the Polar Cloud settings tab to Mainsail
     */
    function addSettingsTab() {
        // Wait for Mainsail to be fully loaded
        if (typeof window.mainsail === 'undefined' || !window.mainsail.plugins) {
            setTimeout(addSettingsTab, 1000);
            return;
        }

        // Create the settings panel HTML
        const settingsHTML = createSettingsHTML();
        
        // Add to Mainsail settings
        const settingsContainer = document.querySelector('.settings-content') || 
                                 document.querySelector('[data-testid="settings-content"]') ||
                                 document.querySelector('#settings-content');
        
        if (settingsContainer) {
            // Create tab button
            const tabButton = createTabButton();
            const tabContainer = settingsContainer.querySelector('.settings-tabs') ||
                               settingsContainer.querySelector('.v-tabs');
            
            if (tabContainer) {
                tabContainer.appendChild(tabButton);
            }
            
            // Create tab content
            const contentContainer = settingsContainer.querySelector('.settings-content-area') ||
                                   settingsContainer.querySelector('.v-tab-content');
            
            if (contentContainer) {
                settingsPanel = document.createElement('div');
                settingsPanel.id = 'polar-cloud-settings';
                settingsPanel.className = 'settings-panel polar-cloud-panel';
                settingsPanel.style.display = 'none';
                settingsPanel.innerHTML = settingsHTML;
                contentContainer.appendChild(settingsPanel);
                
                // Bind event handlers
                bindEventHandlers();
            }
        } else {
            // Fallback: Add to body and show as modal
            console.warn('Could not find settings container, using fallback method');
            createFallbackUI();
        }
    }

    /**
     * Create the tab button for settings
     */
    function createTabButton() {
        const button = document.createElement('button');
        button.className = 'v-tab settings-tab polar-cloud-tab';
        button.setAttribute('data-tab', 'polar-cloud');
        button.innerHTML = `
            <i class="mdi mdi-cloud-outline"></i>
            <span>Polar Cloud Connection</span>
        `;
        
        button.addEventListener('click', function() {
            showPolarCloudSettings();
        });
        
        return button;
    }

    /**
     * Create the settings panel HTML
     */
    function createSettingsHTML() {
        return `
            <div class="polar-cloud-settings">
                <div class="settings-header">
                    <h2>
                        <i class="mdi mdi-cloud-outline"></i>
                        Polar Cloud Connection
                    </h2>
                    <p class="settings-description">
                        Connect your printer to the Polar Cloud service at printer4.polar3d.com
                    </p>
                </div>

                <div class="polar-cloud-status" id="polar-cloud-status">
                    <div class="status-card">
                        <div class="status-header">
                            <h3>Connection Status</h3>
                            <div class="status-indicator" id="status-indicator">
                                <span class="status-dot inactive"></span>
                                <span class="status-text">Not Connected</span>
                            </div>
                        </div>
                        <div class="status-details" id="status-details">
                            <div class="status-item">
                                <span class="label">Service Status:</span>
                                <span class="value" id="service-status">inactive</span>
                            </div>
                            <div class="status-item">
                                <span class="label">Serial Number:</span>
                                <span class="value" id="serial-number">Not registered</span>
                            </div>
                            <div class="status-item">
                                <span class="label">Username:</span>
                                <span class="value" id="username-display">Not set</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="polar-cloud-config">
                    <form id="polar-cloud-form" class="config-form">
                        <h3>Connection Settings</h3>
                        
                        <div class="form-group">
                            <label for="username">Username (Email):</label>
                            <input 
                                type="email" 
                                id="username" 
                                name="username" 
                                placeholder="your.email@example.com"
                                required
                            >
                        </div>
                        
                        <div class="form-group">
                            <label for="pin">PIN:</label>
                            <input 
                                type="password" 
                                id="pin" 
                                name="pin" 
                                placeholder="Your Polar Cloud PIN"
                                required
                            >
                        </div>
                        
                        <div class="form-group">
                            <label for="machine_type">Machine Type:</label>
                            <select id="machine_type" name="machine_type">
                                <option value="Cartesian">Cartesian</option>
                                <option value="Delta">Delta</option>
                                <option value="CoreXY">CoreXY</option>
                                <option value="Polar">Polar</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label for="printer_type">Printer Type:</label>
                            <select id="printer_type" name="printer_type">
                                <option value="Cartesian">Cartesian</option>
                                <option value="Delta">Delta</option>
                                <option value="CoreXY">CoreXY</option>
                                <option value="Polar">Polar</option>
                            </select>
                        </div>
                        
                        <div class="form-actions">
                            <button type="submit" id="connect-btn" class="btn btn-primary">
                                <i class="mdi mdi-cloud-upload"></i>
                                Connect to Polar Cloud
                            </button>
                            <button type="button" id="disconnect-btn" class="btn btn-warning" style="display: none;">
                                <i class="mdi mdi-cloud-off"></i>
                                Disconnect
                            </button>
                        </div>
                    </form>
                </div>

                <div class="polar-cloud-logs" style="margin-top: 2rem;">
                    <h3>Service Logs</h3>
                    <div class="log-container">
                        <textarea 
                            id="log-output" 
                            readonly 
                            rows="8" 
                            placeholder="Service logs will appear here..."
                        ></textarea>
                    </div>
                    <div class="log-actions">
                        <button type="button" id="refresh-logs-btn" class="btn btn-secondary">
                            <i class="mdi mdi-refresh"></i>
                            Refresh Logs
                        </button>
                        <button type="button" id="clear-logs-btn" class="btn btn-secondary">
                            <i class="mdi mdi-delete"></i>
                            Clear Logs
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create fallback UI if settings integration fails
     */
    function createFallbackUI() {
        // Create a floating widget
        const widget = document.createElement('div');
        widget.id = 'polar-cloud-widget';
        widget.className = 'polar-cloud-widget';
        widget.innerHTML = `
            <div class="widget-header">
                <h3>Polar Cloud</h3>
                <button class="widget-toggle" onclick="togglePolarCloudWidget()">
                    <i class="mdi mdi-chevron-up"></i>
                </button>
            </div>
            <div class="widget-content">
                ${createSettingsHTML()}
            </div>
        `;
        
        // Add styles
        const style = document.createElement('style');
        style.textContent = getPolarCloudStyles() + getWidgetStyles();
        document.head.appendChild(style);
        
        // Add to body
        document.body.appendChild(widget);
        
        // Bind event handlers
        bindEventHandlers();
        
        // Make it globally accessible
        window.togglePolarCloudWidget = function() {
            const content = widget.querySelector('.widget-content');
            const toggle = widget.querySelector('.widget-toggle i');
            if (content.style.display === 'none') {
                content.style.display = 'block';
                toggle.className = 'mdi mdi-chevron-up';
            } else {
                content.style.display = 'none';
                toggle.className = 'mdi mdi-chevron-down';
            }
        };
    }

    /**
     * Show the Polar Cloud settings panel
     */
    function showPolarCloudSettings() {
        // Hide other settings panels
        const allPanels = document.querySelectorAll('.settings-panel');
        allPanels.forEach(panel => panel.style.display = 'none');
        
        // Remove active class from all tabs
        const allTabs = document.querySelectorAll('.settings-tab');
        allTabs.forEach(tab => tab.classList.remove('active', 'v-tab--active'));
        
        // Show polar cloud panel
        if (settingsPanel) {
            settingsPanel.style.display = 'block';
        }
        
        // Activate polar cloud tab
        const polarTab = document.querySelector('.polar-cloud-tab');
        if (polarTab) {
            polarTab.classList.add('active', 'v-tab--active');
        }
        
        // Load current status
        loadPolarCloudStatus();
    }

    /**
     * Bind event handlers for the UI
     */
    function bindEventHandlers() {
        const form = document.getElementById('polar-cloud-form');
        const connectBtn = document.getElementById('connect-btn');
        const disconnectBtn = document.getElementById('disconnect-btn');
        const refreshLogsBtn = document.getElementById('refresh-logs-btn');
        const clearLogsBtn = document.getElementById('clear-logs-btn');

        if (form) {
            form.addEventListener('submit', handleConnect);
        }
        
        if (disconnectBtn) {
            disconnectBtn.addEventListener('click', handleDisconnect);
        }
        
        if (refreshLogsBtn) {
            refreshLogsBtn.addEventListener('click', loadServiceLogs);
        }
        
        if (clearLogsBtn) {
            clearLogsBtn.addEventListener('click', clearLogs);
        }
    }

    /**
     * Handle connection form submission
     */
    async function handleConnect(event) {
        event.preventDefault();
        
        const formData = new FormData(event.target);
        const data = {
            username: formData.get('username'),
            pin: formData.get('pin'),
            machine_type: formData.get('machine_type'),
            printer_type: formData.get('printer_type')
        };
        
        try {
            showLoading('Connecting to Polar Cloud...');
            
            const response = await fetch(`${API_BASE}/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams(data)
            });
            
            const result = await response.json();
            
            if (result.success) {
                showNotification('Successfully initiated connection to Polar Cloud', 'success');
                setTimeout(loadPolarCloudStatus, 2000); // Reload status after 2 seconds
            } else {
                showNotification(`Connection failed: ${result.error || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            console.error('Error connecting to Polar Cloud:', error);
            showNotification(`Connection failed: ${error.message}`, 'error');
        } finally {
            hideLoading();
        }
    }

    /**
     * Handle disconnection
     */
    async function handleDisconnect() {
        if (!confirm('Are you sure you want to disconnect from Polar Cloud?')) {
            return;
        }
        
        try {
            showLoading('Disconnecting...');
            
            const response = await fetch(`${API_BASE}/unregister`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                showNotification('Successfully disconnected from Polar Cloud', 'success');
                loadPolarCloudStatus();
            } else {
                showNotification(`Disconnect failed: ${result.error || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            console.error('Error disconnecting from Polar Cloud:', error);
            showNotification(`Disconnect failed: ${error.message}`, 'error');
        } finally {
            hideLoading();
        }
    }

    /**
     * Load current Polar Cloud status
     */
    async function loadPolarCloudStatus() {
        try {
            const response = await fetch(`${API_BASE}/status`);
            const data = await response.json();
            
            if (data.error) {
                console.error('Error loading status:', data.error);
                return;
            }
            
            // Update state
            polarCloudState = { ...polarCloudState, ...data };
            
            // Update UI
            updateStatusDisplay();
            updateForm();
            
        } catch (error) {
            console.error('Error loading Polar Cloud status:', error);
        }
    }

    /**
     * Update the status display
     */
    function updateStatusDisplay() {
        const statusIndicator = document.getElementById('status-indicator');
        const serviceStatus = document.getElementById('service-status');
        const serialNumber = document.getElementById('serial-number');
        const usernameDisplay = document.getElementById('username-display');
        
        if (statusIndicator) {
            const dot = statusIndicator.querySelector('.status-dot');
            const text = statusIndicator.querySelector('.status-text');
            
            if (polarCloudState.service_status === 'active' && polarCloudState.registered) {
                dot.className = 'status-dot active';
                text.textContent = 'Connected';
            } else if (polarCloudState.service_status === 'active') {
                dot.className = 'status-dot warning';
                text.textContent = 'Service Active (Not Registered)';
            } else {
                dot.className = 'status-dot inactive';
                text.textContent = 'Not Connected';
            }
        }
        
        if (serviceStatus) {
            serviceStatus.textContent = polarCloudState.service_status || 'inactive';
        }
        
        if (serialNumber) {
            serialNumber.textContent = polarCloudState.serial_number || 'Not registered';
        }
        
        if (usernameDisplay) {
            usernameDisplay.textContent = polarCloudState.username || 'Not set';
        }
    }

    /**
     * Update the form based on current state
     */
    function updateForm() {
        const connectBtn = document.getElementById('connect-btn');
        const disconnectBtn = document.getElementById('disconnect-btn');
        const usernameInput = document.getElementById('username');
        const machineTypeSelect = document.getElementById('machine_type');
        const printerTypeSelect = document.getElementById('printer_type');
        
        if (polarCloudState.registered) {
            if (connectBtn) {
                connectBtn.style.display = 'none';
            }
            if (disconnectBtn) {
                disconnectBtn.style.display = 'inline-block';
            }
        } else {
            if (connectBtn) {
                connectBtn.style.display = 'inline-block';
            }
            if (disconnectBtn) {
                disconnectBtn.style.display = 'none';
            }
        }
        
        // Populate form with current values
        if (usernameInput && polarCloudState.username) {
            usernameInput.value = polarCloudState.username;
        }
        
        if (machineTypeSelect && polarCloudState.machine_type) {
            machineTypeSelect.value = polarCloudState.machine_type;
        }
        
        if (printerTypeSelect && polarCloudState.printer_type) {
            printerTypeSelect.value = polarCloudState.printer_type;
        }
    }

    /**
     * Load service logs
     */
    async function loadServiceLogs() {
        const logOutput = document.getElementById('log-output');
        if (!logOutput) return;
        
        try {
            // Try to read logs from journalctl via a custom endpoint
            const response = await fetch('/server/files/logs/polar_cloud.log');
            if (response.ok) {
                const logs = await response.text();
                logOutput.value = logs;
            } else {
                logOutput.value = 'Unable to load logs. Check service status.';
            }
        } catch (error) {
            console.error('Error loading logs:', error);
            logOutput.value = 'Error loading logs: ' + error.message;
        }
    }

    /**
     * Clear log display
     */
    function clearLogs() {
        const logOutput = document.getElementById('log-output');
        if (logOutput) {
            logOutput.value = '';
        }
    }

    /**
     * Show loading indicator
     */
    function showLoading(message = 'Loading...') {
        // Simple loading implementation
        const forms = document.querySelectorAll('.polar-cloud-settings form');
        forms.forEach(form => {
            form.style.opacity = '0.5';
            form.style.pointerEvents = 'none';
        });
        
        showNotification(message, 'info');
    }

    /**
     * Hide loading indicator
     */
    function hideLoading() {
        const forms = document.querySelectorAll('.polar-cloud-settings form');
        forms.forEach(form => {
            form.style.opacity = '1';
            form.style.pointerEvents = 'auto';
        });
    }

    /**
     * Show notification
     */
    function showNotification(message, type = 'info') {
        // Try to use Mainsail's notification system if available
        if (window.mainsail && window.mainsail.notification) {
            window.mainsail.notification(message, type);
            return;
        }
        
        // Fallback notification
        console.log(`[Polar Cloud] ${type.toUpperCase()}: ${message}`);
        
        // Simple toast notification
        const toast = document.createElement('div');
        toast.className = `polar-cloud-toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: ${type === 'error' ? '#f44336' : type === 'success' ? '#4caf50' : '#2196f3'};
            color: white;
            border-radius: 4px;
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    /**
     * Get CSS styles for the plugin
     */
    function getPolarCloudStyles() {
        return `
            .polar-cloud-settings {
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }

            .settings-header h2 {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 8px;
                color: #333;
            }

            .settings-description {
                color: #666;
                margin-bottom: 24px;
            }

            .status-card {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 24px;
            }

            .status-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 16px;
            }

            .status-indicator {
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .status-dot {
                width: 12px;
                height: 12px;
                border-radius: 50%;
            }

            .status-dot.active {
                background: #4caf50;
                box-shadow: 0 0 8px rgba(76, 175, 80, 0.4);
            }

            .status-dot.warning {
                background: #ff9800;
                box-shadow: 0 0 8px rgba(255, 152, 0, 0.4);
            }

            .status-dot.inactive {
                background: #9e9e9e;
            }

            .status-details {
                display: grid;
                gap: 8px;
            }

            .status-item {
                display: flex;
                justify-content: space-between;
            }

            .status-item .label {
                font-weight: 500;
                color: #666;
            }

            .config-form {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 20px;
            }

            .form-group {
                margin-bottom: 16px;
            }

            .form-group label {
                display: block;
                margin-bottom: 4px;
                font-weight: 500;
                color: #333;
            }

            .form-group input,
            .form-group select {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 14px;
            }

            .form-group input:focus,
            .form-group select:focus {
                outline: none;
                border-color: #007bff;
                box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
            }

            .form-actions {
                display: flex;
                gap: 12px;
                margin-top: 20px;
            }

            .btn {
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                display: inline-flex;
                align-items: center;
                gap: 8px;
                transition: all 0.2s;
            }

            .btn-primary {
                background: #007bff;
                color: white;
            }

            .btn-primary:hover {
                background: #0056b3;
            }

            .btn-warning {
                background: #ffc107;
                color: #212529;
            }

            .btn-warning:hover {
                background: #e0a800;
            }

            .btn-secondary {
                background: #6c757d;
                color: white;
            }

            .btn-secondary:hover {
                background: #545b62;
            }

            .log-container {
                margin-bottom: 12px;
            }

            .log-container textarea {
                width: 100%;
                font-family: 'Roboto Mono', 'Consolas', monospace;
                font-size: 12px;
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 12px;
                resize: vertical;
            }

            .log-actions {
                display: flex;
                gap: 8px;
            }

            @keyframes slideIn {
                from { transform: translateX(100%); }
                to { transform: translateX(0); }
            }

            @keyframes slideOut {
                from { transform: translateX(0); }
                to { transform: translateX(100%); }
            }
        `;
    }

    /**
     * Get CSS styles for the widget
     */
    function getWidgetStyles() {
        return `
            .polar-cloud-widget {
                position: fixed;
                top: 100px;
                right: 20px;
                width: 400px;
                background: white;
                border: 1px solid #ccc;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                z-index: 9999;
            }

            .widget-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 16px;
                background: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
                border-radius: 8px 8px 0 0;
            }

            .widget-header h3 {
                margin: 0;
                color: #333;
            }

            .widget-toggle {
                background: none;
                border: none;
                cursor: pointer;
                padding: 4px;
                color: #666;
            }

            .widget-toggle:hover {
                color: #333;
            }
        `;
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPolarCloudPlugin);
    } else {
        initPolarCloudPlugin();
    }

    // Also try to initialize after a delay in case Mainsail loads later
    setTimeout(initPolarCloudPlugin, 2000);

})(); 