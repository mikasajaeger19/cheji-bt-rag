from langchain_ollama import OllamaLLM
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
import chromadb
import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

# =========================
# CONFIG
# =========================

embedding_model = "nomic-embed-text"
llm_model = "llama3.2:3b"

corpus_text_file = "bruzz.txt"
collection_name = "uncz_rag"

# =========================
# CHROMA SETUP
# =========================

chroma_client = chromadb.PersistentClient(
    path=os.path.join(
        os.getcwd(),
        "chroma_db"
    )
)

embedding = OllamaEmbeddingFunction(
    url="http://127.0.0.1:11434",
    model_name=embedding_model,
    timeout=10800
)

collection = chroma_client.get_or_create_collection(
    name=collection_name,
    metadata={
        "description":
        "RAG for group chat mimic"
    },
    embedding_function=embedding
)

# =========================
# LLM SETUP
# =========================

llm = OllamaLLM(
    model=llm_model,
    base_url="http://127.0.0.1:11434",
    temperature=0
)

query_prompt = """
You are replying as a member of a group chat.

Use ONLY information present in retrieved messages.

ABSOLUTE RULES:
- Do NOT invent details
- Do NOT infer
- Do NOT add actions
- Prefer retrieved wording
- Match group chat style
- Return ONLY the reply
-Reply directly.
Do not reason.
Do not explain.
Use retrieved text only.
"""

# =========================
# CORPUS PROCESSING
# =========================

def process_text_corpus(
    file_path,
    window_size=5,
    overlap=2,
    max_chunk_chars=500
):

    messages = []

    # Remove timestamps
    datetime_prefix = re.compile(
        r'^\s*\d{1,2}/\d{1,2}/\d{4},\s*\d{1,2}:\d{2}\s*-\s*'
    )

    # Remove sender names
    sender_prefix = re.compile(
        r'^[^:]+:\s*'
    )

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as f:

        for raw in f:

            line = raw.strip()

            if not line:
                continue

            low = line.lower()

            if "<media omitted>" in low:
                continue

            # Remove timestamp
            line = datetime_prefix.sub(
                '',
                line
            )

            # Remove sender
            line = sender_prefix.sub(
                '',
                line
            )

            line = line.strip()

            if not line:
                continue

            messages.append(
                line
            )

    chunks = []

    step = (
        window_size
        - overlap
    )

    for i in range(
        0,
        len(messages),
        step
    ):

        window = messages[
            i:i+window_size
        ]

        if not window:
            continue

        current_chunk = ""

        for msg in window:

            candidate = (
                current_chunk
                + "\n"
                + msg
            ).strip()

            if (
                len(candidate)
                > max_chunk_chars
            ):

                if current_chunk:

                    chunks.append(
                        current_chunk
                    )

                current_chunk = msg

            else:

                current_chunk = candidate

        if current_chunk:

            chunks.append(
                current_chunk
            )

    return chunks

# =========================
# DATABASE
# =========================

def query_chromadb(
    query_text,
    n_results=5
):

    results = collection.query(
        query_texts=[
            query_text
        ],
        n_results=n_results
    )

    return results["documents"]


def query_rag(query):
    docs = query_chromadb(query, n_results=5)
    context_text = ""

    if docs and docs[0]:
        context_text = "\n\n".join(
            [
                f"Chunk {i+1}:\n{x}"
                for i, x in enumerate(docs[0])
            ]
        )

    augmented_prompt = f"""
{query_prompt}

Retrieved messages:

{context_text}

Current message:

{query}

Reply:
"""

    response = query_ollama(augmented_prompt)
    return response, docs


def query_ollama(
    prompt
):

    return llm.invoke(
        prompt
    )

# =========================
# BUILD
# =========================

def build_corpus():

    documents = process_text_corpus(
        corpus_text_file
    )

    ids = [

        f"bruzz_{i}"

        for i in range(
            len(documents)
        )

    ]

    print(
        f"Generated {len(documents)} chunks"
    )

    if not documents:

        print(
            "No documents found"
        )

        return

    batch_size = 5000

    for i in range(
        0,
        len(documents),
        batch_size
    ):

        batch_docs = documents[
            i:i+batch_size
        ]

        batch_ids = ids[
            i:i+batch_size
        ]

        collection.add(
            documents=batch_docs,
            ids=batch_ids
        )

        print(
            f"Added batch "
            f"{i//batch_size + 1} "
            f"({len(batch_docs)} docs)"
        )

    print(
        "Finished indexing"
    )
# =========================
# CHATBOT
# =========================

def rag_chatbot():

    print(
        "\n=== UNCZ CHATBOT ==="
    )

    print(
        "Type exit to quit\n"
    )

    while True:

        query = input(
            "You: "
        ).strip()

        if query.lower() in [
            "exit",
            "quit",
            "bye"
        ]:

            print(
                "\nBot: cya"
            )

            break

        docs = query_chromadb(
            query,
            n_results=5
        )

        context_text = ""

        if docs and docs[0]:

            context_text = "\n\n".join(

                [

                    f"Chunk {i+1}:\n{x}"

                    for i, x in enumerate(
                        docs[0]
                    )

                ]

            )

        print(
            "\n=== Retrieved Chunks ==="
        )

        print(
            context_text
        )

        augmented_prompt = f"""

{query_prompt}

Retrieved messages:

{context_text}

Current message:

{query}

Reply:

"""

        response = query_ollama(
            augmented_prompt
        )

        print(
            f"\ncheji bt: {response}\n"
        )

# =========================
# STATUS
# =========================

def check_collection():

    count = collection.count()

    print(
        f"Documents: {count}"
    )


class RAGHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def do_POST(self):
        if self.path != "/query":
            self._send_json({"error": "Not found"}, status=404)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, status=400)
            return

        query_text = payload.get("query")
        if not query_text:
            self._send_json({"error": "Missing query field"}, status=400)
            return

        try:
            answer, docs = query_rag(query_text)
            self._send_json({"answer": answer, "documents": docs})
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)


def serve_rag_api(host="127.0.0.1", port=8000):
    server = HTTPServer((host, port), RAGHandler)
    print(f"Serving RAG API on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down RAG API")
        server.server_close()

# =========================
# MAIN
# =========================

def main():

    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument(

        "command",

        choices=[

            "build",
            "chat",
            "status",
            "serve"
        ]

    )

    args = parser.parse_args()

    if args.command == "build":

        build_corpus()

    elif args.command == "chat":

        rag_chatbot()

    elif args.command == "status":

        check_collection()

    elif args.command == "serve":

        serve_rag_api()


if __name__ == "__main__":
    main()