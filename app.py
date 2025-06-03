from flask import Flask, render_template, request, redirect, session, flash
from db_config import get_connection
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = "thoughts_project"

def time_ago(post_time):
    now = datetime.now()
    diff = now - post_time

    seconds = diff.total_seconds()
    minutes = seconds // 60
    hours = minutes // 60

    if seconds < 60:
        return "Just now"
    elif minutes < 60:
        return f"{int(minutes)} minutes ago"
    elif hours < 24:
        return f"{int(hours)} hours ago"
    else:
        return post_time.strftime("%Y-%m-%d %H:%M")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        identifier = request.form['username']  # Could be username or email
        password = request.form['password']

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE (username = %s OR email = %s) AND password = %s", 
                       (identifier, identifier, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['username'] = user[1]  # Assuming username is the second column
            return redirect('/dashboard')
        else:
            msg = 'Incorrect username/email or password!'
    
    return render_template('login.html', msg=msg)

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, title, content, created_at, id, views, likes FROM posts ORDER BY created_at DESC")
    raw_posts = cursor.fetchall()
    conn.close()

    # Convert to "5 minutes ago" format
    posts = []
    for username, title, content, created_at, post_id, views, likes in raw_posts:
        formatted_time = time_ago(created_at)
        posts.append((username, title, content, formatted_time, post_id, views, likes))

    return render_template('dashboard.html', username=session['username'], posts=posts)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        new_username = request.form['username']
        new_email = request.form['email']
        new_password = request.form['password']

        if len(new_password) < 6:
            flash("Password must be at least 6 characters.")
            return redirect('/edit_profile')

        cursor.execute("UPDATE users SET username=%s, email=%s, password=%s WHERE username=%s",
                       (new_username, new_email, new_password, session['username']))
        conn.commit()
        conn.close()

        # Update session
        session['username'] = new_username
        flash("Profile updated successfully!")
        return redirect('/dashboard')

    # Get current user details
    cursor.execute("SELECT username, email FROM users WHERE username=%s", (session['username'],))
    user = cursor.fetchone()
    conn.close()

    return render_template('edit_profile.html', user=user)

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        conn = get_connection()
        cursor = conn.cursor()

        # Check if username or email already exists
        cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        existing_user = cursor.fetchone()

        if existing_user:
            msg = 'Username or Email already exists!'
        else:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, password))
            conn.commit()
            return redirect('/login')

        conn.close()

    return render_template('register.html', msg=msg)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/')

@app.route('/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if 'username' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()
    # Delete only if post belongs to current user
    sql = "DELETE FROM posts WHERE id = %s AND username = %s"
    val = (post_id, session['username'])
    cursor.execute(sql, val)
    conn.commit()
    conn.close()

    return redirect('/dashboard')

@app.route('/post/<int:post_id>')
def view_post(post_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, title, content, created_at FROM posts WHERE id = %s", (post_id,))
    post = cursor.fetchone()
    conn.close()

    if post:
        return render_template('view_post.html', post=post)
    return "Post not found", 404

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title, content, created_at, id FROM posts WHERE username = %s ORDER BY created_at DESC", (session['username'],))
    user_posts = cursor.fetchall()
    conn.close()

    return render_template('profile.html', username=session['username'], posts=user_posts)

@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'username' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()

    # Get current content
    if request.method == 'GET':
        sql = "SELECT content FROM posts WHERE id = %s AND username = %s"
        cursor.execute(sql, (post_id, session['username']))
        result = cursor.fetchone()
        conn.close()

        if result:
            return render_template('edit.html', content=result[0])
        else:
            return "Unauthorized or post not found", 403

    # Update post
    if request.method == 'POST':
        new_content = request.form['content']
        sql = "UPDATE posts SET content = %s WHERE id = %s AND username = %s"
        val = (new_content, post_id, session['username'])
        cursor.execute(sql, val)
        conn.commit()
        conn.close()

        return redirect('/dashboard')

@app.route('/post', methods=['GET', 'POST'])
def post():
    if 'username' not in session:
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        username = session['username']

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO posts (username, title, content) VALUES (%s, %s, %s)", (username, title, content))
        conn.commit()
        conn.close()

        return redirect('/dashboard')

    return render_template('post.html')

@app.route('/story/<int:post_id>', methods=['GET', 'POST'])
def view_story(post_id):
    if 'username' not in session:
        return redirect('/login')

    user = session['username']
    conn = get_connection()
    cursor = conn.cursor()

    # Check if user has already interacted with this post
    cursor.execute("SELECT viewed, liked FROM post_interactions WHERE user = %s AND post_id = %s", (user, post_id))
    result = cursor.fetchone()

    viewed, liked = False, False
    if result:
        viewed, liked = result
    else:
        # Create interaction record
        cursor.execute("INSERT INTO post_interactions (user, post_id, viewed, liked) VALUES (%s, %s, %s, %s)", (user, post_id, False, False))
        conn.commit()

    # Increment view only if not viewed before
    if not viewed:
        cursor.execute("UPDATE posts SET views = views + 1 WHERE id = %s", (post_id,))
        cursor.execute("UPDATE post_interactions SET viewed = TRUE WHERE user = %s AND post_id = %s", (user, post_id))
        conn.commit()

    # Handle Like button press
    if request.method == 'POST' and not liked:
        cursor.execute("UPDATE posts SET likes = likes + 1 WHERE id = %s", (post_id,))
        cursor.execute("UPDATE post_interactions SET liked = TRUE WHERE user = %s AND post_id = %s", (user, post_id))
        conn.commit()
        liked = True  # to avoid another like immediately

    # Fetch the updated post
    cursor.execute("SELECT username, title, content, created_at, views, likes FROM posts WHERE id = %s", (post_id,))
    post = cursor.fetchone()
    conn.close()

    if post:
        return render_template('story.html', post=post, liked=liked)
    else:
        return "Story not found", 404


if __name__ == '__main__':
    app.run(debug=True)
