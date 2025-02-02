from flask import Flask, jsonify, request  # Add render_template here
from utils import parse_email_content, place_trade


app = Flask(__name__)  # This line tells Flask where to look for templates

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "online",
        "message": "Email monitor API is running",
        "endpoints": {
            "/": "This information",
            "/start": "Start email monitor (POST)",
            "/stop": "Stop email monitor (POST)",
            "/status": "Get monitor status (GET)"
        }
    })

@app.route('/trade', methods=['POST'])
def trade():
    """Start email monitor with configuration"""
    try:
        data = request.get_json()
        
        # Get configuration from request
        email = data.get('email')
        if email:
            symbol, to_position, from_position = parse_email_content(email)

        if symbol and to_position and from_position:
            place_trade(symbol, to_position, from_position)

        
        return jsonify({
            "status": "success",
            "config": {
                "email": email
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)

