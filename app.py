from flask import Flask, session, request, render_template, redirect, url_for, flash
from werkzeug.utils import secure_filename
from firebase_access import *
import re
from datetime import datetime
from functools import wraps

app = Flask(__name__)

app.config.from_object('config.BaseConfig')
ALLOWED_EXTENSIONS = {'txt': 'text/plain',
                      'pdf': 'application/pdf',
                      'png': 'image/png',
                      'jpg': 'image/jpeg',
                      'jpeg': 'image/jpeg',
                      'gif': 'image/gif',
                      'mp4': 'video/mp4',
                      'mp3': 'audio/mpeg',
                      'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}

theme = {
    'light': {
        'theme_name': 'light',
        'nav': 'bg-primary',
        'buttons': 'btn-primary',
        'body-bg': '#ffffff',
        'text': 'text-dark',
        'cards': 'bg-light',
        'list-group-item-bg': '#007BFF'
    },
    'dark': {
        'theme_name': 'dark',
        'nav': 'bg-dark',
        'buttons': 'btn-secondary',
        'body-bg': '#212529',
        'text': 'text-white',
        'cards': 'bg-dark',
        'list-group-item-bg': '#6C757D'
    }
}

error_codes = {

}


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
    if session.get('uid', None):
        return redirect(url_for('dashboard'))
    else:
        return render_template('home.html', signed_out=True)


# Routes Dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    if session.get('user_cat') == 'teacher':
        template = 'teacher_dashboard.html'
    else:
        template = 'dashboard.html'
    batches = retrieve_data_from_db(f"users/{session.get('uid')}/batches") or []
    for index in range(len(batches)):
        batch_data = retrieve_data_from_db(f"batches/{batches[index]}")
        batch_data['creatorName'] = firebase_admin.auth.get_user(batch_data['created-by']).display_name
        batches[index] = batch_data
    decks = list(zip(*[iter(batches)]*3))
    if len(batches) % 3 != 0:
        decks.append(tuple(batches[(-1) * (len(batches) % 3):]))
    if decks == [()]:
        decks = None
    session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
    return render_template(template, decks=decks, profile_data=session.get('profile_data'))


# Handles 'Not Found Error'
@app.errorhandler(404)
def not_found_error(_):
    if session.get('uid', None):
        session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
        signed_out = False
    else:
        signed_out = True
    return render_template('404.html', profile_data=session.get('profile_data'), signed_out=signed_out), 404


# Handles 'Method not Allowed Error'
@app.errorhandler(405)
def method_not_allowed_error(_):
    if session.get('uid', None):
        session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
        signed_out = False
    else:
        signed_out = True
    return render_template('404.html', profile_data=session.get('profile_data'), signed_out=signed_out), 405


# routes login-signup screen
@app.route('/auth/<action>')
def auth(action):
    locale_error_msg = session.get('error_msg', None)
    session.pop('error_msg', None)
    return render_template('auth.html', action=action, error_msg=locale_error_msg, signed_out=True)


# auth verification
@app.route('/auth', methods=['POST'])
def auth_verification():
    if request.method == 'POST':
        if request.form['auth-submit'] == "Log In":
            email = request.form['email']
            password = request.form['password']
            login_success, msg = login(email, password)
            if login_success:
                session['uid'] = msg[0]
                session['display_name'] = msg[1]
                session['email'] = email
                session['user_cat'] = retrieve_data_from_db(f"users/{session.get('uid')}/category")
                session['profile_data'] = {
                    "displayName": msg[1],
                    "email": email,
                    "userCat": session.get('user_cat'),
                    "theme": theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
                }
                return redirect(url_for('dashboard'))
            else:
                session['error_msg'] = msg
                return redirect(url_for('auth', action="login"))
        else:
            f_name = request.form['f_name']
            l_name = request.form['l_name']
            email = request.form['email']
            password = request.form['password']
            if request.form['auth-submit'] == 'Sign Up as Student':
                user_category = "student"
            elif request.form['auth-submit'] == 'Sign Up as Teacher':
                user_category = "teacher"
            signup_success, msg = signup(f_name, l_name, email, password, user_category)
            if signup_success:
                return redirect(url_for('auth', action="login"))
            else:
                session['error_msg'] = msg
                return redirect(url_for('auth', action="signup"))
    session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
    return render_template('404.html')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS.keys()


@app.route('/invite', methods=['POST'])
@login_required
def invite():
    if request.method == 'POST':
        batch_id = session.get('last_batch_opened')
        email = request.form['email']
        success, r = get_user_info(email)
        if success:
            if f"batch_{batch_id}" not in (retrieve_data_from_db(f'users/{r.uid}/batches') or []):
                cat = retrieve_data_from_db(f'users/{r.uid}/category')
                append_to_list_db(f'users/{r.uid}/batches', f"batch_{batch_id}")
                append_to_list_db(f'batches/batch_{batch_id}/participants', (request.form['email'], cat))
                send_text_message(batch_id, "MemoHub", f"'{r.display_name}' added to this batch.")
            else:
                session['error_msg'] = "User already enrolled in this batch. Please enter email of some other user."
        elif r == 'EMAIL_NOT_FOUND':
            append_to_list_db(f"pendingInvitation/{re.sub('[^a-zA-Z]', '_', email)}", f"batch_{batch_id}")
            append_to_list_db(f'batches/batch_{batch_id}/participants', (request.form['email'], 'undefined'))
            send_text_message(batch_id, "MemoHub", f"'{email}' added to this batch.")
        else:
            session['error_msg'] = r
        return redirect(url_for('render_batch_data', batch_id=batch_id))
    session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
    return render_template('404.html')


@app.route('/dashboard/createNewBatch/', methods=['POST'])
@login_required
def new_batch():
    if request.method == 'POST':
        if do_duplicate_batches_exist(request.form['class-name'],
                                      request.form['section'],
                                      request.form['subject']):
            flash("Couldn't create batch due to duplicate data.")
            return redirect(url_for('dashboard'))
        batch_id = datetime.now().strftime("%Y%m%d%H%M%S%f%z")
        save_data_to_db(f'batches/batch_{batch_id}', {
            'name': request.form['class-name'],
            'section': request.form['section'],
            'subject': request.form['subject'],
            'batch_id': batch_id,
            'created-by': session.get('uid'),
            'creation-date': datetime.now().strftime("%B %d, %Y"),
            'messages': [
                {
                    'timestamp': datetime.now().strftime("%H:%M %B %d, %Y"),
                    'type': 'text',
                    'sender': 'MemoHub',
                    'value': f'{request.form["class-name"]} "{request.form["section"]}" ({request.form["subject"]}) created.'
                }
            ],
            'participants': [(session.get('email'), session.get('user_cat'))],
            'active': True
        })
        append_to_list_db(f'users/{session["uid"]}/batches', f'batch_{batch_id}')
        return redirect(url_for('dashboard'))
    session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
    return render_template('404.html')


def do_duplicate_batches_exist(name, section, subject):
    batches = retrieve_data_from_db(f'users/{session["uid"]}/batches') or []
    for batch in batches:
        corresponding_batch_data = retrieve_data_from_db(f'batches/{batch}')
        if all([corresponding_batch_data['name'] == name,
                corresponding_batch_data['section'] == section,
                corresponding_batch_data['subject'] == subject]):
            return True
    return False


@app.route('/batch/<batch_id>')
@login_required
def render_batch_data(batch_id):
    if f"batch_{batch_id}" in retrieve_data_from_db(f'users/{session["uid"]}/batches'):
        session['last_batch_opened'] = batch_id
        batch_data = retrieve_data_from_db(f'batches/batch_{batch_id}')
        locale_error_msg = session.get('error_msg')
        session.pop('error_msg', None)
        for idx, msg in enumerate(batch_data['messages']):
            if msg['type'] == 'text':
                batch_data['messages'][idx]['value'] = msg['value'].replace("\r\n", "<br>")
        batch_data['participants'].remove([session.get('email'), session.get('user_cat')])
        is_creator = session.get('uid', None) == retrieve_data_from_db(f'batches/batch_{batch_id}/created-by')
        session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
        return render_template('memos.html', cat=session.get('user_cat'), batch_data=batch_data, error_msg=locale_error_msg, is_creator=is_creator, profile_data=session.get('profile_data'))
    session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
    return render_template('404.html')


def send_text_message(batch_id, sender, msg):
    append_to_list_db(f'batches/batch_{batch_id}/messages', {
        'timestamp': datetime.now().strftime("%H:%M %B %d, %Y"),
        'type': 'text',
        'sender': sender,
        'value': msg
    })


def send_attachment_message(batch_id, sender, topic, file_link):
    append_to_list_db(f'batches/batch_{batch_id}/messages', {
        'timestamp': datetime.now().strftime("%H:%M %B %d, %Y"),
        'type': 'file',
        'sender': sender,
        'value': [topic, file_link]
    })


@app.route('/batch/sendTextMessage', methods=['POST'])
def send_msg():
    if request.method == 'POST':
        batch_id = session.get('last_batch_opened')
        send_text_message(batch_id, session.get('display_name'), request.form['msg'])
        return redirect(url_for('render_batch_data', batch_id=batch_id))
    session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
    return render_template('404.html')


@app.route('/batch/sendAttachmentMessage', methods=['POST'])
def send_attachment():
    if request.method == 'POST':
        batch_id = session.get('last_batch_opened')
        files = request.files.getlist("files")
        for file in files:
            if allowed_file(file.filename):
                sender = session.get('display_name')
                file_id = datetime.now().strftime("%Y%m%d%H%M%S%f%z")
                file_link = upload_file_to_firebase(file, f"file_{file_id}.{secure_filename(file.filename).rsplit('.', 1)[1].lower()}", ALLOWED_EXTENSIONS[secure_filename(file.filename).rsplit('.', 1)[1].lower()])
                topic = file.filename
                send_attachment_message(batch_id, sender, topic, file_link)
            else:
                flash(f"Could not upload {file.filename} due to invalid file type")
        return redirect(url_for('render_batch_data', batch_id=batch_id))
    session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
    return render_template('404.html')



@app.route('/resetPassword', methods=['POST'])
def reset_password():
    if request.method == 'POST':
        r = send_password_reset_email(request.form['forgot-pass-email'])
        if 'error' in r.keys():
            session['error_msg'] = r['error']['message']
        return redirect(url_for('logout'))
    session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
    return render_template('404.html')


def delete_participant_from_batch(email, uid, display_name, batch_id, cat):
    remove_from_list_db(f'batches/batch_{batch_id}/participants', [email, cat])
    remove_from_list_db(f'users/{uid}/batches', f'batch_{batch_id}')
    send_text_message(batch_id, "MemoHub", f"'{display_name}' removed from this batch.")


@app.route('/deleteParticipant', methods=['POST'])
def delete_participant():
    if request.method == 'POST':
        participant, participant_cat = request.form['participant'].split(',')
        batch_id = session.get('last_batch_opened', None)
        success, r = get_user_info(participant)
        if participant_cat == 'student' or participant_cat == 'undefined':
            delete_participant_from_batch(participant, r.uid, r.display_name, batch_id, participant_cat)
        else:
            delete_participant_from_batch(participant, r.uid, r.display_name, batch_id, participant_cat)
        return redirect(url_for('render_batch_data', batch_id=batch_id))
    session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
    return render_template('404.html')


@app.route('/deleteBatch', methods=['POST'])
def delete_batch():
    if request.method == 'POST':
        batch_id = session.get('last_batch_opened', None)
        save_data_to_db(f'batches/batch_{batch_id}/active', False)
        return redirect(url_for('render_batch_data', batch_id=batch_id))
    session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
    return render_template('404.html')


@app.route('/removeBatch', methods=['POST'])
def remove_batch_from_list():
    if request.method == 'POST':
        batch_id = session.get('last_batch_opened', None)
        email = session.get('email', None)
        uid = session.get('uid', None)
        display_name = session.get('display_name', None)
        cat = session.get('user_cat', None)
        delete_participant_from_batch(email, uid, display_name, batch_id, cat)
        return redirect(url_for('home'))
    session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
    return render_template('404.html')


@app.route('/changeTheme', methods=['POST'])
def change_theme():
    if request.method == 'POST':
        uid = session.get('uid')
        save_data_to_db(f"users/{uid}/theme", request.form['theme'])
        session['profile_data']['theme'] = theme[request.form['theme']]
        return redirect(url_for('dashboard'))
    session['profile_data']['theme'] = theme[retrieve_data_from_db(f"users/{session.get('uid')}/theme")]
    return render_template('404.html')


# logout function
@app.route('/logout')
def logout():
    session.pop('uid', None)
    return redirect(url_for('home'))


# Runs App
if __name__ == '__main__':
    app.run()
