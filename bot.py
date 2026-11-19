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
}


# تحديد اسم وعلم الدولة بدقة
def get_country_info(phone):
  prefixes = [
      ("+1", "🇺🇸 USA / Canada"),
      ("+44", "🇬🇧 United Kingdom"),
      ("+49", "🇩🇪 Germany"),
      ("+33", "🇫🇷 France"),
      ("+61", "🇦🇺 Australia"),
      ("+55", "🇧🇷 Brazil"),
      ("+91", "🇮🇳 India"),
      ("+46", "🇸🇪 Sweden"),
      ("+31", "🇳🇱 Netherlands"),
      ("+34", "🇪🇸 Spain"),
      ("+39", "🇮🇹 Italy"),
      ("+48", "🇵🇱 Poland"),
      ("+7", "🇷🇺 Russia"),
      ("+62", "🇮🇩 Indonesia"),
      ("+358", "🇫🇮 Finland"),
      ("+45", "🇩🇰 Denmark"),
  ]
  for code, name in prefixes:
    if phone.startswith(code):
      return name
  return "🌍 International"


# دالة سحب الأرقام الكاملة والشغالة فقط (تستبعد الأرقام القصيرة أو المخفية)
def fetch_working_numbers():
  numbers = []
  seen = set()

  try:
    res = requests.get(
        "https://quackr.io", headers=HEADERS, timeout=15
    )
    if res.status_code == 200:
      soup = BeautifulSoup(res.text, "html.parser")
      # استخراج الرقم الكامل من الروابط الداخلية للصفحات النشطة
      for a in soup.find_all("a", href=re.compile(r"/temporary-numbers/\d+")):
        href = a.get("href", "")
        match = re.search(r"/temporary-numbers/(\d{11,15})$", href)
        if match:
          digits = match.group(1)
          # استبعاد الأرقام الوهمية المتكررة
          if len(set(digits)) > 3 and digits not in seen:
            seen.add(digits)
            full_num = "+" + digits
            country = get_country_info(full_num)
            numbers.append((country, full_num))
        if len(numbers) >= 15:
          break
  except Exception as e:
    print("Error fetching numbers:", e)

  return numbers


# دالة سحب أحدث الرسائل الواردة للرقم المختار
def fetch_messages(phone_number):
  clean_num = phone_number.replace("+", "").strip()
  msgs = []
  try:
    url = f"https://quackr.io/{clean_num}"
    res = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")

    for row in soup.find_all("tr")[1:7]:
      cols = [c.get_text(" ", strip=True) for c in row.find_all("td")]
      if len(cols) >= 2:
        sender = cols[0]
        body = cols[-1]
        msgs.append(f"📩 **{sender}**:\n`{body}`")

    if not msgs:
      for p in soup.find_all(["p", "div"]):
        t = p.get_text(" ", strip=True)
        if (
            15 < len(t) < 250
            and any(c.isdigit() for c in t)
            and "quackr" not in t.lower()
        ):
          entry = f"📩 `{t}`"
          if entry not in msgs:
            msgs.append(entry)
        if len(msgs) >= 5:
          break
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
      "🟢 Verified Full & Active Numbers\n\n"
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
        message.chat.id, "⏳ جاري فحص وجلب الأرقام الكاملة المتوفرة..."
    )
    nums = fetch_working_numbers()
    if not nums:
      bot.edit_message_text(
          "⚠️ تعذر جلب الأرقام حالياً، حاول مرة أخرى بعد دقيقة.",
          message.chat.id,
          wait_msg.message_id,
      )
      return

    markup = InlineKeyboardMarkup(row_width=1)
    for country, num in nums:
      markup.add(
          InlineKeyboardButton(
              f"{country} | {num}", callback_data=f"num_{num}"
          )
      )
    markup.add(
        InlineKeyboardButton(
            "🔄 تحديث قائمة الأرقام", callback_data="refresh_list"
        )
    )

    bot.edit_message_text(
        "📱 **الأرقام المتوفرة حالياً (أرقام كاملة وشغالة):**\n*(اختر رقماً لعرض"
        " الرسائل الواردة عليه)*",
        message.chat.id,
        wait_msg.message_id,
        parse_mode="Markdown",
        reply_markup=markup,
    )

  elif message.text == "📊 Live Traffic":
    bot.send_message(
        message.chat.id,
        "📊 البوت متصل ويعمل بنظام الفحص المباشر للأرقام الكاملة النشطة.",
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
  if call.data == "refresh_list":
    bot.answer_callback_query(call.id, "🔄 جاري تحديث القائمة...")
    nums = fetch_working_numbers()
    if nums:
      markup = InlineKeyboardMarkup(row_width=1)
      for country, num in nums:
        markup.add(
            InlineKeyboardButton(
                f"{country} | {num}", callback_data=f"num_{num}"
            )
        )
      markup.add(
          InlineKeyboardButton(
              "🔄 تحديث قائمة الأرقام", callback_data="refresh_list"
          )
      )
      try:
        bot.edit_message_reply_markup(
            call.message.chat.id, call.message.message_id, reply_markup=markup
        )
      except Exception:
        pass

  elif call.data.startswith("num_") or call.data.startswith("ref_"):
    phone = call.data.split("_")[1]
    bot.answer_callback_query(call.id, "🔄 جاري فحص الرسائل الواردة...")
    msgs = fetch_messages(phone)

    msg_body = (
        "\n\n".join(msgs)
        if msgs
        else "📭 لا توجد رسائل حديثة لهذا الرقم، اضغط تحديث بعد طلب الكود."
    )
    text = (
        f"📞 **الرقم الكامل:** `{phone}`\n*(اضغط على الرقم لنسخه)*\n\n"
        f"📥 **آخر الرسائل الواردة:**\n{msg_body}"
    )

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "🔄 تحديث الرسائل (Refresh)", callback_data=f"ref_{phone}"
        ),
        InlineKeyboardButton(
            "🔙 رجوع لقائمة الأرقام", callback_data="refresh_list"
        ),
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
