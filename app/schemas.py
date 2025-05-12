from pydantic import BaseModel, EmailStr, Field, validator
from typing import Dict, Optional, List, Union, Tuple
from datetime import date, datetime
import re
from .models import Gender, Sexuality, Theme, LoginType


class PhoneValidationResult(BaseModel):
    """Response model for phone validation results"""
    is_valid: bool
    message: str
    formatted_number: Optional[str] = None


class CountryPhoneData:
    """Country phone number validation data and functions"""
    
    # Database of country codes with their validation rules
    # Format: country_code -> {pattern, min_length, max_length, display_format, etc}
    COUNTRY_PHONE_DATA = {
        # North America
        "1": {
            "country": "United States/Canada",
            "pattern": r"^[2-9]\d{9}$",  # Excludes area codes starting with 0 or 1
            "display": "(XXX) XXX-XXXX",
            "min_length": 10,
            "max_length": 10,
            "starts_with": ["2", "3", "4", "5", "6", "7", "8", "9"]  # Valid first digits
        },
        
        # Europe
        "33": {
            "country": "France",
            "pattern": r"^[1-9]\d{8}$",
            "display": "X XX XX XX XX",
            "min_length": 9,
            "max_length": 9
        },
        "44": {
            "country": "United Kingdom",
            "pattern": r"^[1-9]\d{9,10}$",
            "display": "XXXX XXXXXX",
            "min_length": 10,
            "max_length": 11
        },
        "49": {
            "country": "Germany",
            "pattern": r"^[1-9]\d{9,11}$",
            "display": "XXXXX XXXXXX",
            "min_length": 10,
            "max_length": 12
        },
        
        # Asia
        "81": {
            "country": "Japan",
            "pattern": r"^[1-9]\d{8,9}$",
            "display": "XX-XXXX-XXXX",
            "min_length": 9,
            "max_length": 10
        },
        "86": {
            "country": "China",
            "pattern": r"^[1-9]\d{10}$",
            "display": "XXX XXXX XXXX",
            "min_length": 11,
            "max_length": 11
        },
        "91": {
            "country": "India",
            "pattern": r"^[6-9]\d{9}$",
            "display": "XXXXX XXXXX",
            "min_length": 10,
            "max_length": 10,
            "starts_with": ["6", "7", "8", "9"]  # Valid first digits for Indian mobile numbers
        },
        
        # Default for other countries
        "default": {
            "pattern": r"^\d{6,15}$",
            "min_length": 6,
            "max_length": 15
        }
    }
    
    # Add more countries (truncated for brevity - in production use the full list from the JS example)
    # This would include all the countries from the JavaScript example
    ADDITIONAL_COUNTRIES = {
        # Europe
        "30": {"country": "Greece", "pattern": r"^[2-9]\d{9}$", "min_length": 10, "max_length": 10},
        "31": {"country": "Netherlands", "pattern": r"^[1-9]\d{8}$", "min_length": 9, "max_length": 9},
        "32": {"country": "Belgium", "pattern": r"^[1-9]\d{7,8}$", "min_length": 8, "max_length": 9},
        "34": {"country": "Spain", "pattern": r"^[6-9]\d{8}$", "min_length": 9, "max_length": 9},
        "39": {"country": "Italy", "pattern": r"^[3-9]\d{8,9}$", "min_length": 9, "max_length": 10},
        
        # Asia 
        "60": {"country": "Malaysia", "pattern": r"^[1-9]\d{7,9}$", "min_length": 8, "max_length": 10},
        "61": {"country": "Australia", "pattern": r"^[1-9]\d{8}$", "min_length": 9, "max_length": 9},
        "62": {"country": "Indonesia", "pattern": r"^[1-9]\d{8,11}$", "min_length": 9, "max_length": 12},
        "65": {"country": "Singapore", "pattern": r"^[3-9]\d{7}$", "min_length": 8, "max_length": 8},
        "66": {"country": "Thailand", "pattern": r"^[1-9]\d{8,9}$", "min_length": 9, "max_length": 10},
        "880": {"country": "Bangladesh", "pattern": r"^1[3-9]\d{8}$", "min_length": 10, "max_length": 10},
        "92": {"country": "Pakistan", "pattern": r"^3[0-9]{9}$", "min_length": 10, "max_length": 10},

        # South America
        "54": {"country": "Argentina", "pattern": r"^[1-9]\d{9,10}$", "min_length": 10, "max_length": 11},
        "55": {"country": "Brazil", "pattern": r"^[1-9]\d{9,10}$", "min_length": 10, "max_length": 11},

        # Middle East
        "90": {"country": "Turkey", "pattern": r"^5\d{9}$", "min_length": 10, "max_length": 10},
        "971": {"country": "UAE", "pattern": r"^5[0-9]{8}$", "min_length": 9, "max_length": 9},
        "972": {"country": "Israel", "pattern": r"^5[0-9]{8}$", "min_length": 9, "max_length": 9},
        "966": {"country": "Saudi Arabia", "pattern": r"^5\d{8}$", "min_length": 9, "max_length": 9},

        # Africa
        "20": {"country": "Egypt", "pattern": r"^1[0-9]{9}$", "min_length": 10, "max_length": 10},
        "27": {"country": "South Africa", "pattern": r"^[1-9]\d{8}$", "min_length": 9, "max_length": 9},
        "234": {"country": "Nigeria", "pattern": r"^[7-9]\d{9}$", "min_length": 10, "max_length": 10}

    }
    
    def __init__(self):
        # Merge additional countries into the main database
        self.COUNTRY_PHONE_DATA.update(self.ADDITIONAL_COUNTRIES)
    
    def get_country_data(self, country_code: str) -> Dict:
        """Get validation data for a specific country code"""
        return self.COUNTRY_PHONE_DATA.get(str(country_code), self.COUNTRY_PHONE_DATA["default"])

    def get_all_country_codes(self) -> List[Dict]:
        """Get all available country codes for dropdown population"""
        return [
            {
                "code": code,
                "name": data.get("country", f"Country code +{code}"),
                "example": data.get("display", None)
            }
            for code, data in self.COUNTRY_PHONE_DATA.items()
            if code != "default"
        ]
    
    def format_phone_number(self, country_code: str, phone_number: str) -> str:
        """Format a phone number according to the country's display format"""
        country_data = self.get_country_data(str(country_code))
        display_format = country_data.get("display")
        
        # If no format is provided, return with basic formatting
        if not display_format:
            return f"+{country_code} {phone_number}"
        
        # Format based on country code
        if country_code == "1":  # US/Canada: (XXX) XXX-XXXX
            return f"+{country_code} ({phone_number[:3]}) {phone_number[3:6]}-{phone_number[6:]}"
        
        elif country_code == "44":  # UK: XXXX XXXXXX
            if len(phone_number) == 10:
                return f"+{country_code} {phone_number[:4]} {phone_number[4:]}"
            else:
                return f"+{country_code} {phone_number[:5]} {phone_number[5:]}"
        
        elif country_code == "91":  # India: XXXXX XXXXX
            return f"+{country_code} {phone_number[:5]} {phone_number[5:]}"
        
        else:
            # Generic formatting based on length
            if len(phone_number) <= 8:
                return f"+{country_code} {phone_number[:4]} {phone_number[4:]}"
            else:
                return f"+{country_code} {phone_number[:5]} {phone_number[5:]}"


class PhoneValidator:
    """Phone number validator with country-specific validation"""
    
    def __init__(self):
        self.country_data = CountryPhoneData()
    
    def parse_phone_number(self, phone: str) -> Tuple[str, str]:
        """Parse a phone number into country code and local number"""
        # Remove any non-numeric characters except the leading +
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        if not clean_phone.startswith('+'):
            raise ValueError("Phone number must start with a '+' followed by the country code")
        
        # Remove the + sign
        clean_phone = clean_phone[1:]
        
        # Try to extract country code
        # First check for 3-digit country codes
        for i in range(1, 4):
            potential_code = clean_phone[:i]
            if potential_code in self.country_data.COUNTRY_PHONE_DATA:
                return potential_code, clean_phone[i:]
        
        # If no country code found, assume it's invalid
        raise ValueError("Invalid country code")
    
    def validate_phone(self, phone: str) -> PhoneValidationResult:
        """Validate a phone number with comprehensive country rules"""
        if phone is None:
            return PhoneValidationResult(is_valid=False, message="Phone number cannot be empty")
        
        try:
            # Parse the phone number
            country_code, local_number = self.parse_phone_number(phone)
            
            # Get country-specific validation rules
            country_data = self.country_data.get_country_data(str(country_code))
            
            # Check length constraints
            min_length = country_data.get("min_length", 6)
            max_length = country_data.get("max_length", 15)
            
            if len(local_number) < min_length:
                return PhoneValidationResult(
                    is_valid=False,
                    message=f"Phone number is too short for {country_data.get('country', 'this country')}. "
                           f"Minimum length: {min_length}"
                )
            
            if len(local_number) > max_length:
                return PhoneValidationResult(
                    is_valid=False,
                    message=f"Phone number is too long for {country_data.get('country', 'this country')}. "
                           f"Maximum length: {max_length}"
                )
            
            # Check pattern
            pattern = country_data.get("pattern")
            if pattern and not re.match(pattern, local_number):
                return PhoneValidationResult(
                    is_valid=False,
                    message=f"Invalid phone number format for {country_data.get('country', 'this country')}"
                )
            
            # Special case validations for specific countries
            if country_code == "1":
                # North American Numbering Plan validation
                area_code = local_number[:3]
                if area_code in ["000", "911"]:
                    return PhoneValidationResult(is_valid=False, message="Invalid area code")
            
            if country_code == "44" and local_number.startswith("0"):
                return PhoneValidationResult(
                    is_valid=False,
                    message="UK numbers should not start with 0 when using country code"
                )
            
            if country_code == "91" and not any(local_number.startswith(digit) for digit in ["6", "7", "8", "9"]):
                return PhoneValidationResult(
                    is_valid=False,
                    message="Indian mobile numbers must start with 6, 7, 8, or 9"
                )
            
            # Format the phone number
            formatted_number = self.country_data.format_phone_number(country_code, local_number)
            
            # If all checks pass, the number is valid
            return PhoneValidationResult(
                is_valid=True,
                message="Valid phone number",
                formatted_number=formatted_number
            )
            
        except ValueError as e:
            return PhoneValidationResult(is_valid=False, message=str(e))


# Example Pydantic model with phone validation
class UserModel(BaseModel):
    name: str
    email: str
    phone_number: Optional[str] = None
    
    @validator('phone_number')
    def validate_phone(cls, v):
        if v is None:
            return v
        
        validator = PhoneValidator()
        result = validator.validate_phone(v)
        
        if not result.is_valid:
            raise ValueError(result.message)
        
        # Return the formatted number (or just return v if you want to keep the original)
        return result.formatted_number

# ---- Base Models ---- #
class OTPBase(BaseModel):
    country_code: str
    phone_number: str
    email: Optional[EmailStr] = None

    @validator('phone_number')
    def validate_phone(cls, v, values):
        country_code = str(values.get('country_code'))
        if not country_code:
            raise ValueError('country_code is required for phone validation')

        validator = PhoneValidator()
        full_phone = f"+{country_code}{v}"
        result = validator.validate_phone(full_phone)

        if not result.is_valid:
            raise ValueError(result.message)

        return v


class UserBase(BaseModel):
    username: str
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    country_code: str
    phone_number: str
    date_of_birth: date
    gender: Gender
    sexuality: Sexuality
    theme: Theme

    @validator('first_name', 'last_name')
    def validate_names(cls, v):
        if not re.match(r'^[A-Za-z]+$', v):
            raise ValueError('Name must contain only alphabetic characters')
        return v

    @validator('username')
    def validate_username(cls, v):
        if not v.islower():
            raise ValueError('Username must be lowercase')
        if not re.match(r'^[a-z0-9_\.]+$', v):
            raise ValueError('Username must contain only lowercase letters, numbers, underscores (_) or dots (.)')
        if len(v) < 3 or len(v) > 20:
            raise ValueError('Username must be between 3 and 20 characters')
        return v

    @validator('date_of_birth')
    def validate_age(cls, v):
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 13:
            raise ValueError('User must be at least 13 years old')
        return v
        
    @validator('phone_number')
    def validate_phone(cls, v, values):
        country_code = str(values.get('country_code'))
        if not country_code:
            raise ValueError('country_code is required for phone validation')

        validator = PhoneValidator()
        full_phone = f"+{country_code}{v}"
        result = validator.validate_phone(full_phone)

        if not result.is_valid:
            raise ValueError(result.message)

        return v

# ---- Request Models ---- #
class PhoneVerificationRequest(BaseModel):
    country_code: str
    phone_number: str

    @validator('phone_number')
    def validate_phone(cls, v, values):
        country_code = str(values.get('country_code'))
        if not country_code:
            raise ValueError("country_code is required to validate phone_number")

        full_phone = f"+{country_code}{v}"
        validator = PhoneValidator()
        result = validator.validate_phone(full_phone)
        if not result.is_valid:
            raise ValueError(result.message)
        return v


class OTPVerificationRequest(BaseModel):
    country_code: str
    phone_number: str
    otp_code: str

    @validator('phone_number')
    def validate_phone(cls, v, values):
        country_code = str(values.get('country_code'))
        if not country_code:
            raise ValueError('country_code is required for phone validation')

        validator = PhoneValidator()
        full_phone = f"+{country_code}{v}"
        result = validator.validate_phone(full_phone)

        if not result.is_valid:
            raise ValueError(result.message)

        return v

    @validator('otp_code')
    def validate_otp(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError('OTP must be a 6-digit number')
        return v


class UserCreateRequest(UserBase):
    password: str
    confirm_password: str
    profile_picture_url: Optional[str] = None

    @validator('profile_picture_url')
    def validate_profile_url(cls, v):
        if v is not None and not re.match(r'^https?://.+\..+', v):
            raise ValueError('Invalid URL format for profile picture')
        return v

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v

    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v


class LoginRequest(BaseModel):
    login_id: str  # Can be phone, email, or username
    password: str

    @validator('login_id')
    def detect_login_format(cls, v):
        # Phone number format validation (E.164 with exactly 10 digits after country code)
        if re.match(r'^\+[1-9]\d{1,3}\d{10}$', v):
            return v  # Valid phone number
        # Email validation
        elif re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
            return v  # Valid email
        # Username validation (lowercase, alphanumeric, and only _ or . as special chars)
        elif re.match(r'^[a-z0-9_\.]+$', v):
            return v  # Valid username
        raise ValueError('login_id must be a valid phone number (E.164 format), email, or username (lowercase with only _ or . as special characters)')
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v
    
    # Simulating a check against user database
    def validate_user_exists(self, db_users):
        # This would normally query a database
        # For demonstration purposes only
        mock_users = {
            "+12345678901": "user1",
            "user.name": "user2",
            "test@example.com": "user3"
        }
        
        if self.login_id not in mock_users:
            raise ValueError("User with this login ID does not exist")
        return True

class OAuthLoginRequest(BaseModel):
    token: str
    provider: str  # "google" or "apple"
    
    @validator('provider')
    def validate_provider(cls, v):
        valid_providers = ["google", "apple"]
        if v.lower() not in valid_providers:
            raise ValueError(f"Provider must be one of: {', '.join(valid_providers)}")
        return v.lower()

class ForgotPasswordRequest(BaseModel):
    login_id: str  # Can be phone, email, or username
    country_code: str
    
    @validator('login_id')
    def detect_login_format(cls, v):
        # Phone number format validation (E.164 with exactly 10 digits after country code)
        if re.match(r'^\+[1-9]\d{1,3}\d{10}$', v):
            return v  # Valid phone number
        # Email validation
        elif re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
            return v  # Valid email
        # Username validation (lowercase, alphanumeric, and only _ or . as special chars)
        elif re.match(r'^[a-z0-9_\.]+$', v):
            return v  # Valid username
        raise ValueError('login_id must be a valid phone number (E.164 format), email, or username (lowercase with only _ or . as special characters)')

class ResetPasswordRequest(BaseModel):
    login_id: str
    otp_code: str
    new_password: str
    confirm_password: str
    
    @validator('login_id')
    def detect_login_format(cls, v):
        # Phone number format validation (E.164 with exactly 10 digits after country code)
        if re.match(r'^\+[1-9]\d{1,3}\d{10}$', v):
            return v  # Valid phone number
        # Email validation
        elif re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
            return v  # Valid email
        # Username validation (lowercase, alphanumeric, and only _ or . as special chars)
        elif re.match(r'^[a-z0-9_\.]+$', v):
            return v  # Valid username
        raise ValueError('login_id must be a valid phone number (E.164 format), email, or username (lowercase with only _ or . as special characters)')
    
    @validator('otp_code')
    def validate_otp(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError('OTP must be a 6-digit number')
        return v
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

class ThemeUpdateRequest(BaseModel):
    theme: Theme
    
    @validator('theme')
    def validate_theme(cls, v):
        if v not in [Theme.Dark, Theme.Light]:
            raise ValueError('Theme must be either "Dark" or "Light"')
        return v

# ---- Response Models ---- #
class UserResponse(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    country_code: str
    phone_number: str
    date_of_birth: date
    gender: Gender
    sexuality: Sexuality
    theme: Theme
    profile_picture_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        orm_mode = True
        
    @property
    def formatted_phone_number(self):
        return f"+{self.country_code}{self.phone_number}"

class OTPResponse(BaseModel):
    message: str
    expires_at: datetime

class MessageResponse(BaseModel):
    message: str

    
class Token(BaseModel):
    """Schema for token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str
    
class RefreshTokenInDB(BaseModel):
    """Schema for a stored refresh token"""
    token: str
    expires_at: datetime
    
class CountryCodeResponse(BaseModel):
    code: str
    name: str
    example: Optional[str]
