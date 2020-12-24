from flask import Flask, session, request, render_template, redirect, url_for
from firedb_access import *
from functools import wraps

app = Flask(__name__)


auth_action = None
auth_error_msg = None


# login required decorator
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'email' in session:
            return f(*args, **kwargs)
        else:
            return redirect(url_for('auth', action="login"))
    return wrap


# Routes Home (Redirects to Dashboard)
@app.route('/')
def home():
    return redirect(url_for('dashboard'))


# Routes Dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    print(session['email'])
    return render_template("dashboard.html")


# Handles 'Not Found Error'
@app.errorhandler(404)
def not_found_error(_):
    return render_template('404.html'), 404


# routes login-signup screen
@app.route('/auth/<action>')
def auth(action):
    global auth_action, auth_error_msg
    auth_action = action
    locale_error_msg = auth_error_msg
    auth_error_msg = None
    return render_template('auth.html', action=action, error_msg=locale_error_msg)


# auth verification
@app.route('/auth', methods=['POST'])
def auth_verification():
    if request.method == 'POST' and auth_action:
        global auth_error_msg
        if auth_action == "login":
            email = request.form['email']
            password = request.form['password']
            login_success, msg = login(email, password)
            if login_success:
                session['email'] = email
                return redirect(url_for('dashboard'))
            else:
                auth_error_msg = msg
                return redirect(url_for('auth', action="login"))
        else:
            f_name = request.form['f_name']
            l_name = request.form['l_name']
            email = request.form['email']
            password = request.form['password']
            print(f_name, l_name, email, password)
            signup_success, msg = signup(f_name, l_name, email, password)
            if signup_success:
                return redirect(url_for('auth', action="login"))
            else:
                auth_error_msg = msg
                return redirect(url_for('auth', action="signup"))
    return render_template('404.html')


# logout function
@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('auth', action="login"))


# Runs App
if __name__ == '__main__':
    app.secret_key = b'c57p7p30pmjtgg4hpc06t1ny74751f'
    app.run(debug=True)

