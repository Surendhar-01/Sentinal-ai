from ..config import settings

class ChromaVectorStore:
    """Persistent local Chroma collection. Chroma telemetry is explicitly disabled."""
    def __init__(self):
        import chromadb
        self.client=chromadb.PersistentClient(path=settings.chroma_path,settings=chromadb.Settings(anonymized_telemetry=False))
        self.collection=self.client.get_or_create_collection("sentinel_enterprise_knowledge",metadata={"hnsw:space":"cosine"})

    def add(self,chunk_id:int,document_id:int,filename:str,page:int,text:str,embedding:list[float]):
        self.collection.upsert(ids=[str(chunk_id)],documents=[text],embeddings=[embedding],metadatas=[{"document_id":document_id,"filename":filename,"page":page}])

    def delete_document(self,document_id:int):
        self.collection.delete(where={"document_id":document_id})

    def search(self,query_embedding:list[float],limit:int=5):
        if self.collection.count()==0:return []
        result=self.collection.query(query_embeddings=[query_embedding],n_results=min(limit,self.collection.count()),include=["documents","metadatas","distances"])
        return [{"document_id":int(meta["document_id"]),"filename":meta["filename"],"page":int(meta["page"]),"excerpt":text,"relevance_score":round(max(0.0,1.0-float(distance)),4)} for text,meta,distance in zip(result["documents"][0],result["metadatas"][0],result["distances"][0])]

_store=None
def vector_store():
    global _store
    if _store is None:_store=ChromaVectorStore()
    return _store
