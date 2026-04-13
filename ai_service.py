import re
from groq import Groq
from config import Config

groq_client = Groq(api_key=Config.GROQ_API_KEY)
MODEL = Config.LLAMA_MODEL


def _chat(prompt: str, temperature: float = 0.7) -> str:
    try:
        resp = groq_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=2048,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        err = str(e)
        print(f"[AI] Groq error: {err}")
        return f"AI_ERROR: {err}"


def _is_error(text: str) -> bool:
    return text.startswith("AI_ERROR:") or "decommissioned" in text or "invalid_request" in text


# ── Relevance Score ──────────────────────────────────────────────────────────

def calculate_relevance_score(jd_text: str, resume_text: str) -> str:
    prompt = f"""You are an expert HR analyst. Score how well this resume matches the job description.

JOB DESCRIPTION:
{jd_text[:3000]}

RESUME:
{resume_text[:3000]}

You MUST respond in EXACTLY this format, nothing else:
Relevance Score: [NUMBER between 0 and 100]
Reason: [2-3 sentences about key strengths and weaknesses]

Example:
Relevance Score: 72
Reason: The candidate has strong Flutter and JavaScript experience. However they lack Python backend skills mentioned in the JD. Their freelance experience shows relevant real-world development.
"""
    result = _chat(prompt, temperature=0.3)
    if _is_error(result):
        return "Relevance Score: 0\nReason: AI error — please try again."
    return result


# ── Interview Questions ──────────────────────────────────────────────────────

def generate_questions(jd_text: str, resume_text: str) -> list:
    prompt = f"""You are a senior technical interviewer. Generate exactly 10 interview questions.

RULES:
- Questions 1-5: Technical (about candidate skills + JD requirements)
- Questions 6-8: Behavioral (STAR method)
- Questions 9-10: Situational
- Every question MUST end with ?
- Number them: 1. 2. 3. etc.
- ONLY output the 10 numbered questions, no other text

JOB DESCRIPTION:
{jd_text[:2500]}

RESUME:
{resume_text[:2500]}

Output 10 questions:"""

    result = _chat(prompt, temperature=0.7)

    fallbacks = [
        "Could you walk me through your most relevant technical project?",
        "What programming languages and frameworks are you most comfortable with?",
        "How do you approach debugging a complex production issue?",
        "Describe your experience with version control and collaborative development.",
        "How do you ensure code quality and maintainability in your projects?",
        "Tell me about a time you had to learn a new technology quickly. How did you handle it?",
        "Describe a situation where you disagreed with a team member. How did you resolve it?",
        "Tell me about your most challenging project and how you overcame obstacles.",
        "If given a project with unclear requirements, how would you proceed?",
        "How would you handle a situation where a deadline is at risk due to technical blockers?",
    ]

    if _is_error(result):
        return fallbacks

    lines = result.strip().split("\n")
    questions = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r'^[\dQq]+[\.\)\-]\s*', '', line).strip()
        if cleaned and len(cleaned) > 15:
            if not cleaned.endswith('?'):
                cleaned += '?'
            questions.append(cleaned)

    while len(questions) < 10:
        questions.append(fallbacks[len(questions) % len(fallbacks)])

    return questions[:12]


# ── Skill Gap Analysis ───────────────────────────────────────────────────────

def identify_skill_gaps(jd_text: str, resume_text: str) -> str:
    prompt = f"""You are an AI Career Coach. Find skill gaps between this job description and resume.

JOB DESCRIPTION:
{jd_text[:2500]}

RESUME:
{resume_text[:2500]}

Respond ONLY in this EXACT format:

Technical Gaps:
• [missing technical skill]
• [missing technical skill]

Soft Skill / Experience Gaps:
• [missing soft skill or experience]
• [missing soft skill or experience]

If no gaps in a section write "• None identified".
Start with "Technical Gaps:" now:"""

    result = _chat(prompt, temperature=0.3)
    if _is_error(result):
        return "Technical Gaps:\n• Could not analyze — AI error. Please try again.\n\nSoft Skill / Experience Gaps:\n• N/A"
    return result


# ── Answer Evaluation ────────────────────────────────────────────────────────

def evaluate_answer(question: str, answer_transcript: str, job_role: str = "") -> str:
    prompt = f"""Evaluate this interview answer briefly (3-4 sentences). Cover clarity, relevance, depth, and one improvement tip.

Question: {question}
Answer: {answer_transcript}"""
    result = _chat(prompt, temperature=0.5)
    if _is_error(result):
        return "Could not evaluate answer at this time."
    return result
