from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
import os
import logging
import uuid
import io
import tempfile

# Import Supabase and Grok clients
from supabase import create_client, Client
from groq import Groq

# Import document processing libraries
import PyPDF2
import docx
from PIL import Image
import pytesseract

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Supabase client
supabase_url = os.environ['SUPABASE_URL']
supabase_key = os.environ['SUPABASE_ANON_KEY']
supabase: Client = create_client(supabase_url, supabase_key)

# Grok client
grok_client = Groq(api_key=os.environ['GROK_API_KEY'])
grok_model = os.environ.get('GROK_MODEL', 'llama-3-groq-70b-tool-use')

# Storage bucket name
storage_bucket = os.environ.get('STORAGE_BUCKET', 'army-documents')

# Create the main app
app = FastAPI(title="Indian Army Document Management System")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Models
class UserSignup(BaseModel):
    email: str
    password: str
    role: str  # 'clerk' or 'officer'
    full_name: str

class UserLogin(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    user_id: str
    email: str
    role: str
    message: str

class DocumentMetadata(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    file_size: int
    content_type: str
    storage_path: str
    uploaded_by: str
    extracted_text: str
    keywords: List[str]
    upload_date: datetime = Field(default_factory=datetime.utcnow)

class SearchRequest(BaseModel):
    query: str
    user_id: str

class SearchResult(BaseModel):
    document_id: str
    document_name: str
    relevance_score: float
    matched_content: str
    storage_path: str
    upload_date: str

# Helper Functions
def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF file"""
    try:
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""

def extract_text_from_docx(file_content: bytes) -> str:
    """Extract text from DOCX file"""
    try:
        doc = docx.Document(io.BytesIO(file_content))
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
    except Exception as e:
        logger.error(f"DOCX extraction error: {e}")
        return ""

def extract_text_from_image(file_content: bytes) -> str:
    """Extract text from image using OCR"""
    try:
        image = Image.open(io.BytesIO(file_content))
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        logger.error(f"OCR extraction error: {e}")
        return ""

def extract_text_from_file(filename: str, file_content: bytes) -> str:
    """Extract text based on file type"""
    ext = filename.lower().split('.')[-1]
    
    if ext == 'pdf':
        return extract_text_from_pdf(file_content)
    elif ext in ['docx', 'doc']:
        return extract_text_from_docx(file_content)
    elif ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
        return extract_text_from_image(file_content)
    elif ext == 'txt':
        return file_content.decode('utf-8', errors='ignore')
    else:
        return ""

def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extract keywords from text using simple frequency analysis"""
    # Remove common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'them', 'their', 'what', 'which', 'who', 'when', 'where', 'why', 'how'}
    
    words = text.lower().split()
    word_freq = {}
    
    for word in words:
        # Clean word
        word = ''.join(c for c in word if c.isalnum())
        if len(word) > 3 and word not in stop_words:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Sort by frequency and return top keywords
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, freq in sorted_words[:max_keywords]]

async def verify_auth_token(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Verify Supabase auth token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        # Extract token from "Bearer <token>"
        token = authorization.replace("Bearer ", "")
        
        # Verify token with Supabase
        user = supabase.auth.get_user(token)
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Get user role from database
        user_doc = await db.users.find_one({"supabase_id": user.user.id})
        
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found in database")
        
        return {
            "user_id": user_doc["_id"],
            "supabase_id": user.user.id,
            "email": user.user.email,
            "role": user_doc["role"]
        }
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# API Endpoints
@api_router.get("/")
async def root():
    return {"message": "Indian Army Document Management System API", "status": "active"}

@api_router.post("/auth/signup", response_model=AuthResponse)
async def signup(user_data: UserSignup):
    """Sign up a new user"""
    try:
        # Validate role
        if user_data.role not in ['clerk', 'officer']:
            raise HTTPException(status_code=400, detail="Invalid role. Must be 'clerk' or 'officer'")
        
        # Sign up with Supabase
        auth_response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "full_name": user_data.full_name,
                    "role": user_data.role
                }
            }
        })
        
        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Signup failed")
        
        # Store user in MongoDB
        user_doc = {
            "_id": str(uuid.uuid4()),
            "supabase_id": auth_response.user.id,
            "email": user_data.email,
            "role": user_data.role,
            "full_name": user_data.full_name,
            "created_at": datetime.utcnow()
        }
        
        await db.users.insert_one(user_doc)
        
        return AuthResponse(
            access_token=auth_response.session.access_token,
            user_id=user_doc["_id"],
            email=user_data.email,
            role=user_data.role,
            message="Signup successful"
        )
        
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")

@api_router.post("/auth/login", response_model=AuthResponse)
async def login(credentials: UserLogin):
    """Login user"""
    try:
        # Login with Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if not auth_response.user or not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Get user from MongoDB
        user_doc = await db.users.find_one({"supabase_id": auth_response.user.id})
        
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        return AuthResponse(
            access_token=auth_response.session.access_token,
            user_id=user_doc["_id"],
            email=credentials.email,
            role=user_doc["role"],
            message="Login successful"
        )
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=401, detail="Login failed")

@api_router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    """Upload document (Clerk only)"""
    # Verify authentication
    user_info = await verify_auth_token(authorization)
    
    # Check if user is clerk
    if user_info["role"] != "clerk":
        raise HTTPException(status_code=403, detail="Only clerks can upload documents")
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Extract text from document
        extracted_text = extract_text_from_file(file.filename, file_content)
        
        if not extracted_text:
            raise HTTPException(status_code=400, detail="Could not extract text from document")
        
        # Extract keywords
        keywords = extract_keywords(extracted_text)
        
        # Upload to Supabase Storage
        storage_path = f"{user_info['user_id']}/{uuid.uuid4()}_{file.filename}"
        
        supabase.storage.from_(storage_bucket).upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": file.content_type or "application/octet-stream"}
        )
        
        # Store metadata in MongoDB
        doc_metadata = {
            "_id": str(uuid.uuid4()),
            "name": file.filename,
            "file_size": len(file_content),
            "content_type": file.content_type or "application/octet-stream",
            "storage_path": storage_path,
            "uploaded_by": user_info["user_id"],
            "extracted_text": extracted_text,
            "keywords": keywords,
            "upload_date": datetime.utcnow()
        }
        
        await db.documents.insert_one(doc_metadata)
        
        return {
            "message": "Document uploaded successfully",
            "document_id": doc_metadata["_id"],
            "filename": file.filename,
            "keywords": keywords
        }
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@api_router.post("/documents/search", response_model=List[SearchResult])
async def search_documents(
    search_req: SearchRequest,
    authorization: Optional[str] = Header(None)
):
    """Search documents using AI (Officer only)"""
    # Verify authentication
    user_info = await verify_auth_token(authorization)
    
    # Check if user is officer
    if user_info["role"] != "officer":
        raise HTTPException(status_code=403, detail="Only officers can search documents")
    
    try:
        # Get all documents from MongoDB
        documents = await db.documents.find().to_list(length=None)
        
        if not documents:
            return []
        
        # Prepare documents for AI analysis
        doc_summaries = []
        for doc in documents:
            doc_summaries.append({
                "id": doc["_id"],
                "name": doc["name"],
                "keywords": doc["keywords"],
                "content_preview": doc["extracted_text"][:500]  # First 500 chars
            })
        
        # Use Grok AI to analyze and rank documents
        system_prompt = """You are an intelligent document search assistant for the Indian Army document management system.

Your task is to analyze the user's search query and find the most relevant documents from the provided list.

Documents available:
""" + str(doc_summaries) + """

For each relevant document, return a JSON object with:
- document_id: The ID of the document
- relevance_score: A score from 0.0 to 1.0 indicating relevance
- matched_content: A brief explanation of why this document matches

Return ONLY a JSON array of matching documents, ordered by relevance (highest first).
If no documents match, return an empty array: []

Example format:
[
  {"document_id": "abc123", "relevance_score": 0.95, "matched_content": "Contains information about..."},
  {"document_id": "def456", "relevance_score": 0.78, "matched_content": "Discusses..."}
]
"""
        
        response = grok_client.chat.completions.create(
            model=grok_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Find documents matching this query: {search_req.query}"}
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        # Parse AI response
        ai_response = response.choices[0].message.content.strip()
        
        # Extract JSON from response
        import json
        import re
        
        # Try to find JSON array in response
        json_match = re.search(r'\[.*\]', ai_response, re.DOTALL)
        if json_match:
            ranked_docs = json.loads(json_match.group())
        else:
            # Fallback: simple keyword matching
            ranked_docs = []
            query_lower = search_req.query.lower()
            for doc in documents:
                # Check if query matches document name or keywords
                name_match = query_lower in doc["name"].lower()
                keyword_match = any(query_lower in kw.lower() for kw in doc["keywords"])
                text_match = query_lower in doc["extracted_text"].lower()
                
                if name_match or keyword_match or text_match:
                    score = 0.0
                    if name_match:
                        score += 0.5
                    if keyword_match:
                        score += 0.3
                    if text_match:
                        score += 0.2
                    
                    ranked_docs.append({
                        "document_id": doc["_id"],
                        "relevance_score": min(score, 1.0),
                        "matched_content": f"Matches found in document: {doc['name']}"
                    })
            
            ranked_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        # Build search results
        results = []
        for ranked_doc in ranked_docs[:20]:  # Top 20 results
            doc = next((d for d in documents if d["_id"] == ranked_doc["document_id"]), None)
            if doc:
                results.append(SearchResult(
                    document_id=doc["_id"],
                    document_name=doc["name"],
                    relevance_score=ranked_doc["relevance_score"],
                    matched_content=ranked_doc["matched_content"],
                    storage_path=doc["storage_path"],
                    upload_date=doc["upload_date"].isoformat()
                ))
        
        return results
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@api_router.get("/documents")
async def list_documents(authorization: Optional[str] = Header(None)):
    """List all documents"""
    user_info = await verify_auth_token(authorization)
    
    try:
        documents = await db.documents.find().to_list(length=None)
        
        return {
            "total": len(documents),
            "documents": [
                {
                    "id": doc["_id"],
                    "name": doc["name"],
                    "size": doc["file_size"],
                    "upload_date": doc["upload_date"].isoformat(),
                    "keywords": doc["keywords"]
                }
                for doc in documents
            ]
        }
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Include the router in the main app
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize storage bucket on startup"""
    try:
        # Try to create bucket if it doesn't exist
        try:
            supabase.storage.get_bucket(storage_bucket)
            logger.info(f"Storage bucket '{storage_bucket}' already exists")
        except:
            supabase.storage.create_bucket(storage_bucket, options={"public": False})
            logger.info(f"Created storage bucket '{storage_bucket}'")
    except Exception as e:
        logger.warning(f"Storage bucket initialization: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()