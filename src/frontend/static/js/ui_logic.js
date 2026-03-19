/**
 * ui_logic.js - Handles DOM interactions and basic UI components.
 */

const UILogic = {
    /**
     * Toggles the open class on an expander element.
     */
    initExpanders() {
        document.querySelectorAll('.expander-header').forEach(header => {
            header.addEventListener('click', () => {
                header.parentElement.classList.toggle('open');
            });
        });
    },

    /**
     * appends a log message to the log container with terminal styling.
     */
    addLog(message, containerId = 'log_container') {
        const container = document.getElementById(containerId);
        const logElement = document.createElement('div');
        
        // Assign color class based on message content
        let typeClass = 'info';
        if (message.includes('✅') || message.includes('concluído')) typeClass = 'success';
        if (message.includes('❌') || message.includes('Erro')) typeClass = 'error';
        
        logElement.className = `terminal-line ${typeClass} fade-in`;
        logElement.textContent = message;
        container.appendChild(logElement);
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Updates the progress bar and status text.
     */
    updateProgress(percent, statusText, color = "#0056b3") {
        const bar = document.getElementById('progress_bar');
        const text = document.getElementById('status_text');
        
        bar.style.width = `${percent}%`;
        text.textContent = statusText;
        if (color) bar.style.backgroundColor = color;
    },

    /**
     * Appends a new result row to the results table with SaaS button styles.
     */
    addResult(result, bodyId = 'results_body') {
        const tbody = document.getElementById(bodyId);
        const row = document.createElement('tr');
        row.className = 'fade-in';
        
        row.innerHTML = `
            <td><span style="font-weight:700; color:var(--primary);">${result.marketplace}</span></td>
            <td><a href="${result.link_produto}" target="_blank" class="table-btn btn-view"><i class="fas fa-external-link-alt"></i> Produto</a></td>
            <td style="text-align: right;"><a href="${result.link_afiliado}" target="_blank" class="table-btn btn-copy"><i class="fas fa-money-bill-wave"></i> Afiliado</a></td>
        `;
        
        tbody.prepend(row);
    },

    clearResults(bodyId = 'results_body', logId = 'log_container') {
        document.getElementById(bodyId).innerHTML = '';
        document.getElementById(logId).innerHTML = '';
        this.updateProgress(0, 'Iniciando...');
    },

    showExportActions(show = true) {
        document.getElementById('export_panel').style.display = show ? 'flex' : 'none';
    }
};
