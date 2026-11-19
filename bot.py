import os
import re
import threading
from bs4 import BeautifulSoup
from flask import Flask
import requests
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

app = Flask(__name__)


@app.route("/")
def home():
  return "Bot is alive!"


def run_web():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# دالة سحب الأرقام من مصدر مفتوح (sms24.me)
def fetch_free_numbers():
  try:
    res = requests.get("https://sms24.me", headers=HEADERS, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    numbers = []
    for a in soup.find_all("a", href=re.compile(r"/en/numbers/\d+")):
      text = a.get_text(" ", strip=True)
      match = re.search(r"(\+\d+)", text)
      if match:
        num = match.group(1)
        country = text.replace(num, "").strip() or "International"
        if (country, num) not in numbers:
          numbers.append((country, num))
      if len(numbers) >= 12:
        break
    return numbers
  except Exception as e:
    print("Error fetching numbers:", e)
    return []


# دالة سحب الرسائل الواردة للرقم المختار
def fetch_messages(phone_number):
  clean_num = phone_number.replace("+", "").strip()
  url = f"https://sms24.me/{clean_num}"
  try:
    res = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    msgs = []
    for dd in soup.find_all("dd")[:6]:
      msg_text = dd.get_text(" ", strip=True)
      if msg_text:
        msgs.append(f"📩 `{msg_text}`")
    return msgs
  except Exception as e:
    print("Error fetching messages:", e)
    return []


def main_reply_menu():
  markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  markup.add(
      KeyboardButton("📞 Get number"),
      KeyboardButton("📊 Live Traffic"),
      KeyboardButton("💳 My Wallet"),
      KeyboardButton("📈 My Stats"),
  )
  return markup


@bot.message_handler(commands=["start"])
def send_welcome(message):
  user_name = message.from_user.first_name
  welcome_text = (
      f"🤖 **Welcome {user_name} !** 💠\n\n"
      "🟢 Free Public OTP Bot\n"
      "🟢 Fast & Auto-Updated Numbers\n\n"
      "⬇️ Please select an option below:"
  )
  bot.send_message(
      message.chat.id,
      welcome_text,
      parse_mode="Markdown",
      reply_markup=main_reply_menu(),
  )


@bot.message_handler(func=lambda msg: True)
def handle_buttons(message):
  if message.text == "📞 Get number":
    wait_msg = bot.send_message(
        message.chat.id, "⏳ جاري سحب الأرقام المتاحة الآن..."
    )
    nums = fetch_free_numbers()
    if not nums:
      bot.edit_message_text(
          "⚠️ لم نتمكن من جلب الأرقام حالياً، حاول مرة أخرى بعد دقيقة.",
          message.chat.id,
          wait_msg.message_id,
      )
      return

    markup = InlineKeyboardMarkup(row_width=1)
    for country, num in nums:
      markup.add(
          InlineKeyboardButton(
              f"🌍 {country} | {num}", callback_data=f"num_{num}"
          )
      )
    bot.edit_message_text(
        "📱 **اختر رقماً من القائمة (أرقام عامة مجانية):**",
        message.chat.id,
        wait_msg.message_id,
        parse_mode="Markdown",
        reply_markup=markup,
    )

  elif message.text == "📊 Live Traffic":
    bot.send_message(
        message.chat.id, "📊 البوت متصل ويعمل بنظام السحب المباشر للأرقام العامة."
    )
  elif message.text == "💳 My Wallet":
    bot.send_message(
        message.chat.id,
        "💳 **الخدمة مجانية بالكامل!** لا تحتاج إلى رصيد لاستخدام الأرقام.",
    )
  elif message.text == "📈 My Stats":
    bot.send_message(
        message.chat.id,
        f"📈 معرف حسابك: `{message.from_user.id}`",
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
  if call.data.startswith("num_") or call.data.startswith("ref_"):
    phone = call.data.split("_")[1]
    bot.answer_callback_query(call.id, "🔄 جاري فحص الرسائل الواردة...")
    msgs = fetch_messages(phone)

    msg_body = (
        "\n\n".join(msgs)
        if msgs
        else "📭 لا توجد رسائل حديثة لهذا الرقم، اضغط تحديث بعد طلب الكود."
    )
    text = (
        f"📞 **الرقم المختار:** `{phone}`\n*(اضغط على الرقم لنسخه)*\n\n"
        f"📥 **آخر الرسائل الواردة:**\n{msg_body}"
    )

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "🔄 تحديث الرسائل (Refresh)", callback_data=f"ref_{phone}"
        )
    )

    try:
      bot.edit_message_text(
          text,
          call.message.chat.id,
          call.message.message_id,
          parse_mode="Markdown",
          reply_markup=markup,
      )
    except Exception:
      pass


if __name__ == "__main__":
  threading.Thread(target=run_web).start()
  print("Bot is running on Render...")
  bot.infinity_polling()
