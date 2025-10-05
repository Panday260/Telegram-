import telebot
from telebot import types, util
import time
import re
import threading
import random
import datetime
from collections import defaultdict
import os
import sys

TOKEN = "7700512610:AAFGNTmtXpjgnZGQqMpmVHYffJl2zeyjGyQ"
bot = telebot.TeleBot(TOKEN)

# Database structure: list of all items
database = []
flashcards = []  # Store flashcards
quiz_questions = []  # Store quiz questions
study_sessions = {}  # Track study sessions
reminders = []  # Store reminders
notes_by_subject = defaultdict(list)  # Organize notes by subject

# Admin features
users = set()  # Track all users
banned_users = set()  # Track banned users
admin_broadcasts = []  # Track broadcast messages

admin_id = 6978422074  # Replace with your Telegram ID (as integer)
channel_link = "@DARK_STUDY"  # Replace with your channel link

# Track batch mode
batch_add_mode = False

def escape_markdown(text):
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

def escape_markdown_url(text):
    url_pattern = re.compile(r'https?://\S+')
    urls = url_pattern.findall(text)
    for url in urls:
        safe_url = escape_markdown(url)
        text = text.replace(url, safe_url)
    return text

def create_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("📥 Add Item", callback_data='add'),
        types.InlineKeyboardButton("📚 Batch Add", callback_data='batchadd'),
        types.InlineKeyboardButton("🔍 Search", callback_data='search'),
        types.InlineKeyboardButton("📋 List All", callback_data='list'),
        types.InlineKeyboardButton("🧠 Flashcards", callback_data='flashcard'),
        types.InlineKeyboardButton("📝 Quiz", callback_data='quiz'),
        types.InlineKeyboardButton("⏱️ Study Timer", callback_data='timer'),
        types.InlineKeyboardButton("📖 Notes", callback_data='notes'),
        types.InlineKeyboardButton("⏰ Reminder", callback_data='reminder'),
        types.InlineKeyboardButton("ℹ️ Help", callback_data='help')
    ]
    markup.add(*buttons)
    return markup

def create_admin_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("📊 Statistics", callback_data='admin_stats'),
        types.InlineKeyboardButton("📢 Broadcast", callback_data='admin_broadcast'),
        types.InlineKeyboardButton("🚫 Ban User", callback_data='admin_ban'),
        types.InlineKeyboardButton("✅ Unban User", callback_data='admin_unban'),
        types.InlineKeyboardButton("➕ Add Quiz", callback_data='admin_add_quiz'),
        types.InlineKeyboardButton("➖ Remove Quiz", callback_data='admin_remove_quiz'),
        types.InlineKeyboardButton("📝 View Reminders", callback_data='admin_view_reminders'),
        types.InlineKeyboardButton("🗑 Delete File", callback_data='admin_delete_file'),
        types.InlineKeyboardButton("🔄 Restart Bot", callback_data='admin_restart'),
        types.InlineKeyboardButton("⬅️ Back", callback_data='back_to_main')
    ]
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    # Add user to the set of users
    users.add(message.from_user.id)
    
    # Check if user is banned
    if message.from_user.id in banned_users:
        bot.send_message(message.chat.id, "⚠️ You have been banned from using this bot.")
        return
    
    welcome_msg = escape_markdown(f"""
🌟 Welcome to Study Guru Bot! 🌟
Your Ultimate Study Companion
📚 Features:
- Add any study materials (PDFs, videos, photos, notes)
- Search across all shared resources
- Create and study flashcards
- Test your knowledge with quizzes
- Track study sessions with Pomodoro timer
- Organize notes by subject
- Set study reminders
⚡ Quick Commands:
/add - Add new material  
/batchadd - Add multiple files  
/search - Find files  
/list - View all files  
/flashcard - Manage flashcards
/quiz - Take a quiz
/timer - Start study timer
/notes - Organize notes
/remind - Set reminder
/admin - Admin panel (admins only)
/help - Get support
🔗 Join our channel: {channel_link}
""")
    bot.send_message(message.chat.id, welcome_msg, 
                   parse_mode='MarkdownV2',
                   reply_markup=create_main_menu())

def save_to_database(content, content_type='text', file_name=None, caption=None, subject=None):
    item = {
        'type': content_type,
        'content': content,
        'file_name': file_name or "",
        'caption': caption or "",
        'timestamp': time.time(),
        'searchable_text': f"{file_name or ''} {caption or ''} {content if content_type in ['text', 'url'] else ''}".lower()
    }
    
    database.append(item)
    
    # Also add to notes_by_subject if it's a note and subject is provided
    if content_type == 'text' and subject:
        notes_by_subject[subject].append(item)

def process_add_step(message):
    try:
        # Check if user is banned
        if message.from_user.id in banned_users:
            bot.send_message(message.chat.id, "⚠️ You have been banned from using this bot.")
            return
            
        # Check if user sent a command instead of content
        if message.text and message.text.startswith('/'):
            handle_command_in_step(message)
            return
            
        if message.text:
            if 'http' in message.text.lower():
                save_to_database(message.text, 'url')
                safe_text = escape_markdown_url(message.text)
                bot.send_message(message.chat.id, f"✅ *Link added:*\n{safe_text}", parse_mode='MarkdownV2')
            else:
                save_to_database(message.text, 'text')
                safe_text = escape_markdown(message.text)
                bot.send_message(message.chat.id, f"✅ *Text added:*\n`{safe_text}`", parse_mode='MarkdownV2')
        elif message.document:
            save_to_database(
                message.document.file_id,
                'document',
                message.document.file_name,
                message.caption
            )
            safe_name = escape_markdown(message.document.file_name)
            reply = f"📄 *Added:* `{safe_name}`"
            if message.caption:
                safe_caption = escape_markdown(message.caption)
                reply += f"\n📝 *Caption:* {safe_caption}"
            bot.send_message(message.chat.id, reply, parse_mode='MarkdownV2')
        elif message.photo:
            save_to_database(
                message.photo[-1].file_id,
                'photo',
                None,
                message.caption
            )
            reply = "📷 *Photo added*"
            if message.caption:
                safe_caption = escape_markdown(message.caption)
                reply += f"\n📝 *Caption:* {safe_caption}"
            bot.send_message(message.chat.id, reply, parse_mode='MarkdownV2')
        elif message.video:
            save_to_database(
                message.video.file_id,
                'video',
                message.video.file_name,
                message.caption
            )
            name = message.video.file_name or "Video"
            safe_name = escape_markdown(name)
            reply = f"🎬 *Added:* {safe_name}"
            if message.caption:
                safe_caption = escape_markdown(message.caption)
                reply += f"\n📝 *Caption:* {safe_caption}"
            bot.send_message(message.chat.id, reply, parse_mode='MarkdownV2')
        elif message.audio:
            save_to_database(
                message.audio.file_id,
                'audio',
                message.audio.file_name,
                message.caption
            )
            name = message.audio.file_name or "Audio"
            safe_name = escape_markdown(name)
            reply = f"🎵 *Added:* {safe_name}"
            if message.caption:
                safe_caption = escape_markdown(message.caption)
                reply += f"\n📝 *Caption:* {safe_caption}"
            bot.send_message(message.chat.id, reply, parse_mode='MarkdownV2')
        else:
            bot.send_message(message.chat.id, "⚠️ Unsupported format. Please send text, links, PDF, photo, video, or audio.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

def handle_command_in_step(message):
    """Handle commands sent during step operations"""
    command = message.text[1:].split('@')[0]  # Extract command without / and @botname
    
    # Cancel current operation
    bot.send_message(message.chat.id, "⚠️ Operation cancelled.")
    
    # Execute the command
    if command == 'start' or command == 'help':
        handle_start(message)
    elif command == 'add':
        add_command(message)
    elif command == 'batchadd':
        batchadd_command(message)
    elif command == 'search':
        search_command(message)
    elif command == 'list':
        list_command(message)
    elif command == 'flashcard':
        flashcard_command(message)
    elif command == 'quiz':
        quiz_command(message)
    elif command == 'timer':
        timer_command(message)
    elif command == 'notes':
        notes_command(message)
    elif command == 'remind':
        remind_command(message)
    elif command == 'admin':
        admin_command(message)
    else:
        bot.send_message(message.chat.id, 
                        escape_markdown("❓ Unknown command. Type /help for available commands."),
                        parse_mode='MarkdownV2',
                        reply_markup=create_main_menu())

@bot.message_handler(commands=['add'])
def add_command(message):
    global batch_add_mode
    batch_add_mode = False
    msg = bot.send_message(message.chat.id, 
                         escape_markdown("📤 Send me any file or text to add:"),
                         parse_mode='MarkdownV2',
                         reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_add_step)

def process_batchadd_step(message):
    global batch_add_mode
    try:
        # Check if user is banned
        if message.from_user.id in banned_users:
            bot.send_message(message.chat.id, "⚠️ You have been banned from using this bot.")
            return
            
        # Check if user sent a command instead of content
        if message.text and message.text.startswith('/'):
            handle_command_in_step(message)
            return
            
        if message.text and message.text.lower() == 'done':
            batch_add_mode = False
            bot.send_message(message.chat.id, "✅ Batch upload completed!")
            return
            
        if message.document:
            save_to_database(
                message.document.file_id,
                'document',
                message.document.file_name,
                message.caption
            )
            safe_name = escape_markdown(message.document.file_name)
            reply = f"📄 *Added to batch:* `{safe_name}`"
            if message.caption:
                safe_caption = escape_markdown(message.caption)
                reply += f"\n📝 *Caption:* {safe_caption}"
            bot.send_message(message.chat.id, reply, parse_mode='MarkdownV2')
        elif message.photo:
            save_to_database(
                message.photo[-1].file_id,
                'photo',
                None,
                message.caption
            )
            reply = "📷 *Photo added to batch*"
            if message.caption:
                safe_caption = escape_markdown(message.caption)
                reply += f"\n📝 *Caption:* {safe_caption}"
            bot.send_message(message.chat.id, reply, parse_mode='MarkdownV2')
        elif message.video:
            save_to_database(
                message.video.file_id,
                'video',
                message.video.file_name,
                message.caption
            )
            name = message.video.file_name or "Video"
            safe_name = escape_markdown(name)
            reply = f"🎬 *Added to batch:* {safe_name}"
            if message.caption:
                safe_caption = escape_markdown(message.caption)
                reply += f"\n📝 *Caption:* {safe_caption}"
            bot.send_message(message.chat.id, reply, parse_mode='MarkdownV2')
        elif message.audio:
            save_to_database(
                message.audio.file_id,
                'audio',
                message.audio.file_name,
                message.caption
            )
            name = message.audio.file_name or "Audio"
            safe_name = escape_markdown(name)
            reply = f"🎵 *Added to batch:* {safe_name}"
            if message.caption:
                safe_caption = escape_markdown(message.caption)
                reply += f"\n📝 *Caption:* {safe_caption}"
            bot.send_message(message.chat.id, reply, parse_mode='MarkdownV2')
        else:
            bot.send_message(message.chat.id, "⚠️ Please send files or type 'done' to finish")
            
        # Stay in batch mode
        batch_add_mode = True
        bot.register_next_step_handler(message, process_batchadd_step)
            
    except Exception as e:
        batch_add_mode = False
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['batchadd'])
def batchadd_command(message):
    global batch_add_mode
    batch_add_mode = True
    msg = bot.send_message(message.chat.id, 
                         escape_markdown("""
📚 *Batch Add Mode:*
1. Send files one by one
2. Each will be added immediately
3. Type 'done' when finished
Files will be searchable by exact filename.
"""),
                         parse_mode='MarkdownV2',
                         reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_batchadd_step)

def process_search_step(message, is_command=False):
    try:
        if not database:
            bot.send_message(message.chat.id, "The library is empty. Add some files first!")
            return
            
        if not message.text:
            bot.send_message(message.chat.id, "🔍 Please enter search keywords")
            return
        
        search_query = message.text.lower().strip()
        results = []
        
        # Search across ALL files
        for item in database:
            if search_query in item['searchable_text']:
                results.append(item)
        
        if results:
            safe_query = escape_markdown(search_query)
            reply_text = f"🔍 Found {len(results)} results for '{safe_query}':"
            bot.send_message(message.chat.id, reply_text, parse_mode='MarkdownV2')
            
            # Show all matching results (limited to first 10)
            for item in results[:10]:
                if item['type'] == 'text':
                    safe_content = escape_markdown(item['content'])
                    bot.send_message(message.chat.id, f"📝 *Text Note:*\n{safe_content}", parse_mode='MarkdownV2')
                elif item['type'] == 'url':
                    safe_url = escape_markdown_url(item['content'])
                    bot.send_message(message.chat.id, f"🔗 *Link:*\n{safe_url}", parse_mode='MarkdownV2')
                elif item['type'] == 'document':
                    safe_name = escape_markdown(item['file_name'])
                    safe_caption = escape_markdown(item['caption']) if item['caption'] else None
                    bot.send_document(message.chat.id, item['content'], 
                                   caption=f"📄 *{safe_name}*\n{safe_caption}" if item['caption'] else None,
                                   parse_mode='MarkdownV2')
                elif item['type'] == 'photo':
                    safe_caption = escape_markdown(item['caption']) if item['caption'] else None
                    bot.send_photo(message.chat.id, item['content'],
                                 caption=f"📷 *Photo*\n{safe_caption}" if item['caption'] else None,
                                 parse_mode='MarkdownV2')
                elif item['type'] == 'video':
                    name = item['file_name'] or "Video"
                    safe_caption = escape_markdown(item['caption']) if item['caption'] else None
                    bot.send_video(message.chat.id, item['content'],
                                 caption=f"🎬 *{escape_markdown(name)}*\n{safe_caption}" if item['caption'] else None,
                                 parse_mode='MarkdownV2')
                elif item['type'] == 'audio':
                    name = item['file_name'] or "Audio"
                    safe_caption = escape_markdown(item['caption']) if item['caption'] else None
                    bot.send_audio(message.chat.id, item['content'],
                                 caption=f"🎵 *{escape_markdown(name)}*\n{safe_caption}" if item['caption'] else None,
                                 parse_mode='MarkdownV2')
            
            if len(results) > 10:
                bot.send_message(message.chat.id, f"ℹ️ Showing 10 of {len(results)} results. Be more specific for exact matches.")
        else:
            safe_query = escape_markdown(search_query)
            bot.send_message(message.chat.id, 
                           f"❌ No files found matching '{safe_query}'",
                           parse_mode='MarkdownV2')
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Search error: {str(e)}")

@bot.message_handler(commands=['search'])
def search_command(message):
    process_search_step(message, is_command=True)

@bot.message_handler(commands=['list'])
def list_command(message):
    if not database:
        bot.send_message(message.chat.id, "The library is empty. Add some files first!")
        return
    
    # Count files by type
    counts = {
        'document': 0,
        'photo': 0,
        'video': 0,
        'audio': 0,
        'text': 0,
        'url': 0
    }
    
    for item in database:
        counts[item['type']] += 1
    
    msg = escape_markdown(f"""
📊 Library Statistics:
📄 Documents: {counts['document']}
📷 Photos: {counts['photo']}
🎬 Videos: {counts['video']}
🎵 Audio: {counts['audio']}
📝 Notes: {counts['text']}
🔗 Links: {counts['url']}
⭐ Total: {len(database)} items
Use /search to find files.
""")
    
    bot.send_message(message.chat.id, msg, parse_mode='MarkdownV2')

# New: Flashcard Management
@bot.message_handler(commands=['flashcard'])
def flashcard_command(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("➕ Add Flashcard", callback_data='add_flashcard'),
        types.InlineKeyboardButton("📖 Study Flashcards", callback_data='study_flashcards'),
        types.InlineKeyboardButton("📊 My Flashcards", callback_data='list_flashcards')
    ]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, 
                    escape_markdown("🧠 *Flashcard Management*\nChoose an option:"),
                    parse_mode='MarkdownV2',
                    reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'add_flashcard')
def add_flashcard_callback(call):
    msg = bot.send_message(call.message.chat.id, 
                          escape_markdown("➕ *Add New Flashcard*\nSend in format:\n`Q: Your question\nA: Your answer`"),
                          parse_mode='MarkdownV2',
                          reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_add_flashcard)

def process_add_flashcard(message):
    try:
        # Check if user is banned
        if message.from_user.id in banned_users:
            bot.send_message(message.chat.id, "⚠️ You have been banned from using this bot.")
            return
            
        # Check if user sent a command instead of content
        if message.text and message.text.startswith('/'):
            handle_command_in_step(message)
            return
            
        text = message.text.strip()
        if not text.startswith('Q:') or '\nA:' not in text:
            bot.send_message(message.chat.id, 
                            escape_markdown("❌ Invalid format. Please use:\n`Q: Your question\nA: Your answer`"),
                            parse_mode='MarkdownV2')
            return
            
        parts = text.split('\nA:', 1)
        question = parts[0][2:].strip()
        answer = parts[1].strip()
        
        flashcards.append({
            'question': question,
            'answer': answer,
            'user_id': message.from_user.id,
            'created_at': time.time()
        })
        
        safe_q = escape_markdown(question)
        safe_a = escape_markdown(answer)
        bot.send_message(message.chat.id, 
                        f"✅ *Flashcard Added:*\nQ: {safe_q}\nA: {safe_a}",
                        parse_mode='MarkdownV2')
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == 'study_flashcards')
def study_flashcards_callback(call):
    user_flashcards = [fc for fc in flashcards if fc['user_id'] == call.from_user.id]
    
    if not user_flashcards:
        bot.send_message(call.message.chat.id, 
                        escape_markdown("📭 You don't have any flashcards yet. Add some first!"),
                        parse_mode='MarkdownV2')
        return
        
    random.shuffle(user_flashcards)
    study_flashcards_session(call.message.chat.id, user_flashcards, 0)

def study_flashcards_session(chat_id, flashcards_list, index):
    if index >= len(flashcards_list):
        bot.send_message(chat_id, 
                        escape_markdown("🎉 Congratulations! You've completed all flashcards!"),
                        parse_mode='MarkdownV2')
        return
        
    card = flashcards_list[index]
    safe_q = escape_markdown(card['question'])
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Show Answer", callback_data=f'show_answer_{index}'))
    
    bot.send_message(chat_id, 
                    f"🧠 *Question {index+1}/{len(flashcards_list)}:*\n{safe_q}",
                    parse_mode='MarkdownV2',
                    reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('show_answer_'))
def show_flashcard_answer(call):
    index = int(call.data.split('_')[2])
    user_flashcards = [fc for fc in flashcards if fc['user_id'] == call.from_user.id]
    
    if index < len(user_flashcards):
        card = user_flashcards[index]
        safe_a = escape_markdown(card['answer'])
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Next Question", callback_data=f'next_question_{index+1}'))
        
        bot.send_message(call.message.chat.id, 
                        f"💡 *Answer:*\n{safe_a}",
                        parse_mode='MarkdownV2',
                        reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('next_question_'))
def next_flashcard_question(call):
    index = int(call.data.split('_')[2])
    user_flashcards = [fc for fc in flashcards if fc['user_id'] == call.from_user.id]
    study_flashcards_session(call.message.chat.id, user_flashcards, index)

@bot.callback_query_handler(func=lambda call: call.data == 'list_flashcards')
def list_flashcards_callback(call):
    user_flashcards = [fc for fc in flashcards if fc['user_id'] == call.from_user.id]
    
    if not user_flashcards:
        bot.send_message(call.message.chat.id, 
                        escape_markdown("📭 You don't have any flashcards yet."),
                        parse_mode='MarkdownV2')
        return
        
    msg = escape_markdown(f"📊 *Your Flashcards ({len(user_flashcards)}):*\n")
    for i, card in enumerate(user_flashcards[:10]):  # Show first 10
        safe_q = escape_markdown(card['question'])
        msg += f"\n{i+1}. {safe_q}"
    
    if len(user_flashcards) > 10:
        msg += escape_markdown(f"\n\n... and {len(user_flashcards)-10} more")
    
    bot.send_message(call.message.chat.id, msg, parse_mode='MarkdownV2')

# New: Quiz Feature
@bot.message_handler(commands=['quiz'])
def quiz_command(message):
    if not quiz_questions:
        bot.send_message(message.chat.id, 
                        escape_markdown("📭 No quiz questions available yet. Admin needs to add questions first."),
                        parse_mode='MarkdownV2')
        return
        
    random.shuffle(quiz_questions)
    start_quiz_session(message.chat.id, quiz_questions, 0, 0)

def start_quiz_session(chat_id, questions, index, score):
    if index >= len(questions):
        bot.send_message(chat_id, 
                        escape_markdown(f"🎉 Quiz completed! Your score: {score}/{len(questions)}"),
                        parse_mode='MarkdownV2')
        return
        
    q = questions[index]
    safe_q = escape_markdown(q['question'])
    
    markup = types.InlineKeyboardMarkup()
    for i, option in enumerate(q['options']):
        markup.add(types.InlineKeyboardButton(option, callback_data=f'quiz_answer_{index}_{i}'))
    
    bot.send_message(chat_id, 
                    f"📝 *Question {index+1}/{len(questions)}:*\n{safe_q}",
                    parse_mode='MarkdownV2',
                    reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('quiz_answer_'))
def handle_quiz_answer(call):
    parts = call.data.split('_')
    index = int(parts[2])
    answer_index = int(parts[3])
    
    q = quiz_questions[index]
    is_correct = (answer_index == q['correct_index'])
    
    if is_correct:
        score = 1
        bot.answer_callback_query(call.id, "✅ Correct!", show_alert=True)
    else:
        score = 0
        correct_answer = q['options'][q['correct_index']]
        bot.answer_callback_query(call.id, f"❌ Incorrect! Correct answer: {correct_answer}", show_alert=True)
    
    # Get current score from previous questions
    current_score = sum(1 for i in range(index) if quiz_questions[i]['correct_index'] == answer_index)
    
    start_quiz_session(call.message.chat.id, quiz_questions, index + 1, current_score + score)

# New: Study Timer (Pomodoro)
@bot.message_handler(commands=['timer'])
def timer_command(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("25 min Study", callback_data='timer_25'),
        types.InlineKeyboardButton("50 min Study", callback_data='timer_50'),
        types.InlineKeyboardButton("5 min Break", callback_data='timer_5'),
        types.InlineKeyboardButton("10 min Break", callback_data='timer_10')
    ]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, 
                    escape_markdown("⏱️ *Study Timer*\nSelect a session:"),
                    parse_mode='MarkdownV2',
                    reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('timer_'))
def start_timer_callback(call):
    duration = int(call.data.split('_')[1])
    user_id = call.from_user.id
    
    study_sessions[user_id] = {
        'end_time': time.time() + duration * 60,
        'duration': duration,
        'is_break': duration <= 10
    }
    
    session_type = "Break" if duration <= 10 else "Study"
    bot.send_message(call.message.chat.id, 
                    escape_markdown(f"⏱️ *{duration} min {session_type} Session Started!*\nI'll notify you when it's time to take a break or get back to studying."),
                    parse_mode='MarkdownV2')
    
    # Start timer thread
    threading.Thread(target=timer_thread, args=(call.message.chat.id, user_id, duration)).start()

def timer_thread(chat_id, user_id, duration):
    time.sleep(duration * 60)
    
    if user_id in study_sessions and study_sessions[user_id]['duration'] == duration:
        session_type = "break" if duration <= 10 else "study"
        bot.send_message(chat_id, 
                        escape_markdown(f"⏰ *Time's up!*\nYour {duration} minute {session_type} session is over."),
                        parse_mode='MarkdownV2')
        
        # Suggest next action
        markup = types.InlineKeyboardMarkup()
        if duration > 10:  # Was a study session
            markup.add(types.InlineKeyboardButton("Start 5 min Break", callback_data='timer_5'))
        else:  # Was a break
            markup.add(types.InlineKeyboardButton("Start 25 min Study", callback_data='timer_25'))
        
        bot.send_message(chat_id, 
                        escape_markdown("What would you like to do next?"),
                        parse_mode='MarkdownV2',
                        reply_markup=markup)

# New: Notes Organizer
@bot.message_handler(commands=['notes'])
def notes_command(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("📝 Add Note", callback_data='add_note'),
        types.InlineKeyboardButton("📂 View Subjects", callback_data='view_subjects'),
        types.InlineKeyboardButton("📖 View Notes", callback_data='view_notes')
    ]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, 
                    escape_markdown("📖 *Notes Organizer*\nChoose an option:"),
                    parse_mode='MarkdownV2',
                    reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'add_note')
def add_note_callback(call):
    msg = bot.send_message(call.message.chat.id, 
                          escape_markdown("📝 *Add New Note*\nFirst, send the subject name:"),
                          parse_mode='MarkdownV2',
                          reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_add_note_subject)

def process_add_note_subject(message):
    # Check if user is banned
    if message.from_user.id in banned_users:
        bot.send_message(message.chat.id, "⚠️ You have been banned from using this bot.")
        return
        
    # Check if user sent a command instead of content
    if message.text and message.text.startswith('/'):
        handle_command_in_step(message)
        return
        
    subject = message.text.strip()
    msg = bot.send_message(message.chat.id, 
                          escape_markdown(f"📝 *Add Note for {escape_markdown(subject)}*\nNow send your note content:"),
                          parse_mode='MarkdownV2',
                          reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_add_note_content, subject)

def process_add_note_content(message, subject):
    # Check if user is banned
    if message.from_user.id in banned_users:
        bot.send_message(message.chat.id, "⚠️ You have been banned from using this bot.")
        return
        
    # Check if user sent a command instead of content
    if message.text and message.text.startswith('/'):
        handle_command_in_step(message)
        return
        
    content = message.text.strip()
    save_to_database(content, 'text', None, None, subject)
    
    safe_content = escape_markdown(content)
    bot.send_message(message.chat.id, 
                    f"✅ *Note added to {escape_markdown(subject)}:*\n{safe_content}",
                    parse_mode='MarkdownV2')

@bot.callback_query_handler(func=lambda call: call.data == 'view_subjects')
def view_subjects_callback(call):
    if not notes_by_subject:
        bot.send_message(call.message.chat.id, 
                        escape_markdown("📭 No subjects found. Add some notes first!"),
                        parse_mode='MarkdownV2')
        return
        
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for subject in notes_by_subject.keys():
        buttons.append(types.InlineKeyboardButton(subject, callback_data=f'view_notes_{subject}'))
    
    markup.add(*buttons)
    
    bot.send_message(call.message.chat.id, 
                    escape_markdown("📂 *Your Subjects:*\nSelect a subject to view notes:"),
                    parse_mode='MarkdownV2',
                    reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_notes_'))
def view_notes_callback(call):
    subject = call.data.split('_', 2)[2]
    notes = notes_by_subject.get(subject, [])
    
    if not notes:
        bot.send_message(call.message.chat.id, 
                        escape_markdown(f"📭 No notes found for {escape_markdown(subject)}."),
                        parse_mode='MarkdownV2')
        return
        
    msg = escape_markdown(f"📖 *Notes for {subject}:*\n")
    for i, note in enumerate(notes[:5]):  # Show first 5 notes
        safe_content = escape_markdown(note['content'][:100] + '...' if len(note['content']) > 100 else note['content'])
        msg += f"\n{i+1}. {safe_content}"
    
    if len(notes) > 5:
        msg += escape_markdown(f"\n\n... and {len(notes)-5} more notes")
    
    bot.send_message(call.message.chat.id, msg, parse_mode='MarkdownV2')

# New: Reminder Feature
@bot.message_handler(commands=['remind'])
def remind_command(message):
    msg = bot.send_message(message.chat.id, 
                          escape_markdown("⏰ *Set Reminder*\nSend reminder in format:\n`[time in minutes] [reminder text]`\nExample: `30 Review biology notes`"),
                          parse_mode='MarkdownV2',
                          reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_add_reminder)

def process_add_reminder(message):
    try:
        # Check if user is banned
        if message.from_user.id in banned_users:
            bot.send_message(message.chat.id, "⚠️ You have been banned from using this bot.")
            return
            
        # Check if user sent a command instead of content
        if message.text and message.text.startswith('/'):
            handle_command_in_step(message)
            return
            
        text = message.text.strip()
        parts = text.split(' ', 1)
        
        if len(parts) < 2 or not parts[0].isdigit():
            bot.send_message(message.chat.id, 
                            escape_markdown("❌ Invalid format. Please use:\n`[minutes] [reminder text]`"),
                            parse_mode='MarkdownV2')
            return
            
        minutes = int(parts[0])
        reminder_text = parts[1]
        
        # Create reminder object
        reminder = {
            'user_id': message.from_user.id,
            'text': reminder_text,
            'trigger_time': time.time() + minutes * 60,
            'created_at': time.time()
        }
        
        reminders.append(reminder)
        
        safe_text = escape_markdown(reminder_text)
        bot.send_message(message.chat.id, 
                        f"⏰ *Reminder Set!*\nI'll remind you in {minutes} minutes about:\n{safe_text}",
                        parse_mode='MarkdownV2')
        
        # Start reminder thread
        threading.Thread(target=reminder_thread, args=(message.chat.id, reminder)).start()
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

def reminder_thread(chat_id, reminder):
    try:
        # Calculate time to wait
        wait_time = reminder['trigger_time'] - time.time()
        if wait_time > 0:
            time.sleep(wait_time)
        
        # Check if reminder still exists
        if reminder in reminders:
            # Remove the reminder
            reminders.remove(reminder)
            
            # Send the reminder
            safe_text = escape_markdown(reminder['text'])
            bot.send_message(chat_id, 
                            f"⏰ *Reminder!*\n{safe_text}",
                            parse_mode='MarkdownV2')
    except Exception as e:
        print(f"Reminder thread error: {str(e)}")

# Admin Panel
@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id != admin_id:
        bot.send_message(message.chat.id, "⚠️ Access denied")
        return
        
    # Show admin panel
    total_files = len(database)
    total_users = len(users)
    banned_count = len(banned_users)
    
    admin_msg = escape_markdown(f"""
👑 *Admin Panel*
📊 Files: {total_files}
👥 Users: {total_users}
🚫 Banned: {banned_count}
📝 Quiz Questions: {len(quiz_questions)}
⏰ Active Reminders: {len(reminders)}
""")
    
    bot.send_message(message.chat.id,
                    admin_msg,
                    parse_mode='MarkdownV2',
                    reply_markup=create_admin_panel())

# Admin callback handlers - MOVED BEFORE GENERAL HANDLER
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_callbacks(call):
    if call.from_user.id != admin_id:
        bot.answer_callback_query(call.id, "⚠️ Access denied")
        return
        
    try:
        if call.data == 'admin_stats':
            show_admin_stats(call.message)
        elif call.data == 'admin_broadcast':
            start_broadcast(call.message)
        elif call.data == 'admin_ban':
            start_ban_user(call.message)
        elif call.data == 'admin_unban':
            start_unban_user(call.message)
        elif call.data == 'admin_add_quiz':
            start_add_quiz(call.message)
        elif call.data == 'admin_remove_quiz':
            start_remove_quiz(call.message)
        elif call.data == 'admin_view_reminders':
            show_reminders(call.message)
        elif call.data == 'admin_delete_file':
            start_delete_file(call.message)
        elif call.data == 'admin_restart':
            restart_bot(call.message)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Error: {str(e)}")

def show_admin_stats(message):
    total_files = len(database)
    total_users = len(users)
    banned_count = len(banned_users)
    active_reminders = len(reminders)
    
    # Count files by type
    counts = {
        'document': 0,
        'photo': 0,
        'video': 0,
        'audio': 0,
        'text': 0,
        'url': 0
    }
    
    for item in database:
        counts[item['type']] += 1
    
    stats_msg = escape_markdown(f"""
📊 *Detailed Statistics*
📄 Documents: {counts['document']}
📷 Photos: {counts['photo']}
🎬 Videos: {counts['video']}
🎵 Audio: {counts['audio']}
📝 Notes: {counts['text']}
🔗 Links: {counts['url']}
⭐ Total Files: {total_files}
👥 Total Users: {total_users}
🚫 Banned Users: {banned_count}
📝 Quiz Questions: {len(quiz_questions)}
⏰ Active Reminders: {active_reminders}
🧠 Flashcards: {len(flashcards)}
""")
    
    bot.send_message(message.chat.id, stats_msg, parse_mode='MarkdownV2', reply_markup=create_admin_panel())

def start_broadcast(message):
    msg = bot.send_message(message.chat.id, 
                          escape_markdown("📢 *Broadcast Message*\nSend the message you want to broadcast to all users:"),
                          parse_mode='MarkdownV2',
                          reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    try:
        if not message.text:
            bot.send_message(message.chat.id, "⚠️ Message cannot be empty.")
            return
            
        broadcast_text = message.text
        success_count = 0
        failed_count = 0
        
        # Store broadcast for history
        admin_broadcasts.append({
            'text': broadcast_text,
            'timestamp': time.time(),
            'admin_id': message.from_user.id
        })
        
        # Send to all users except banned ones
        for user_id in users:
            if user_id not in banned_users:
                try:
                    safe_text = escape_markdown(broadcast_text)
                    bot.send_message(user_id, f"📢 *Broadcast from Admin:*\n{safe_text}", parse_mode='MarkdownV2')
                    success_count += 1
                except Exception as e:
                    print(f"Failed to send to {user_id}: {str(e)}")
                    failed_count += 1
        
        bot.send_message(message.chat.id, 
                        f"✅ Broadcast completed!\n✅ Success: {success_count}\n❌ Failed: {failed_count}",
                        reply_markup=create_admin_panel())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

def start_ban_user(message):
    msg = bot.send_message(message.chat.id, 
                          escape_markdown("🚫 *Ban User*\nSend the user ID to ban:"),
                          parse_mode='MarkdownV2',
                          reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_ban_user)

def process_ban_user(message):
    try:
        if not message.text:
            bot.send_message(message.chat.id, "⚠️ User ID cannot be empty.")
            return
            
        user_id = int(message.text.strip())
        
        if user_id == admin_id:
            bot.send_message(message.chat.id, "⚠️ You cannot ban yourself!")
            return
            
        if user_id in banned_users:
            bot.send_message(message.chat.id, "⚠️ This user is already banned.")
            return
            
        banned_users.add(user_id)
        
        # Notify the user
        try:
            bot.send_message(user_id, "⚠️ You have been banned from using this bot.")
        except:
            pass  # User might have blocked the bot
        
        bot.send_message(message.chat.id, 
                        f"✅ User {user_id} has been banned.",
                        reply_markup=create_admin_panel())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

def start_unban_user(message):
    msg = bot.send_message(message.chat.id, 
                          escape_markdown("✅ *Unban User*\nSend the user ID to unban:"),
                          parse_mode='MarkdownV2',
                          reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_unban_user)

def process_unban_user(message):
    try:
        if not message.text:
            bot.send_message(message.chat.id, "⚠️ User ID cannot be empty.")
            return
            
        user_id = int(message.text.strip())
        
        if user_id not in banned_users:
            bot.send_message(message.chat.id, "⚠️ This user is not banned.")
            return
            
        banned_users.remove(user_id)
        
        # Notify the user
        try:
            bot.send_message(user_id, "✅ You have been unbanned and can now use the bot again.")
        except:
            pass  # User might have blocked the bot
        
        bot.send_message(message.chat.id, 
                        f"✅ User {user_id} has been unbanned.",
                        reply_markup=create_admin_panel())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

def start_add_quiz(message):
    msg = bot.send_message(message.chat.id, 
                          escape_markdown("➕ *Add Quiz Question*\nSend in format:\n`Question?\nOption1\nOption2\nOption3\nOption4\n[Correct option number]`\nExample:\n`What is 2+2?\n3\n4\n5\n6\n2`"),
                          parse_mode='MarkdownV2',
                          reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_add_quiz)

def process_add_quiz(message):
    try:
        if not message.text:
            bot.send_message(message.chat.id, "⚠️ Question cannot be empty.")
            return
            
        lines = message.text.strip().split('\n')
        if len(lines) < 6:
            bot.send_message(message.chat.id, "⚠️ Invalid format. Please use the specified format.")
            return
            
        question = lines[0]
        options = lines[1:5]
        
        try:
            correct_index = int(lines[5]) - 1  # Convert to 0-based index
            if correct_index < 0 or correct_index > 3:
                raise ValueError
        except:
            bot.send_message(message.chat.id, "⚠️ Correct option must be a number between 1 and 4.")
            return
            
        quiz_questions.append({
            'question': question,
            'options': options,
            'correct_index': correct_index
        })
        
        safe_q = escape_markdown(question)
        bot.send_message(message.chat.id, 
                        f"✅ Quiz question added:\n{safe_q}",
                        reply_markup=create_admin_panel())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

def start_remove_quiz(message):
    if not quiz_questions:
        bot.send_message(message.chat.id, "⚠️ No quiz questions available.")
        return
        
    msg = bot.send_message(message.chat.id, 
                          escape_markdown(f"➖ *Remove Quiz Question*\nSend the question number to remove (1-{len(quiz_questions)}):"),
                          parse_mode='MarkdownV2',
                          reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_remove_quiz)

def process_remove_quiz(message):
    try:
        if not message.text or not message.text.isdigit():
            bot.send_message(message.chat.id, "⚠️ Please enter a valid question number.")
            return
            
        question_num = int(message.text.strip())
        if question_num < 1 or question_num > len(quiz_questions):
            bot.send_message(message.chat.id, f"⚠️ Question number must be between 1 and {len(quiz_questions)}.")
            return
            
        removed = quiz_questions.pop(question_num - 1)
        safe_q = escape_markdown(removed['question'])
        
        bot.send_message(message.chat.id, 
                        f"✅ Quiz question removed:\n{safe_q}",
                        reply_markup=create_admin_panel())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

def show_reminders(message):
    if not reminders:
        bot.send_message(message.chat.id, "⚠️ No active reminders.")
        return
        
    msg = escape_markdown("⏰ *Active Reminders:*\n")
    for i, reminder in enumerate(reminders[:10]):  # Show first 10
        safe_text = escape_markdown(reminder['text'])
        trigger_time = datetime.datetime.fromtimestamp(reminder['trigger_time']).strftime('%Y-%m-%d %H:%M:%S')
        msg += f"\n{i+1}. User: {reminder['user_id']}\n   Text: {safe_text}\n   Time: {trigger_time}\n"
    
    if len(reminders) > 10:
        msg += escape_markdown(f"\n... and {len(reminders)-10} more")
    
    bot.send_message(message.chat.id, msg, parse_mode='MarkdownV2', reply_markup=create_admin_panel())

def start_delete_file(message):
    msg = bot.send_message(message.chat.id, "Enter file ID to delete:")
    bot.register_next_step_handler(msg, process_admin_file_delete)

def process_admin_file_delete(message):
    try:
        if message.from_user.id != admin_id:
            return
            
        # Check if user sent a command instead of content
        if message.text and message.text.startswith('/'):
            handle_command_in_step(message)
            return
            
        file_id_to_delete = message.text.strip()
        initial_count = len(database)
        
        # Remove all matching files
        database[:] = [item for item in database 
                      if not (item.get('content') == file_id_to_delete or 
                             item.get('file_name') == file_id_to_delete)]
        
        if len(database) < initial_count:
            bot.send_message(message.chat.id, "✅ File(s) deleted successfully", reply_markup=create_admin_panel())
        else:
            bot.send_message(message.chat.id, "❌ File not found", reply_markup=create_admin_panel())
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Error: {str(e)}")

def restart_bot(message):
    bot.send_message(message.chat.id, "🔄 Restarting bot...")
    # This will cause the bot to restart
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_main')
def back_to_main_callback(call):
    if call.from_user.id != admin_id:
        bot.answer_callback_query(call.id, "⚠️ Access denied")
        return
        
    admin_command(call.message)

# General callback handler - MOVED AFTER ADMIN HANDLER
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    try:
        if call.data == "add":
            add_command(call.message)
        elif call.data == "batchadd":
            batchadd_command(call.message)
        elif call.data == "search":
            search_command(call.message)
        elif call.data == "list":
            list_command(call.message)
        elif call.data == "flashcard":
            flashcard_command(call.message)
        elif call.data == "quiz":
            quiz_command(call.message)
        elif call.data == "timer":
            timer_command(call.message)
        elif call.data == "notes":
            notes_command(call.message)
        elif call.data == "reminder":
            remind_command(call.message)
        elif call.data == "help":
            help_msg = escape_markdown(f"""
ℹ️ Help and Support
Join our official channel for updates:
{channel_link}
For any issues or questions, please contact the admin.
Bot Features:
- Add any study materials
- Search across all shared resources
- Batch uploads
- Admin file management
- Flashcards for memorization
- Quiz for self-testing
- Study timer for productivity
- Notes organizer by subject
- Reminders for study sessions
""")
            bot.send_message(call.message.chat.id, help_msg, parse_mode='MarkdownV2')
    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Error: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    global batch_add_mode
    
    # Check if user is banned
    if message.from_user.id in banned_users:
        bot.send_message(message.chat.id, "⚠️ You have been banned from using this bot.")
        return
        
    if batch_add_mode:
        process_batchadd_step(message)
    elif message.text and message.text.startswith('/'):
        bot.send_message(message.chat.id,
                        escape_markdown("""
🛠 Available Commands:
/add - Add new item
/batchadd - Add multiple files
/search - Find files
/list - View all files
/flashcard - Manage flashcards
/quiz - Take a quiz
/timer - Start study timer
/notes - Organize notes
/remind - Set reminder
/admin - Admin panel (admins only)
/help - Get support
"""),
                        parse_mode='MarkdownV2',
                        reply_markup=create_main_menu())
    else:
        process_search_step(message, is_command=False)

print("🌟 Study Guru Bot is running with admin features...")
while True:
    try:
        bot.polling(none_stop=True, interval=2, timeout=60)
    except Exception as e:
        print(f"⚠️ Bot crashed: {str(e)}")
        print("🔄 Restarting in 5 seconds...")
        time.sleep(5)