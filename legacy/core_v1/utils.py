import pypdf 
import docx
import pytesseract
from PIL import Image
import os
import json
from sentence_transformers import SentenceTransformer
from django.conf import settings
from pgvector.django import CosineDistance
from groq import Groq
from dotenv import load_dotenv

from .models import DocumentChunk, Document

load_dotenv() 

model = SentenceTransformer('all-MiniLM-L6-v2')

# Note: Make sure this path is correct for your local machine
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def get_groq_client():
    """Helper function to guarantee a fresh, open connection to Groq"""
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))

def extract_document_metadata(raw_text):
    if not raw_text or len(raw_text.strip()) == 0:
        return {"document_type": "Empty", "document_date": "Unknown", "summary": "Document contained no readable text."}

    if len(raw_text) > 4000:
        text_sample = raw_text[:2500] + "\n\n...[TEXT SKIPPED]...\n\n" + raw_text[-1500:]
    else:
        text_sample = raw_text 
    
    prompt = f"""
    Analyze the following document text and extract the exact metadata.
    Return ONLY a raw, valid JSON object. Do not include markdown formatting or conversational text.
    
    Required JSON structure:
    {{
        "document_type": "Infer the specific type of document. Keep it to 1-4 words.",
        "all_dates": [
            {{"date": "Exact Date", "context": "What this date represents (e.g., Effective Date, Due Date, Signed Date)"}}
        ],
        "summary": "CRITICAL: Write an extremely short summary. ABSOLUTE MAXIMUM 9 WORDS."
    }}
    Note: If no dates exist anywhere, return an empty array [] for all_dates.
    
    DOCUMENT TEXT:
    {text_sample}
    """

    # NEW: Instantiate a fresh client just for this request
    client = get_groq_client()

    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-oss-20b",
            temperature=0.0, 
        )
        
        result_text = response.choices[0].message.content.strip()
        
        if result_text.startswith("```"):
            result_text = result_text.strip("`").replace("json", "", 1).strip()
            
        metadata = json.loads(result_text)
        return metadata
    except Exception as e:
        print(f"🚨 METADATA EXTRACTION FAILED: {e}")
        return {"document_type": "Document", "document_date": "Unknown", "summary": "Analysis failed."}

def generate_embedding(text):
    try:
        vector = model.encode(text).tolist()
        return vector
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def process_document(document):
    text = ""
    file_path = document.file.path
    
    try:
        if document.file_type == 'PDF':
            with open(file_path, 'rb') as f:
                pdf = pypdf.PdfReader(f)
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
                        
        elif document.file_type == 'DOCX':
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
                
        elif document.file_type == 'IMAGE':
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            
        text = text.strip()
        
        if text:
            metadata = extract_document_metadata(text)
            
            if not document.extracted_type:
                document.extracted_type = metadata.get("document_type", "Unknown")
            document.extracted_summary = metadata.get("summary", "")
            document.extracted_dates = metadata.get("all_dates", []) 
            document.save()
            
            chunk_and_save_text(document, text)
            
    except Exception as e:
        print(f"Failed to process document {document.title}: {str(e)}")

def chunk_and_save_text(document, text, chunk_size=1000, chunk_overlap=200):
    start = 0
    sequence = 1
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk_text = text[start:end]
        
        vector = generate_embedding(chunk_text)
        
        if vector:
            DocumentChunk.objects.create(
                document=document,
                content_text=chunk_text,
                sequence_number=sequence,
                embedding=vector
            )
        
        start += (chunk_size - chunk_overlap)
        sequence += 1

def generate_rag_response(user_query, conversation, document_ids=None):
    query_vector = generate_embedding(user_query)
    chunks_query = DocumentChunk.objects.all()
    
    if document_ids and len(document_ids) > 0:
        chunks_query = chunks_query.filter(document__id__in=document_ids)
    
    relevant_chunks = chunks_query.annotate(
        distance=CosineDistance('embedding', query_vector)
    ).order_by('distance')[:3]
    
    # 1. NEW: Build a structured source array and numbered context
    context_text = ""
    sources = []
    
    for index, chunk in enumerate(relevant_chunks):
        source_id = index + 1
        context_text += f"\n=== SOURCE [{source_id}] (From: {chunk.document.title}) ===\n{chunk.content_text}\n"
        
        # Save the exact snippet to send to the Vue frontend
        sources.append({
            "id": source_id,
            "document_id": chunk.document.id,
            "document_title": chunk.document.title,
            "text_snippet": chunk.content_text
        })
    
    metadata_context = "=== ABSOLUTE DOCUMENT METADATA (Use this as ultimate truth) ===\n"
    if document_ids and len(document_ids) > 0:
        docs = Document.objects.filter(id__in=document_ids)
        for doc in docs:
            metadata_context += f"- Title: {doc.title}\n  Type: {doc.extracted_type}\n  Summary: {doc.extracted_summary}\n"
            metadata_context += "  Timeline of Dates:\n"
            if doc.extracted_dates and len(doc.extracted_dates) > 0:
                for date_info in doc.extracted_dates:
                    metadata_context += f"    * {date_info.get('date', 'Unknown')}: {date_info.get('context', 'Mentioned in text')}\n"
            else:
                metadata_context += "    * No dates found in document.\n"
            metadata_context += "\n"
    else:
        metadata_context += "No specific documents selected.\n\n"

    final_context = metadata_context + context_text

    if not context_text and not document_ids:
        return "I don't have any matching context in the selected documents to answer that question.", []

    client = get_groq_client()

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": """You are DocuMind AI, a precise, enterprise document analysis assistant. 
                    
                    RULES:
                    1. Answer based STRICTLY on the provided context. 
                    2. CRITICAL CITATIONS: Every time you state a fact from a source, you MUST append the source ID inline (e.g., "The effective date is August 4th [1].").
                    3. If using absolute metadata, cite it as [Metadata].
                    4. ZERO TRUNCATION: If the user asks for a list, a table of contents, or data extraction, you MUST output EVERY SINGLE ITEM present in the context. Never use shortcuts like "etc.", "and so on", or stop early. If there are 50 items, you must list all 50.
                    5. Do not use fluff or robotic introductory filler."""
                },
                {
                    "role": "user",
                    "content": f"CONTEXT:\n{final_context}\n\nUSER QUESTION:\n{user_query}"
                }
            ],
            model="openai/gpt-oss-20b", 
            temperature=0.1,  
            # NEW: Ensure the model has enough room to output long lists
            max_tokens=2048 
        )
        
        # 2. NEW: Return both the LLM's text AND the source array
        return chat_completion.choices[0].message.content, sources
        
    except Exception as e:
        print(f"Groq API Error: {e}")
        return "I'm sorry, I encountered an error while generating the response.", []