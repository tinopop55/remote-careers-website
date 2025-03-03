from pathlib import Path
import sys
import os
import traceback  # Import traceback for detailed error logging
from dotenv import load_dotenv

# Load environment variables FIRST
env_path = Path(__file__).parent / '.env'
print(f"Looking for .env at: {env_path}")
load_dotenv(env_path)

# Use an absolute path for UPLOAD_FOLDER so it's correctly located on Render
UPLOAD_FOLDER = os.path.join(os.getcwd(), os.getenv('PDF_UPLOAD_FOLDER', 'uploads'))
print(f"UPLOAD_FOLDER path: {UPLOAD_FOLDER}")
print(f"Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")
if os.path.exists(UPLOAD_FOLDER):
    print(f"Upload folder permissions: {oct(os.stat(UPLOAD_FOLDER).st_mode)[-3:]}")

print(f"Current directory: {os.getcwd()}")
print(f"OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')}")  # Check if API key is loaded

# Add backend folder to system path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
import logging
import json
import smtplib
import pdfplumber
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from services.ai.openai_client import analyze_cv
# Comment out the Stripe import since we don't need it yet
# from services.payments.stripe_client import create_checkout_session
from services.logging.error_logger import log_error  # Import the error logger
from services.users.user_manager import register_user, record_cv_analysis, update_language_preference

# Flask app setup
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
ALLOWED_EXTENSIONS = {'pdf'}
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("EMAIL_USER")
SMTP_PASS = os.getenv("EMAIL_PASS")

# Ensure uploads folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    """Extract text from a PDF file with multiple fallback methods."""
    extraction_results = []
    extracted_text = ""
    
    # Method 1: Try with pdfplumber first
    try:
        with pdfplumber.open(file_path) as pdf:
            text = '\n'.join([page.extract_text() or "" for page in pdf.pages])
        if text.strip():
            app.logger.info("PDF extracted successfully with pdfplumber")
            extraction_results.append(("pdfplumber", True, text))
            extracted_text = text.strip()
        else:
            extraction_results.append(("pdfplumber", False, "No text extracted"))
    except Exception as e:
        app.logger.warning(f"pdfplumber extraction failed: {str(e)}")
        extraction_results.append(("pdfplumber", False, str(e)))
    
    # If we already have text, return it
    if extracted_text:
        return extracted_text
    
    # Method 2: Try with PyPDF2
    try:
        import PyPDF2
        # Try newer PyPDF2 version first
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            if text.strip():
                app.logger.info("PDF extracted successfully with PyPDF2 PdfReader")
                extraction_results.append(("PyPDF2 PdfReader", True, text))
                return text.strip()
            else:
                extraction_results.append(("PyPDF2 PdfReader", False, "No text extracted"))
        except Exception as e:
            app.logger.warning(f"PyPDF2 PdfReader extraction failed: {str(e)}")
            extraction_results.append(("PyPDF2 PdfReader", False, str(e)))
            
            # Try older PyPDF2 version
            try:
                with open(file_path, 'rb') as file:
                    reader = PyPDF2.PdfFileReader(file)
                    text = ""
                    for page_num in range(reader.getNumPages()):
                        extracted = reader.getPage(page_num).extractText()
                        if extracted:
                            text += extracted + "\n"
                if text.strip():
                    app.logger.info("PDF extracted successfully with PyPDF2 PdfFileReader")
                    extraction_results.append(("PyPDF2 PdfFileReader", True, text))
                    return text.strip()
                else:
                    extraction_results.append(("PyPDF2 PdfFileReader", False, "No text extracted"))
            except Exception as e:
                app.logger.warning(f"PyPDF2 PdfFileReader extraction failed: {str(e)}")
                extraction_results.append(("PyPDF2 PdfFileReader", False, str(e)))
    except ImportError:
        app.logger.warning("PyPDF2 not available")
        extraction_results.append(("PyPDF2", False, "Module not available"))
    
    # Method 3: Try with OCR if available and previous methods failed
    try:
        from pdf2image import convert_from_path
        import pytesseract
        
        app.logger.info("Attempting OCR extraction with pdf2image and pytesseract")
        
        # Convert PDF to images
        images = convert_from_path(file_path)
        
        # Extract text from images using OCR
        text = ""
        for i, img in enumerate(images):
            app.logger.info(f"Processing page {i+1} with OCR")
            page_text = pytesseract.image_to_string(img)
            if page_text.strip():
                text += page_text + "\n"
        
        if text.strip():
            app.logger.info("PDF extracted successfully with OCR")
            extraction_results.append(("OCR", True, text))
            return text.strip()
        else:
            extraction_results.append(("OCR", False, "No text extracted"))
    except Exception as e:
        app.logger.warning(f"OCR extraction failed: {str(e)}")
        extraction_results.append(("OCR", False, str(e)))
    
    # Final fallback - try a simple binary read of the PDF to extract any text
    try:
        app.logger.info("Attempting basic text extraction")
        with open(file_path, 'rb') as file:
            binary_data = file.read()
            # Try to decode as UTF-8, ignoring errors
            text = binary_data.decode('utf-8', errors='ignore')
            # Filter to only printable ASCII characters
            import string
            printable = set(string.printable)
            text = ''.join(filter(lambda x: x in printable, text))
            
            if len(text) > 100:  # If we have a reasonable amount of text
                app.logger.info("Basic text extraction succeeded")
                extraction_results.append(("Basic", True, text))
                return text
            else:
                extraction_results.append(("Basic", False, "Insufficient text extracted"))
    except Exception as e:
        app.logger.warning(f"Basic extraction failed: {str(e)}")
        extraction_results.append(("Basic", False, str(e)))
    
    # Log all extraction attempts for debugging
    app.logger.error(f"All text extraction methods failed for {file_path}")
    for method, success, message in extraction_results:
        app.logger.error(f"  Method: {method}, Success: {success}, Message: {message[:100]+'...' if len(message)>100 else message}")
    
    # If all methods failed
    return ""

def validate_pdf(file_path):
    """
    Validate the PDF file, checking file size, page count, and if it contains extractable text.
    
    Args:
        file_path (str): Path to the PDF file
        
    Returns:
        dict: Dictionary with 'valid' boolean and 'message' string
    """
    try:
        # Check file size (10MB max)
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # in MB
        if file_size > 10:
            return {"valid": False, "message": "File is too large (maximum 10MB)"}
            
        # First attempt - try with pdfplumber
        try:
            with pdfplumber.open(file_path) as pdf:
                if len(pdf.pages) > 10:
                    return {"valid": False, "message": "PDF has too many pages (maximum 10 pages)"}
                
                # Check if at least one page has extractable text
                has_text = False
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    if text.strip():
                        has_text = True
                        break
                
                if not has_text:
                    app.logger.warning(f"No text found in PDF with pdfplumber: {file_path}")
                    # Continue validation with other methods
                else:
                    return {"valid": True, "message": "PDF is valid (pdfplumber)"}
        except Exception as e:
            app.logger.warning(f"pdfplumber validation failed: {str(e)}")
            # Continue with other validation methods
        
        # Second attempt - try with PyPDF2
        try:
            import PyPDF2
            try:
                # Try newer PyPDF2 version first
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    num_pages = len(reader.pages)
                    
                    if num_pages > 10:
                        return {"valid": False, "message": "PDF has too many pages (maximum 10 pages)"}
                    
                    # Check if at least one page has extractable text
                    has_text = False
                    for page in reader.pages:
                        text = page.extract_text() or ""
                        if text.strip():
                            has_text = True
                            break
                    
                    if not has_text:
                        app.logger.warning(f"No text found in PDF with PyPDF2 (PdfReader): {file_path}")
                    else:
                        return {"valid": True, "message": "PDF is valid (PyPDF2 PdfReader)"}
            except Exception as e1:
                app.logger.warning(f"PyPDF2 PdfReader validation failed: {str(e1)}")
                
                # Try older PyPDF2 version
                try:
                    with open(file_path, 'rb') as f:
                        reader = PyPDF2.PdfFileReader(f)
                        num_pages = reader.getNumPages()
                        
                        if num_pages > 10:
                            return {"valid": False, "message": "PDF has too many pages (maximum 10 pages)"}
                        
                        # Check if at least one page has extractable text
                        has_text = False
                        for page_num in range(num_pages):
                            text = reader.getPage(page_num).extractText() or ""
                            if text.strip():
                                has_text = True
                                break
                        
                        if not has_text:
                            app.logger.warning(f"No text found in PDF with PyPDF2 (PdfFileReader): {file_path}")
                        else:
                            return {"valid": True, "message": "PDF is valid (PyPDF2 PdfFileReader)"}
                except Exception as e2:
                    app.logger.warning(f"PyPDF2 PdfFileReader validation failed: {str(e2)}")
        except ImportError:
            app.logger.warning("PyPDF2 not available")
        
        # Third attempt - just check if file exists and is non-empty
        # This is a more lenient fallback option to avoid rejecting valid PDFs
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            app.logger.info(f"Falling back to basic validation for PDF: {file_path}")
            return {"valid": True, "message": "PDF passed basic validation"}
        
        # If all methods failed, return false
        return {"valid": False, "message": "Could not validate PDF file with any available method"}
        
    except Exception as e:
        app.logger.error(f"Error validating PDF: {str(e)}")
        traceback.print_exc()
        return {"valid": False, "message": f"Error validating PDF: {str(e)}"}

@app.route('/')
def home():
    return render_template('landing.html', stripe_public_key=os.getenv("STRIPE_PUBLIC_KEY"))

@app.route('/analyze', methods=['POST'])
def analyze():
    file_path = None
    try:
        # Get email and language
        email = request.form.get('email')
        language = request.form.get('language', 'ro')  # Default to Romanian
        
        app.logger.info(f"Processing analysis request for {email} in language: {language}")
        
        # Register or update user
        register_user(email, language)
        
        # File validation
        if 'cv' not in request.files:
            app.logger.error(f"No file part in the request for {email}")
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['cv']
        if file.filename == '':
            app.logger.error(f"No selected file for {email}")
            return jsonify({"error": "No selected file"}), 400
        
        if not file.filename.lower().endswith('.pdf'):
            app.logger.error(f"File is not a PDF: {file.filename}")
            return jsonify({"error": "File must be a PDF document"}), 400
        
        if file:
            # Create a timestamp-based unique filename to avoid collisions
            import uuid
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            original_filename = secure_filename(file.filename)
            filename = f"{timestamp}_{unique_id}_{original_filename}"
            
            # Ensure upload directory exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            # Save the file
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            app.logger.info(f"File saved at {file_path} for {email}")
            
            # Validate PDF
            app.logger.info(f"Validating PDF: {file_path}")
            validation_result = validate_pdf(file_path)
            if not validation_result['valid']:
                app.logger.error(f"PDF validation failed for {email}: {validation_result['message']}")
                # Attempt to clean up
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        app.logger.info(f"Deleted invalid file: {file_path}")
                except Exception as cleanup_err:
                    app.logger.warning(f"Failed to delete invalid file: {cleanup_err}")
                return jsonify({"error": validation_result['message']}), 400
            
            # Extract text
            app.logger.info(f"Extracting text from PDF: {file_path}")
            extracted_text = extract_text_from_pdf(file_path)
            if not extracted_text:
                app.logger.error(f"Failed to extract text from PDF for {email}")
                # Attempt to clean up
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        app.logger.info(f"Deleted unprocessable file: {file_path}")
                except Exception as cleanup_err:
                    app.logger.warning(f"Failed to delete unprocessable file: {cleanup_err}")
                return jsonify({"error": "Failed to extract text from PDF. Please ensure it contains selectable text."}), 400
            
            # Record CV analysis
            record_cv_analysis(email)
            
            # Analyze CV
            try:
                app.logger.info(f"Analyzing CV text for {email} (text length: {len(extracted_text)})")
                analysis_result = analyze_cv(extracted_text, language)
                app.logger.info(f"CV analyzed successfully for {email}")
                
                # Send email with analysis
                try:
                    send_analysis_email(email, analysis_result, language)
                    app.logger.info(f"Analysis email sent to {email}")
                except Exception as e:
                    traceback.print_exc()
                    app.logger.error(f"Failed to send email to {email}: {str(e)}")
                    # Continue even if email fails
                
                # Attempt to clean up the uploaded file
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        app.logger.info(f"Deleted processed file: {file_path}")
                except Exception as cleanup_err:
                    app.logger.warning(f"Failed to delete processed file: {cleanup_err}")
                
                # Return analysis result to the frontend
                return jsonify({
                    "message": "CV analyzed successfully",
                    "summary": analysis_result
                }), 200
                
            except Exception as e:
                traceback.print_exc()
                app.logger.error(f"Error analyzing CV for {email}: {str(e)}")
                return jsonify({"error": f"Error analyzing CV: {str(e)}"}), 500
                
    except Exception as e:
        traceback.print_exc()
        app.logger.error(f"Unexpected error in analyze route: {str(e)}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
    finally:
        # Final cleanup in case any error occurred and file wasn't deleted
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                app.logger.info(f"Cleaned up file in finally block: {file_path}")
            except Exception as cleanup_err:
                app.logger.warning(f"Failed to clean up file in finally block: {cleanup_err}")

def send_analysis_email(recipient_email, cv_report, language='ro'):
    """Send CV analysis report via email."""
    try:
        # Parse JSON report
        report_data = json.loads(cv_report)
        
        # Choose email template based on language
        if language.lower() == 'en':
            subject = "Your CV Analysis Results"
            body = create_email_template_en(report_data)
        else:
            subject = "Rezultatul Analizei CV-ului Tău"
            body = create_email_template_ro(report_data)
        
        # Send email
        sender_email = os.environ.get('EMAIL_USER')
        password = os.environ.get('EMAIL_PASS')
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email
        
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP(os.environ.get('SMTP_SERVER'), int(os.environ.get('SMTP_PORT'))) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        
        app.logger.info(f"Email sent to {recipient_email}")
        return True
    except Exception as e:
        app.logger.error(f"Failed to send email: {str(e)}")
        traceback.print_exc()
        return False

@app.route('/create-payment-session', methods=['POST'])
def create_payment():
    try:
        data = request.get_json()
        email = data.get("email")
        if not email:
            logger.error("No email provided in payment request")
            return jsonify({"error": "Email address is required"}), 400

        # Since we're not using Stripe yet, return a placeholder URL
        session_url = "https://buy.stripe.com/cN200t3Ac3ID23uaEF"  # placeholder Stripe URL
        logger.info(f"Payment placeholder URL returned for email: {email}")
        return jsonify({"url": session_url})

    except Exception as e:
        log_error("payment_processing", str(e), data.get("email") if data else None, data)
        logger.error(f"Payment session error: {str(e)}")
        return jsonify({"error": "Payment processing error"}), 500

@app.route('/set-language', methods=['POST'])
def set_language():
    """Update a user's language preference."""
    try:
        data = request.get_json()
        email = data.get("email")
        language = data.get("language")
        
        if not email or not language:
            return jsonify({"error": "Email and language are required"}), 400
            
        if language not in ['ro', 'en']:
            return jsonify({"error": "Invalid language selection"}), 400
            
        success = update_language_preference(email, language)
        
        if success:
            return jsonify({"success": True, "message": "Language preference updated"})
        else:
            return jsonify({"error": "Failed to update language preference"}), 500
            
    except Exception as e:
        log_error("set_language", str(e), data.get("email") if data else None, data)
        return jsonify({"error": "Error updating language preference"}), 500

@app.route('/tool')
def cv_tool():
    success = request.args.get('success')
    email = request.args.get('email')
    
    if not success or not email:
        logger.warning(f"Invalid tool access attempt - success: {success}, email: {email}")
        return redirect(url_for('home'))

    logger.info(f"User accessing tool after payment: {email}")
    return render_template('index.html', user_email=email)

@app.route('/tools/cv-analyzer')
def cv_analyzer():
    """Render the CV analyzer tool page."""
    return render_template('tools/cv-analyzer.html')

@app.route('/tools/cv-evaluator')
def cv_evaluator():
    """Render the CV evaluator page."""
    return render_template('tools/cv-evaluator.html')

@app.route('/index.html')
def index():
    return render_template('index.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/services/accelerator')
def accelerator():
    return render_template('services/accelerator.html')

@app.route('/about')
def about_page():
    return render_template('about.html')

@app.route('/send-contact', methods=['POST'])
def send_contact():
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        field = request.form.get('field')
        message = request.form.get('message')
        language = request.form.get('language', 'ro')
        
        if not all([name, email, field, message]):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        # Create email subject and body
        subject = f"New Contact Form Submission from {name}"
        email_body = f"""
        New contact form submission:
        
        Name: {name}
        Email: {email}
        Professional Field: {field}
        Message: {message}
        Language: {language}
        """
        
        # Send email
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = SMTP_USER
        msg['To'] = "remotegururomania@gmail.com"
        msg.attach(MIMEText(email_body, 'plain'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        
        if language == 'ro':
            success_message = "Mulțumim pentru mesaj! Te vom contacta în curând."
        else:
            success_message = "Thank you for your message! We'll contact you soon."
            
        return jsonify({'success': True, 'message': success_message})
    
    except Exception as e:
        app.logger.error(f"Error in contact form: {str(e)}")
        log_error("Contact Form", str(e), traceback.format_exc())
        return jsonify({'success': False, 'message': 'An error occurred. Please try again later.'}), 500

def create_email_template_en(report_data):
    """Create HTML email template in English."""
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #2C3E50; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0;">
            <h1 style="margin: 0;">Your CV Analysis Results</h1>
        </div>
        
        <div style="background-color: #f9f9f9; padding: 20px; border-radius: 0 0 5px 5px; border: 1px solid #ddd; border-top: none;">
            <p>Hello,</p>
            <p>Thank you for using our CV analysis service. Here are your results:</p>
            
            <div style="background-color: #fff; padding: 15px; border-radius: 5px; margin: 20px 0; border: 1px solid #ddd;">
                <h2 style="color: #2C3E50; margin-top: 0; text-align: center;">Overall Score: <span style="color: {get_score_color(report_data['scor_general'])}">{report_data['scor_general']}%</span></h2>
                
                <div style="display: flex; justify-content: space-between; margin: 20px 0; text-align: center;">
                    <div style="flex: 1; padding: 10px; background-color: #f2f2f2; border-radius: 5px; margin: 0 5px;">
                        <div style="font-size: 24px; font-weight: bold; color: #3498DB;">{report_data['scor_ats']}%</div>
                        <div style="font-size: 14px; color: #7f8c8d;">ATS Score</div>
                    </div>
                    <div style="flex: 1; padding: 10px; background-color: #f2f2f2; border-radius: 5px; margin: 0 5px;">
                        <div style="font-size: 24px; font-weight: bold; color: #3498DB;">{report_data['industry_fitness']}%</div>
                        <div style="font-size: 14px; color: #7f8c8d;">Industry Fitness</div>
                    </div>
                    <div style="flex: 1; padding: 10px; background-color: #f2f2f2; border-radius: 5px; margin: 0 5px;">
                        <div style="font-size: 24px; font-weight: bold; color: #3498DB;">{report_data['job_fit_score']}%</div>
                        <div style="font-size: 14px; color: #7f8c8d;">Job Fit Score</div>
                    </div>
                </div>
                
                <h3 style="color: #27AE60;">Strengths:</h3>
                <ul style="color: #333;">
                    {''.join([f"<li>{point}</li>" for point in report_data['puncte_forte']])}
                </ul>
                
                <h3 style="color: #E74C3C;">Areas for Improvement:</h3>
                <ul style="color: #333;">
                    {''.join([f"<li>{area}</li>" for area in report_data['puncte_slabe']])}
                </ul>
                
                <h3 style="color: #F39C12;">Recommendations:</h3>
                <ul style="color: #333;">
                    {''.join([f"<li>{tip}</li>" for tip in report_data['recomandari']])}
                </ul>
                
                <h3 style="color: #3498DB;">Areas to Focus On Next:</h3>
                <ul style="color: #333;">
                    {''.join([f"<li>{area}</li>" for area in report_data['areas_to_focus_on_next']])}
                </ul>
            </div>
            
            <div style="background-color: #2C3E50; color: white; padding: 15px; border-radius: 5px; text-align: center; margin: 20px 0;">
                <h3 style="margin-top: 0;">Ready to take your career to the next level?</h3>
                <p>Get a professionally optimized CV and stand out among other candidates!</p>
                <a href="https://buy.stripe.com/cN200t3Ac3ID23uaEF" style="display: inline-block; background-color: #E74C3C; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 10px;">Improve Your CV Now</a>
            </div>
            
            <p>If you have any questions, feel free to reply to this email.</p>
            <p>Best regards,<br>The Remote Coaching Academy Team</p>
        </div>
        
        <div style="text-align: center; padding: 20px; color: #7f8c8d; font-size: 12px;">
            <p>© 2023 Remote Coaching Academy. All rights reserved.</p>
        </div>
    </body>
    </html>
    """

def create_email_template_ro(report_data):
    """Create HTML email template in Romanian
