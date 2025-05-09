import re
from datetime import date
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format (E.164)"""
    if not phone:
        return False
    return bool(re.match(r'^\+[1-9]\d{1,14}$', phone))

def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def calculate_age(birth_date: date) -> int:
    """Calculate age from date of birth"""
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def simulate_otp_delivery(method: str, destination: str, otp_code: str, purpose: str):
    """Simulate sending an OTP code via WhatsApp or email"""
    # In a real application, this would integrate with WhatsApp API or email service
    # For simulation, we just log the event
    
    purpose_messages = {
        "signup": "to complete your signup",
        "login": "to log in to your account",
        "password_reset": "to reset your password",
    }
    
    purpose_text = purpose_messages.get(purpose, "for verification")
    
    if method == 'phone':
        message = f"Your verification code {purpose_text} is: {otp_code}"
        logger.info(f"[WHATSAPP SIMULATION] To: {destination}, Message: {message}")
    elif method == 'email':
        subject = f"Your verification code {purpose_text}"
        message = f"Your verification code is: {otp_code}\nThis code will expire in 5 minutes."
        logger.info(f"[EMAIL SIMULATION] To: {destination}, Subject: {subject}, Message: {message}")