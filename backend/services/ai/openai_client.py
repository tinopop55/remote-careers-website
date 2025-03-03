from pathlib import Path
from dotenv import load_dotenv
import os
from openai import OpenAI
import json
import logging
import time

# Load environment variables
load_dotenv(Path(__file__).parents[2] / '.env')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure the OpenAI API key is set
openai_api_key = os.getenv('OPENAI_API_KEY')
if not openai_api_key:
    raise ValueError("The OPENAI_API_KEY environment variable is not set")

# Initialize OpenAI client
client = OpenAI(
    api_key=openai_api_key,
)

# Define a maximum token limit
MAX_TOKENS = 4000  # Adjust based on GPT-4 model limits

def analyze_cv(text, language='ro'):
    """
    Analyze CV text using OpenAI GPT model.
    
    Args:
        text (str): The CV text to analyze
        language (str): 'ro' for Romanian or 'en' for English
    
    Returns:
        str: JSON string with analysis results
    """
    try:
        # Select prompt based on language
        if language == 'en':
            prompt = """
            You are a senior recruitment and CV analysis expert with 15+ years of experience evaluating candidates for Fortune 500 companies. Critically analyze this CV using strict evaluation criteria.

            Evaluation criteria for overall_score:
            - Below 40%: CVs with major flaws, lack of structure, no concrete achievements
            - 40-60%: Basic CVs with limited achievements and simple structure
            - 60-75%: Good CVs with quantifiable achievements and clear structure
            - 75-85%: Excellent CVs with demonstrated impact and ATS optimization
            - 85-95%: Exceptional CVs with remarkable achievements and measurable impact
            - Above 95%: Extremely rare - only for perfectly optimized CVs with extraordinary achievements

            Criteria for ats_score:
            - Evaluate formatting, keywords, structure
            - Penalize heavy formatting, tables, images
            - Check relevant keyword density
            - Analyze section clarity and formatting consistency

            Criteria for industry_fitness:
            - Evaluate relevance of experience for industry
            - Check domain-specific skills
            - Analyze relevant certifications and education
            - Measure impact in similar projects

            Return a JSON object with the following format:
            {
                "overall_score": number (using criteria above),
                "strengths": [
                    "Specifically identify: 'In role X you achieved Y measurable result...'",
                    "Highlight concrete data: 'You demonstrated Z through...'",
                    "Emphasize unique achievements: 'You differentiate yourself by...'"
                ],
                "weaknesses": [
                    "Specific and actionable: 'Section X would benefit from...'",
                    "With concrete examples: 'Metrics missing for achievement Y...'",
                    "With impact: 'Absence of Z reduces visibility...'"
                ],
                "recommendations": [
                    "Actionable and specific: 'Add metrics for project X...'",
                    "With examples: 'Rephrase achievement Y to highlight...'",
                    "With expected results: 'Including Z will increase ATS score by...'"
                ],
                "ats_score": number (based on ATS criteria),
                "industry_fitness": number (based on industry criteria),
                "job_fit_score": number (holistic evaluation),
                "areas_to_focus_on_next": [
                    "Clear priorities for improvement",
                    "With estimated impact for each change",
                    "With suggested timeframe for implementation"
                ]
            }

            IMPORTANT:
            - Be VERY critical in your evaluation
            - Strictly use the defined scoring criteria
            - Base all scores on concrete evidence from the CV
            - Specifically highlight shortcomings and areas for improvement
            - Penalize lack of metrics and quantifiable achievements
            - Overall score must reflect a strict holistic evaluation
            """
        else:  # Romanian prompt (existing)
            prompt = """
            Ești un expert senior în recrutare și analiză CV cu 15+ ani de experiență în evaluarea candidaților pentru companii Fortune 500. Analizează critic acest CV folosind criterii stricte de evaluare.

            Criterii de evaluare pentru scor_general:
            - Sub 40%: CV-uri cu greșeli majore, lipsă de structură, fără realizări concrete
            - 40-60%: CV-uri de bază cu realizări limitate și structură simplă
            - 60-75%: CV-uri bune cu realizări cuantificabile și structură clară
            - 75-85%: CV-uri excelente cu impact demonstrat și optimizare ATS
            - 85-95%: CV-uri excepționale cu realizări remarcabile și impact măsurabil
            - Peste 95%: Extrem de rar - doar pentru CV-uri perfect optimizate cu realizări extraordinare

            Criterii pentru scor_ats:
            - Evaluează formatarea, cuvintele cheie, structura
            - Penalizează heavy formatting, tabele, imagini
            - Verifică densitatea cuvintelor cheie relevante
            - Analizează claritatea secțiunilor și consistența formatării

            Criterii pentru industry_fitness:
            - Evaluează relevanța experienței pentru industrie
            - Verifică skillurile specifice domeniului
            - Analizează certificările și educația relevantă
            - Măsoară impactul în proiecte similare

            Returnează un obiect JSON cu următorul format:
            {
                "scor_general": number (folosește criteriile de mai sus),
                "puncte_forte": [
                    "Identifică specific: 'În rolul X ai obținut Y rezultat măsurabil...'",
                    "Evidențiază date concrete: 'Ai demonstrat Z prin...'",
                    "Subliniază realizări unice: 'Te diferențiezi prin...'"
                ],
                "puncte_slabe": [
                    "Specific și acționabil: 'Secțiunea X ar beneficia de...'",
                    "Cu exemple concrete: 'Lipsesc metrici pentru realizarea Y...'",
                    "Cu impact: 'Absența Z reduce vizibilitatea...'"
                ],
                "recomandari": [
                    "Acționabile și specifice: 'Adaugă metrici pentru proiectul X...'",
                    "Cu exemple: 'Reformulează realizarea Y pentru a evidenția...'",
                    "Cu rezultate așteptate: 'Includerea Z va crește scorul ATS cu...'"
                ],
                "scor_ats": number (bazat pe criteriile ATS),
                "industry_fitness": number (bazat pe criteriile de industrie),
                "job_fit_score": number (evaluare holistică),
                "areas_to_focus_on_next": [
                    "Priorități clare pentru îmbunătățire",
                    "Cu impact estimat pentru fiecare schimbare",
                    "Cu timeframe sugerat pentru implementare"
                ]
            }

            IMPORTANT:
            - Fii FOARTE critic în evaluare
            - Folosește strict criteriile de scoring definite
            - Bazează toate scorurile pe dovezi concrete din CV
            - Evidențiază specific lipsurile și zonele de îmbunătățire
            - Penalizează lipsa de metrici și realizări cuantificabile
            - Scorul general trebuie să reflecte o evaluare holistică strictă
            """

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ești un evaluator strict de CV-uri la nivel executiv, cu focus pe metrici și impact demonstrabil." if language == 'ro' else 
                                             "You are a strict CV evaluator at the executive level, focusing on metrics and demonstrable impact."},
                {"role": "user", "content": f"{prompt}\n\nCV Text:\n{text}"}
            ],
            temperature=0.3,  # Lower temperature for more consistent, critical evaluation
            max_tokens=1500
        )
        
        raw_analysis = response.choices[0].message.content
        analysis = json.loads(raw_analysis)
        
        # Handle response based on language
        if language == 'en':
            score = analysis["overall_score"]
            if score <= 25:
                classification = "Disastrous"
                color = "Red"
            elif score <= 50:
                classification = "Insufficient"
                color = "Amber"
            elif score <= 70:
                classification = "Encouraging"
                color = "Amber"
            elif score <= 85:
                classification = "Very Promising"
                color = "Green"
            elif score <= 95:
                classification = "Excellent"
                color = "Green"
            else:
                classification = "Exemplary"
                color = "Green"
                
            # Map English keys to expected keys for frontend compatibility
            analysis["scor_general"] = analysis.pop("overall_score")
            analysis["puncte_forte"] = analysis.pop("strengths")
            analysis["puncte_slabe"] = analysis.pop("weaknesses")
            analysis["recomandari"] = analysis.pop("recommendations")
            analysis["scor_ats"] = analysis.pop("ats_score")
            # Keep industry_fitness as is
            # Keep job_fit_score as is
            # Keep areas_to_focus_on_next as is
        else:  # Romanian
            score = analysis["scor_general"]
            if score <= 25:
                classification = "Dezastruos"
                color = "Red"
            elif score <= 50:
                classification = "Insuficient"
                color = "Amber"
            elif score <= 70:
                classification = "Încurajator"
                color = "Amber"
            elif score <= 85:
                classification = "Foarte Promițător"
                color = "Green"
            elif score <= 95:
                classification = "Excelent"
                color = "Green"
            else:
                classification = "Exemplar"
                color = "Green"
        
        analysis["classification"] = classification
        analysis["color"] = color
        analysis["language"] = language
        
        return json.dumps(analysis, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"Error in GPT analysis: {str(e)}")
        raise
