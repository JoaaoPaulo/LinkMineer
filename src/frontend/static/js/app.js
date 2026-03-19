/**
 * app.js - Main Application Orchestrator.
 */

document.addEventListener('DOMContentLoaded', () => {
    UILogic.initExpanders();
    
    const startBtn = document.getElementById('start_btn');
    const stopBtn = document.getElementById('stop_btn');
    
    startBtn.addEventListener('click', async () => {
        // Collect current config from DOM
        const config = {
            qtd_produtos: parseInt(document.getElementById('qtd_produtos').value),
            demo_mode: document.getElementById('demo_mode').checked,
            marketplaces: {
                "Amazon": {
                    active: document.getElementById('amz_active').checked,
                    access_key: document.getElementById('amz_access_key').value,
                    secret_key: document.getElementById('amz_secret_key').value,
                    tag: document.getElementById('amz_tag').value,
                    keyword: document.getElementById('amz_keyword').value
                },
                "Mercado Livre": {
                    active: document.getElementById('ml_active').checked,
                    cookies: document.getElementById('ml_cookies').value
                },
                "Shopee": {
                    active: document.getElementById('shp_active').checked,
                    affiliate_id: document.getElementById('shp_aff_id').value,
                    cookies: document.getElementById('shp_cookies').value
                },
                "Pichau": { active: document.getElementById('pic_active').checked },
                "Kabum": { active: document.getElementById('kab_active').checked }
            }
        };

        // UI Reset
        UILogic.clearResults();
        UILogic.showExportActions(false);
        startBtn.style.display = 'none';
        stopBtn.style.display = 'block';

        // Start Mining via API
        try {
            const resp = await ApiClient.startMining(config);
            if (resp.status !== 'ok') {
                UILogic.addLog(`❌ Erro: ${resp.message}`);
                return;
            }

            // Begin Streaming
            ApiClient.streamLogs(
                (data) => {
                    // onUpdate
                    UILogic.addLog(data.message);
                    if (data.progress) {
                        UILogic.updateProgress(data.progress * 100, `${Math.round(data.progress * 100)}%`);
                    }
                },
                (result) => {
                    // onResult
                    UILogic.addResult(result);
                },
                () => {
                    // onDone
                    UILogic.addLog("✅ Processo finalizado com sucesso.");
                    UILogic.updateProgress(100, "Concluído!", "var(--accent)");
                    UILogic.showExportActions(true);
                    startBtn.style.display = 'block';
                    stopBtn.style.display = 'none';
                },
                (error) => {
                    // onError
                    UILogic.addLog(`❌ Erro: ${error}`);
                    startBtn.style.display = 'block';
                    stopBtn.style.display = 'none';
                }
            );

        } catch (err) {
            UILogic.addLog(`❌ Erro de conexão: ${err.message}`);
            startBtn.style.display = 'block';
            stopBtn.style.display = 'none';
        }
    });

    stopBtn.addEventListener('click', async () => {
        await ApiClient.stopMining();
        UILogic.addLog("🛑 Interrupção solicitada...");
    });
});
