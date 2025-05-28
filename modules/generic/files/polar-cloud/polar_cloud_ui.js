/*!
 * Polar Cloud UI Plugin for Mainsail
 * Adds Polar Cloud card to the MACHINE tab
 */

(function() {
    'use strict';

    // Plugin configuration
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

    /**
     * Initialize the Polar Cloud plugin
     */
    function initPolarCloudPlugin() {
        console.log('Initializing Polar Cloud Plugin for MACHINE tab');
        
        // Wait for page to load and try to add to machine tab
        setTimeout(addToMachineTab, 2000);
        
        // Try multiple times in case the page loads slowly
        setTimeout(addToMachineTab, 5000);
        setTimeout(addToMachineTab, 10000);
    }

    /**
     * Add Polar Cloud card to the MACHINE tab
     */
    function addToMachineTab() {
        // Look for the machine tab content area
        const machineTab = document.querySelector('[data-testid="machine-tab"]') ||
                          document.querySelector('#machine-tab') ||
                          document.querySelector('.machine-tab') ||
                          findMachineTabByContent();
        
        if (!machineTab) {
            console.log('Machine tab not found, retrying...');
            return;
        }

        // Check if already added
        if (document.querySelector('#polar-cloud-card')) {
            console.log('Polar Cloud card already exists');
            return;
        }

        // Create the Polar Cloud card
        const polarCloudCard = createPolarCloudCard();
        
        // Find a good place to insert it (after system loads or update manager)
        const systemLoads = machineTab.querySelector('[data-testid="system-loads"]') ||
                           machineTab.querySelector('.system-loads') ||
                           machineTab.querySelector('h3');
        
        if (systemLoads && systemLoads.parentNode) {
            // Insert after system loads or similar element
            systemLoads.parentNode.insertBefore(polarCloudCard, systemLoads.nextSibling);
        } else {
            // Fallback: append to machine tab
            machineTab.appendChild(polarCloudCard);
        }

        // Bind event handlers
        bindEventHandlers();
        
        // Load initial status
        loadPolarCloudStatus();
        
        console.log('Polar Cloud card added to MACHINE tab');
    }

    /**
     * Find machine tab by looking for characteristic content
     */
    function findMachineTabByContent() {
        // Look for elements that are typically in the machine tab
        const indicators = [
            'System Loads',
            'Update Manager',
            'system-loads',
            'update-manager'
        ];
        
        for (const indicator of indicators) {
            const element = document.querySelector(`[data-testid*="${indicator}"]`) ||
                           document.querySelector(`[class*="${indicator}"]`) ||
                           Array.from(document.querySelectorAll('*')).find(el => 
                               el.textContent && el.textContent.includes(indicator)
                           );
            
            if (element) {
                // Find the parent container that looks like a tab content area
                let parent = element.parentNode;
                while (parent && parent !== document.body) {
                    if (parent.classList.contains('tab-content') ||
                        parent.classList.contains('v-tab-content') ||
                        parent.classList.contains('machine') ||
                        parent.id.includes('machine')) {
                        return parent;
                    }
                    parent = parent.parentNode;
                }
                // Fallback to a reasonable parent
                return element.parentNode?.parentNode || element.parentNode;
            }
        }
        
        return null;
    }

    /**
     * Create the Polar Cloud card HTML
     */
    function createPolarCloudCard() {
        const card = document.createElement('div');
        card.id = 'polar-cloud-card';
        card.className = 'v-card v-sheet theme--dark polar-cloud-card';
        card.innerHTML = `
            <div class="v-card__title">
                <h3>
                    <i class="mdi mdi-cloud-outline"></i>
                    Polar Cloud Connection
                </h3>
            </div>
            <div class="v-card__text">
                <div class="polar-cloud-status">
                    <div class="status-row">
                        <span class="status-label">Status:</span>
                        <span class="status-value" id="pc-status">
                            <span class="status-dot inactive"></span>
                            <span id="pc-status-text">Not Connected</span>
                        </span>
                    </div>
                    <div class="status-row">
                        <span class="status-label">Service:</span>
                        <span class="status-value" id="pc-service-status">inactive</span>
                    </div>
                    <div class="status-row">
                        <span class="status-label">Serial:</span>
                        <span class="status-value" id="pc-serial">Not registered</span>
                    </div>
                    <div class="status-row">
                        <span class="status-label">Username:</span>
                        <span class="status-value" id="pc-username">Not set</span>
                    </div>
                </div>
                
                <div class="polar-cloud-form" id="pc-form-container">
                    <div class="form-row">
                        <input type="email" id="pc-username-input" placeholder="Email/Username" class="form-input">
                        <input type="password" id="pc-pin-input" placeholder="PIN" class="form-input">
                    </div>
                    <div class="form-row">
                        <select id="pc-machine-type" class="form-select">
                            <option value="Cartesian">Cartesian</option>
                            <option value="Delta">Delta</option>
                            <option value="CoreXY">CoreXY</option>
                            <option value="Polar">Polar</option>
                        </select>
                        <select id="pc-printer-type" class="form-select">
                            <option value="Cartesian">Cartesian</option>
                            <option value="Delta">Delta</option>
                            <option value="CoreXY">CoreXY</option>
                            <option value="Polar">Polar</option>
                        </select>
                    </div>
                    <div class="form-actions">
                        <button id="pc-connect-btn" class="btn btn-primary">
                            <i class="mdi mdi-cloud-upload"></i>
                            Connect
                        </button>
                        <button id="pc-disconnect-btn" class="btn btn-warning" style="display: none;">
                            <i class="mdi mdi-cloud-off"></i>
                            Disconnect
                        </button>
                        <button id="pc-refresh-btn" class="btn btn-secondary">
                            <i class="mdi mdi-refresh"></i>
                            Refresh
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Add styles
        addPolarCloudStyles();
        
        return card;
    }

    /**
     * Bind event handlers
     */
    function bindEventHandlers() {
        const connectBtn = document.getElementById('pc-connect-btn');
        const disconnectBtn = document.getElementById('pc-disconnect-btn');
        const refreshBtn = document.getElementById('pc-refresh-btn');

        if (connectBtn) {
            connectBtn.addEventListener('click', handleConnect);
        }
        
        if (disconnectBtn) {
            disconnectBtn.addEventListener('click', handleDisconnect);
        }
        
        if (refreshBtn) {
            refreshBtn.addEventListener('click', loadPolarCloudStatus);
        }
    }

    /**
     * Handle connection
     */
    async function handleConnect() {
        const username = document.getElementById('pc-username-input').value;
        const pin = document.getElementById('pc-pin-input').value;
        const machineType = document.getElementById('pc-machine-type').value;
        const printerType = document.getElementById('pc-printer-type').value;
        
        if (!username || !pin) {
            showNotification('Please enter both username and PIN', 'error');
            return;
        }
        
        try {
            showLoading('Connecting...');
            
            const response = await fetch(`${API_BASE}/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: username,
                    pin: pin,
                    machine_type: machineType,
                    printer_type: printerType
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                showNotification('Connection initiated successfully!', 'success');
                setTimeout(loadPolarCloudStatus, 2000);
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
                showNotification('Disconnected successfully!', 'success');
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
     * Load current status
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
            // Set error state
            document.getElementById('pc-status-text').textContent = 'Error';
            document.getElementById('pc-service-status').textContent = 'Error';
        }
    }

    /**
     * Update status display
     */
    function updateStatusDisplay() {
        const statusText = document.getElementById('pc-status-text');
        const statusDot = document.querySelector('#pc-status .status-dot');
        const serviceStatus = document.getElementById('pc-service-status');
        const serial = document.getElementById('pc-serial');
        const username = document.getElementById('pc-username');
        
        if (statusText && statusDot) {
            if (polarCloudState.service_status === 'active' && polarCloudState.registered) {
                statusDot.className = 'status-dot active';
                statusText.textContent = 'Connected';
            } else if (polarCloudState.service_status === 'active') {
                statusDot.className = 'status-dot warning';
                statusText.textContent = 'Service Active';
            } else {
                statusDot.className = 'status-dot inactive';
                statusText.textContent = 'Not Connected';
            }
        }
        
        if (serviceStatus) {
            serviceStatus.textContent = polarCloudState.service_status || 'inactive';
        }
        
        if (serial) {
            serial.textContent = polarCloudState.serial_number || 'Not registered';
        }
        
        if (username) {
            username.textContent = polarCloudState.username || 'Not set';
        }
    }

    /**
     * Update form
     */
    function updateForm() {
        const connectBtn = document.getElementById('pc-connect-btn');
        const disconnectBtn = document.getElementById('pc-disconnect-btn');
        const usernameInput = document.getElementById('pc-username-input');
        const machineType = document.getElementById('pc-machine-type');
        const printerType = document.getElementById('pc-printer-type');
        
        if (polarCloudState.registered) {
            if (connectBtn) connectBtn.style.display = 'none';
            if (disconnectBtn) disconnectBtn.style.display = 'inline-flex';
        } else {
            if (connectBtn) connectBtn.style.display = 'inline-flex';
            if (disconnectBtn) disconnectBtn.style.display = 'none';
        }
        
        // Populate form
        if (usernameInput && polarCloudState.username) {
            usernameInput.value = polarCloudState.username;
        }
        
        if (machineType && polarCloudState.machine_type) {
            machineType.value = polarCloudState.machine_type;
        }
        
        if (printerType && polarCloudState.printer_type) {
            printerType.value = polarCloudState.printer_type;
        }
    }

    /**
     * Show loading state
     */
    function showLoading(message) {
        const card = document.getElementById('polar-cloud-card');
        if (card) {
            card.style.opacity = '0.6';
            card.style.pointerEvents = 'none';
        }
        console.log(`[Polar Cloud] ${message}`);
    }

    /**
     * Hide loading state
     */
    function hideLoading() {
        const card = document.getElementById('polar-cloud-card');
        if (card) {
            card.style.opacity = '1';
            card.style.pointerEvents = 'auto';
        }
    }

    /**
     * Show notification
     */
    function showNotification(message, type = 'info') {
        console.log(`[Polar Cloud] ${type.toUpperCase()}: ${message}`);
        
        // Try to use browser notification if available
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('Polar Cloud', { body: message });
        } else {
            // Simple alert fallback
            alert(`Polar Cloud: ${message}`);
        }
    }

    /**
     * Add CSS styles
     */
    function addPolarCloudStyles() {
        if (document.getElementById('polar-cloud-styles')) {
            return; // Already added
        }
        
        const style = document.createElement('style');
        style.id = 'polar-cloud-styles';
        style.textContent = `
            .polar-cloud-card {
                margin: 16px 0;
                background: rgba(255, 255, 255, 0.05) !important;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            .polar-cloud-card .v-card__title h3 {
                display: flex;
                align-items: center;
                gap: 8px;
                color: #fff;
                margin: 0;
                font-size: 1.1rem;
            }
            
            .polar-cloud-status {
                margin-bottom: 16px;
            }
            
            .status-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
                padding: 4px 0;
            }
            
            .status-label {
                color: #ccc;
                font-weight: 500;
            }
            
            .status-value {
                color: #fff;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                display: inline-block;
            }
            
            .status-dot.active {
                background: #4caf50;
                box-shadow: 0 0 6px rgba(76, 175, 80, 0.6);
            }
            
            .status-dot.warning {
                background: #ff9800;
                box-shadow: 0 0 6px rgba(255, 152, 0, 0.6);
            }
            
            .status-dot.inactive {
                background: #666;
            }
            
            .polar-cloud-form {
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                padding-top: 16px;
            }
            
            .form-row {
                display: flex;
                gap: 8px;
                margin-bottom: 12px;
            }
            
            .form-input, .form-select {
                flex: 1;
                padding: 8px 12px;
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                color: #fff;
                font-size: 14px;
            }
            
            .form-input::placeholder {
                color: #aaa;
            }
            
            .form-input:focus, .form-select:focus {
                outline: none;
                border-color: #2196f3;
                box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.3);
            }
            
            .form-actions {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
            }
            
            .btn {
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                transition: all 0.2s;
                text-decoration: none;
            }
            
            .btn-primary {
                background: #2196f3;
                color: white;
            }
            
            .btn-primary:hover {
                background: #1976d2;
            }
            
            .btn-warning {
                background: #ff9800;
                color: white;
            }
            
            .btn-warning:hover {
                background: #f57c00;
            }
            
            .btn-secondary {
                background: #666;
                color: white;
            }
            
            .btn-secondary:hover {
                background: #555;
            }
            
            .btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
        `;
        
        document.head.appendChild(style);
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPolarCloudPlugin);
    } else {
        initPolarCloudPlugin();
    }

    // Also try after delays to catch late-loading content
    setTimeout(initPolarCloudPlugin, 3000);
    setTimeout(initPolarCloudPlugin, 8000);

})(); 