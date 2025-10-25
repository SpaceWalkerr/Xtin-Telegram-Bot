import logging
from telegram import Update, User
from telegram.ext import (
    Application,
    MessageHandler,
    ChatMemberHandler,
    filters,
    ContextTypes
)
from telegram.constants import ChatMemberStatus
import re
import asyncio
from collections import defaultdict

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = '7363695605:AAGyAE1uRV7-qUUS8T25o2ALZooh43HahTI'
ANALYST_GROUP_ID = -1003197843879 # Replace with your analyst group ID
OPEN_GROUP_ID = -1003059299532    # Replace with your open group ID
ADMIN_CONTACT = '@suraj_nandan'  # Replace with admin contact

# Spam detection keywords (customize as needed)
SPAM_KEYWORDS = [
    'buy now', 'click here', 'limited offer', 'free money',
    'guaranteed profit', 'investment opportunity', 'make money fast'
]

# Store user warnings (user_id: warning_count)
user_warnings = defaultdict(int)


async def forward_analyst_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Forward messages from analyst group to open group with modifications
    """
    # Check if message is from analyst group
    if update.message and update.message.chat.id == ANALYST_GROUP_ID:
        message = update.message
        
        # Extract message content
        if message.text:
            modified_text = process_message_text(message.text)
            
            # Send to open group
            await context.bot.send_message(
                chat_id=OPEN_GROUP_ID,
                text=modified_text,
                parse_mode='HTML'
            )
            
        elif message.photo:
            caption = message.caption if message.caption else ""
            modified_caption = process_message_text(caption)
            
            await context.bot.send_photo(
                chat_id=OPEN_GROUP_ID,
                photo=message.photo[-1].file_id,
                caption=modified_caption,
                parse_mode='HTML'
            )
            
        elif message.document:
            caption = message.caption if message.caption else ""
            modified_caption = process_message_text(caption)
            
            await context.bot.send_document(
                chat_id=OPEN_GROUP_ID,
                document=message.document.file_id,
                caption=modified_caption,
                parse_mode='HTML'
            )
            
        elif message.video:
            caption = message.caption if message.caption else ""
            modified_caption = process_message_text(caption)
            
            await context.bot.send_video(
                chat_id=OPEN_GROUP_ID,
                video=message.video.file_id,
                caption=modified_caption,
                parse_mode='HTML'
            )
            
        elif message.voice:
            caption = message.caption if message.caption else ""
            modified_caption = process_message_text(caption) if caption else "🎤 Voice message from analyst"
            
            await context.bot.send_voice(
                chat_id=OPEN_GROUP_ID,
                voice=message.voice.file_id,
                caption=modified_caption,
                parse_mode='HTML'
            )
            
        logger.info(f"Forwarded message from analyst group to open group")


def process_message_text(text: str) -> str:
    """
    Process message text to:
    1. Make analyst name and designation bold
    2. Replace contact info with admin contact
    """
    if not text:
        return ""
    
    # Pattern to detect name and designation (customize based on your format)
    # Example: "John Doe, Senior Analyst" or "Name: John Doe\nDesignation: Analyst"
    
    # Make common titles and names bold
    text = re.sub(
        r'(Research Analyst|Senior Analyst|Chief Analyst|Analyst)(\s*[-:]\s*)(\w+\s+\w+)',
        r'<b>\3, \1</b>',
        text,
        flags=re.IGNORECASE
    )
    
    # Pattern for "Name: Something" format
    text = re.sub(
        r'(Name\s*:\s*)(\w+\s+\w+)',
        r'\1<b>\2</b>',
        text,
        flags=re.IGNORECASE
    )
    
    # Pattern for "Designation: Something" format
    text = re.sub(
        r'(Designation\s*:\s*)(\w+\s*\w*)',
        r'\1<b>\2</b>',
        text,
        flags=re.IGNORECASE
    )
    
    # Remove phone numbers and replace with admin contact
    text = re.sub(r'\+?\d[\d\s\-\(\)]{8,}\d', '', text)
    
    # Remove email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    
    # Remove @username mentions (except if it's the admin)
    text = re.sub(r'@\w+', lambda m: m.group(0) if ADMIN_CONTACT in m.group(0) else '', text)
    
    # Add admin contact at the end if not already present
    if ADMIN_CONTACT not in text:
        text += f"\n\n📞 For inquiries, contact: {ADMIN_CONTACT}"
    
    return text.strip()


async def greet_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Greet new members joining the open group
    """
    if not update.chat_member:
        return
        
    if update.chat_member.chat.id != OPEN_GROUP_ID:
        return
    
    new_status = update.chat_member.new_chat_member.status
    old_status = update.chat_member.old_chat_member.status
    
    # Check if user just joined
    if (old_status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED] and 
        new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]):
        
        user = update.chat_member.new_chat_member.user
        welcome_message = f"""
🎉 <b>Welcome to our group, {user.first_name}!</b> 🎉

We're glad to have you here! 

📌 <b>Group Rules:</b>
• No spam or promotional content
• Be respectful to all members
• Share valuable insights and discussions
• No offensive language

⚠️ <b>Note:</b> Spam messages will result in warnings. After 3 warnings, you will be removed from the group.

Enjoy your stay! 🚀

For any questions, contact: {ADMIN_CONTACT}
"""
        
        try:
            await context.bot.send_message(
                chat_id=OPEN_GROUP_ID,
                text=welcome_message,
                parse_mode='HTML'
            )
            logger.info(f"Welcomed new member: {user.first_name} (ID: {user.id})")
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")


async def check_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Check messages for spam in the open group and issue warnings
    """
    if not update.message or update.message.chat.id != OPEN_GROUP_ID:
        return
    
    # Skip if message is from a bot or if it's a forwarded message from analyst group
    if update.message.from_user.is_bot:
        return
    
    # Skip if user is admin or group creator
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=OPEN_GROUP_ID,
            user_id=update.message.from_user.id
        )
        if chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return
    except Exception as e:
        logger.error(f"Error checking user status: {e}")
    
    message_text = update.message.text or update.message.caption or ""
    message_text_lower = message_text.lower()
    
    # Check for spam keywords
    is_spam = any(keyword in message_text_lower for keyword in SPAM_KEYWORDS)
    
    # Additional spam checks
    if not is_spam:
        # Check for excessive links
        link_count = len(re.findall(r'http[s]?://\S+', message_text))
        if link_count > 2:
            is_spam = True
        
        # Check for excessive capitals
        if len(message_text) > 10:
            caps_ratio = sum(1 for c in message_text if c.isupper()) / len(message_text)
            if caps_ratio > 0.6:
                is_spam = True
        
        # Check for repeated messages (potential spam)
        if len(message_text) > 20 and message_text.count(message_text[:10]) > 3:
            is_spam = True
    
    if is_spam:
        user_id = update.message.from_user.id
        user_name = update.message.from_user.first_name
        user_warnings[user_id] += 1
        
        warning_count = user_warnings[user_id]
        
        # Delete the spam message
        try:
            await update.message.delete()
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
        
        if warning_count >= 3:
            # Ban user after 3 warnings
            try:
                await context.bot.ban_chat_member(
                    chat_id=OPEN_GROUP_ID,
                    user_id=user_id
                )
                
                await context.bot.send_message(
                    chat_id=OPEN_GROUP_ID,
                    text=f"⛔ <b>{user_name}</b> has been removed from the group for repeated spam violations.",
                    parse_mode='HTML'
                )
                
                # Reset warnings
                del user_warnings[user_id]
                logger.info(f"Banned user {user_name} (ID: {user_id}) for spam")
                
            except Exception as e:
                logger.error(f"Error banning user: {e}")
        else:
            # Issue warning
            warnings_left = 3 - warning_count
            warning_message = f"""
⚠️ <b>Warning for {user_name}</b> ⚠️

Your message has been removed for violating our spam policy.

<b>Warning {warning_count}/3</b>
You have <b>{warnings_left} warning(s)</b> remaining before removal.

Please follow the group rules!
"""
            
            try:
                await context.bot.send_message(
                    chat_id=OPEN_GROUP_ID,
                    text=warning_message,
                    parse_mode='HTML'
                )
                logger.info(f"Issued warning {warning_count}/3 to {user_name} (ID: {user_id})")
            except Exception as e:
                logger.error(f"Error sending warning: {e}")


def main():
    """
    Start the bot
    """
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    # Handler for analyst group messages (must come first to forward before spam check)
    application.add_handler(
        MessageHandler(
            filters.Chat(ANALYST_GROUP_ID) & filters.ALL,
            forward_analyst_message
        )
    )
    
    # Handler for new members
    application.add_handler(
        ChatMemberHandler(greet_new_member, ChatMemberHandler.CHAT_MEMBER)
    )
    
    # Handler for spam detection in open group
    application.add_handler(
        MessageHandler(
            filters.Chat(OPEN_GROUP_ID) & (filters.TEXT | filters.CAPTION) & ~filters.FORWARDED,
            check_spam
        )
    )
    
    # Start the bot
    logger.info("Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
