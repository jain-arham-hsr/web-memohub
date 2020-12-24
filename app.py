from flask import Flask, session, request, render_template, redirect, url_for
from firedb_access import *
from functools import wraps

app = Flask(__name__)

app.config.from_object('config.BaseConfig')


# login required decorator
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'uid' in session:
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
    return render_template("dashboard.html")


# Handles 'Not Found Error'
@app.errorhandler(404)
def not_found_error(_):
    return render_template('404.html'), 404

# Handles 'Method not Allowed Error'
@app.errorhandler(405)
def method_not_allowed_error(_):
    return render_template('404.html'), 405


# routes login-signup screen
@app.route('/auth/<action>')
def auth(action):
    locale_error_msg = session.get('auth_error_msg', None)
    session.pop('auth_error_msg', None)
    return render_template('auth.html', action=action, error_msg=locale_error_msg)


# auth verification
@app.route('/auth', methods=['POST'])
def auth_verification():
    if request.method == 'POST':
        if request.form['auth-submit'] == "Log In":
            email = request.form['email']
            password = request.form['password']
            login_success, msg = login(email, password)
            if login_success:
                session['uid'] = msg
                return redirect(url_for('dashboard'))
            else:
                session['auth_error_msg'] = msg
                return redirect(url_for('auth', action="login"))
        else:
            f_name = request.form['f_name']
            l_name = request.form['l_name']
            email = request.form['email']
            password = request.form['password']
            if request.form['auth-submit'] == 'Sign Up as Student':
                user_category = "Student"
            elif request.form['auth-submit'] == 'Sign Up as Teacher':
                user_category = "Teacher"
            signup_success, msg = signup(f_name, l_name, email, password, user_category)
            if signup_success:
                return redirect(url_for('auth', action="login"))
            else:
                session['auth_error_msg'] = msg
                return redirect(url_for('auth', action="signup"))
    return render_template('404.html')


@app.route('/dashboard/<subject>/')
@login_required
def subject(subject):
    return retrieve_data_from_db(subject)


# logout function
@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('auth', action="login"))


# Runs App
if __name__ == '__main__':
    app.run()
