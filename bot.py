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
        " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://google.com",
}


# دالة السحب الذكي من عدة مصادر مفتوحة
def fetch_free_numbers():
  numbers = []

  # المصدر الأول: receivesms.cc
  try:
    res = requests.get("https://receivesms.cc", headers=HEADERS, timeout=12)
    if res.status_code == 200:
      soup = BeautifulSoup(res.text, "html.parser")
      for item in soup.find_all("a", href=re.compile(r"/number/\d+")):
        txt = item.get_text(" ", strip=True)
        match = re.search(r"(\+\d{7,15})", txt)
        if match:
          num = match.group(1)
          country = txt.replace(num, "").strip() or "Public"
          if not any(n[1] == num for n in numbers):
            numbers.append((country[:18], num, "cc"))
        if len(numbers) >= 12:
          return numbers
  except Exception as e:
    print("Source 1 error:", e)

  # المصدر الثاني الاحتياطي: quackr.io
  try:
    res = requests.get(
        "https://quackr.io", headers=HEADERS, timeout=12
    )
    if res.status_code == 200:
      soup = BeautifulSoup(res.text, "html.parser")
      for match in re.findall(r"\+\d{8,15}", soup.get_text()):
        if not any(n[1] == match for n in numbers):
          numbers.append(("Free Number", match, "qk"))
        if len(numbers) >= 12:
          return numbers
  except Exception as e:
    print("Source 2 error:", e)

  return numbers


# دالة جلب الرسائل حسب المصدر
def fetch_messages(phone_number, source):
  clean_num = phone_number.replace("+", "").strip()
  msgs = []

  try:
    if source == "cc":
      url = f"https://receivesms.ccnumber/{clean_num}"
      res = requests.get(url, headers=HEADERS, timeout=12)
      soup = BeautifulSoup(res.text, "html.parser")
      for row in soup.find_all("tr")[1:6]:
        cols = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        if len(cols) >= 2:
          msgs.append(f"📩 **{cols[0]}**:\n`{cols[1]}`")

    elif source == "qk":
      url = f"https://quackr.io/{clean_num}"
      res = requests.get(url, headers=HEADERS, timeout=12)
      soup = BeautifulSoup(res.text, "html.parser")
      for p in soup.find_all("p")[:8]:
        t = p.get_text(" ", strip=True)
        if len(t) > 10 and any(char.isdigit() for char in t):
          msgs.append(f"📩 `{t}`")
  except Exception as e:
    print("Fetch msg error:", e)

  return msgs[:5]


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
      "🟢 Multi-Source Auto-Updated Numbers\n\n"
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
        message.chat.id, "⏳ جاري البحث وسحب الأرقام المتاحة..."
    )
    nums = fetch_free_numbers()
    if not nums:
      bot.edit_message_text(
          "⚠️ جميع المصادر مشغولة حالياً أو تحظر السيرفر، حاول مرة أخرى بعد"
          " دقيقة.",
          message.chat.id,
          wait_msg.message_id,
      )
      return

    markup = InlineKeyboardMarkup(row_width=1)
    for country, num, src in nums:
      markup.add(
          InlineKeyboardButton(
              f"🌍 {country} | {num}", callback_data=f"num_{src}_{num}"
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
        message.chat.id,
        "📊 البوت متصل ويعمل بنظام السحب متعدد المصادر للأرقام العامة.",
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
    parts = call.data.split("_")
    src = parts[1]
    phone = parts[2]
    bot.answer_callback_query(call.id, "🔄 جاري فحص الرسائل الواردة...")
    msgs = fetch_messages(phone, src)

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
            "🔄 تحديث الرسائل (Refresh)", callback_data=f"ref_{src}_{phone}"
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
