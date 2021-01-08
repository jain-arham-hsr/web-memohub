from flask import session, request, render_template, redirect, url_for, flash
# noinspection PyProtectedMember
from firebase_admin._auth_utils import UserNotFoundError
from datetime import datetime
from werkzeug.utils import secure_filename

# noinspection PyPackageRequirements,PyUnresolvedReferences
from helpers import login_required, Firebase, Memohub, set_theme, validate_duplicate_batches, timezone, get_timestamp


Firebase = Firebase()


def home():
    if session.get('uid', False):
        signed_out = False
        set_theme()
    else:
        signed_out = True
    return render_template('home.html', signed_out=signed_out, profile_data=session.get('profile_data', {'theme': {'theme_name': 'light'}}))


def auth(action):
    locale_error_msg = session.get('error_msg', None)
    session.pop('error_msg', None)
    return render_template('auth.html', action=action, error_msg=locale_error_msg, signed_out=True)


def auth_verification():
    if request.method == 'POST':
        if request.form['action'] == "Log In":
            email = request.form['email']
            password = request.form['password']
            # noinspection PyBroadException
            try:
                uid, display_name, profile_pic = Firebase.login(email, password)
            except Exception as e:
                session['error_msg'] = str(e)
                return redirect(url_for('auth', action="login"))
            session['uid'] = uid
            session['display_name'] = display_name
            session['email'] = email
            session['user_cat'] = Firebase.retrieve_data(f"users/{session.get('uid')}/category")
            session['profile_data'] = {
                "displayName": display_name,
                "email": email,
                "profilePicture": profile_pic,
                "userCat": session.get('user_cat')
            }
            session['profile_pic'] = profile_pic
            return redirect(url_for('dashboard'))
        else:
            f_name = request.form['f_name']
            l_name = request.form['l_name']
            email = request.form['email']
            password = request.form['password']
            user_category = "teacher" if request.form['action'] == 'Sign Up as Teacher' else "student"
            # noinspection PyBroadException
            try:
                Firebase.signup(f_name, l_name, email, password, user_category)
                session['error_msg'] = "Sign up successful! Please verify your email via the link sent to your inbox."
                return redirect(url_for('auth', action="login"))
            except Exception as e:
                session['error_msg'] = str(e)
                return redirect(url_for('auth', action="signup"))
    set_theme()
    return render_template('404.html')


def reset_password():
    if request.method == 'POST':
        # noinspection PyBroadException
        try:
            Firebase.send_password_reset_email(request.form['forgot-pass-email'])
        except Exception as e:
            session['error_msg'] = str(e)
        return redirect(url_for('logout'))
    set_theme()
    return render_template('404.html')


@login_required
def dashboard():
    dashboard_template_name = "teacher_dashboard.html" if session.get("user_cat") == "teacher" else "dashboard.html"
    batches = Firebase.retrieve_data(f"users/{session.get('uid')}/batches") or []
    for index, batch_name in enumerate(batches):
        batch_data = Firebase.retrieve_data(f"batches/{batch_name}")
        batch_data['creatorName'] = Firebase.get_user_by_uid(batch_data['created-by']).display_name
        batches[index] = batch_data
    decks = list(zip(*[iter(batches)]*3))
    if len(batches) % 3 != 0:
        decks.append(tuple(batches[(-1) * (len(batches) % 3):]))
    if not all(decks):
        decks = None
    set_theme()
    return render_template(dashboard_template_name, decks=decks, profile_data=session.get('profile_data'))


def create_batch():
    if request.method == 'POST':
        if validate_duplicate_batches(request.form['class-name'],
                                      request.form['section'],
                                      request.form['subject']):
            flash("Couldn't create batch due to duplicate data.")
            return redirect(url_for('dashboard'))
        batch_id = datetime.now().astimezone(timezone).strftime("%Y%m%d%H%M%S%f")
        Firebase.save_data(f'batches/batch_{batch_id}', {
            'name': request.form['class-name'],
            'section': request.form['section'],
            'subject': request.form['subject'],
            'batch_id': batch_id,
            'created-by': session.get('uid'),
            'creation-date': datetime.now().astimezone(timezone).strftime("%B %d, %Y"),
            'messages': [
                {
                    'timestamp': get_timestamp(),
                    'type': 'text',
                    'sender': 'MemoHub',
                    'value': f'{request.form["class-name"]} "{request.form["section"]}" ({request.form["subject"]}) created.'
                }
            ],
            'participants': [(session.get('email'), session.get('user_cat'))],
            'active': True
        })
        Firebase.append_data(f'users/{session["uid"]}/batches', f'batch_{batch_id}')
        return redirect(url_for('dashboard'))
    set_theme()
    return render_template('404.html')


@login_required
def batch(batch_id):
    if f"batch_{batch_id}" in Firebase.retrieve_data(f'users/{session["uid"]}/batches'):
        session['last_batch_opened'] = batch_id
        batch_data = Firebase.retrieve_data(f'batches/batch_{batch_id}')
        locale_error_msg = session.get('error_msg')
        session.pop('error_msg', None)
        for idx, msg in enumerate(batch_data['messages']):
            if msg['type'] == 'text':
                batch_data['messages'][idx]['value'] = msg['value'].replace("\r\n", "<br>")
        batch_data['participants'].remove([session.get('email'), session.get('user_cat')])
        is_creator = session.get('uid', None) == Firebase.retrieve_data(f'batches/batch_{batch_id}/created-by')
        set_theme()
        return render_template('memos.html', cat=session.get('user_cat'), batch_data=batch_data, error_msg=locale_error_msg, is_creator=is_creator, profile_data=session.get('profile_data'))
    set_theme()
    return render_template('404.html')


def add_participant():
    if request.method == 'POST':
        batch_id = session.get('last_batch_opened')
        email = request.form['email']
        try:
            user_data = Firebase.get_user_by_email(email)
            if f"batch_{batch_id}" not in (Firebase.retrieve_data(f'users/{user_data.uid}/batches') or []):
                cat = Firebase.retrieve_data(f'users/{user_data.uid}/category')
                Firebase.append_data(f'users/{user_data.uid}/batches', f"batch_{batch_id}")
                Firebase.append_data(f'batches/batch_{batch_id}/participants', (request.form['email'], cat))
                Memohub.save_text_msg(batch_id, "MemoHub", f"'{user_data.display_name}' added to this batch.")
            else:
                session['error_msg'] = "User already enrolled in this batch. Please enter email of some other user."
        except UserNotFoundError:
            session['error_msg'] = "User with that email doesn't exist in our database."
        except ValueError:
            session['error_msg'] = "Please enter a valid email address."
        return redirect(url_for('batch', batch_id=batch_id))
    set_theme()
    return render_template('404.html')


def remove_participant():
    if request.method == 'POST':
        email, cat = request.form['participant'].split(',')
        batch_id = session.get('last_batch_opened', None)
        Firebase.remove_list_item(f'batches/batch_{batch_id}/participants', [email, cat])
        try:
            user_data = Firebase.get_user_by_email(email)
            Firebase.remove_list_item(f'users/{user_data.uid}/batches', f'batch_{batch_id}')
            Memohub.save_text_msg(batch_id, "MemoHub", f"'{user_data.display_name}' removed from this batch.")
        except UserNotFoundError:
            Firebase.remove_list_item(f'pendingInvitation/{format_email(email)}', f'batch_{batch_id}')
            Memohub.save_text_msg(batch_id, "MemoHub", f"'{email}' removed from this batch.")
        return redirect(url_for('batch', batch_id=batch_id))
    set_theme()
    return render_template('404.html')


def delete_batch():
    if request.method == 'POST':
        batch_id = session.get('last_batch_opened', None)
        Firebase.save_data(f'batches/batch_{batch_id}/active', False)
        return redirect(url_for('batch', batch_id=batch_id))
    set_theme()
    return render_template('404.html')


def remove_batch():
    if request.method == 'POST':
        batch_id = session.get('last_batch_opened', None)
        uid = session.get('uid', None)
        Firebase.remove_list_item(f'users/{uid}/batches', f'batch_{batch_id}')
        return redirect(url_for('dashboard'))
    set_theme()
    return render_template('404.html')


def not_found_error(_):
    if session.get('uid', None):
        set_theme()
    signed_out = False if session.get('uid', None) else True
    return render_template('404.html', profile_data=session.get('profile_data'), signed_out=signed_out), 404


def method_not_allowed_error(_):
    if session.get('uid', None):
        set_theme()
    signed_out = False if session.get('uid', None) else True
    return render_template('404.html', profile_data=session.get('profile_data'), signed_out=signed_out), 405


def change_theme():
    if request.method == 'POST':
        uid = session.get('uid', None)
        Firebase.save_data(f"users/{uid}/theme", request.form['theme'])
        set_theme()
        return redirect(url_for('dashboard'))
    set_theme()
    return render_template('404.html')


def change_profile_pic():
    print(True)
    if request.method == 'POST':
        new_picture = request.files['newPicture']
        file_type = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg'}[secure_filename(new_picture.filename).split('.')[1]]
        print(file_type)
        filename = f"{session.get('uid')}_profilePicture.{file_type}"
        Firebase.delete_file_from_storage(filename)
        photo_url = Firebase.upload_file_to_storage(new_picture, filename, f"image/{file_type}")
        Firebase.update_user_by_uid(session.get('uid'), session.get('display_name'), photo_url)
        session['profile_pic'] = photo_url
        session['profile_data']['profilePicture'] = photo_url
        print(photo_url)
        return redirect(url_for('dashboard'))
    return render_template('404.html')


def logout():
    session.pop('uid', None)
    return redirect(url_for('home'))
