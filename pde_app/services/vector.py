import hashlib
from typing import List
from openai import OpenAI
from pde_app.config import config

def get_embedding(text: str) -> List[float]:
    """
    Generates a vector embedding for the given text.
    
    If config.OPENAI_API_KEY is empty or not configured, it returns a 
    deterministic mock vector based on the text hash (normalized to unit length).
    This guarantees offline testing and database constraints function correctly.
    """
    dim = config.EMBEDDING_DIMENSION
    
    if not config.OPENAI_API_KEY:
        # Generate a deterministic mock vector based on the text
        hasher = hashlib.md5(text.encode("utf-8"))
        hash_digest = hasher.digest()
        
        result = []
        seed = int.from_bytes(hash_digest, "big")
        
        for _ in range(dim):
            # Simple LCG pseudo-random generator
            seed = (1103515245 * seed + 12345) & 0x7fffffff
            val = (seed / 0x7fffffff) * 2.0 - 1.0  # Range [-1.0, 1.0]
            result.append(val)
            
        # Normalize the vector to unit length (important for cosine distance metrics)
        magnitude = sum(x * x for x in result) ** 0.5
        if magnitude > 0:
            result = [x / magnitude for x in result]
            
        return result

    # Standard OpenAI client execution
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.embeddings.create(
        input=[text],
        model=config.EMBEDDING_MODEL
    )
    return response.data[0].embedding
