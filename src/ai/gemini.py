import os
from google import genai
from src.config import Config
from src.utils.logger import logger


class ResumeGenerator:
    def __init__(self):
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY) if Config.GEMINI_API_KEY else None

    def generate_cover_letter(self, job_title: str, company: str, job_description: str) -> str:
        if not self.client:
            return f"Dear Hiring Manager,\n\nI am excited to apply for the {job_title} position at {company}."

        prompt = f"""Write a professional cover letter (3-4 paragraphs) for a {job_title} position at {company}.

Job Description: {job_description[:2000]}

The applicant is based in Pakistan and is authorized to work remotely for UK companies.
Keep it concise, professional, and tailored to the job description."""

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            return response.text
        except Exception as e:
            logger.warning(f"Gemini cover letter failed: {e}")
            return f"Dear Hiring Manager,\n\nI am excited to apply for the {job_title} position at {company}."

    def tailor_resume_text(self, resume_text: str, job_title: str, job_description: str) -> str:
        if not self.client:
            return resume_text

        prompt = f"""Tailor the following resume for a {job_title} position.

Job Description: {job_description[:2000]}

Resume:
{resume_text[:3000]}

Return the tailored resume with relevant skills and experience highlighted based on the job requirements."""

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            return response.text
        except Exception as e:
            logger.warning(f"Gemini resume tailoring failed: {e}")
            return resume_text
