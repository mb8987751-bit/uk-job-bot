import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
    LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")

    INDEED_EMAIL = os.getenv("INDEED_EMAIL", "")
    INDEED_PASSWORD = os.getenv("INDEED_PASSWORD", "")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    FULL_NAME = os.getenv("FULL_NAME", "")
    PHONE = os.getenv("PHONE", "")
    EMAIL = os.getenv("EMAIL", "")
    CITY = os.getenv("CITY", "London, United Kingdom")
