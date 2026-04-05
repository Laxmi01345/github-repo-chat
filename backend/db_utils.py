import os
import psycopg2


def get_connection():
    # Use DATABASE_URL if provided (standard format), otherwise use individual env vars
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # Format: postgresql://user:password@host:port/dbname
        return psycopg2.connect(database_url)
    else:
        # Fallback to individual environment variables
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME", "repo_analysis_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )


def ensure_schema(cursor):
    cursor.execute(
        """
        ALTER TABLE repo_analysis
        ADD COLUMN IF NOT EXISTS tech_stack TEXT;
        """
    )

def store_repo_analysis(repo_url, data):

    conn = get_connection()
    cursor = conn.cursor()
    ensure_schema(cursor)

    query = """
    INSERT INTO repo_analysis
    (repo_url, purpose_scope, repo_layout, source_layer, tech_stack, architecture_text, architecture_diagram, rpc_protocol)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (repo_url) DO UPDATE SET
    purpose_scope = EXCLUDED.purpose_scope,
    repo_layout = EXCLUDED.repo_layout,
    source_layer = EXCLUDED.source_layer,
    tech_stack = EXCLUDED.tech_stack,
    architecture_text = EXCLUDED.architecture_text,
    architecture_diagram = EXCLUDED.architecture_diagram,
    rpc_protocol = EXCLUDED.rpc_protocol;
    """

    cursor.execute(query, (
        repo_url,
        data["purpose_scope"],
        data["repo_layout"],
        data["source_layer"],
        data.get("tech_stack", ""),
        data["architecture_text"],
        data["architecture_diagram"],
        data["rpc_protocol"]
    ))

    conn.commit()
    cursor.close()
    conn.close()

def get_repo_analysis(repo_url):

    conn = get_connection()
    cursor = conn.cursor()
    ensure_schema(cursor)

    cursor.execute(
        """
        SELECT repo_url, purpose_scope, repo_layout, source_layer, tech_stack,
               architecture_text, architecture_diagram, rpc_protocol
        FROM repo_analysis
        WHERE repo_url = %s
        """,
        (repo_url,)
    )

    row = cursor.fetchone()

    if row is None:
        result = None
    else:
        result = {
            "repo_url": row[0],
            "purpose_scope": row[1],
            "repo_layout": row[2],
            "source_layer": row[3],
            "tech_stack": row[4],
            "architecture_text": row[5],
            "architecture_diagram": row[6],
            "rpc_protocol": row[7],
        }

    cursor.close()
    conn.close()

    return result