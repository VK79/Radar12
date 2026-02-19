"""
Flask веб-админка для управления мониторингом
"""
import os
import sys
from functools import wraps
from pathlib import Path

# Добавляем родительскую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin

# Импортируем из родительского модуля
from main import config_manager, monitor_service


# Создаем Flask приложение
app = Flask(__name__)
app.secret_key = 'change-this-secret-key'

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin):
    """Пользователь для Flask-Login"""
    def __init__(self, username):
        self.id = username
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    config = config_manager.get()
    admin_config = config.get('admin', {})
    if user_id == admin_config.get('username', 'admin'):
        return User(user_id)
    return None


def check_auth(username, password):
    """Проверка авторизации"""
    config = config_manager.get()
    admin_config = config.get('admin', {})
    return (username == admin_config.get('username', 'admin') and 
            password == admin_config.get('password', 'admin123'))


# === Маршруты авторизации ===

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if check_auth(username, password):
            user = User(username)
            login_user(user)
            flash('Вы успешно вошли в систему', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


# === Основные маршруты ===

@app.route('/')
@login_required
def index():
    """Главная страница"""
    config = config_manager.get()
    return render_template('index.html', 
                           config=config,
                           monitor_running=monitor_service.is_running())


@app.route('/keywords')
@login_required
def keywords():
    """Управление ключевыми словами"""
    keywords_list = config_manager.get_keywords()
    return render_template('keywords.html', keywords=keywords_list)


@app.route('/keywords/add', methods=['POST'])
@login_required
def add_keyword():
    """Добавление ключевого слова"""
    keyword = request.form.get('keyword', '').strip()
    if keyword:
        if config_manager.add_keyword(keyword):
            flash(f'Ключевое слово "{keyword}" добавлено', 'success')
        else:
            flash(f'Ключевое слово "{keyword}" уже существует', 'warning')
    return redirect(url_for('keywords'))


@app.route('/keywords/remove/<path:keyword>')
@login_required
def remove_keyword(keyword):
    """Удаление ключевого слова"""
    if config_manager.remove_keyword(keyword):
        flash(f'Ключевое слово "{keyword}" удалено', 'success')
    return redirect(url_for('keywords'))


@app.route('/recipients')
@login_required
def recipients():
    """Управление получателями"""
    recipients_list = config_manager.get_recipients()
    return render_template('recipients.html', recipients=recipients_list)


@app.route('/recipients/add', methods=['POST'])
@login_required
def add_recipient():
    """Добавление получателя"""
    try:
        chat_id = int(request.form.get('chat_id', ''))
        if config_manager.add_recipient(chat_id):
            flash(f'Получатель {chat_id} добавлен', 'success')
        else:
            flash(f'Получатель {chat_id} уже существует', 'warning')
    except ValueError:
        flash('Неверный формат Chat ID', 'error')
    return redirect(url_for('recipients'))


@app.route('/recipients/remove/<int:chat_id>')
@login_required
def remove_recipient(chat_id):
    """Удаление получателя"""
    if config_manager.remove_recipient(chat_id):
        flash(f'Получатель {chat_id} удален', 'success')
    return redirect(url_for('recipients'))


@app.route('/telegram')
@login_required
def telegram():
    """Управление Telegram каналами"""
    channels = config_manager.get_telegram_channels()
    config = config_manager.get()
    tg_config = config.get('telegram', {})
    return render_template('telegram.html', 
                           channels=channels,
                           config=tg_config)


@app.route('/telegram/add', methods=['POST'])
@login_required
def add_telegram_channel():
    """Добавление Telegram канала"""
    channel = request.form.get('channel', '').strip()
    if channel:
        if config_manager.add_telegram_channel(channel):
            flash(f'Канал "{channel}" добавлен', 'success')
        else:
            flash(f'Канал "{channel}" уже существует', 'warning')
    return redirect(url_for('telegram'))


@app.route('/telegram/remove/<path:channel>')
@login_required
def remove_telegram_channel(channel):
    """Удаление Telegram канала"""
    if config_manager.remove_telegram_channel(channel):
        flash(f'Канал "{channel}" удален', 'success')
    return redirect(url_for('telegram'))


@app.route('/telegram/config', methods=['POST'])
@login_required
def update_telegram_config():
    """Обновление конфигурации Telegram"""
    config = config_manager.get()
    tg_config = config.setdefault('telegram', {})
    
    try:
        tg_config['api_id'] = int(request.form.get('api_id', 0))
    except ValueError:
        tg_config['api_id'] = 0
    
    tg_config['api_hash'] = request.form.get('api_hash', '')
    tg_config['bot_token'] = request.form.get('bot_token', '')
    tg_config['phone'] = request.form.get('phone', '')
    
    config_manager.save(config)
    flash('Конфигурация Telegram обновлена', 'success')
    return redirect(url_for('telegram'))


@app.route('/vk')
@login_required
def vk():
    """Управление VK группами"""
    groups = config_manager.get_vk_groups()
    config = config_manager.get()
    vk_config = config.get('vk', {})
    return render_template('vk.html', 
                           groups=groups,
                           config=vk_config)


@app.route('/vk/add', methods=['POST'])
@login_required
def add_vk_group():
    """Добавление VK группы"""
    group = request.form.get('group', '').strip()
    if group:
        if config_manager.add_vk_group(group):
            flash(f'Группа "{group}" добавлена', 'success')
        else:
            flash(f'Группа "{group}" уже существует', 'warning')
    return redirect(url_for('vk'))


@app.route('/vk/remove/<path:group>')
@login_required
def remove_vk_group(group):
    """Удаление VK группы"""
    if config_manager.remove_vk_group(group):
        flash(f'Группа "{group}" удалена', 'success')
    return redirect(url_for('vk'))


@app.route('/vk/config', methods=['POST'])
@login_required
def update_vk_config():
    """Обновление конфигурации VK"""
    config = config_manager.get()
    config.setdefault('vk', {})['access_token'] = request.form.get('access_token', '')
    
    config_manager.save(config)
    flash('Конфигурация VK обновлена', 'success')
    return redirect(url_for('vk'))


@app.route('/settings')
@login_required
def settings():
    """Настройки мониторинга"""
    config = config_manager.get()
    admin_config = config.get('admin', {})
    monitoring_config = config.get('monitoring', {})
    return render_template('settings.html',
                           admin=admin_config,
                           monitoring=monitoring_config)


@app.route('/settings/admin', methods=['POST'])
@login_required
def update_admin_settings():
    """Обновление настроек админа"""
    config = config_manager.get()
    admin_config = config.setdefault('admin', {})
    
    new_username = request.form.get('username', '').strip()
    new_password = request.form.get('password', '').strip()
    
    if new_username:
        admin_config['username'] = new_username
    if new_password:
        admin_config['password'] = new_password
    
    config_manager.save(config)
    flash('Настройки админа обновлены', 'success')
    return redirect(url_for('settings'))


@app.route('/settings/monitoring', methods=['POST'])
@login_required
def update_monitoring_settings():
    """Обновление настроек мониторинга"""
    config = config_manager.get()
    monitoring_config = config.setdefault('monitoring', {})
    
    try:
        monitoring_config['check_interval'] = int(request.form.get('check_interval', 300))
        monitoring_config['max_posts_per_check'] = int(request.form.get('max_posts_per_check', 20))
    except ValueError:
        flash('Неверные значения', 'error')
        return redirect(url_for('settings'))
    
    config_manager.save(config)
    flash('Настройки мониторинга обновлены', 'success')
    return redirect(url_for('settings'))


# === API маршруты ===

@app.route('/api/status')
@login_required
def api_status():
    """API: Статус мониторинга"""
    return jsonify({
        'running': monitor_service.is_running(),
        'keywords_count': len(config_manager.get_keywords()),
        'recipients_count': len(config_manager.get_recipients()),
        'telegram_channels_count': len(config_manager.get_telegram_channels()),
        'vk_groups_count': len(config_manager.get_vk_groups())
    })


@app.route('/api/start', methods=['POST'])
@login_required
def api_start():
    """API: Запуск мониторинга"""
    if not monitor_service.is_running():
        monitor_service.start()
        return jsonify({'success': True, 'message': 'Мониторинг запущен'})
    return jsonify({'success': False, 'message': 'Мониторинг уже запущен'})


@app.route('/api/stop', methods=['POST'])
@login_required
def api_stop():
    """API: Остановка мониторинга"""
    if monitor_service.is_running():
        monitor_service.stop()
        return jsonify({'success': True, 'message': 'Мониторинг остановлен'})
    return jsonify({'success': False, 'message': 'Мониторинг не запущен'})


def run_admin(host='0.0.0.0', port=5000, debug=False):
    """Запуск Flask сервера"""
    print(f"\nАдмин-панель запущена: http://localhost:{port}")
    print("Данные для входа указаны в config.json (admin.username, admin.password)")
    print("-" * 50)
    
    # Обновляем secret_key из конфигурации
    config = config_manager.get()
    app.secret_key = config.get('admin', {}).get('secret_key', app.secret_key)
    
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    run_admin(debug=True)
