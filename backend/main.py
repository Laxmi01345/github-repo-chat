from repo_utils import get_repo, read_all_files
from chunk_utils import chunk_files
from embedding_utils import embed_chunks, retrieve_chunks
from vector_store import create_vector_store
from prompts import PROMPTS
from llm_utils import ask_llm
from db_utils import store_repo_analysis


def generate_repo_analysis(repo_url):
    repo = get_repo(repo_url)
    if repo is None:
        raise RuntimeError("Failed to initialize the repository.")

    print(f"Repository '{repo.working_dir}' initialized successfully.")

    files_content = read_all_files(repo.working_dir)
    print(f"Total files read: {len(files_content)}")

    chunks = chunk_files(files_content)
    print("Total chunks:", len(chunks))

    chunks_emb = embed_chunks(chunks)
    print("Embeddings generated:", len(chunks_emb))

    index = create_vector_store(chunks)
    print("Vector store created")

    results = {}

    for key, prompt in PROMPTS.items():
        retrieved_chunks = retrieve_chunks(prompt, index, chunks)
        context = "\n".join(retrieved_chunks)

        answer = ask_llm(prompt, context, section_key=key)

        results[key] = answer
        print(f"{key}: {answer}")

    store_repo_analysis(repo_url, results)
    print("Saved to database")

    return {
        "repo_url": repo_url,
        **results,
    }


if __name__ == "__main__":
    user_input = input("Enter the path to the Git repository: ")
    try:
        generate_repo_analysis(user_input)
    except Exception as exc:
        print(f"Error: {exc}")
        raise