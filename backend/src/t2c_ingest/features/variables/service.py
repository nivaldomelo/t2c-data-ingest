from __future__ import annotations

import re

from t2c_ingest.core.crypto import decrypt_secret, encrypt_secret
from t2c_ingest.models.variable import Variable

MASK = "********"


def normalize_name(raw: str) -> str:
    """Code-safe env-var style name: UPPER_SNAKE (letters/digits/underscore)."""
    s = (raw or "").strip().upper()
    s = re.sub(r"[^A-Z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def is_secret_variable(variable_type: str | None, is_secret: bool | None) -> bool:
    return bool(is_secret) or variable_type == "secret"


def store_value(value: str | None, *, secret: bool) -> str | None:
    """Encrypt secret values before persisting; keep others as plaintext."""
    if value is None:
        return None
    return encrypt_secret(value) if secret else value


def reveal_value(var: Variable) -> str | None:
    """Return the usable plaintext value (decrypting secrets). For internal/runtime use only —
    never send secret plaintext to the API layer."""
    if var.value is None:
        return None
    return decrypt_secret(var.value) if var.is_secret else var.value


def public_value(var: Variable) -> tuple[str | None, str | None]:
    """(value, masked_value) for API output. Secrets never expose the real value."""
    if var.is_secret:
        return None, (MASK if var.value else None)
    return var.value, None


def _example_value(name: str, variable_type: str) -> str:
    return {
        "date": "2026-07-08",
        "datetime": "2026-07-08T03:00:00",
        "integer": "1000",
        "decimal": "10.5",
        "boolean": "true",
        "json": "{}",
    }.get(variable_type, f"valor_de_{name.lower()}")


def usage_examples(name: str, variable_type: str) -> dict[str, str]:
    """Python + Spark snippets showing how to consume the variable via env at runtime."""
    default = _example_value(name, variable_type)

    if variable_type == "boolean":
        py_read = f'{name.lower()} = os.getenv("{name}", "false").lower() == "true"'
    elif variable_type == "integer":
        py_read = f'{name.lower()} = int(os.getenv("{name}", "{default}"))'
    elif variable_type == "decimal":
        py_read = f'{name.lower()} = float(os.getenv("{name}", "{default}"))'
    elif variable_type == "json":
        py_read = (
            "import json\n"
            f'{name.lower()} = json.loads(os.getenv("{name}", "{{}}"))'
        )
    else:
        py_read = f'{name.lower()} = os.getenv("{name}")'

    python = (
        "import os\n\n"
        f"{py_read}\n\n"
        f'if {name.lower()} is None:\n'
        f'    raise RuntimeError("Variável {name} não definida.")\n\n'
        f'print(f"{name} = {{{name.lower()}}}")\n'
    )

    spark = (
        "import os\n"
        "from pyspark.sql import SparkSession\n\n"
        'spark = SparkSession.builder.appName("exemplo_uso_variavel").getOrCreate()\n\n'
        f'{name.lower()} = os.getenv("{name}")\n'
        f'if not {name.lower()}:\n'
        f'    raise RuntimeError("Variável {name} não definida.")\n\n'
        f'# use a variável no seu processamento, ex.:\n'
        f'# df = spark.read.parquet(f"s3a://{{{name.lower()}}}/datalake/tabela/")\n'
    )
    return {"python": python, "spark": spark}
