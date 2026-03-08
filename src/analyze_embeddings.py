import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.decomposition import PCA
import umap
from dotenv import load_dotenv
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from supabase.client import create_client, Client
import ast

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY or not GOOGLE_API_KEY:
    raise ValueError("Missing SUPABASE_URL, SUPABASE_KEY, or GOOGLE_API_KEY in .env")

def get_query_embedding(query_text: str):
    print(f"Generating embedding for query: '{query_text}'")
    model_name = "BAAI/bge-small-en-v1.5"
    model_kwargs = {'device': 'cpu'}
    encode_kwargs = {'normalize_embeddings': True}
    embeddings_model = HuggingFaceBgeEmbeddings(
        model_name=model_name,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )
    return embeddings_model.embed_query(query_text)

def main():
    print("Connecting to Supabase REST API...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    print("Extracting documents and embeddings...")
    response = supabase.table('documents').select('id, content, metadata, embedding').limit(2000).execute()
    data = response.data
    df = pd.DataFrame(data)

    if df.empty:
        print("No embeddings found in the database. Run ingest.py first.")
        return

    # Convert string representation of list to actual Python list, then to numpy array
    print("Processing embeddings...")
    df['embedding'] = df['embedding'].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)
    
    # Extract form_type or title for coloring
    df['form_type'] = df['metadata'].apply(lambda meta: meta.get('form_type', 'unknown') if isinstance(meta, dict) else 'unknown')
    df['title'] = df['metadata'].apply(lambda meta: meta.get('title', 'Unknown') if isinstance(meta, dict) else 'Unknown')
    
    X = np.stack(df['embedding'].values)
    labels = df['form_type'].values

    # Test "Outlier" Query: 
    # Query: "How do I file Form 8843?" should cluster with Form 8843 chunks.
    # Query: "What is the substantial presence test?" should cluster with Pub 519 chunks.
    test_queries = [
        ("How do I file Form 8843?", "query_8843"),
        ("What is the substantial presence test?", "query_519_spt")
    ]
    
    query_embeddings = []
    query_labels = []
    
    for q_text, q_label in test_queries:
        q_emb = get_query_embedding(q_text)
        query_embeddings.append(q_emb)
        query_labels.append(q_label)
        
    # Append queries to X to apply reduction to the combined dataset
    X_combined = np.vstack([X, np.array(query_embeddings)])
    labels_combined = np.concatenate([labels, query_labels])

    print("Applying PCA for 2D visualization...")
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_combined)

    print("Applying UMAP for 2D visualization...")
    try:
        reducer = umap.UMAP(n_components=2, random_state=42)
        X_umap = reducer.fit_transform(X_combined)
    except Exception as e:
        print(f"UMAP failed, falling back to PCA only: {e}")
        X_umap = None

    # Plotting
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    
    # Custom palette setup to highlight queries
    unique_labels = list(set(labels_combined))
    palette = sns.color_palette("husl", len(unique_labels))
    color_map = dict(zip(unique_labels, palette))
    
    # Ensure queries stand out (e.g., black and red X marks)
    color_map["query_8843"] = "red"
    color_map["query_519_spt"] = "black"

    # Scatter for PCA
    is_query = [("query" in l) for l in labels_combined]
    sns.scatterplot(
        ax=axes[0], 
        x=X_pca[:, 0], 
        y=X_pca[:, 1], 
        hue=labels_combined, 
        palette=color_map,
        style=is_query,
        markers={True: "X", False: "o"},
        size=is_query,
        sizes={True: 200, False: 40},
        alpha=0.8
    )
    axes[0].set_title("PCA: Embedding Quality & Logical Clusters")

    # Scatter for UMAP
    if X_umap is not None:
        sns.scatterplot(
            ax=axes[1], 
            x=X_umap[:, 0], 
            y=X_umap[:, 1], 
            hue=labels_combined, 
            palette=color_map,
            style=is_query,
            markers={True: "X", False: "o"},
            size=is_query,
            sizes={True: 200, False: 40},
            alpha=0.8
        )
        axes[1].set_title("UMAP: Embedding Domain-Specificity Check")

    plt.tight_layout()
    plot_path = "embedding_clusters.png"
    plt.savefig(plot_path)
    print(f"Saved visualization to {plot_path}")
    
    # Analyze where the queries landed (k-Nearest Neighbors calculation could be done here as a strict programmatic check)
    print("Embedding Quality Analysis script completed successfully!")

if __name__ == "__main__":
    main()
