from flask import Flask, request, jsonify
from training_loop import run_training

app = Flask(__name__)

@app.route('/train', methods=['POST'])
def train():
    try:
        episodes = int(request.json.get('episodes', 5))
    except Exception:
        episodes = 5
    stats = run_training(num_episodes=episodes, verbose=False)
    return jsonify({"status": "ok", "stats": stats})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
