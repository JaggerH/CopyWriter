class TaskDashboard {
    constructor() {
        this.websocket = null;
        this.selectedTaskId = null;
        this.tasks = new Map();
        this.isConnected = false;
        
        this.initializeElements();
        this.bindEvents();
        this.connectWebSocket();
        this.loadTasks();
    }

    initializeElements() {
        this.elements = {
            // Forms and inputs
            createTaskForm: document.getElementById('createTaskForm'),
            urlInput: document.getElementById('urlInput'),
            createTaskBtn: document.getElementById('createTaskBtn'),
            createBtnText: document.getElementById('createBtnText'),
            createBtnSpinner: document.getElementById('createBtnSpinner'),
            withWatermark: document.getElementById('withWatermark'),
            qualitySelect: document.getElementById('qualitySelect'),
            
            // Task list
            taskList: document.getElementById('taskList'),
            refreshBtn: document.getElementById('refreshBtn'),
            clearCompletedBtn: document.getElementById('clearCompletedBtn'),
            
            // Task detail
            taskDetail: document.getElementById('taskDetail'),
            
            // Connection status
            connectionStatus: document.getElementById('connectionStatus'),
            statusIndicator: document.getElementById('statusIndicator'),
            statusText: document.getElementById('statusText'),
            
            // Modal
            modalOverlay: document.getElementById('modalOverlay'),
            modalTitle: document.getElementById('modalTitle'),
            modalMessage: document.getElementById('modalMessage'),
            modalClose: document.getElementById('modalClose'),
            modalCancel: document.getElementById('modalCancel'),
            modalConfirm: document.getElementById('modalConfirm'),
            
            // Toast container
            toastContainer: document.getElementById('toastContainer')
        };
    }

    bindEvents() {
        // Form submission
        this.elements.createTaskForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.createTask();
        });

        // Button clicks
        this.elements.refreshBtn.addEventListener('click', () => this.loadTasks());
        this.elements.clearCompletedBtn.addEventListener('click', () => this.clearCompletedTasks());

        // Modal events
        this.elements.modalClose.addEventListener('click', () => this.hideModal());
        this.elements.modalCancel.addEventListener('click', () => this.hideModal());
        this.elements.modalOverlay.addEventListener('click', (e) => {
            if (e.target === this.elements.modalOverlay) {
                this.hideModal();
            }
        });
    }

    // WebSocket Connection
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/tasks`;
        
        try {
            this.websocket = new WebSocket(wsUrl);
            this.updateConnectionStatus('connecting', '连接中...');
            
            this.websocket.onopen = () => {
                this.isConnected = true;
                this.updateConnectionStatus('online', '已连接');
                console.log('WebSocket connected');
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleWebSocketMessage(message);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };
            
            this.websocket.onclose = () => {
                this.isConnected = false;
                this.updateConnectionStatus('offline', '连接断开');
                console.log('WebSocket disconnected');
                
                // Reconnect after 3 seconds
                setTimeout(() => {
                    if (!this.isConnected) {
                        this.connectWebSocket();
                    }
                }, 3000);
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('offline', '连接错误');
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.updateConnectionStatus('offline', '连接失败');
        }
    }

    updateConnectionStatus(status, text) {
        this.elements.statusIndicator.className = `status-indicator ${status}`;
        this.elements.statusText.textContent = text;
    }

    handleWebSocketMessage(message) {
        switch (message.type) {
            case 'task_update':
                this.updateTaskInList(message.data);
                if (this.selectedTaskId === message.task_id) {
                    this.loadTaskDetail(message.task_id);
                }
                break;
            case 'task_created':
                this.addTaskToList(message.data);
                break;
            case 'task_deleted':
                this.removeTaskFromList(message.task_id);
                break;
            default:
                console.log('Unknown message type:', message.type);
        }
    }

    // API Calls
    async apiCall(endpoint, options = {}) {
        try {
            const response = await fetch(endpoint, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API call failed: ${endpoint}`, error);
            this.showToast('API请求失败', error.message, 'error');
            throw error;
        }
    }

    // Task Management
    async createTask() {
        const inputText = this.elements.urlInput.value.trim();
        if (!inputText) {
            this.showToast('输入错误', '请输入包含视频链接的文本', 'warning');
            return;
        }

        // 简单检查是否包含可能的视频链接
        const hasVideoLink = /https?:\/\/[^\s]+/.test(inputText) && 
                           /(douyin|tiktok|bilibili|youtube|xiaohongshu|kuaishou)/i.test(inputText);
        
        if (!hasVideoLink) {
            this.showToast('输入错误', '未检测到支持的视频平台链接', 'warning');
            return;
        }

        this.setCreateTaskLoading(true);

        try {
            const taskData = {
                url: inputText,
                quality: this.elements.qualitySelect.value,
                with_watermark: this.elements.withWatermark.checked
            };

            const response = await this.apiCall('/api/tasks', {
                method: 'POST',
                body: JSON.stringify(taskData)
            });

            this.showToast('任务创建成功', response.message, 'success');
            this.elements.urlInput.value = '';
            this.loadTasks(); // Refresh task list
            
        } catch (error) {
            this.showToast('创建任务失败', error.message, 'error');
        } finally {
            this.setCreateTaskLoading(false);
        }
    }

    setCreateTaskLoading(loading) {
        this.elements.createTaskBtn.disabled = loading;
        this.elements.createBtnText.style.display = loading ? 'none' : 'inline';
        this.elements.createBtnSpinner.style.display = loading ? 'inline-block' : 'none';
    }

    async loadTasks() {
        try {
            const response = await this.apiCall('/api/tasks');
            this.renderTaskList(response.tasks);
        } catch (error) {
            this.showErrorInTaskList('加载任务列表失败');
        }
    }

    async loadTaskDetail(taskId) {
        try {
            const task = await this.apiCall(`/api/tasks/${taskId}`);
            this.renderTaskDetail(task);
            this.selectedTaskId = taskId;
        } catch (error) {
            this.showErrorInTaskDetail('加载任务详情失败');
        }
    }

    // UI Rendering
    renderTaskList(tasks) {
        if (!tasks || tasks.length === 0) {
            this.elements.taskList.innerHTML = `
                <div class="loading-placeholder">
                    <div class="empty-icon">📝</div>
                    <p>暂无任务</p>
                </div>
            `;
            return;
        }

        this.elements.taskList.innerHTML = tasks.map(task => this.renderTaskItem(task)).join('');
        
        // Add click events to task items
        this.elements.taskList.querySelectorAll('.task-item').forEach(item => {
            item.addEventListener('click', (e) => {
                // Don't select task if clicking on delete button
                if (e.target.classList.contains('delete-task-btn') || e.target.closest('.delete-task-btn')) {
                    return;
                }
                const taskId = item.dataset.taskId;
                this.selectTask(taskId);
            });
        });
    }

    renderTaskItem(task) {
        const statusClass = `status-${task.status}`;
        const createdTime = new Date(task.created_time).toLocaleString('zh-CN');
        
        return `
            <div class="task-item" data-task-id="${task.task_id}">
                <div class="task-item-header">
                    <div class="task-title" title="${task.title}">${task.title}</div>
                    <div class="task-actions">
                        <div class="task-time">${createdTime}</div>
                        <button class="delete-task-btn" onclick="window.taskDashboard.deleteTask('${task.task_id}', '${task.title}')" title="删除任务">
                            🗑️
                        </button>
                    </div>
                </div>
                <div class="task-status">
                    <span class="status-badge ${statusClass}">${this.getStatusText(task.status)}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${task.progress}%"></div>
                </div>
            </div>
        `;
    }

    renderTaskDetail(task) {
        if (!task) {
            this.showEmptyTaskDetail();
            return;
        }

        const createdTime = new Date(task.created_time).toLocaleString('zh-CN');
        const updatedTime = new Date(task.updated_time).toLocaleString('zh-CN');
        
        // Extract file paths from result if available
        let filePaths = '';
        if (task.result && typeof task.result === 'object') {
            let result = task.result;
            if (typeof result === 'string') {
                try {
                    result = JSON.parse(result);
                } catch (e) {
                    result = task.result;
                }
            }
            
            if (result.video_path) {
                filePaths += `
                    <div class="info-row">
                        <span class="info-label">视频文件:</span>
                        <span class="info-value" style="word-break: break-all;">${result.video_path}</span>
                    </div>`;
            }
            if (result.audio_path) {
                filePaths += `
                    <div class="info-row">
                        <span class="info-label">音频文件:</span>
                        <span class="info-value" style="word-break: break-all;">${result.audio_path}</span>
                    </div>`;
            }
            if (result.text_path) {
                filePaths += `
                    <div class="info-row">
                        <span class="info-label">文本文件:</span>
                        <span class="info-value" style="word-break: break-all;">${result.text_path}</span>
                    </div>`;
            }
        }

        let contentHtml = `
            <div class="detail-section">
                <h3>📋 基本信息</h3>
                <div class="detail-info">
                    <div class="info-row">
                        <span class="info-label">任务ID:</span>
                        <span class="info-value">${task.task_id}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">标题:</span>
                        <span class="info-value">${task.title}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">URL:</span>
                        <span class="info-value" style="word-break: break-all;">${task.url}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">创建时间:</span>
                        <span class="info-value">${createdTime}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">更新时间:</span>
                        <span class="info-value">${updatedTime}</span>
                    </div>
                    ${filePaths}
                </div>
            </div>

            <div class="progress-section">
                <h3>⚡ 执行进度</h3>
                <div class="progress-header">
                    <span class="progress-text">当前步骤: ${task.current_step}</span>
                    <span class="progress-percentage">${task.progress}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${task.progress}%"></div>
                </div>
                <div class="detail-info" style="margin-top: 1rem;">
                    <div class="info-row">
                        <span class="info-label">状态:</span>
                        <span class="info-value">
                            <span class="status-badge status-${task.status}">${this.getStatusText(task.status)}</span>
                        </span>
                    </div>
                </div>
            </div>
        `;

        // Add result section if completed
        if (task.status === 'completed' && task.result) {
            const transcriptText = this.getTranscriptText(task.result);
            if (transcriptText) {
                contentHtml += `
                    <div class="result-section">
                        <div class="result-header">
                            <h3>✅ 转录内容</h3>
                            <button class="copy-btn" onclick="window.taskDashboard.copyToClipboard('${task.task_id}')" title="复制转录内容">
                                📋 复制
                            </button>
                        </div>
                        <div class="result-content" id="transcript-${task.task_id}">${transcriptText}</div>
                    </div>
                `;
            }
        }

        // Add error section if failed
        if (task.status === 'failed' && task.error) {
            contentHtml += `
                <div class="error-section">
                    <h3>❌ 错误信息</h3>
                    <div class="error-content">${task.error}</div>
                </div>
            `;
        }

        this.elements.taskDetail.innerHTML = contentHtml;
    }

    showEmptyTaskDetail() {
        this.elements.taskDetail.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📋</div>
                <p>选择一个任务查看详情</p>
            </div>
        `;
    }

    showErrorInTaskList(message) {
        this.elements.taskList.innerHTML = `
            <div class="loading-placeholder">
                <div class="empty-icon">❌</div>
                <p>${message}</p>
                <button onclick="window.taskDashboard.loadTasks()" style="margin-top: 1rem; padding: 0.5rem 1rem; border: none; border-radius: 8px; background: #667eea; color: white; cursor: pointer;">重试</button>
            </div>
        `;
    }

    showErrorInTaskDetail(message) {
        this.elements.taskDetail.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">❌</div>
                <p>${message}</p>
            </div>
        `;
    }

    selectTask(taskId) {
        // Update UI selection
        this.elements.taskList.querySelectorAll('.task-item').forEach(item => {
            item.classList.toggle('selected', item.dataset.taskId === taskId);
        });
        
        // Load task detail
        this.loadTaskDetail(taskId);
    }

    updateTaskInList(taskData) {
        const taskItem = this.elements.taskList.querySelector(`[data-task-id="${taskData.task_id}"]`);
        if (taskItem) {
            // Update existing task item
            const newItem = this.createTaskItemElement(taskData);
            taskItem.replaceWith(newItem);
            
            // Re-add click event with proper event handling
            newItem.addEventListener('click', (e) => {
                if (e.target.classList.contains('delete-task-btn') || e.target.closest('.delete-task-btn')) {
                    return;
                }
                this.selectTask(taskData.task_id);
            });
            
            // Maintain selection
            if (this.selectedTaskId === taskData.task_id) {
                newItem.classList.add('selected');
            }
        }
    }

    addTaskToList(taskData) {
        const newItem = this.createTaskItemElement(taskData);
        this.elements.taskList.prepend(newItem);
        
        newItem.addEventListener('click', (e) => {
            if (e.target.classList.contains('delete-task-btn') || e.target.closest('.delete-task-btn')) {
                return;
            }
            this.selectTask(taskData.task_id);
        });
    }

    removeTaskFromList(taskId) {
        const taskItem = this.elements.taskList.querySelector(`[data-task-id="${taskId}"]`);
        if (taskItem) {
            taskItem.remove();
            
            if (this.selectedTaskId === taskId) {
                this.selectedTaskId = null;
                this.showEmptyTaskDetail();
            }
        }
    }

    createTaskItemElement(task) {
        const div = document.createElement('div');
        div.className = 'task-item';
        div.dataset.taskId = task.task_id;
        div.innerHTML = this.renderTaskItem(task);
        return div.firstElementChild;
    }

    // Utility Methods
    getStatusText(status) {
        const statusMap = {
            'queued': '队列中',
            'downloading': '下载中',
            'converting': '转换中',
            'transcribing': '识别中',
            'completed': '已完成',
            'failed': '失败'
        };
        return statusMap[status] || status;
    }

    getTranscriptText(result) {
        if (typeof result === 'string') {
            try {
                result = JSON.parse(result);
            } catch (e) {
                return result;
            }
        }
        
        if (result && typeof result === 'object' && result.text) {
            return result.text;
        }
        
        return null;
    }

    formatResult(result) {
        // This method is kept for backward compatibility but should not be used for completed tasks
        if (typeof result === 'string') {
            try {
                result = JSON.parse(result);
            } catch (e) {
                return result;
            }
        }
        
        if (result && typeof result === 'object') {
            // Only show the transcribed text, file paths are shown in basic info
            if (result.text) {
                return result.text;
            }
            // If no text but other data exists, show as JSON (fallback)
            return JSON.stringify(result, null, 2);
        }
        
        return String(result);
    }

    async copyToClipboard(taskId) {
        try {
            const textElement = document.getElementById(`transcript-${taskId}`);
            if (!textElement) {
                this.showToast('复制失败', '找不到转录内容', 'error');
                return;
            }

            const text = textElement.textContent || textElement.innerText;
            
            if (navigator.clipboard && window.isSecureContext) {
                // Use the modern Clipboard API
                await navigator.clipboard.writeText(text);
                this.showToast('复制成功', '转录内容已复制到剪贴板', 'success');
            } else {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                
                try {
                    document.execCommand('copy');
                    textArea.remove();
                    this.showToast('复制成功', '转录内容已复制到剪贴板', 'success');
                } catch (err) {
                    textArea.remove();
                    this.showToast('复制失败', '浏览器不支持复制功能', 'error');
                }
            }
        } catch (err) {
            console.error('Copy failed:', err);
            this.showToast('复制失败', '复制过程中出现错误', 'error');
        }
    }

    // Modal Methods
    showModal(title, message, onConfirm) {
        this.elements.modalTitle.textContent = title;
        this.elements.modalMessage.textContent = message;
        this.elements.modalOverlay.style.display = 'flex';
        
        this.elements.modalConfirm.onclick = () => {
            this.hideModal();
            if (onConfirm) onConfirm();
        };
    }

    hideModal() {
        this.elements.modalOverlay.style.display = 'none';
        this.elements.modalConfirm.onclick = null;
    }

    async deleteTask(taskId, taskTitle) {
        // Prevent event bubbling
        event.stopPropagation();
        
        this.showModal(
            '删除任务',
            `确定要删除任务 "${taskTitle}" 吗？此操作无法撤销。`,
            async () => {
                try {
                    await this.apiCall(`/api/tasks/${taskId}`, { method: 'DELETE' });
                    this.showToast('删除成功', '任务已成功删除', 'success');
                    
                    // If the deleted task was selected, clear the detail view
                    if (this.selectedTaskId === taskId) {
                        this.selectedTaskId = null;
                        this.showEmptyTaskDetail();
                    }
                    
                    // Reload task list
                    this.loadTasks();
                } catch (error) {
                    this.showToast('删除失败', error.message, 'error');
                }
            }
        );
    }

    async clearCompletedTasks() {
        this.showModal(
            '清除已完成任务',
            '确定要删除所有已完成的任务吗？此操作无法撤销。',
            async () => {
                try {
                    await this.apiCall('/api/tasks/completed', { method: 'DELETE' });
                    this.showToast('清除完成', '已成功清除所有已完成的任务', 'success');
                    this.loadTasks();
                    this.showEmptyTaskDetail();
                } catch (error) {
                    this.showToast('清除失败', error.message, 'error');
                }
            }
        );
    }

    // Toast Notifications
    showToast(title, message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icons = {
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        };
        
        toast.innerHTML = `
            <div class="toast-icon">${icons[type] || icons.info}</div>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close">×</button>
        `;
        
        this.elements.toastContainer.appendChild(toast);
        
        // Add close event
        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.remove();
        });
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 5000);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.taskDashboard = new TaskDashboard();
});