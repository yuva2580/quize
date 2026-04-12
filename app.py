
from flask import Flask, jsonify,render_template,request,redirect,session
import psycopg2
import os
import pandas as pd
import random


app = Flask(__name__)
app.secret_key = "Yuvaquiz"

def get_db():
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
    return conn

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
            return "User already exists"
        
        cursor.execute("INSERT INTO users (regno, password) VALUES (%s, %s)", (regno, password))
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

        # Check in database
        cursor.execute("SELECT * FROM users WHERE regno=%s AND password=%s", (regno , password))
        user=cursor.fetchone()

        if user:
            session['user'] = regno
            conn.close()
            return redirect('/quiz')
        else:
            conn.close()
            return "Invalid login"
        
    conn.close()
    
    return render_template("student_login.html")


@app.route('/admin_login', methods= ['GET','POST'])
def admin_login():


    if request.method == 'POST':
        username=request.form['username']
        password=request.form['password']

        if username=="admin" and password=="admin@123":
            session['admin'] = username
            return redirect('/admin_dashboard')
        
    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():

    if 'admin' not in session:
        return redirect('/admin_login')
    
    return render_template("admin_dashboard.html")

@app.route('/upload_users', methods=['POST'])
def upload_users():
    if 'admin' not in session:
        return redirect('/admin_login')
    
    file= request.files['file']
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
        return "Exam Not Active Yet. Please Try Again Later. <a href='/'>Go Home</a>"
    
    cursor.execute("SELECT * FROM results WHERE regno=%s",(regno,))
    already = cursor.fetchone()

    if already:
        return "You have already attempted the Assesment. <a href='/'>Go Home</a>"
    
    
    
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

    cursor.execute("TRUNCATE TABLE results RESTART INDENTITY")
    cursor.execute("TRUNCATE TABLE answers RESTART INDENTITY")
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