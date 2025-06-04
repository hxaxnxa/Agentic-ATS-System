from crewai import Agent, Task, Crew
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import logging
from google.api_core.exceptions import ResourceExhausted
from time import sleep
import re

logging.basicConfig(level=logging.DEBUG, filename='logs.txt', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def get_llm(model_name, api_key):
    try:
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize {model_name}: {str(e)}")
        raise

api_key = os.getenv("GOOGLE_API_KEY")
llm = get_llm("gemini-1.5-flash", api_key)
llm_backup = get_llm("gemini-1.0-pro", api_key)

def fallback_ats_score(resume_text, job_description, required_experience):
    score = 50
    pain_points = []
    experience_match = re.search(r'(\d+)\s*(?:year|yr)', resume_text, re.IGNORECASE)
    candidate_years = int(experience_match.group(1)) if experience_match else 0
    if candidate_years < required_experience:
        gap = required_experience - candidate_years
        score -= 10 * gap
        pain_points.append(f"Insufficient experience: {candidate_years} years vs {required_experience} required")
    skills = ['Python', 'GCP', 'AWS', 'Kubernetes', 'Terraform', 'CI/CD', 'Java', 'Go', 'C++']
    for skill in skills:
        if skill.lower() in job_description.lower() and skill.lower() not in resume_text.lower():
            score -= 5
            pain_points.append(f"Missing skill: {skill}")
    score = max(0, min(100, score))
    pain_points = pain_points or ["No specific gaps identified"]
    logger.info(f"Fallback ATS score: {score}, Pain points: {pain_points}")
    return f"ATS Score: {score}\nPain Points:\n- " + "\n- ".join(pain_points)

def create_agents(primary_llm):
    agent1 = Agent(
        role="ATS Scorer",
        goal="Score a resume against a job description, identifying gaps.",
        backstory="Expert in applicant tracking systems, skilled at evaluating candidate fit.",
        llm=primary_llm,
        verbose=False,
        allow_delegation=False,
        max_iter=10,
        max_rpm=5,
        cache=False
    )
    agent2 = Agent(
        role="Job Description Generator",
        goal="Generate a job description and evaluate the resume against it.",
        backstory="Expert in crafting job descriptions and identifying candidate gaps.",
        llm=primary_llm,
        verbose=False,
        allow_delegation=False,
        max_iter=10,
        max_rpm=5,
        cache=False
    )
    logger.debug("Agents created successfully")
    return agent1, agent2

def create_tasks(resume_text, job_description, required_experience, primary_llm):
    agent1, agent2 = create_agents(primary_llm)
    task1 = Task(
        description=f"""
        Analyze the resume: {resume_text}
        Against the job description: {job_description}
        Required experience: {required_experience} years

        Instructions:
        - Calculate an ATS score (0-100) based on skill match, experience match, and qualifications.
        - Identify at least one pain point (e.g., missing skills, insufficient experience).

        Output:
        ATS Score: <score>
        Pain Points:
        - <pain_point>
        """,
        agent=agent1,
        expected_output="ATS Score: <score>\nPain Points: <list>",
        async_execution=False
    )
    task2 = Task(
        description=f"""
        From the resume: {resume_text}
        Instructions:
        - Generate a job description for a role requiring {required_experience} years of experience.
        - Start with a specific job title (e.g., "Junior AI/ML Engineer") on its own line.
        - Follow with a detailed job description including responsibilities and qualifications, without prefixes like "Job Description:" or separate summary sections.
        - Avoid placeholders or redundant text.
        - Calculate an ATS score (0-100) against the generated job description.
        - Identify at least one pain point.

        Output:
        Generated Job Description:
        <job_title>
        <job_description>
        ATS Score: <score>
        Pain Points:
        - <list>
        """,
        agent=agent2,
        expected_output="Generated Job Description: <job>\nATS Score: <score>\nPain Points: <list>",
        async_execution=False
    )
    logger.debug("Tasks created successfully")
    return task1, task2

def run_crew(resume_text, job_description, required_experience):
    max_retries = 3
    retry_delay = 15
    llms = [llm, llm_backup]

    for llm_instance in llms:
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Attempt {attempt} with {llm_instance.model}: Initializing tasks")
                task1, task2 = create_tasks(resume_text, job_description, required_experience, llm_instance)

                logger.info(f"Attempt {attempt}: Running Task 1")
                crew1 = Crew(agents=[task1.agent], tasks=[task1], verbose=1)
                task1_output = crew1.kickoff()
                logger.debug(f"Attempt {attempt}: Task 1 output: {task1_output}")
                if not task1_output or not isinstance(task1_output, str) or "ATS Score:" not in task1_output:
                    logger.error(f"Attempt {attempt}: Task 1 output invalid, using fallback")
                    task1_output = fallback_ats_score(resume_text, job_description, required_experience)

                logger.info(f"Attempt {attempt}: Running Task 2")
                crew2 = Crew(agents=[task2.agent], tasks=[task2], verbose=1)
                task2_output = crew2.kickoff()
                logger.debug(f"Attempt {attempt}: Task 2 output: {task2_output}")
                if not task2_output or not isinstance(task2_output, str) or "Generated Job Description:" not in task2_output:
                    logger.error(f"Attempt {attempt}: Task 2 output invalid")
                    raise Exception("Task 2 output invalid")

                result = f"{task1_output}\n\n{task2_output}"
                logger.info(f"Attempt {attempt}: Combined result: {result}")
                return result

            except ResourceExhausted as e:
                logger.error(f"Attempt {attempt}: Gemini API quota exceeded: {e}")
                if attempt < max_retries:
                    logger.info(f"Retrying after {retry_delay} seconds...")
                    sleep(retry_delay)
                    continue
                if llm_instance == llms[-1]:
                    logger.error("All LLM attempts failed, using fallback for Task 1")
                    task1_output = fallback_ats_score(resume_text, job_description, required_experience)
                    task2_output = "Generated Job Description:\nSoftware Engineer\nGeneric software engineering role requiring basic programming skills.\nATS Score: 50\nPain Points:\n- Unable to generate specific job description"
                    return f"{task1_output}\n\n{task2_output}"
            except Exception as e:
                logger.error(f"Attempt {attempt}: Error: {e}")
                if attempt < max_retries:
                    logger.info(f"Retrying after {retry_delay} seconds...")
                    sleep(retry_delay)
                    continue
                if llm_instance != llms[-1]:
                    logger.info(f"Switching to backup LLM: {llms[llms.index(llm_instance) + 1].model}")
                    break
    logger.error("All attempts failed, using fallback for Task 1")
    task1_output = fallback_ats_score(resume_text, job_description, required_experience)
    task2_output = "Generated Job Description:\nSoftware Engineer\nGeneric software engineering role requiring basic programming skills.\nATS Score: 50\nPain Points:\n- Unable to generate specific job description"
    return f"{task1_output}\n\n{task2_output}"