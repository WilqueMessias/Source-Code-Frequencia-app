from flask import Flask, render_template, request, redirect, session, flash, jsonify
import pandas as pd
import os
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
app.secret_key = 'secret_key'

data_dir = Path(os.getcwd()) / "data"
if not data_dir.exists():
    os.makedirs(data_dir)

user_file = data_dir / 'users.csv'
presence_file = data_dir / 'presence.csv'

def load_users():
    if os.path.exists(user_file):
        return pd.read_csv(user_file, dtype=str)
    else:
        return pd.DataFrame(columns=['cpf', 'name', 'password', 'tipo_usuario'])

def save_users(df):
    try:
        df.to_csv(user_file, index=False)
        print(f'Usuários salvos com sucesso em {user_file}')
    except Exception as e:
        print(f'Erro ao salvar usuários: {e}')

def load_presence():
    if os.path.exists(presence_file):
        return pd.read_csv(presence_file, dtype=str)
    else:
        return pd.DataFrame(columns=['cpf', 'name', 'data', 'hora', 'tipo'])

def save_presence(df):
    df.to_csv(presence_file, index=False)

def get_user_presence(cpf):
    presence_df = load_presence()
    user_presence = presence_df[presence_df['cpf'] == cpf]
    return user_presence.to_dict(orient='records')

def format_cpf(cpf):
    cpf = cpf.zfill(11)  
    return f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        cpf = request.form.get('cpf')
        password = request.form.get('password')
        
        if cpf == 'admin' and password == 'adminpass':
            session['user'] = 'admin'
            session['tipo_usuario'] = 'admin'
            return redirect('/admin_dashboard')
        else:
            flash('Usuário ou senha incorretos.')
    
    return render_template('admin_login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        cpf = request.form.get('cpf').replace('.', '').replace('-', '')

        if not cpf:
            flash('Por favor, insira o CPF.')
            return redirect('/login')

        users_df = load_users()

        user = users_df[users_df['cpf'] == cpf]

        if not user.empty:
            session['user'] = cpf
            session['name'] = user.iloc[0]['name']
            session['tipo_usuario'] = user.iloc[0]['tipo_usuario']
            
            presence_df = load_presence()
            last_record = presence_df[presence_df['cpf'] == cpf].tail(1)
            current_time = datetime.now()
            current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')

            if not last_record.empty:
                last_record_type = last_record['tipo'].values[0]
                if last_record_type == 'Entrada':
                    tipo = 'Saída'
                else:
                    tipo = 'Entrada'
            else:
                tipo = 'Entrada'  

            if not last_record.empty:
                last_record_time = datetime.strptime(last_record['data'].values[0] + ' ' + last_record['hora'].values[0], '%Y-%m-%d %H:%M:%S')
                time_diff = (current_time - last_record_time).total_seconds()
                
                if time_diff < 60:  
                    flash('Você deve aguardar 1 minuto antes de registrar novamente.')
                    return redirect('/login')

            new_presence = pd.DataFrame({'cpf': [cpf], 'name': [session['name']], 'data': [current_time_str.split(' ')[0]], 'hora': [current_time_str.split(' ')[1]], 'tipo': [tipo]})
            presence_df = pd.concat([presence_df, new_presence], ignore_index=True)
            save_presence(presence_df)

            flash(f'{tipo} registrada com sucesso!')
            return redirect('/login')
        else:
            flash('CPF não encontrado ou foi excluído.', 'error')
    
    return render_template('login.html')

@app.route('/verificar_cpf', methods=['POST'])
def verificar_cpf():
    data = request.json
    cpf = data['cpf']

    users_df = load_users()
    user_exists = not users_df[users_df['cpf'] == cpf].empty

    return jsonify({'exists': user_exists})


@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'user' not in session or session['tipo_usuario'] != 'admin':
        return redirect('/admin_login')

    users_df = load_users()

    if request.method == 'POST':

        if 'delete_user' in request.form:
            cpf_to_delete = request.form['cpf'].replace('.', '').replace('-', '')
            users_df = users_df[users_df['cpf'] != cpf_to_delete]
            save_users(users_df)

            presence_df = load_presence()
            presence_df = presence_df[presence_df['cpf'] != cpf_to_delete]
            save_presence(presence_df)

            flash('Usuário excluído com sucesso!')
            return redirect('/admin_dashboard')

        if 'update_user' in request.form:
            cpf_to_update = request.form['cpf'].replace('.', '').replace('-', '')
            new_name = request.form['name']
            new_password = request.form['password']

            users_df.loc[users_df['cpf'] == cpf_to_update, ['name', 'password']] = [new_name, new_password]
            save_users(users_df)
            flash('Usuário atualizado com sucesso!')
            return redirect('/admin_dashboard')

    users_df['cpf'] = users_df['cpf'].apply(format_cpf)
    
    return render_template('admin_dashboard.html', users=users_df.to_dict(orient='records'))

@app.route('/register_user', methods=['GET', 'POST'])
def register_user():
    if 'user' not in session or session['tipo_usuario'] != 'admin':
        return redirect('/admin_login')

    if request.method == 'POST':
        cpf = request.form.get('cpf').replace('.', '').replace('-', '')  
        cpf = cpf.zfill(11)  
        name = request.form.get('name')

        users_df = load_users()

        if cpf in users_df['cpf'].values:
            flash('Usuário já existe com esse CPF.')
            return redirect('/register_user')

        new_user = pd.DataFrame({'cpf': [cpf], 'name': [name], 'password': [''], 'tipo_usuario': ['user']})
        users_df = pd.concat([users_df, new_user], ignore_index=True)
        save_users(users_df)

        flash('Usuário cadastrado com sucesso!')
        return redirect('/admin_dashboard')

    return render_template('register_user.html')

@app.route('/edit_user', methods=['GET', 'POST'])
def edit_user():
    if 'user' not in session or session['tipo_usuario'] != 'admin':
        return redirect('/admin_login')

    cpf = request.args.get('cpf').replace('.', '').replace('-', '')
    users_df = load_users()
    
    user = users_df[users_df['cpf'] == cpf]
    if user.empty:
        flash('Usuário não encontrado.')
        return redirect('/admin_dashboard')

    user = user.iloc[0]

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_password = request.form.get('password')

        if not new_name or not new_password:
            flash('Nome e senha são obrigatórios.')
            return redirect(f'/edit_user?cpf={cpf}')

        users_df.loc[users_df['cpf'] == cpf, ['name', 'password']] = [new_name, new_password]
        save_users(users_df)  
        flash('Usuário atualizado com sucesso!')
        return redirect('/admin_dashboard')

    return render_template('edit_user.html', user=user)

@app.route('/admin_view_user_presence/<cpf>', methods=['GET', 'POST'])
def admin_view_user_presence(cpf):

    cpf = cpf.replace('.', '').replace('-', '')

    user_presence = get_user_presence(cpf)

    for presence in user_presence:
        presence['data'] = datetime.strptime(presence['data'], '%Y-%m-%d').strftime('%d/%m/%Y')

    user_presence_sorted = sorted(user_presence, key=lambda x: datetime.strptime(x['data'] + ' ' + x['hora'], '%d/%m/%Y %H:%M:%S'), reverse=True)

    users_df = load_users()
    user = users_df[users_df['cpf'] == cpf]

    if user.empty:
        flash('Usuário não encontrado.')
        return redirect('/admin_dashboard')
    
    user_name = user.iloc[0]['name']

    return render_template('admin_view_user_presence.html', presencas=user_presence_sorted, cpf=format_cpf(cpf), user={'name': user_name})


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        cpf = request.form.get('cpf').replace('.', '').replace('-', '')
        flash('Instruções para redefinir a senha foram enviadas.')
        return redirect('/login')
    return render_template('forgot_password.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

from waitress import serve

if __name__ == '__main__':
    app.run(debug=True)

