import json
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# 1. Initialize local Qdrant Client (pointing to your Docker gRPC port)
client = QdrantClient(host="localhost", port=6333)

COLLECTION_NAME = "academic_papers"
VECTOR_SIZE = 384  # Dimension size for 'all-MiniLM-L6-v2'

# 2. Re-create the collection if it doesn't exist
if not client.collection_exists(collection_name=COLLECTION_NAME):
    print(f"Creating collection: {COLLECTION_NAME}")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

# 3. Load the embedding model locally
print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

# 4. Path to your cloned papercopilot JSON file
# Update this path to target the specific JSON file you want to feed (e.g., iclr/iclr2025.json)
json_file_path = "/Users/salehalizade/Desktop/tttt/paperlists/iclr/iclr2023.json"

if not os.path.exists(json_file_path):
    raise FileNotFoundError(f"Could not find JSON file at: {json_file_path}")

with open(json_file_path, "r", encoding="utf-8") as f:
    papers_data = json.load(f)

# The file might be a dictionary or a list depending on the specific archive structure
if isinstance(papers_data, dict):
    # If the JSON maps submission IDs to paper objects
    papers_list = list(papers_data.values())
else:
    papers_list = papers_data

print(f"Loaded {len(papers_list)} papers from JSON. Commencing embedding and ingestion...")

# 5. Process and upload in chunks to optimize network transfer
BATCH_SIZE = 64
points = []

for idx, paper in enumerate(tqdm(papers_list)):
    # Extract metadata safely
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    keywords = paper.get("keywords", [])
    if isinstance(keywords, list):
        keywords_str = ", ".join(keywords)
    else:
        keywords_str = str(keywords)
    
    # Construct a rich text string representing the semantic fingerprint of the paper
    text_to_embed = f"Title: {title}\nKeywords: {keywords_str}\nAbstract: {abstract}"
    
    # Generate embedding vector
    vector = model.encode(text_to_embed).tolist()
    
    # Clean payload data to store alongside the vector
    payload = {
        "title": title,
        "abstract": abstract,
        "keywords": keywords,
        "primary_area": paper.get("primary_area", "N/A"),
        "authors": paper.get("authors", []),
        "url": paper.get("url", ""),
        "pdf_url": paper.get("pdf_url", "")
    }
    
    # Create Qdrant structural point (using loop index as point ID)
    point = PointStruct(
        id=idx,
        vector=vector,
        payload=payload
    )
    points.append(point)
    
    # Upload batch when buffer limit is reached
    if len(points) >= BATCH_SIZE:
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        points = []

# Upload any remaining papers
if points:
    client.upsert(collection_name=COLLECTION_NAME, points=points)

print(f"Successfully fed data into collection '{COLLECTION_NAME}'!")
