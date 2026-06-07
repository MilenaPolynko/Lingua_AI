from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import json
from datetime import datetime

LANGUAGE_NAMES = {
    'en': 'английский',
    'es': 'испанский',
    'fr': 'французский',
    'de': 'немецкий'
}

app = Flask(__name__)
app.config['SECRET_KEY'] = '******'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' 

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    target_language = db.Column(db.String(10), default='en')   # en, es, fr, de
    level = db.Column(db.String(5), default='A1')              # A1, A2, B1, B2, C1
    
    def set_password(self, password):
        # Хешируем пароль 
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


OPENROUTER_API_KEY = "sk-or-v1-***********"

def call_nemotron(prompt, user_level, target_language):
    """
    Вызывает ИИ через OpenRouter (бесплатные модели).
    Работает с твоим ключом без селфи и кредиток.
    """
    # Системный промпт 
    system_prompt = f"""
    Ты дружелюбный репетитор языка {target_language}.
    Уровень ученика: {user_level} (A1 - начинающий, C1 - продвинутый).
    Отвечай кратко, используй слова и грамматику, подходящие для этого уровня.
    Если ученик просит объяснить слово — дай перевод, пример использования и простую ассоциацию.
    Будь тёплым и поощряющим.**ВАЖНО: Все пояснения, переводы, примеры и подсказки пиши НА РУССКОМ ЯЗЫКЕ.**
Сам изучаемый язык ({target_language}) используй только в примерах и переводах.
Например, если ученик спрашивает слово "apple", ты отвечаешь: "Apple — это яблоко. Пример: I eat an apple (Я ем яблоко)."
"""
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f" Ошибка ИИ: {str(e)}. Ошибка интернет-соединения."

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация нового пользователя"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Такой пользователь уже существует', 'danger')
            return redirect(url_for('register'))
        
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Регистрация успешна! Теперь войдите', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Вход в систему"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f'С возвращением, {username}!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required  
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Профиль пользователя — здесь выбирается язык и уровень"""
    if request.method == 'POST':
        current_user.target_language = request.form['target_language']
        current_user.level = request.form['level']
        db.session.commit()
        flash('Настройки сохранены!', 'success')
        return redirect(url_for('profile'))
    
    languages = {
        'en': 'Английский',
        'es': 'Испанский',
        'fr': 'Французский',
        'de': 'Немецкий'
    }
    levels = ['A1', 'A2', 'B1', 'B2', 'C1']
    
    return render_template('profile.html', 
                         user=current_user,
                         languages=languages,
                         levels=levels)

@app.route('/dictionary', methods=['GET', 'POST'])
@login_required
def dictionary():
    """Словарь с ИИ-объяснениями"""
    ai_response = None
    word = None
    
    if request.method == 'POST':
        word = request.form['word'].strip()
        if word:
            prompt = f"Объясни слово '{word}' на языке {current_user.target_language}. Дай перевод на русский, пример использования и простую ассоциацию для запоминания."
            ai_response = call_nemotron(
                prompt=prompt,
                user_level=current_user.level,
                target_language=current_user.target_language
            )
            
    
    return render_template('dictionary.html', 
                         word=word, 
                         ai_response=ai_response,
                         user=current_user)

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if 'chat_history' not in session:
        session['chat_history'] = []
    
    if request.method == 'POST':
        user_message = request.form['message'].strip()
        if user_message:
            session['chat_history'].append({'role': 'user', 'content': user_message})
            
            last_messages = session['chat_history'][-5:]
            context = "\n".join([f"{'Ученик' if m['role']=='user' else 'Репетитор'}: {m['content']}" for m in last_messages])
            
            prompt = f"""История диалога (последние сообщения):
{context}

Ответь ученику на языке {current_user.target_language} (уровень {current_user.level}).
Будь дружелюбным, кратким, поправляй ошибки мягко.
Твой ответ:"""
            
            ai_response = call_nemotron(
                prompt=prompt,
                user_level=current_user.level,
                target_language=current_user.target_language
            )
            
            session['chat_history'].append({'role': 'assistant', 'content': ai_response})
            session.modified = True
    
    return render_template('chat.html', 
                         user=current_user,
                         messages=session.get('chat_history', []))

@app.route('/clear_chat', methods=['POST'])
@login_required
def clear_chat():
    session['chat_history'] = []
    session.modified = True
    flash('История чата очищена', 'success')
    return redirect(url_for('chat'))

@app.route('/exercises', methods=['GET', 'POST'])
@login_required
def exercises():
    generated_exercises = None
    topic = ""
    
    if request.method == 'POST':
        topic = request.form.get('topic', '').strip()
        if not topic:
            topic = "повседневные темы"
        
        prompt = f"""Ты репетитор языка {current_user.target_language}. Уровень ученика: {current_user.level}.
Сгенерируй 5 упражнений с ОДНОЗНАЧНЫМИ ответами.
Запрещены задания, где может быть несколько правильных ответов (например, "вставь слово в предложение" — только если есть жёсткий контекст).

Типы упражнений:
1. translate: перевести слово/фразу с русского на {current_user.target_language}. Ответ — строго одно слово или устойчивая фраза.
2. choose: выбрать правильный вариант из 3-4, где только один верный.

Верни ТОЛЬКО JSON:
[
  {{"type": "translate", "question": "яблоко", "answer": "apple"}},
  {{"type": "choose", "question": "How ___ you?", "options": ["am", "is", "are"], "answer": "are"}}
]"""
        
        response = call_nemotron(prompt, current_user.level, current_user.target_language)
        
        try:
            import json
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                generated_exercises = json.loads(json_match.group())
            else:
                generated_exercises = [{"type": "info", "question": "Не удалось сгенерировать упражнения. Попробуй другую тему.", "answer": ""}]
        except:
            generated_exercises = [{"type": "info", "question": f"Ошибка генерации. Ответ ИИ: {response[:200]}", "answer": ""}]
    
    return render_template('exercises.html', 
                         user=current_user,
                         exercises=generated_exercises,
                         topic=topic)

@app.route('/assessment', methods=['GET', 'POST'])
@login_required
def assessment():
    result = None
    recommended_level = None
    feedback = None
    questions = []
    
    lang_name = LANGUAGE_NAMES.get(current_user.target_language, current_user.target_language)
    
    if request.method == 'POST':
        user_answers = []
        for key, value in request.form.items():
            if key.startswith('q_'):
                user_answers.append(f"Вопрос: {key}\nОтвет: {value}")
        
        prompt = f"""Ты экзаменатор. Пользователь отвечал на вопросы по {lang_name} языку.

Вот ответы пользователя (каждый ответ на новой строке):
{chr(10).join(user_answers)}

Оцени уровень от A1 до C1 строго по правилам:
- A1: только отдельные слова, почти нет предложений
- A2: короткие фразы, базовые ошибки
- B1: связные предложения, ошибки есть но не критичные
- B2: хороший язык, редкие ошибки
- C1: почти без ошибок, богатая лексика

Верни ТОЛЬКО JSON. Никаких пояснений. Формат:
{{"level": "A2", "feedback": "Короткая причина оценки (одно предложение)"}}

ВАЖНО: Если пользователь написал хоть что-то на {lang_name} — оценивай. Не пиши про отсутствие ответов, если они есть.
"""
        
        response = call_nemotron(prompt, current_user.level, current_user.target_language)
        print(f"[DEBUG] Оценка: {response}")
        
        try:
            import json, re
            json_match = re.search(r'\{[^{}]*"level"[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                recommended_level = data.get('level', current_user.level)
                feedback = data.get('feedback', 'Анализ завершён.')
            else:
                recommended_level = current_user.level
                feedback = "Не удалось распознать ответ ИИ. Попробуй ещё раз."
        except Exception as e:
            recommended_level = current_user.level
            feedback = f"Ошибка анализа."
        
        result = True
    
    else:
        gen_prompt = f"""Сгенерируй ровно 5 вопросов на РУССКОМ языке для проверки уровня ученика по {lang_name} языку (сейчас у него уровень {current_user.level}).

Вопросы должны быть на русском, а проверять знание {lang_name} лексики и грамматики.

Примеры правильных вопросов (для {lang_name} языка):
- Как будет 'привет' на {lang_name}?
- Переведи на {lang_name}: 'я люблю кофе'
- Как спросить 'сколько это стоит' на {lang_name}?

Верни ТОЛЬКО JSON массивом, без пояснений, в формате:
[
  {{"text": "Как будет 'привет' на {lang_name}?"}},
  {{"text": "Переведи на {lang_name}: 'я люблю кофе'"}},
  {{"text": "Как спросить 'сколько это стоит' на {lang_name}?"}}
]

ВАЖНО: вопросы должны быть на РУССКОМ языке, но проверять знание {lang_name}.
"""
        
        response = call_nemotron(gen_prompt, current_user.level, current_user.target_language)
        print(f"[DEBUG] Вопросы: {response}")
        
        try:
            import json, re
            json_match = re.search(r'\[[\s\S]*\]', response, re.DOTALL)
            if json_match:
                questions = json.loads(json_match.group())
            else:
                questions = [
                    {"text": f"Как будет 'привет' на {lang_name}?"},
                    {"text": f"Переведи на {lang_name}: 'я люблю собак'"},
                    {"text": f"Как спросить 'сколько это стоит?' на {lang_name}?"},
                    {"text": f"Переведи на {lang_name}: 'мой дом большой'"},
                    {"text": f"Как будет 'красивый цветок' на {lang_name}?"}
                ]
        except Exception as e:
            questions = [
                {"text": f"Как будет 'привет' на {lang_name}?"},
                {"text": f"Переведи на {lang_name}: 'я люблю собак'"},
                {"text": f"Как спросить 'сколько это стоит?' на {lang_name}?"},
                {"text": f"Переведи на {lang_name}: 'мой дом большой'"},
                {"text": f"Как будет 'красивый цветок' на {lang_name}?"}
            ]
    
    return render_template('assessment.html',
                         user=current_user,
                         questions=questions,
                         result=result,
                         recommended_level=recommended_level,
                         feedback=feedback)

@app.route('/update_level', methods=['POST'])
@login_required
def update_level():
    new_level = request.form.get('new_level')
    if new_level in ['A1', 'A2', 'B1', 'B2', 'C1']:
        current_user.level = new_level
        db.session.commit()
        flash(f'Уровень обновлён на {new_level}!', 'success')
    return redirect(url_for('profile'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  
    app.run(debug=True)  