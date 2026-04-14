from werkzeug.security import check_password_hash, generate_password_hash
from flask import Flask, jsonify,render_template,request,redirect,session
import psycopg2
import os
import pandas as pd
import random
import smtplib
from email.mime.text import MIMEText




app = Flask(__name__)
app.secret_key = "Yuvaquiz"

def get_db():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    return conn

def send_otp_email(receiver_email, otp):
    sender_email = os.environ.get("EMAIL_USER")
    app_password = os.environ.get("EMAIL_PASS")

    subject = "Your OTP for Admin Registration"
    body = f"Your OTP for admin registration is: {otp}"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['FROM'] = sender_email
    msg['To'] = receiver_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=20)
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print("OTP email sent successfully")
        return True
    except Exception as e:
        print("Failed to send OTP email:", str(e))
        return False


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        regno TEXT,
        password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions(
        id SERIAL PRIMARY KEY,
        question TEXT,
        option1 TEXT,
        option2 TEXT,
        option3 TEXT,
        option4 TEXT,
        answer TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS results(
        id SERIAL PRIMARY KEY,
        regno TEXT,
        score INTEGER,
        show_key INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS answers(
        id SERIAL PRIMARY KEY,
        regno TEXT,
        question TEXT,
        option1 TEXT,
        option2 TEXT,
        option3 TEXT,
        option4 TEXT,
        user_answer TEXT,
        correct_answer TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        id SERIAL PRIMARY KEY,
        exam_time INTEGER,
        total_questions INTEGER,
        exam_active INTEGER
    )
    """)
    #default vales 
    cursor.execute("INSERT INTO settings (id,exam_time,total_questions,exam_active) VALUES(1,1200,20,0) ON CONFLICT (id) DO NOTHING")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        is_verified INTEGER DEFAULT 0
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_otps(
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        otp TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
                   

    conn.commit()
    conn.close()

@app.route('/')
def dashboard():
    return render_template("dashboard.html")

@app.route('/get_settings')
def get_settings():

    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("SELECT exam_time,total_questions FROM settings WHERE id=1")
    data=cursor.fetchone()

    conn.close()

    return jsonify(list(data))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    
    if 'admin' not in session:
        return redirect('/admin_login')
    
    time_str=request.form['time']
    questions=request.form['questions']

    try:
        mins, secs = map(int, time_str.split(':'))
        total_seconds = mins * 60 + secs
    except :
        return "Invalid time format. Please use MM:SS" 

    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("""UPDATE settings SET exam_time=%s,total_questions=%s WHERE id=1""",(total_seconds,questions))
    conn.commit()
    conn.close()

    return "setting Updated Successfully"


@app.route('/dashboard_data')
def dashboard_data():

    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total=cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT regno) FROM results")
    attempted=cursor.fetchone()[0]

    return jsonify({
        "total": total,
        "attempted": attempted,
        "not_attempted": total - attempted
          })

@app.route('/view_questions')
def view_questions():


    if 'admin' not in session:
        return redirect('/admin_login')
    
    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("SELECT * FROM questions")
    data = cursor.fetchall()

    questions = [list(row) for row in data]

    conn.close()

    return jsonify(questions)

@app.route('/delete_question/<int:id>')
def delete_question(id):

    conn=get_db()
    cursor=conn.cursor()

    if 'admin' not in session:
        return redirect('/admin_login')

    cursor.execute("DELETE FROM questions WHERE id=%s", (id,))
    conn.commit()

    return "Deleted"

@app.route('/clear_questions')
def clear_questions():

    if 'admin' not in session:
        return redirect('/admin_login')
    
    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("TRUNCATE TABLE questions RESTART IDENTITY")
    
    conn.commit()
    conn.close()

    return "All Questions Deleted"

@app.route('/leaderboard_data')
def leaderboard_data():

    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("SELECT regno,score FROM results ORDER BY score DESC")
    data=cursor.fetchall()
    leaderboard = [list(row)for row in data]
    
    return jsonify(leaderboard)

@app.route('/register', methods=['GET','POST'])
def register():

    if request.method == 'POST':
        regno = request.form['regno'].strip()
        password = request.form['password'].strip()

        conn=get_db()
        cursor=conn.cursor()

        cursor.execute("SELECT * FROM users WHERE regno=%s", (regno,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return """<script>
            alert('User with this registration number already exists');
            window.location.href='/register';
            </script>
            """
        hashed_password=generate_password_hash(password)
        cursor.execute("INSERT INTO users (regno, password) VALUES (%s, %s)", (regno, hashed_password))
        conn.commit()
        conn.close()

        return redirect('/student_login')
    return render_template("register.html")

@app.route('/student_login', methods=['GET','POST'])
def student_login():
    conn=get_db()   
    cursor=conn.cursor()
    

    if request.method == 'POST':

        regno = request.form['regno'].strip()
        password = request.form['password'].strip()
        conn=get_db()
        cursor=conn.cursor()

        # Check in database
        cursor.execute("SELECT * FROM users WHERE regno=%s AND password=%s", (regno , password))
        user=cursor.fetchone()

        if user:
            session['user'] = regno
            conn.close()
            return redirect('/quiz')
        else:
            conn.close()
            return """<script>
            alert('Invalid login');
            window.location.href='/student_login';
            </script>
            """
    conn.close()
    
    return render_template("student_login.html")


@app.route('/admin_register', methods=['GET','POST'])
def admin_register():

    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()

        otp = str(random.randint(100000, 999999))

        conn=get_db()
        cursor=conn.cursor()

        cursor.execute("SELECT * FROM admins WHERE username=%s OR email=%s", (username,email))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return """<script>
            alert('Admin with this username or email already exists');
            window.location.href='/admin_register';
            </script>
            """
        

        cursor.execute("DELETE FROM admin_otps WHERE email=%s", (email,))
        cursor.execute("INSERT INTO admin_otps (email, otp) VALUES (%s, %s)", (email, otp))
        conn.commit()
        conn.close()

        email_sent=send_otp_email(email,otp)
        if not email_sent:
            return """
            <script>
            alert('OTP Sends fail. Please try again.');
            window.location.href='/admin_register';
            </script>
            """
        
        hashed_password = generate_password_hash(password)
        session['pending_admin'] ={
            "username": username,
            "email": email,
            "password": hashed_password
        }

    

        return """
            <script>
            alert('OTP sent successfully');
            window.location.href='/verify_admin_otp';
            </script>
            """
    
    return render_template('admin_register.html')

@app.route('/verify_admin_otp', methods=['GET','POST'])
def verify_admin_otp():

    if request.method == 'POST':
        entered_otp = request.form['otp'].strip()
        pending = session.get('pending_admin')

        if not pending:
            return """
            <script>
            alert('Session expired. Please register again');
            window.location.href='/admin_register';
            </script>
            """


        email = pending['email']

        conn=get_db()
        cursor=conn.cursor()

        cursor.execute("""SELECT otp FROM admin_otps WHERE email=%s AND created_at > NOW() - INTERVAL '5 MINUTE' ORDER BY id DESC LIMIT 1""", (email,))
        record = cursor.fetchone()

        if not record:
            conn.close()
            return """
            <script>
            alert('OTP expired or invalid. Please register again');
            </script>
            """
        
        db_otp = record[0]

        if record and entered_otp == db_otp:

            cursor.execute("""INSERT INTO admins (username, email, password, is_verified) VALUES (%s, %s, %s, %s)""", (pending['username'], pending['email'], pending['password'], 1))
            cursor.execute("DELETE FROM admin_otps WHERE email=%s", (email,))
            conn.commit()
            conn.close()
    
            session.pop('pending_admin', None)
            return """
            <script>   
            alert('Admin registered successfully');
            window.location.href='/admin_login';    
            </script>
            """
        else:
            conn.close()
            return """<script>
            alert('Invalid OTP. Please try again'); 
            window.location.href='/verify_admin_otp';
            </script>
            """
    
    return render_template('verify_admin_otp.html')

@app.route('/admin_login', methods= ['GET','POST'])
def admin_login():


    if request.method == 'POST':
        username=request.form['username'].strip()
        password=request.form['password'].strip()

        conn=get_db()
        cursor=conn.cursor()

        cursor.execute("SELECT * FROM admins WHERE username=%s AND is_verified=%s", (username, 1))
        admin=cursor.fetchone()
        conn.close()

        if admin and check_password_hash(admin[3],password):
            session['admin'] = username
            return redirect('/admin_dashboard')
        else:
            return """
            <script>
            alert('Invalid login or account not verified');
            window.location.href='/admin_login';
            </script>
            """
        
    return render_template('admin_login.html')

@app.route('/admin_forgot_password', methods=['GET', 'POST'])
def admin_forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip()

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM admins WHERE email=%s", (email,))
        admin = cursor.fetchone()

        if not admin:
            conn.close()
            return """
            <script>
            alert('Admin email not found');
            window.location.href='/admin_forgot_password';
            </script>"""

        otp = str(random.randint(100000, 999999))

        cursor.execute("DELETE FROM admin_otps WHERE email=%s", (email,))
        cursor.execute(
            "INSERT INTO admin_otps (email, otp) VALUES (%s, %s)",
            (email, otp)
        )
        conn.commit()
        conn.close()

        send_otp_email(email, otp)

        session['reset_email'] = email
        return """
        <script>
         alert('OTP sent successfully');
         window.location.href='/verify_reset_otp';
        </script>
        """

    return render_template("admin_forgot_password.html")

@app.route('/verify_reset_otp', methods=['GET', 'POST'])
def verify_reset_otp():
    if request.method == 'POST':
        entered_otp = request.form['otp'].strip()
        email = session.get('reset_email')

        if not email:
            return """
            <script>
            alert('Session expired. Please try again');
            window.location.href='/admin_forgot_password';
            </script>
            """

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""SELECT otp FROM admin_otps WHERE email=%s AND created_at > NOW() - INTERVAL '5 MINUTE' ORDER BY id DESC LIMIT 1""", (email,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return """<script>
            alert('OPT not found');
            window.location.href='/admin_forgot_password';
            </script>"""

        db_otp = row[0]

        if entered_otp == db_otp:
            conn.close()
            session['otp_verified'] = True
            return """
            <script>
            alert('OTP verified successfully');
            window.location.href='/admin_reset_password';
            </script>
            """
        else:
            conn.close()
            return """
            <script>
            alert('Invalid OTP');
            window.location.href='/verify_reset_otp';
            </script>
            """

    return render_template("verify_reset_otp.html")

@app.route('/admin_reset_password', methods=['GET', 'POST'])
def admin_reset_password():
    email = session.get('reset_email')
    otp_verified = session.get('otp_verified')

    if not email or not otp_verified:
        return """
        <script>
        alert('Unauthorized access');
        window.location.href='/admin_forgot_password';
        </script>
        """

    if request.method == 'POST':
        new_password = request.form['new_password'].strip()
        confirm_password = request.form['confirm_password'].strip()

        if new_password != confirm_password:
            return """
            <script>
            alert('Passwords do not match');
            window.location.href='/admin_reset_password';
            </script>
            """

        conn = get_db()
        cursor = conn.cursor()
        hashed_password = generate_password_hash(new_password)

        cursor.execute("UPDATE admins SET password=%s WHERE email=%s",(hashed_password, email))

        cursor.execute("DELETE FROM admin_otps WHERE email=%s", (email,))
        conn.commit()
        conn.close()

        session.pop('reset_email', None)
        session.pop('otp_verified', None)

        return """
            <script>
            alert('Password updated successfully');
            window.location.href='/admin_login';
            </script>
            """

    return render_template("admin_reset_password.html")

@app.route('/resend_otp')
def resend_otp():
    pending = session.get('pending_admin')
    email = session.get('reset_email') or (pending['email'] if pending else None)

    if not email:
        return """
        <script>
        alert('Session expired');
        window.location.href='/admin_register';
        </script>
        """

    otp = str(random.randint(100000, 999999))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM admin_otps WHERE email=%s", (email,))
    cursor.execute("INSERT INTO admin_otps (email, otp) VALUES (%s, %s)", (email, otp))

    conn.commit()
    conn.close()

    send_otp_email(email, otp)

    return """
    <script>
    alert('OTP resent successfully');
    window.history.back();
    </script>
    """

@app.route('/admin_dashboard')
def admin_dashboard():

    if 'admin' not in session:
        return redirect('/admin_login')
    
    return render_template("admin_dashboard.html")

@app.route('/upload_users', methods=['POST'])
def upload_users():
    if 'admin' not in session:
        return redirect('/admin_login')
    
    file = request.files['file']
    df = pd.read_excel(file)

    df.columns = df.columns.str.strip().str.lower()

    conn=get_db()
    cursor=conn.cursor()

    for i, row in df.iterrows():
        cursor.execute("INSERT INTO users (regno, password) VALUES (%s, %s)", (str(row['regno']), str(row['password'])))

    conn.commit()
    conn.close()

    return "Users uploaded successfully"


@app.route('/upload', methods=['POST'])
def upload():

    if 'admin' not in session:
        return redirect('/admin_login')
    
    file = request.files['file']
    df = pd.read_excel(file)

    df.columns = df.columns.str.strip().str.lower()
    

    conn = get_db()
    cursor = conn.cursor()

    for i, row in df.iterrows():
        cursor.execute("""
        INSERT INTO questions(question, option1, option2, option3, option4, answer)
        VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            str(row['question']),
            str(row['option1']),
            str(row['option2']),
            str(row['option3']),
            str(row['option4']),
            str(row['answer'])
        ))

    conn.commit()
    conn.close()
    
    return redirect('/admin_dashboard')


@app.route('/quiz')
def quiz():
    conn=get_db()
    cursor=conn.cursor()

    if 'user' not in session:
        return redirect('/student_login')
    
    
    regno = session['user']
    
    cursor.execute("SELECT exam_active FROM settings WHERE id=1")
    exam_active = cursor.fetchone()[0]
    if exam_active == 0:
        return """
        <script>
        alert('Exam Not Active Yet. Please Try Again Later.');
        window.location.href = '/';
        </script>
        """

    cursor.execute("SELECT * FROM results WHERE regno=%s",(regno,))
    already = cursor.fetchone()

    if already:
        return """
        <script>
        alert('You have already attempted the Assessment.');
        window.location.href = '/';
        </script>
        """

    cursor.execute("SELECT * FROM questions")
    questions=[list(q) for q in cursor.fetchall()]

    print("SESSION USER:", session.get('user'))  # Debugging line
   
    cursor.execute("SELECT exam_time, total_questions FROM settings WHERE id=1")
    settings=cursor.fetchone()
    exam_time=settings[0]
    total_questions=settings[1]

    questions = [list(q) for q in questions]

    if len(questions) < total_questions:
        random_questions = questions
    else:   
        random_questions = random.sample(questions,total_questions)

    session['quiz_questions'] = random_questions
    session['exam_time'] = exam_time

    return render_template("quiz.html",questions=random_questions)

@app.route('/submit',methods=['POST'])
def submit():

    conn=get_db()
    cursor=conn.cursor()

    if 'user' not in session:
        return redirect('/')
    
    regno=session.get('user')
    questions=session.get('quiz_questions') 

    correct=0
    wrong=0
    not_attempt=0

    for q in questions:

        qid=str(q[0])
        question = q[1]
        o1,o2,o3,o4 = q[2],q[3],q[4],q[5]
        correct_ans = q[6]

        user_answer = request.form.get(qid)

        if user_answer is None:
            not_attempt +=1

        elif user_answer == correct_ans:
            correct +=1

        else:
            wrong +=1
            
        cursor.execute("""INSERT INTO answers(regno,question,option1,option2,option3,option4,user_answer,correct_answer) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                   (regno,question,o1,o2,o3,o4,user_answer,correct_ans))
        
          
    conn.commit()
    conn.close()

    total =len(questions)
    score = correct
    percentage = round((score/total)*100,2)

    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("INSERT INTO results (regno, score, show_key) VALUES (%s,%s,0)", (regno,score))
    conn.commit()
    conn.close()

    session.pop('user', None)

    return render_template("result.html",score=score,correct=correct,wrong=wrong,not_attempt=not_attempt,percentage=percentage,total=total)


@app.route('/release_key')
def release_key():

    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("UPDATE results SET show_key=1")
    conn.commit()
    conn.close()

    return "Answer Key Released Successfully" \
          "<a href='/admin_dashboard'>go home</a>"

@app.route('/answer_key', methods=['GET','POST'])
def answer_key():
    conn=get_db()
    cursor=conn.cursor()

    if request.method == 'POST':

        regno = request.form['regno']

        cursor.execute("SELECT show_key FROM results WHERE regno=%s", (regno,))
        status = cursor.fetchone()

        if not status:
            return "Invalid Reg Number"

        if status[0] == 0:
            return "Answer Key Not Released Yet"

        cursor.execute("SELECT * FROM answers WHERE regno=%s", (regno,))
        data = cursor.fetchall()

        return render_template("answer_key_view.html", data=data)

    return render_template("answer_key_login.html")

@app.route('/reset_exam')
def reset_exam():
    
    if 'admin' not in session:
        return redirect('/admin_login')
    
    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("TRUNCATE TABLE results RESTART IDENTITY")
    cursor.execute("TRUNCATE TABLE answers RESTART IDENTITY")
    conn.commit()
    conn.close()

    return "Exam Reset Successfully"

@app.route('/download_users_sample')
def download_users_sample():
    
    import pandas as pd
    from flask import send_file
    df = pd.DataFrame({
        'regno': ['101', '102', '103'],
        'password': ['1234', 'abcd', 'pass']
    })
    file_path ="users_sample.xlsx"
    df.to_excel(file_path, index=False)
    return send_file(file_path, as_attachment=True)

@app.route('/download_questions_sample')
def download_questions_sample():
    import pandas as pd
    from flask import send_file
    df = pd.DataFrame({
        'question': ['Capital of India'],
        'option1': ['Delhi'],
        'option2': ['Mumbai'],
        'option3': ['Chennai'],
        'option4': ['Kolkata'],
        'answer': ['Delhi']
    })
    file_path ="questions_sample.xlsx"
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True) 

@app.route('/start_exam')
def start_exam():

    if 'admin' not in session:
        return redirect('/admin_login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("UPDATE settings SET exam_active=1 WHERE id=1")

    conn.commit()
    conn.close()

    return "Exam Started"

@app.route('/stop_exam')
def stop_exam():

    if 'admin' not in session:
        return redirect('/admin_login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("UPDATE settings SET exam_active=0 WHERE id=1")

    conn.commit()
    conn.close()

    return "Exam Stopped"

@app.route('/view_users')
def view_users():
    if 'admin' not in session:
        return redirect('/admin_login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users")
    data = cursor.fetchall()

    users= [list(row) for row in data]

    conn.close()

    return jsonify(users)

@app.route('/delete_user/<int:id>')
def delete_user(id):
    if 'admin' not in session:
        return redirect('/admin_login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM users WHERE id=%s", (id,))
    conn.commit()
    conn.close()

    return "Deleted"

@app.route('/logout')
def logout():
    session.clear()
    return render_template('dashboard.html')


@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__=="__main__":
    init_db()