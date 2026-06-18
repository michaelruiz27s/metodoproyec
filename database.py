import os
import mysql.connector

_ENV_LOADED = False
_SCHEMA_READY = False


def _load_env_file():
    """Carga variables desde .env en la carpeta del proyecto (solo una vez)."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(env_path):
        return

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def get_db_config():
    _load_env_file()
    return {
        "host": os.environ.get("DB_HOST", "127.0.0.1"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "database": os.environ.get("DB_NAME", "metodos_numericos"),
    }


def get_connection():
    return mysql.connector.connect(**get_db_config())


def init_database():
    """Crea la base de datos y tablas si no existen."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    cfg = get_db_config()
    db_name = cfg["database"]
    conn = mysql.connector.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
    )
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
    cur.execute(f"USE `{db_name}`")

    sql_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Modelo Fisico Mysql.sql")
    if os.path.isfile(sql_path):
        with open(sql_path, encoding="utf-8") as f:
            sql = f.read()
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if not stmt or stmt.startswith("--"):
                continue
            upper = stmt.upper()
            if upper.startswith("CREATE DATABASE") or upper.startswith("USE "):
                continue
            cur.execute(stmt)

    conn.commit()
    cur.close()
    conn.close()
    _SCHEMA_READY = True
