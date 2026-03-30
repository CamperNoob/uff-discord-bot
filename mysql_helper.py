import pymysql
from configs.tokens import MySQL
import logging
from configs.tokens import GeminiAPIInstruction

GEMINI_DB_NAME = 'gemini_db'
GEMINI_TABLES = [
    {
        "name": "temporary_message_context",
        "type": "data",
        "create_sql": """
            CREATE TABLE IF NOT EXISTS `{name}` (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME,
                author VARCHAR(255),
                message TEXT,
                response TEXT
            )
        """,
        "clean_sql": """
            DELETE t
            FROM `{name}` t
            LEFT JOIN (
                SELECT id
                FROM (
                    SELECT id
                    FROM `{name}`
                    ORDER BY timestamp DESC
                    LIMIT {limit}
                ) AS keep_ids
            ) k ON t.id = k.id
            WHERE k.id IS NULL;
        """,
        "clean_limit": 500
    },
    {
        "name": "persistent_context",
        "type": "lookup",
        "create_sql": """
            CREATE TABLE IF NOT EXISTS `{name}` (
                id INT AUTO_INCREMENT PRIMARY KEY,
                entry TEXT
            )
        """,
        "init_data_query": """
            INSERT INTO `{name}` (id, entry)
            VALUES (%s, %s)

        """,
        "init_data": GeminiAPIInstruction
    },
]

# legacy db
def get_db_connection():
    return pymysql.connect(
        host=MySQL.get("host"),
        port=MySQL.get("port", 3306),
        user=MySQL.get("user"),
        password=MySQL.get("password"),
        database=MySQL.get("database"),
        cursorclass=pymysql.cursors.DictCursor
    )

class GeminiMySqlConnectionManager:
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def conn_server(self, autocommit: bool = False, db_name: str = GEMINI_DB_NAME):
        conn_dict = {
            "host":MySQL.get("host"),
            "port":MySQL.get("port", 3306),
            "user":MySQL.get("user"),
            "password":MySQL.get("password"),
            "cursorclass":pymysql.cursors.DictCursor,
            "autocommit": autocommit
        }

        if db_name:
            conn_dict["database"] = db_name
        
        return pymysql.connect(**conn_dict)
    
    def init_db(self):
        with self.conn_server(autocommit=True, db_name=None) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{GEMINI_DB_NAME}`")
                self.logger.info(f"DB {GEMINI_DB_NAME} created if didnt exist.")
    
    def table_exists(self, conn, table_name):
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                    AND table_name = '{name}'
                )
            """.format(name=table_name))
            result = cursor.fetchone()
            return result["table_exists"]
    
    def init_tables(self):
        with self.conn_server(autocommit=True) as conn:
            with conn.cursor() as cursor:
                for table in GEMINI_TABLES:
                    table_name = table.get("name")
                    table_sql = table.get("create_sql")
                    table_type = table.get("type")
                    did_exist = None
                    if table_type == "lookup":
                        did_exist = self.table_exists(conn, table_name)
                    cursor.execute(table_sql.format(name=table_name))
                    self.logger.info(f"Table {table_name} {'created if didnt exist.' if not did_exist else 'already exist.'}")
                    if table_type == "lookup" and not did_exist:
                        table_data = table.get("init_data")
                        table_data_init = table.get("init_data_query").format(name=table_name)
                        formatted_data = [(key, *row) for key, row in table_data.items()]
                        cursor.executemany(table_data_init, formatted_data)
    
    def get_persistent_context(self):
        with self.conn_server(autocommit=False) as conn:
            with conn.cursor() as cursor:
                table_name = 'persistent_context'
                cursor.execute(f'SELECT entry FROM `{table_name}` ORDER BY id ASC')
                data = cursor.fetchall()
                return [r["entry"] for r in data]

    def get_temporary_context(self):
        with self.conn_server(autocommit=False) as conn:
            with conn.cursor() as cursor:
                table_name = 'temporary_message_context'
                cursor.execute(f'SELECT author, message, response FROM `{table_name}` ORDER BY id ASC')
                data = cursor.fetchall()
                return [(r["author"], r["message"], r["response"]) for r in data]
    
    def insert_temporary_context(self, author: str, message: str, response: str):
        with self.conn_server(autocommit=True) as conn:
            with conn.cursor() as cursor:
                table_name = 'temporary_message_context'
                sql = 'INSERT INTO `{table}` (timestamp, author, message, response) VALUES (NOW(), %s, %s, %s)'.format(table=table_name)
                cursor.execute(sql, (author, message, response))
    
    def clean_temporary_context(self):
        table_name = 'temporary_message_context'
        clear_sql = None
        for table in GEMINI_TABLES:
            if table.get("name") == table_name:
                clear_sql = table.get("clean_sql").format(name=table_name, limit=table.get("clean_limit", 500))
        if clear_sql:
            with self.conn_server(autocommit=True) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(clear_sql)
                
