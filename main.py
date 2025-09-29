import sqlite3
import json
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Database setup
DATABASE = 'pong_game.db'

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create players table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create games table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1_id INTEGER,
            player2_id INTEGER,
            player1_score INTEGER DEFAULT 0,
            player2_score INTEGER DEFAULT 0,
            winner_id INTEGER,
            game_duration INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player1_id) REFERENCES players (id),
            FOREIGN KEY (player2_id) REFERENCES players (id),
            FOREIGN KEY (winner_id) REFERENCES players (id)
        )
    ''')
    
    conn.commit()
    conn.close()

class PongGame:
    """Pong game logic"""
    def __init__(self):
        self.reset_game()
    
    def reset_game(self):
        """Reset game to initial state"""
        self.ball_x = 400
        self.ball_y = 300
        self.ball_velocity_x = 5
        self.ball_velocity_y = 3
        self.paddle1_y = 250  # Left paddle
        self.paddle2_y = 250  # Right paddle
        self.paddle_speed = 8
        self.paddle_height = 100
        self.paddle_width = 15
        self.ball_radius = 10
        self.canvas_width = 800
        self.canvas_height = 600
        self.player1_score = 0
        self.player2_score = 0
        self.game_over = False
        self.winner = None
    
    def update_ball(self):
        """Update ball position and handle collisions"""
        if self.game_over:
            return
        
        # Move ball
        self.ball_x += self.ball_velocity_x
        self.ball_y += self.ball_velocity_y
        
        # Ball collision with top/bottom walls
        if self.ball_y <= self.ball_radius or self.ball_y >= self.canvas_height - self.ball_radius:
            self.ball_velocity_y = -self.ball_velocity_y
        
        # Ball collision with paddles
        # Left paddle collision
        if (self.ball_x <= 50 + self.paddle_width and 
            self.ball_y >= self.paddle1_y and 
            self.ball_y <= self.paddle1_y + self.paddle_height and
            self.ball_velocity_x < 0):
            self.ball_velocity_x = -self.ball_velocity_x
            # Add some spin based on where ball hits paddle
            hit_pos = (self.ball_y - self.paddle1_y) / self.paddle_height
            self.ball_velocity_y += (hit_pos - 0.5) * 5
        
        # Right paddle collision
        if (self.ball_x >= self.canvas_width - 50 - self.paddle_width and 
            self.ball_y >= self.paddle2_y and 
            self.ball_y <= self.paddle2_y + self.paddle_height and
            self.ball_velocity_x > 0):
            self.ball_velocity_x = -self.ball_velocity_x
            # Add some spin based on where ball hits paddle
            hit_pos = (self.ball_y - self.paddle2_y) / self.paddle_height
            self.ball_velocity_y += (hit_pos - 0.5) * 5
        
        # Ball out of bounds - scoring
        if self.ball_x < 0:
            self.player2_score += 1
            self.reset_ball()
        elif self.ball_x > self.canvas_width:
            self.player1_score += 1
            self.reset_ball()
        
        # Check for game over (first to 5 points)
        if self.player1_score >= 5:
            self.game_over = True
            self.winner = "player1"
        elif self.player2_score >= 5:
            self.game_over = True
            self.winner = "player2"
    
    def reset_ball(self):
        """Reset ball to center after scoring"""
        self.ball_x = self.canvas_width // 2
        self.ball_y = self.canvas_height // 2
        self.ball_velocity_x = -self.ball_velocity_x  # Alternate direction
        self.ball_velocity_y = 3
    
    def move_paddle(self, paddle, direction):
        """Move paddle up or down"""
        if paddle == 1:  # Left paddle
            if direction == "up" and self.paddle1_y > 0:
                self.paddle1_y -= self.paddle_speed
            elif direction == "down" and self.paddle1_y < self.canvas_height - self.paddle_height:
                self.paddle1_y += self.paddle_speed
        elif paddle == 2:  # Right paddle
            if direction == "up" and self.paddle2_y > 0:
                self.paddle2_y -= self.paddle_speed
            elif direction == "down" and self.paddle2_y < self.canvas_height - self.paddle_height:
                self.paddle2_y += self.paddle_speed
    
    def get_game_state(self):
        """Return current game state"""
        return {
            "ball": {"x": self.ball_x, "y": self.ball_y},
            "paddle1": {"y": self.paddle1_y},
            "paddle2": {"y": self.paddle2_y},
            "scores": {"player1": self.player1_score, "player2": self.player2_score},
            "game_over": self.game_over,
            "winner": self.winner
        }

# Global game instance
game = PongGame()

# API Routes
@app.route('/')
def index():
    """Serve the main game page"""
    return render_template('index.html')

@app.route('/api/game/state', methods=['GET'])
def get_game_state():
    """Get current game state"""
    return jsonify(game.get_game_state())

@app.route('/api/game/reset', methods=['POST'])
def reset_game():
    """Reset the game"""
    game.reset_game()
    return jsonify({"message": "Game reset successfully"})

@app.route('/api/game/update', methods=['POST'])
def update_game():
    """Update game state (move ball, handle physics)"""
    game.update_ball()
    return jsonify(game.get_game_state())

@app.route('/api/game/move', methods=['POST'])
def move_paddle():
    """Move a paddle"""
    data = request.get_json()
    paddle = data.get('paddle')  # 1 or 2
    direction = data.get('direction')  # 'up' or 'down'
    
    if paddle in [1, 2] and direction in ['up', 'down']:
        game.move_paddle(paddle, direction)
        return jsonify({"message": "Paddle moved successfully"})
    else:
        return jsonify({"error": "Invalid paddle or direction"}), 400

@app.route('/api/players', methods=['POST'])
def create_player():
    """Create a new player"""
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return jsonify({"error": "Name is required"}), 400
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO players (name) VALUES (?)", (name,))
        player_id = cursor.lastrowid
        conn.commit()
        return jsonify({"id": player_id, "name": name, "message": "Player created successfully"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Player name already exists"}), 400
    finally:
        conn.close()

@app.route('/api/players', methods=['GET'])
def get_players():
    """Get all players"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, created_at FROM players ORDER BY name")
    players = cursor.fetchall()
    conn.close()
    
    return jsonify([{"id": p[0], "name": p[1], "created_at": p[2]} for p in players])

@app.route('/api/games', methods=['POST'])
def save_game():
    """Save game result to database"""
    data = request.get_json()
    player1_id = data.get('player1_id')
    player2_id = data.get('player2_id')
    player1_score = data.get('player1_score')
    player2_score = data.get('player2_score')
    winner_id = data.get('winner_id')
    game_duration = data.get('game_duration', 0)
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO games (player1_id, player2_id, player1_score, player2_score, winner_id, game_duration)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (player1_id, player2_id, player1_score, player2_score, winner_id, game_duration))
    
    game_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({"id": game_id, "message": "Game saved successfully"})

@app.route('/api/games', methods=['GET'])
def get_games():
    """Get all games with player names"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT g.id, g.player1_score, g.player2_score, g.winner_id, g.game_duration, g.created_at,
               p1.name as player1_name, p2.name as player2_name
        FROM games g
        LEFT JOIN players p1 ON g.player1_id = p1.id
        LEFT JOIN players p2 ON g.player2_id = p2.id
        ORDER BY g.created_at DESC
    """)
    games = cursor.fetchall()
    conn.close()
    
    return jsonify([{
        "id": g[0],
        "player1_score": g[1],
        "player2_score": g[2],
        "winner_id": g[3],
        "game_duration": g[4],
        "created_at": g[5],
        "player1_name": g[6],
        "player2_name": g[7]
    } for g in games])

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    """Get leaderboard of top players"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.name, COUNT(g.winner_id) as wins
        FROM players p
        LEFT JOIN games g ON p.id = g.winner_id
        GROUP BY p.id, p.name
        ORDER BY wins DESC, p.name
    """)
    leaderboard = cursor.fetchall()
    conn.close()
    
    return jsonify([{"name": l[0], "wins": l[1]} for l in leaderboard])

def main():
    """Initialize database and start Flask app"""
    init_db()
    print("Pong Game Server starting...")
    print("Database initialized successfully!")
    print("Visit http://localhost:5001 to play Pong!")
    app.run(debug=True, host='0.0.0.0', port=5001)

if __name__ == "__main__":
    main()
