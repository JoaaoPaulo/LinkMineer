/**
 * api_client.js - Handles communication with the Flask backend.
 */

const ApiClient = {
    async startMining(config) {
        const response = await fetch('/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        return await response.json();
    },

    async stopMining() {
        const response = await fetch('/stop', {
            method: 'POST'
        });
        return await response.json();
    },

    streamLogs(onUpdate, onResult, onDone, onError) {
        const eventSource = new EventSource('/stream');
        
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'update') {
                onUpdate(data);
            } else if (data.type === 'result') {
                onResult(data.result);
            } else if (data.type === 'done') {
                onDone();
                eventSource.close();
            } else if (data.type === 'error') {
                onError(data.message);
                eventSource.close();
            }
        };

        eventSource.onerror = (err) => {
            console.error('EventSource failed:', err);
            onError('Conexão perdida com o servidor.');
            eventSource.close();
        };

        return eventSource;
    }
};
