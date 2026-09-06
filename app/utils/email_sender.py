"""
PDN Report Email Sender

"""

import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Configuration
class EmailConfig:
    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT = 587
    FROM_EMAIL = os.environ.get('GMAIL_USER', 'tomergur@gmail.com')
    APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
    REPORTS_DIR = Path("app/static/reports")

def get_html_template(pdn_code: str, first_name: str) -> str:
    """Generate HTML email template with minimal inline CSS for better email client support."""
    return f"""
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>מפת קוד המקור - {pdn_code}</title>
</head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; direction: rtl;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <tr>
            <td style="background: linear-gradient(135deg, #0b2e6b, #0a2a5f); color: white; padding: 30px; text-align: center;">
                <h1 style="margin: 0 0 10px 0; font-size: 24px; font-weight: bold;"> מפת קוד המקור</h1>
                <h2 style="margin: 0; font-size: 16px; font-weight: normal; opacity: 0.9;">ברוך הבא למסע הגילוי</h2>
            </td>
        </tr>
        <tr>
            <td style="padding: 30px;">
                <div style="font-size: 20px; font-weight: bold; color: #0b2e6b; margin-bottom: 20px; text-align: right; line-height: 1.4;">
                   {first_name}, ברוך הבא למסע שלך
                        מצ״ב מפת קוד המקור שלך.
                </div>
                <div style="background: rgba(11, 46, 107, 0.05); border: 1px solid rgba(11, 46, 107, 0.1); border-radius: 8px; padding: 20px; margin: 20px 0;">
                    <p style="font-size: 16px; line-height: 1.6; color: #1f2937; margin: 0;">שיטת PDN מאבחנת את "קוד המקור" – הצופן האישי שלך.<br>
זהו כלי אבחוני פורץ דרך בתחום התפתחות אישית תודעתית מוגן בפטנט, המהווה תבנית לניווט חייך. כפי ש־Waze מוביל אותך בדרכים הפיזיות, כך מפת קוד המקור משמשת מצפן, נווט פנימי המכוון אותך לבחור נכון, לנווט בביטחון ולצעוד בבירור לעבר הגשמת מטרותיך ויעודך.</p>
                </div>
                <div style="background: linear-gradient(135deg, rgba(11, 46, 107, 0.1), rgba(10, 42, 95, 0.08)); border: 2px solid #0b2e6b; border-radius: 12px; padding: 25px; margin: 25px 0; text-align: center;">
                    <div style="font-size: 14px; font-weight: 600; color: #6b7280; margin-bottom: 10px;">עפ“י תוצאות האבחון הצופן שלך</div>
                    <div style="font-size: 36px; font-weight: bold; color: #0b2e6b; margin: 15px 0;">{pdn_code}</div>
                </div>
                <div style="background: rgba(11, 46, 107, 0.05); border: 1px solid rgba(11, 46, 107, 0.1); border-radius: 8px; padding: 20px; margin: 20px 0;">
                    <p style="font-size: 16px; line-height: 1.6; color: #1f2937; margin: 0;"><br>
מפת קוד המקור חושפת את שלושת מנועי היסוד הייחודיים, את הדומיננטי, המייצב והמתמיר, המגלמים בתוכם את היכולות הכישורים המתנות ואף את הפחדים הסמויים המעצבים את בחירותיך ואת אופן התנהלותך בעולם.<br>
כאשר שלושת המנועים פועלים בהרמוניה, מתגלה הייעוד שלך, ביטוי חי של הערך, המתנה והחותם הייחודי שאתה מביא לעולם. מפת הצופן מעניקה לך בהירות, השראה וכלים מעשיים לנווט את חייך מתוך עוצמה, חיבור ומשמעות, כדי לממש את מלוא הפוטנציאל הטמון בך</p>
                </div>
            </td>
        </tr>
        <tr>
            <td style="background: rgba(255, 255, 255, 0.95); padding: 20px; text-align: center; border-top: 1px solid rgba(11, 46, 107, 0.1);">
                <div style="font-size: 12px; color: #6b7280; line-height: 1.4;">האבחון, הייעוץ, הכלים וכל ידע הניתן – אינם מהווים תחליף לטיפול רפואי, פסיכולוגי ,כלכלי או אחר. השימוש בהם איש בלבד ואינו מסחרי.<br>כל הזכויות שמורות למרכז CENTER PDN ובעליו.</div>
            </td>
        </tr>
    </table>
</body>
</html>
    """

def find_pdf_attachment(pdn_code: str) -> Optional[Path]:
    """Find PDF attachment for the given PDN code."""
    pdf_filename = f"{pdn_code.upper()}.pdf"
    pdf_path = EmailConfig.REPORTS_DIR / pdf_filename

    if pdf_path.exists():
        return pdf_path

    logger.warning(f"PDF file not found: {pdf_path}")
    return None

def attach_pdf(msg: MIMEMultipart, pdf_path: Path, pdn_code: str) -> bool:
    """Attach PDF file to email message."""
    try:
        with open(pdf_path, "rb") as file:
            attach = MIMEApplication(file.read(), _subtype="pdf")
            attach.add_header('Content-Disposition', 'attachment',
                              filename=f"{pdn_code.lower()}.pdf")
            msg.attach(attach)
        logger.info(f"PDF attachment added: {pdf_path.name}")
        return True
    except Exception as e:
        logger.error(f"Error attaching PDF {pdf_path}: {e}")
        return False

def send_email_via_smtp(msg: MIMEMultipart) -> bool:
    """Send email via SMTP."""
    try:
        with smtplib.SMTP(EmailConfig.SMTP_SERVER, EmailConfig.SMTP_PORT) as server:
            server.starttls()
            server.login(EmailConfig.FROM_EMAIL, EmailConfig.APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"SMTP error: {e}")
        return False

def send_pdn_code_email(user_answers: Dict[str, Any], pdn_code: str) -> bool:
    """
    Send comprehensive PDN report via email to the user.

    Args:
        user_answers (Dict): User's questionnaire answers and metadata
        pdn_code (str): Calculated PDN code

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Validate input
        user_email = user_answers.get('metadata', {}).get('email')
        first_name = user_answers.get('metadata', {}).get('first_name')
        if not user_email:
            logger.error("No email address found in user answers")
            return False

        if not pdn_code:
            logger.error("PDN code is required")
            return False

        # Create email message
        msg = MIMEMultipart()
        msg['From'] = EmailConfig.FROM_EMAIL
        msg['To'] = user_email
        msg['Subject'] = 'תוצאות אבחון צופן ״קוד המקור״ מבית PDN'

        # Attach HTML content
        html_content = get_html_template(pdn_code, first_name)
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        # Attach PDF if available
        pdf_path = find_pdf_attachment(pdn_code)
        if pdf_path:
            attach_pdf(msg, pdf_path, pdn_code)

        # Send email
        if send_email_via_smtp(msg):
            logger.info(f"Successfully sent PDN report to {user_email}")
            return True
        else:
            return False

    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False


def get_binat_invite_template(first_name: str, user_email: str) -> str:
    """Generate HTML email template for Binat chat invitation."""
    return f"""
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>הזמנה לבינת</title>
</head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; direction: rtl;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <tr>
            <td style="background: linear-gradient(135deg, #0b2e6b, #0a2a5f); color: white; padding: 30px; text-align: center;">
                <h1 style="margin: 0 0 10px 0; font-size: 24px; font-weight: bold;">בינת – המלווה האישית שלך</h1>
                <h2 style="margin: 0; font-size: 16px; font-weight: normal; opacity: 0.9;">גילוי עצמי עם קוד המקור (PDN)</h2>
            </td>
        </tr>
        <tr>
            <td style="padding: 30px;">
                <div style="font-size: 20px; font-weight: bold; color: #0b2e6b; margin-bottom: 20px; text-align: right; line-height: 1.6;">
                    היי {first_name},
                </div>
                <div style="font-size: 16px; line-height: 1.8; color: #1f2937; margin-bottom: 20px;">
                    יצרתי לך גישה לבינת — המלווה האישית שלך לגילוי עצמי עם קוד המקור (PDN).
                </div>
                <div style="background: linear-gradient(135deg, rgba(11, 46, 107, 0.1), rgba(10, 42, 95, 0.08)); border: 2px solid #0b2e6b; border-radius: 12px; padding: 25px; margin: 25px 0;">
                    <div style="font-size: 14px; font-weight: 600; color: #6b7280; margin-bottom: 15px;">פרטי כניסה:</div>
                    <div style="font-size: 16px; line-height: 2; color: #1f2937;">
                        <div style="margin-bottom: 8px;">
                            <strong>כניסה:</strong>
                            <a href="https://pdn-chat.onrender.com/pdn-binat/" style="color: #0b2e6b; text-decoration: underline;">https://pdn-chat.onrender.com/pdn-binat/</a>
                        </div>
                        <div style="margin-bottom: 8px;">
                            <strong>אימייל:</strong> {user_email}
                        </div>
                        <div>
                            <strong>סיסמה:</strong> pdn
                        </div>
                    </div>
                </div>
                <div style="font-size: 16px; line-height: 1.8; color: #1f2937; margin-bottom: 20px;">
                    פשוט נכנסים, מקלידים את מה שמעסיק אותך ובינת מלווה אותך בשיחה אישית מותאמת לקוד שלכם.
                </div>
                <div style="font-size: 18px; font-weight: bold; color: #0b2e6b; text-align: center; margin-top: 20px;">
                    בהצלחה!
                </div>
            </td>
        </tr>
        <tr>
            <td style="background: rgba(255, 255, 255, 0.95); padding: 20px; text-align: center; border-top: 1px solid rgba(11, 46, 107, 0.1);">
                <div style="font-size: 12px; color: #6b7280; line-height: 1.4;">כל הזכויות שמורות למרכז CENTER PDN ובעליו.</div>
            </td>
        </tr>
    </table>
</body>
</html>
    """


def send_binat_invite_email(user_email: str, first_name: str) -> bool:
    """
    Send Binat chat invitation email to the user.

    Args:
        user_email (str): User's email address
        first_name (str): User's first name

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        if not user_email:
            logger.error("No email address provided for Binat invite")
            return False

        if not first_name:
            first_name = user_email.split('@')[0]

        msg = MIMEMultipart()
        msg['From'] = EmailConfig.FROM_EMAIL
        msg['To'] = user_email
        msg['Subject'] = 'הזמנה לבינת – המלווה האישית שלך לגילוי עצמי'

        html_content = get_binat_invite_template(first_name, user_email)
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        if send_email_via_smtp(msg):
            logger.info(f"Successfully sent Binat invite to {user_email}")
            return True
        else:
            return False

    except Exception as e:
        logger.error(f"Failed to send Binat invite email: {str(e)}")
        return False


def send_coupon_invite_email(user_email: str, coupon_code: str, base_url: str = "https://pdn-chat.onrender.com") -> bool:
    """Send coupon invite email with a link to the diagnostic questionnaire.

    Args:
        user_email: Recipient email address
        coupon_code: The coupon code to include in the email
        base_url: The base URL of the application

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        if not user_email:
            logger.error("No email address provided for coupon invite")
            return False

        login_url = f"{base_url}/pdn-diagnose/?code={coupon_code}&email={user_email}"

        html_content = f"""
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>הזמנה לאבחון קוד המקור</title>
</head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; direction: rtl;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <tr>
            <td style="background: linear-gradient(135deg, #0b2e6b, #0a2a5f); color: white; padding: 30px; text-align: center;">
                <h1 style="margin: 0 0 10px 0; font-size: 24px; font-weight: bold;">הזמנה לאבחון קוד המקור</h1>
                <h2 style="margin: 0; font-size: 16px; font-weight: normal; opacity: 0.9;">PDN Center</h2>
            </td>
        </tr>
        <tr>
            <td style="padding: 30px;">
                <p style="font-size: 16px; line-height: 1.8; color: #1f2937; margin: 0 0 20px 0;">
                    שלום,<br><br>
                    קיבלת הזמנה לבצע אבחון קוד המקור שלך במערכת PDN.<br>
                    האבחון יחשוף את הצופן האישי שלך – כלי ייחודי לגילוי עצמי והתפתחות אישית.
                </p>

                <div style="background: linear-gradient(135deg, rgba(201, 169, 110, 0.15), rgba(201, 169, 110, 0.05)); border: 2px solid rgba(201, 169, 110, 0.4); border-radius: 12px; padding: 25px; margin: 25px 0; text-align: center;">
                    <div style="font-size: 14px; font-weight: 600; color: #6b7280; margin-bottom: 10px;">קוד הקופון שלך</div>
                    <div style="font-size: 32px; font-weight: bold; color: #0b2e6b; letter-spacing: 3px; margin: 10px 0; direction: ltr;">{coupon_code}</div>
                </div>

                <div style="background: rgba(11, 46, 107, 0.05); border-radius: 8px; padding: 20px; margin: 20px 0;">
                    <p style="font-size: 15px; line-height: 1.6; color: #374151; margin: 0 0 15px 0; font-weight: 600;">כיצד להתחיל:</p>
                    <ol style="font-size: 14px; line-height: 2; color: #4b5563; margin: 0; padding-right: 20px;">
                        <li>לחץ על הקישור למטה לכניסה למערכת</li>
                        <li>הזן את כתובת האימייל שלך</li>
                        <li>הזן את קוד הקופון שלמעלה בשדה "סיסמה או קוד קופון"</li>
                        <li>מלא את השאלון ותגלה את קוד המקור שלך</li>
                    </ol>
                </div>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{login_url}" style="display: inline-block; background: linear-gradient(135deg, #0b2e6b, #0a2a5f); color: white; text-decoration: none; padding: 14px 40px; border-radius: 8px; font-size: 16px; font-weight: 600;">
                        התחל את האבחון
                    </a>
                </div>

                <p style="font-size: 13px; color: #6b7280; text-align: center; margin-top: 20px;">
                    הקופון תקף לשימוש מוגבל. אם נתקלת בבעיה, פנה למנהל המערכת.
                </p>
            </td>
        </tr>
        <tr>
            <td style="background: rgba(255, 255, 255, 0.95); padding: 20px; text-align: center; border-top: 1px solid rgba(11, 46, 107, 0.1);">
                <div style="font-size: 12px; color: #6b7280;">כל הזכויות שמורות למרכז PDN Center</div>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        msg = MIMEMultipart()
        msg['From'] = EmailConfig.FROM_EMAIL
        msg['To'] = user_email
        msg['Subject'] = f'הזמנה לאבחון קוד המקור - קוד קופון: {coupon_code}'
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        if send_email_via_smtp(msg):
            logger.info("Successfully sent coupon invite to %s (code: %s)", user_email, coupon_code)
            return True
        return False

    except Exception as e:
        logger.error("Failed to send coupon invite email: %s", e)
        return False
