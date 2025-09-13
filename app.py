from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import mysql.connector

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # For session management

db = mysql.connector.connect(
    host='localhost',
    user='root',
    password='root',
    database='simple_social'
)
cursor = db.cursor(dictionary=True)

@app.route('/feed_partial')
def feed_partial():
    if 'user_id' not in session:
        return '', 401
    cursor.execute('''SELECT posts.id, posts.content, posts.created_at, users.username, posts.user_id 
                      FROM posts JOIN users ON posts.user_id = users.id 
                      ORDER BY posts.created_at DESC''')
    posts = cursor.fetchall()
    post_ids = [post['id'] for post in posts]
    like_counts = {}
    user_likes = set()
    if post_ids:
        format_strings = ','.join(['%s'] * len(post_ids))
        cursor.execute(f'SELECT post_id, COUNT(*) as cnt FROM post_likes WHERE post_id IN ({format_strings}) GROUP BY post_id', tuple(post_ids))
        for row in cursor.fetchall():
            like_counts[row['post_id']] = row['cnt']
        cursor.execute(f'SELECT post_id FROM post_likes WHERE user_id=%s AND post_id IN ({format_strings})', (session['user_id'], *post_ids))
        user_likes = set(row['post_id'] for row in cursor.fetchall())
    for post in posts:
        post['like_count'] = like_counts.get(post['id'], 0)
        post['liked_by_user'] = post['id'] in user_likes
    # Render only the feed-list part
    return render_template('feed_partial.html', posts=posts, user_id=session['user_id'])

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('feed'))
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor.execute('SELECT * FROM users WHERE username=%s', (username,))
        if cursor.fetchone():
            return render_template('signup.html', error='Username already exists')
        cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s)', (username, password))
        db.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor.execute('SELECT * FROM users WHERE username=%s AND password=%s', (username, password))
        user = cursor.fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('feed'))
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/feed', methods=['GET', 'POST'])
def feed():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        content = request.form['content']
        cursor.execute('INSERT INTO posts (user_id, content) VALUES (%s, %s)', (session['user_id'], content))
        db.commit()
        return redirect(url_for('feed'))
    cursor.execute('''SELECT posts.id, posts.content, posts.created_at, users.username, posts.user_id 
                      FROM posts JOIN users ON posts.user_id = users.id 
                      ORDER BY posts.created_at DESC''')
    posts = cursor.fetchall()
    # Get like counts and whether current user liked each post
    post_ids = [post['id'] for post in posts]
    like_counts = {}
    user_likes = set()
    if post_ids:
        format_strings = ','.join(['%s'] * len(post_ids))
        cursor.execute(f'SELECT post_id, COUNT(*) as cnt FROM post_likes WHERE post_id IN ({format_strings}) GROUP BY post_id', tuple(post_ids))
        for row in cursor.fetchall():
            like_counts[row['post_id']] = row['cnt']
        cursor.execute(f'SELECT post_id FROM post_likes WHERE user_id=%s AND post_id IN ({format_strings})', (session['user_id'], *post_ids))
        user_likes = set(row['post_id'] for row in cursor.fetchall())
    for post in posts:
        post['like_count'] = like_counts.get(post['id'], 0)
        post['liked_by_user'] = post['id'] in user_likes
    return render_template('feed.html', posts=posts, user_id=session['user_id'], username=session['username'])
@app.route('/like_post/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    try:
        cursor.execute('INSERT IGNORE INTO post_likes (user_id, post_id) VALUES (%s, %s)', (session['user_id'], post_id))
        db.commit()
        # Get new like count
        cursor.execute('SELECT COUNT(*) as cnt FROM post_likes WHERE post_id=%s', (post_id,))
        like_count = cursor.fetchone()['cnt']
        return jsonify({'success': True, 'like_count': like_count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/unlike_post/<int:post_id>', methods=['POST'])
def unlike_post(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    try:
        cursor.execute('DELETE FROM post_likes WHERE user_id=%s AND post_id=%s', (session['user_id'], post_id))
        db.commit()
        cursor.execute('SELECT COUNT(*) as cnt FROM post_likes WHERE post_id=%s', (post_id,))
        like_count = cursor.fetchone()['cnt']
        return jsonify({'success': True, 'like_count': like_count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/post_likes/<int:post_id>')
def post_likes(post_id):
    # Returns a list of usernames who liked the post
    cursor.execute('''SELECT users.username FROM post_likes JOIN users ON post_likes.user_id = users.id WHERE post_likes.post_id=%s''', (post_id,))
    users = [row['username'] for row in cursor.fetchall()]
    return jsonify({'users': users})

@app.route('/delete_post/<int:post_id>')
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cursor.execute('SELECT * FROM posts WHERE id=%s', (post_id,))
    post = cursor.fetchone()
    if post and post['user_id'] == session['user_id']:
        cursor.execute('DELETE FROM posts WHERE id=%s', (post_id,))
        db.commit()
    return redirect(url_for('feed'))

if __name__ == '__main__':
    app.run(debug=True)
