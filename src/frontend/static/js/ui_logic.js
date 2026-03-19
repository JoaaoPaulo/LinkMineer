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
     * appends a log message to the log container.
     */
    addLog(message, containerId = 'log_container') {
        const container = document.getElementById(containerId);
        const logElement = document.createElement('div');
        logElement.className = 'log-entry fade-in';
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
     * Appends a new result row to the results table.
     */
    addResult(result, bodyId = 'results_body') {
        const tbody = document.getElementById(bodyId);
        const row = document.createElement('tr');
        row.className = 'fade-in';
        
        row.innerHTML = `
            <td><strong>${result.marketplace}</strong></td>
            <td><a href="${result.link_produto}" target="_blank" style="color: var(--light-blue); font-size: 0.8rem;">🔗 Ver Produto</a></td>
            <td><a href="${result.link_afiliado}" target="_blank" style="color: var(--accent); font-weight: 700;">💰 Copiar Afiliado</a></td>
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
