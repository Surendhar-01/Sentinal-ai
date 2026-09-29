import hashlib, json, math, re, urllib.request
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader
from docx import Document as DocxDocument
from ..config import settings

def extract_pages(filename: str, data: bytes):
    suffix=Path(filename).suffix.lower()
    if suffix==".pdf":
        return [(i+1, p.extract_text() or "") for i,p in enumerate(PdfReader(BytesIO(data)).pages)]
    if suffix==".docx":
        doc=DocxDocument(BytesIO(data)); return [(1,"\n".join(p.text for p in doc.paragraphs))]
    if suffix==".txt": return [(1,data.decode("utf-8",errors="replace"))]
    raise ValueError("Only PDF, TXT, and DOCX files are supported")

def split_pages(pages, chunk_size=900, overlap=140):
    result=[]
    for page,text in pages:
        clean=re.sub(r"\s+"," ",text).strip()
        start=0
        while start < len(clean):
            end=min(len(clean),start+chunk_size); cut=clean[start:end]
            if end < len(clean) and " " in cut: cut=cut.rsplit(" ",1)[0]
            if cut: result.append((page,cut))
            if end >= len(clean): break
            start += max(1,len(cut)-overlap)
    return result

def _hash_embed(text, dims=384):
    vec=[0.0]*dims
    for token in re.findall(r"[a-z0-9_-]+",text.lower()):
        h=int.from_bytes(hashlib.sha256(token.encode()).digest()[:8],"big")
        vec[h%dims] += -1.0 if h&1 else 1.0
    norm=math.sqrt(sum(x*x for x in vec)) or 1
    return [x/norm for x in vec]

def embed(text):
    if settings.embedding_provider=="ollama":
        body=json.dumps({"model":settings.embedding_model,"prompt":text}).encode()
        req=urllib.request.Request(f"{settings.ollama_url}/api/embeddings",data=body,headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=60) as response: return json.load(response)["embedding"]
    return _hash_embed(text)

def cosine(a,b):
    return sum(x*y for x,y in zip(a,b))/((math.sqrt(sum(x*x for x in a))*math.sqrt(sum(x*x for x in b))) or 1)
