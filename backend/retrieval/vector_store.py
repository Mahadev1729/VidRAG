"""
backend/retrieval/vector_store.py
=================================
TiDB Cloud Vector Store integration for storing and querying 384-dim embeddings.
"""

import json
from typing import List, Optional
from langchain_core.documents import Document

from database import get_db_connection
from retrieval.embeddings import get_embedding_model


class TiDBVectorStore:
    """
    TiDB Cloud Vector Store supporting LangChain similarity search interface.
    """

    def __init__(self, video_id: str):
        self.video_id = video_id
        self.embedding_model = get_embedding_model()

    def similarity_search(self, query: str, k: int = 4) -> List[Document]:
        """
        Search for the top-k most similar transcript chunks in TiDB for this video.
        """
        print(f"[TIDB VECTOR] Searching top-{k} chunks for video '{self.video_id}'...")
        query_vector = self.embedding_model.embed_query(query)
        vector_str = json.dumps(query_vector)

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # TiDB Vector function VEC_COSINE_DISTANCE
                # If VEC_COSINE_DISTANCE or VEC_L2_DISTANCE is used
                cursor.execute(
                    """
                    SELECT page_content, start_time, end_time, source, video_id,
                           VEC_COSINE_DISTANCE(embedding, %s) AS distance
                    FROM transcript_chunks
                    WHERE video_id = %s
                    ORDER BY distance ASC
                    LIMIT %s
                    """,
                    (vector_str, self.video_id, k),
                )
                rows = cursor.fetchall()

                docs = []
                for row in rows:
                    docs.append(
                        Document(
                            page_content=row["page_content"],
                            metadata={
                                "start": row["start_time"],
                                "end": row["end_time"],
                                "source": row["source"],
                                "video_id": row["video_id"],
                                "distance": float(row.get("distance", 0.0)),
                            },
                        )
                    )
                return docs
        finally:
            conn.close()


def store_documents_in_tidb(documents: List[Document], video_id: str) -> TiDBVectorStore:
    """
    Embed chunk documents and save them into TiDB Cloud Serverless.
    If chunks for this video already exist, existing chunks are replaced.
    """
    if not documents:
        raise ValueError("No documents provided to index.")

    print(f"[TIDB VECTOR] Generating embeddings for {len(documents)} chunks...")
    embedding_model = get_embedding_model()
    texts = [doc.page_content for doc in documents]
    embeddings = embedding_model.embed_documents(texts)

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Clean up old chunks for this video if re-indexing
            cursor.execute("DELETE FROM transcript_chunks WHERE video_id = %s", (video_id,))

            # Batch insert
            insert_query = """
                INSERT INTO transcript_chunks 
                (video_id, chunk_index, page_content, start_time, end_time, source, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            batch_data = []
            for i, (doc, emb) in enumerate(zip(documents, embeddings)):
                emb_json = json.dumps(emb)
                batch_data.append((
                    video_id,
                    i,
                    doc.page_content,
                    float(doc.metadata.get("start", 0.0)),
                    float(doc.metadata.get("end", 0.0)),
                    str(doc.metadata.get("source", "youtube")),
                    emb_json,
                ))

            cursor.executemany(insert_query, batch_data)
        print(f"[TIDB VECTOR] Successfully stored {len(documents)} chunks in TiDB Cloud.")
    finally:
        conn.close()

    return TiDBVectorStore(video_id=video_id)


def get_vector_store_for_video(video_id: str) -> Optional[TiDBVectorStore]:
    """
    Check if transcript chunks exist in TiDB for this video. If so, return TiDBVectorStore.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS chunk_count FROM transcript_chunks WHERE video_id = %s",
                (video_id,),
            )
            res = cursor.fetchone()
            if res and res["chunk_count"] > 0:
                return TiDBVectorStore(video_id=video_id)
            return None
    finally:
        conn.close()
