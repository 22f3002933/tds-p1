# llm_utils.py
import os
import requests
import base64
from typing import List, Dict, Any, Optional
import numpy as np
from dotenv import load_dotenv

load_dotenv()
LLM_BASE_URL = "https://aiproxy.sanand.workers.dev/openai/v1"
LLM_API_KEY = os.getenv("AIPROXY_TOKEN")

def call_llm_with_image(image_path: str, prompt: str) -> str:
    image_path = os.path.join(os.path.dirname(__file__),".", image_path)
    """
    Call LLM with an image and return the response.
    Uses gpt-4o-mini model which supports image inputs.
    """
    try:
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        response = requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ]
            }
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"LLM image processing failed: {str(e)}")

def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Get embeddings for a list of texts using text-embedding-3-small model.
    Returns list of embedding vectors.
    """
    try:
        response = requests.post(
            f"{LLM_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "text-embedding-3-small",
                "input": texts
            }
        )
        response.raise_for_status()
        return [item["embedding"] for item in response.json()["data"]]
    except Exception as e:
        raise RuntimeError(f"Embedding generation failed: {str(e)}")

def find_most_similar_pair(texts: List[str]) -> tuple[str, str]:
    """
    Find the most similar pair of texts using embeddings.
    Returns tuple of (text1, text2).
    """
    if len(texts) < 2:
        raise ValueError("Need at least 2 texts to find similar pair")
    
    # Get embeddings
    embeddings = get_embeddings(texts)
    
    # Convert to numpy for faster computation
    vectors = np.array(embeddings)
    
    # Calculate cosine similarity matrix
    similarities = np.dot(vectors, vectors.T)
    norms = np.linalg.norm(vectors, axis=1)
    similarities = similarities / np.outer(norms, norms)
    
    # Set diagonal to -1 to ignore self-similarity
    np.fill_diagonal(similarities, -1)
    
    # Find most similar pair
    max_idx = np.unravel_index(similarities.argmax(), similarities.shape)
    return texts[max_idx[0]], texts[max_idx[1]]