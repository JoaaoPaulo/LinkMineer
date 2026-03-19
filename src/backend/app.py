import os
import io
import json
import queue
import threading
from flask import Flask, render_template, request, Response, send_file, jsonify

from src.backend.config.settings import settings
from src.backend.services.mining_engine import MiningEngine
from src.backend.services.data_exporter import DataExporter

app = Flask(__name__, 
            static_folder=settings.STATIC_DIR, 
            template_folder=settings.TEMPLATE_DIR)

# Global state for current mining session
current_results = []
log_queue = queue.Queue()
stop_event = threading.Event()
mining_thread = None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start_mining():
    global current_results, mining_thread, stop_event, log_queue
    
    if mining_thread and mining_thread.is_alive():
        return jsonify({"status": "error", "message": "Mineração já em curso."}), 400
        
    config = request.json
    current_results = []
    stop_event.clear()
    log_queue = queue.Queue() # Clear queue
    
    config["stop_event"] = stop_event
    engine = MiningEngine(config, log_queue)
    mining_thread = engine.run()
    
    return jsonify({"status": "ok", "message": "Mineração iniciada."})

@app.route("/stop", methods=["POST"])
def stop_mining():
    global stop_event
    stop_event.set()
    return jsonify({"status": "ok", "message": "Interrupção solicitada."})

@app.route("/stream")
def stream():
    """Server-Sent Events route to stream logs and results to the frontend."""
    def event_stream():
        while True:
            try:
                # Use a small timeout to avoid blocking the generator loop indefinitely
                item = log_queue.get(timeout=300) 
                
                if item.get("type") == "done":
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    break
                    
                if item.get("type") == "result":
                    current_results.append(item["result"])
                    
                yield f"data: {json.dumps(item)}\n\n"
            except queue.Empty:
                # Send a keep-alive comment
                yield ": keep-alive\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                break
                
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/download/<fmt>")
def download(fmt):
    global current_results
    if not current_results:
        return "Nenhum dado disponível", 404
        
    if fmt == "csv":
        data = DataExporter.to_csv(current_results)
        return send_file(
            io.BytesIO(data),
            mimetype="text/csv",
            as_attachment=True,
            download_name="links.csv"
        )
    elif fmt == "xlsx":
        data = DataExporter.to_xlsx(current_results)
        return send_file(
            io.BytesIO(data),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="links.xlsx"
        )
    return "Formato inválido", 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.PORT, debug=not settings.IS_SERVER)
