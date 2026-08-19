from langchain_text_splitters import RecursiveCharacterTextSplitter


def create_documents(
    text: str,
    video_id: str
):

    # -----------------------------------------
    # Create text splitter
    # -----------------------------------------

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )

    # -----------------------------------------
    # Create LangChain Documents
    # -----------------------------------------

    documents = text_splitter.create_documents(
        [text],
        metadatas=[
            {
                "video_id": video_id,
                "source": "youtube"
            }
        ]
    )

    return documents
